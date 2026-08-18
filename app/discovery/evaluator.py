"""Eligibility, cumulative caps, and fit — judged against the company profile.

The one process that writes outside the proposals queue, deliberately. What it
writes are **judgements, not facts**: a verdict, a score, a rationale, and the
caps a call imposes. They are advisory, they are recomputed whenever the profile
changes, and they never touch a factual field, a status, or a manual priority.
Facts still enter only through an approved proposal.

Because the profile is what a verdict is relative to, a row evaluated before the
last profile change is stale by definition — `stale_evaluations()` finds those
and the UI offers to re-run them.
"""
import json
import os

import anthropic

from ..db import get_db
from .profile_context import opportunity_block, products_block, profile_block
from .scanner import MODEL

MAX_TURNS = 6
# The evaluator may read the call's own page to settle an eligibility question
# the stored record does not answer. It is capped low: this is a judgement pass,
# not a research pass.
MAX_FETCHES = 3

VERDICTS = ["eligible", "not_eligible", "uncertain"]


def _submit_tool(counter_keys: list[str], product_ids: list[int]) -> dict:
    """Built per call so the counter keys and product ids are a closed enum:
    the model cannot invent a counter that does not exist."""
    return {
        "name": "submit_evaluation",
        "description": (
            "Submit the evaluation of this opportunity against the company profile. "
            "Call this exactly once."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "eligibility_verdict": {"type": "string", "enum": VERDICTS},
                "eligibility_rationale": {
                    "type": "string",
                    "description": "Point by point: which conditions are met, which are "
                                   "not, and which could not be established.",
                },
                "caps": {
                    "type": "array",
                    "description": "Cumulative ceilings this opportunity imposes. Empty "
                                   "if it imposes none.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "counter_key": {"type": "string", "enum": counter_keys or ["none"]},
                            "max_amount": {"type": ["string", "null"]},
                            "comparator": {
                                "type": "string", "enum": ["lt", "lte"],
                                "description": "lt for 'less than', lte for 'no more than'",
                            },
                            "scope_note": {
                                "type": "string",
                                "description": "The perimeter in the source's own words, "
                                               "quoted. Not your paraphrase.",
                            },
                            "verdict": {"type": "string", "enum": ["pass", "fail", "uncertain"]},
                        },
                        "required": ["counter_key", "max_amount", "comparator",
                                     "scope_note", "verdict"],
                        "additionalProperties": False,
                    },
                },
                "product_fit": {
                    "type": "array",
                    "description": "One entry per active product line. Empty when the "
                                   "opportunity is company-level.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer", "enum": product_ids or [0]},
                            "verdict": {"type": "string", "enum": VERDICTS},
                            "fit_score": {"type": "integer"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["product_id", "verdict", "fit_score", "rationale"],
                        "additionalProperties": False,
                    },
                },
                "overall_fit_score": {
                    "type": "integer",
                    "description": "0-100. How worth pursuing this is, beyond bare "
                                   "eligibility: theme, amount, timing, competitiveness.",
                },
                "fit_rationale": {"type": "string"},
                "best_fit_product_id": {"type": ["integer", "null"]},
                "effort": {"type": "string",
                           "enum": ["low", "medium", "high", "needs_consultant"]},
            },
            "required": ["eligibility_verdict", "eligibility_rationale", "caps",
                         "product_fit", "overall_fit_score", "fit_rationale",
                         "best_fit_product_id", "effort"],
            "additionalProperties": False,
        },
    }


SYSTEM = """You judge one funding opportunity against one company. You are not checking whether \
the record is accurate — another process does that. You are answering two questions: may this \
company apply, and is it worth the weeks it would take.

ELIGIBILITY. Go through the conditions one at a time against the profile: country and region \
(only registered locations count — a site marked NOT REGISTERED does not satisfy a requirement \
for a unit in that region), company age, size, sector, required qualifications, partner \
requirements, TRL. Say which conditions are met, which are not, and which you could not \
establish. A single failed hard condition makes it not_eligible. If a condition cannot be \
established from the profile or the call, the verdict is uncertain — never guess your way to \
eligible.

CAPS. Some opportunities impose a ceiling on what the company has already received: they consume \
a de minimis allowance, or they are open only to companies that have raised less than some \
amount. For each such ceiling, name the counter it applies to, the threshold, and — this is the \
part that matters — quote the perimeter **in the source's own words**. "Less than 500k raised" \
may or may not include public contributions, prize money, unconverted convertibles or founder \
money, and different calls count different things. When the wording does not settle what counts, \
the cap's verdict is uncertain. Do not resolve the ambiguity yourself, and do not convert a \
quoted phrase into your own paraphrase.

FIT PER PRODUCT. Maturity belongs to the product, not the company: a call wanting TRL 6-8 may \
suit one line and exclude another. Score each active product line separately. When the \
opportunity is company-level rather than about a product — a round, a hire, a certification, \
advice — leave product_fit empty and best_fit_product_id null.

FIT OVERALL. Eligibility says the company may apply. Fit says whether it should: is the theme \
right, is the amount worth the work, does the timing suit, is the track record competitive for \
this competition. Weigh how the money actually arrives — an award paid only on reimbursement \
after the spend can be out of reach on a short runway, while a smaller one with an advance is \
not. Set effort to what applying would really cost in work.

You may fetch the opportunity's own page if the stored record leaves an eligibility question \
open. Do not go researching beyond that.

Be useful rather than diplomatic: a low score with a clear reason is worth more than a hedge. \
Call submit_evaluation exactly once."""


def _write_result(opportunity: dict, result: dict) -> dict:
    """Advisory columns and the two judgement tables only. Never a factual
    field, never status, never the manual priority."""
    oid = opportunity["id"]
    caps = result.get("caps") or []
    fits = result.get("product_fit") or []

    with get_db() as db:
        db.execute("DELETE FROM opportunity_caps WHERE opportunity_id=?", (oid,))
        for cap in caps:
            db.execute(
                "INSERT INTO opportunity_caps (opportunity_id, counter_key, max_amount, "
                "currency, comparator, scope_note, verdict, checked_at) "
                "VALUES (?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                (oid, cap.get("counter_key"), cap.get("max_amount"),
                 opportunity.get("currency"), cap.get("comparator"),
                 cap.get("scope_note"), cap.get("verdict")),
            )

        db.execute("DELETE FROM opportunity_product_fit WHERE opportunity_id=?", (oid,))
        for fit in fits:
            db.execute(
                "INSERT INTO opportunity_product_fit (opportunity_id, product_id, verdict, "
                "fit_score, rationale, evaluated_at) VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)",
                (oid, fit.get("product_id"), fit.get("verdict"),
                 fit.get("fit_score"), fit.get("rationale")),
            )

        db.execute(
            "UPDATE opportunities SET eligibility_verdict=?, eligibility_rationale=?, "
            "eligibility_checked_at=strftime('%Y-%m-%d %H:%M:%f','now'), "
            "fit_score=?, fit_rationale=?, "
            "best_fit_product_id=?, effort=? WHERE id=?",
            (result.get("eligibility_verdict"), result.get("eligibility_rationale"),
             result.get("overall_fit_score"), result.get("fit_rationale"),
             result.get("best_fit_product_id"), result.get("effort"), oid),
        )

    return {"opportunity": opportunity["title"],
            "outcome": result.get("eligibility_verdict"),
            "fit": result.get("overall_fit_score"),
            "caps": len(caps), "products": len(fits)}


def evaluate_opportunity(opportunity_id: int) -> dict:
    with get_db() as db:
        row = db.execute("SELECT * FROM opportunities WHERE id=?",
                         (opportunity_id,)).fetchone()
        if not row:
            return {"outcome": "error", "detail": f"opportunity {opportunity_id} not found"}
        opportunity = dict(row)
        products = [dict(r) for r in db.execute(
            "SELECT * FROM products WHERE active=1 ORDER BY id")]
        counter_keys = [r["key"] for r in db.execute(
            "SELECT key FROM funding_counters WHERE active=1 ORDER BY key")]

    is_general = bool(opportunity.get("is_general"))
    product_ids = [] if is_general else [p["id"] for p in products]

    prompt = (
        profile_block()
        + "\n\n# OPPORTUNITY TO EVALUATE\n" + opportunity_block(opportunity)
    )
    if is_general:
        prompt += ("\n\nThis opportunity is marked company-level: judge it against the "
                   "company, leave product_fit empty and best_fit_product_id null.\n")
    else:
        prompt += ("\n\n# ACTIVE PRODUCT LINES TO SCORE\n"
                   + products_block(products))

    tools = [
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": MAX_FETCHES},
        _submit_tool(counter_keys, product_ids),
    ]

    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": prompt}]
    result = None
    try:
        for _ in range(MAX_TURNS):
            response = client.messages.create(
                model=MODEL, max_tokens=12000, output_config={"effort": "high"},
                system=SYSTEM, tools=tools, messages=messages,
            )
            if response.stop_reason == "refusal":
                return {"opportunity": opportunity["title"], "outcome": "error",
                        "detail": "refusal"}
            submit = next((b for b in response.content if b.type == "tool_use"
                           and b.name == "submit_evaluation"), None)
            if submit is not None:
                result = submit.input
                break
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason not in ("pause_turn", "tool_use"):
                messages.append({"role": "user", "content":
                                 "Call submit_evaluation now with your judgement."})
    except anthropic.APIError as e:
        return {"opportunity": opportunity["title"], "outcome": "error",
                "detail": f"API error: {e}"}

    if result is None:
        return {"opportunity": opportunity["title"], "outcome": "error",
                "detail": "no submit_evaluation call"}

    summary = _write_result(opportunity, result)
    print(f"[evaluate] {summary}")
    return summary


def stale_evaluations() -> list[dict]:
    """Rows never evaluated, or evaluated before the last change to the profile.
    A verdict is relative to the profile it was judged against, so a profile
    edit makes every older verdict provisional."""
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT o.id, o.title, o.eligibility_checked_at FROM opportunities o "
            "WHERE o.status NOT IN ('won','lost','discarded') AND ("
            "  o.eligibility_checked_at IS NULL"
            "  OR o.eligibility_checked_at < (SELECT updated_at FROM company WHERE id=1)"
            ") ORDER BY o.id")]


def run_evaluations(stale_only: bool = True, limit: int | None = None) -> list[dict]:
    """Called by the scheduler (stale only) and by 'Evaluate' in the UI."""
    if stale_only:
        targets = stale_evaluations()
    else:
        with get_db() as db:
            targets = [dict(r) for r in db.execute(
                "SELECT id, title FROM opportunities "
                "WHERE status NOT IN ('won','lost','discarded') ORDER BY id")]
    if limit:
        targets = targets[:limit]

    results = []
    for target in targets:
        try:
            result = evaluate_opportunity(target["id"])
        except Exception as e:  # one bad row must not stop the batch
            result = {"opportunity": target["title"], "outcome": "error",
                      "detail": repr(e)}
        results.append(result)
    print(f"[evaluate] {len(results)} evaluated")
    return results
