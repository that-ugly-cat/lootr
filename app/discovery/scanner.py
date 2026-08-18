"""Semantic scan: one Claude call per due source, with server-side web search.

The model gets the company profile and the digest of what is already tracked for
that source, and files `new` / `update` proposals. Nothing touches the
opportunities table: everything lands in the queue for human review.

Division of labour with the evaluator: the scanner records **facts as written**
— including eligibility thresholds, verbatim, in `other_requirements`. Turning
those into structured caps and judging them against the profile is the
evaluator's job, because that is interpretation and it has to be recomputable
when the profile changes.
"""
import json
import os
from datetime import date

import anthropic

from .. import jobs
from ..db import OPPORTUNITY_FIELDS, get_db, get_config, opportunities_digest
from .profile_context import profile_block

DEFAULT_MODEL = "claude-opus-5"


def model() -> str:
    """The model scanner, verifier and evaluator run on.

    Read at call time rather than at import, because it is a `config` row and
    the admin page has to be able to change it — as a module constant the row
    was editable and inert, which is worse than not offering it at all. The
    environment variable still wins, for trying a model locally without
    touching the deployed configuration.

    Both fallbacks are `or` rather than a default argument on purpose: an empty
    config row must read as "not set" and fall through, or clearing the box in
    the admin page would send an empty model string to the API.
    """
    return (os.environ.get("LOOTR_MODEL")
            or get_config("scan_model")
            or DEFAULT_MODEL)


MAX_TURNS = 8
MAX_WEB_SEARCHES = 14
CADENCE_DAYS = {"weekly": 7, "monthly": 30, "quarterly": 90}

# Every field is a plain string, with "" meaning not known / not changed.
# Nullable would be the natural shape, but a strict schema allows at most 16
# union-typed parameters and there are far more fields than that, so the empty
# string carries the absence instead. SQLite's column affinity converts the
# numeric and boolean ones on insert; _store_proposals drops the empty ones.
_FIELD_PROPS = {f: {"type": "string"} for f in OPPORTUNITY_FIELDS}

SUBMIT_TOOL = {
    "name": "submit_proposals",
    "description": (
        "Submit the final list of proposals for this source. Call this exactly once, "
        "when you have finished searching. Pass an empty array if nothing new or "
        "changed was found."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "proposals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["new", "update"]},
                        "opportunity_id": {
                            "type": "integer",
                            "description": "ID from the digest for kind=update; 0 for kind=new",
                        },
                        "fields": {
                            "type": "object",
                            "properties": _FIELD_PROPS,
                            "required": list(_FIELD_PROPS.keys()),
                            "additionalProperties": False,
                        },
                        "rationale": {"type": "string"},
                        "source_url": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                    "required": ["kind", "opportunity_id", "fields", "rationale",
                                 "source_url", "confidence"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["proposals"],
        "additionalProperties": False,
    },
}

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search",
                   "max_uses": MAX_WEB_SEARCHES}

# The shapes live in one constant because two processes write these columns: the
# scanner and the verifier. The rules were written after a live run in which the
# model understood everything and destroyed the columns anyway — advance_available
# holding "Sì: entro 4 mesi dalla firma", a geography holding a sentence. The
# verifier writes into the same columns and had none of this, which was the same
# bug waiting for its turn.
FIELD_SHAPE = """THE SHAPE OF EACH FIELD. Some fields are structured and are read by code, \
not by a person. Putting a sentence in one of them destroys it. Prose belongs in description, \
deadline_text and other_requirements, and nowhere else.

- instrument: exactly one of grant, subsidized_loan, tax_credit, guarantee, prize, programme, \
hiring_support, voucher, cascade_grant, equity, convertible, in_kind. One instrument per \
record — a scheme that mixes a soft loan with a grant portion is the instrument that carries \
most of the money, with the rest explained in other_requirements.
- provider_type: exactly one of public_supranational, public_national, public_regional, \
foundation, corporate, vc, angel, accelerator, bank, other.
- deadline_type: exactly one of fixed, cutoffs, rolling, open_until_funds_exhausted, unknown. \
A scheme that stays open until the money runs out is open_until_funds_exhausted, not rolling.
- disbursement: exactly one of advance, milestones, reimbursement_on_report.
- aid_regime: exactly one of de_minimis, block_exempted, notified, none.
- dilutive, is_general, advance_available, requires_partners: "1" or "0" and nothing else. \
Set is_general to "1" when the money is about the company rather than one product line (a round, \
a hire, a certification, advice).
- eligible_geographies: a JSON array, e.g. [{"code":"IT","system":"ISO-3166-1"}] or \
[{"code":"ITF","system":"NUTS"}]. requires_unit_in: a single code, not a sentence.
- unit_required_by: exactly one of at_application, at_award, at_first_payment, \
by_project_end, unknown. This one distinction decides whether a geographic requirement excludes \
a company or merely costs it something: most Italian schemes do not ask for the operating unit \
to exist when applying, they ask the applicant to undertake to open it, and unit_deadline_months \
is how many months it then has, as a bare number. Write unknown when the call does not say, and \
do not assume either way.
- eligible_sme_sizes: a JSON array drawn from micro, small, medium, large.
- sector_tags and impact_focus: JSON arrays of short snake_case tags. The tags already in use \
are listed with the company profile: reuse one whenever it fits, and add a new one only when \
none does. Two tags that mean the same thing are worse than one tag that is slightly wrong, \
because they never filter together.
- requires_qualification: a JSON array of qualification keys exactly as they appear in the \
company profile, e.g. ["it_startup_innovativa"] — not a description of the requirement.
- amounts, percentages, TRL, months and years: bare numbers, no currency symbol, no thousands \
separator, no words. currency is a three-letter code.
- deadline_date and opens_at: ISO YYYY-MM-DD."""

SYSTEM = """You are the discovery engine of Lootr, a funding radar for one company. \
The company profile below is the whole basis for judging relevance: read it before searching.

Given one source and the digest of what is already tracked for it, use web search to find:
1. NEW opportunities from this source that suit this company and are not in the digest.
2. UPDATES to tracked opportunities from this source: a new deadline for a recurring call, \
changed amounts or rules, a scheme that closed or was discontinued.

What counts as an opportunity is wider than a grant: public contributions, subsidised loans, \
tax credits, guarantees, prizes and competitions, accelerator or programme places, support for \
hiring, vouchers, cascade funding from an EU project, and investors.

""" + FIELD_SHAPE + """

Rules on the facts:
- Only propose what you actually verified on a page you visited. Every proposal needs its source_url.
- Leave a field as an empty string when you do not know it or it has not changed. Never write \
"null", "n/a" or "unknown" into a field: an empty string is how absence is recorded.
- For kind=update, set opportunity_id to the digest ID and fill ONLY the fields that changed. \
For kind=new, set opportunity_id to 0 and fill every field you found.
- Record eligibility thresholds and conditions **in the source's own words** in \
other_requirements — especially any cap of the form "open only to companies that have raised \
less than X" or "consumes de minimis". Do not normalise, convert, or interpret them: the exact \
wording decides whether a cap applies, and a later step judges it against the company's figures.
- Conditions that fall due only if the money is won — opening a unit in the region, hiring, \
putting up matching money, obtaining a certification, incorporating a new company — go verbatim \
into other_requirements together with the deadline attached to them. Never treat one as a reason \
to skip an opportunity: they are commitments the company would take on, and a later step judges \
what they would cost.
- deadline_text is the deadline as the call words it, however long. The structured deadline_date \
and deadline_type carry the machine-readable version of the same thing.
- advance_available and disbursement matter: whether the money arrives up front, on milestones, \
or only on reimbursement after the spend decides whether a company with a short runway can use \
it. Put the conditions attached to an advance in other_requirements, not in the flag.

Rules on judgement:
- Skip what the company plainly cannot take: wrong country, wrong sector, a category it does not \
belong to, a closed scheme with no next edition. A region where the company has no unit is not \
one of these cases whenever the call lets the unit be opened after the award.
- Do not skip something merely because eligibility is unclear. Propose it, say what is unclear in \
the rationale, and set confidence=low.
- Be conservative: a wrong proposal costs review time. When unsure, say so rather than guessing.
- When done, call submit_proposals exactly once."""


def _user_prompt(source: dict) -> str:
    # Each source sees its own opportunities plus the ones not yet mapped to any
    # source, so the model can tell a genuinely new find from a duplicate.
    digest = [o for o in opportunities_digest()
              if o.get("source_id") in (source["id"], None)]
    return (
        profile_block()
        + f"\n\n# SOURCE TO SCAN\n- name: {source['name']}\n"
        f"- url: {source['url'] or '(none)'}\n"
        f"- geography: {source['geo_hint'] or '(any)'}\n"
        f"- instruments: {source['instrument_hint'] or '(any)'}\n"
        f"- search hints: {source['hints'] or '(none)'}\n\n"
        f"# ALREADY TRACKED FOR THIS SOURCE (JSON)\n"
        + json.dumps(digest, ensure_ascii=False, default=str)
    )


def _duplicate_pending(db, kind: str, opportunity_id, title: str | None) -> bool:
    if kind == "update" and opportunity_id:
        return db.execute(
            "SELECT id FROM proposals WHERE kind='update' AND opportunity_id=? "
            "AND status='pending'", (opportunity_id,),
        ).fetchone() is not None
    if kind == "new" and title:
        return db.execute(
            "SELECT id FROM proposals WHERE kind='new' AND status='pending' "
            "AND json_extract(payload, '$.title') = ?", (title,),
        ).fetchone() is not None
    return False


def _store_proposals(source: dict, proposals: list[dict]) -> int:
    stored = 0
    with get_db() as db:
        for p in proposals:
            fields = {k: v for k, v in (p.get("fields") or {}).items()
                      if k in OPPORTUNITY_FIELDS and v not in (None, "")}
            kind, oid = p.get("kind"), p.get("opportunity_id") or None
            if kind not in ("new", "update") or (kind == "update" and not oid):
                continue
            if kind == "new" and not fields.get("title"):
                continue
            if _duplicate_pending(db, kind, oid, fields.get("title")):
                continue
            db.execute(
                "INSERT INTO proposals (kind, opportunity_id, source_id, payload, "
                "rationale, source_url, confidence, method) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'llm_scan')",
                (kind, oid if kind == "update" else None, source["id"],
                 json.dumps(fields, ensure_ascii=False), p.get("rationale", ""),
                 p.get("source_url", ""), p.get("confidence", "medium")),
            )
            stored += 1
    return stored


def scan_source(source: dict) -> dict:
    """One agentic loop over a single source."""
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": _user_prompt(source)}]
    tools = [WEB_SEARCH_TOOL, SUBMIT_TOOL]
    proposals = None

    for _ in range(MAX_TURNS):
        response = client.messages.create(
            model=model(),
            max_tokens=16000,
            output_config={"effort": "high"},
            system=SYSTEM,
            tools=tools,
            messages=messages,
        )

        # Check the stop reason before reading content: a refusal carries no
        # answer, and an empty content list would break the search below.
        if response.stop_reason == "refusal":
            return {"source": source["name"], "outcome": "error", "detail": "refusal"}

        submit = next((b for b in response.content
                       if b.type == "tool_use" and b.name == "submit_proposals"), None)
        if submit is not None:
            proposals = submit.input.get("proposals", [])
            break

        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason in ("pause_turn", "tool_use"):
            # Server-side tools ran; nothing for us to execute, just continue.
            continue
        messages.append({"role": "user", "content":
                         "Call submit_proposals now with your findings "
                         "(an empty array if there is nothing)."})

    if proposals is None:
        return {"source": source["name"], "outcome": "error",
                "detail": "no submit_proposals call"}

    stored = _store_proposals(source, proposals)
    return {"source": source["name"], "outcome": "ok",
            "proposed": len(proposals), "stored": stored}


def due_sources() -> list[dict]:
    """Sources whose cadence has come round. Weekly suits competitions and
    accelerator batches; monthly suits bodies that publish one call a year."""
    default = get_config("default_scan_cadence", "monthly")
    with get_db() as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM sources WHERE enabled=1")]
        due = []
        for source in rows:
            days = CADENCE_DAYS.get(source["scan_cadence"] or default, 30)
            if not source["last_scanned_at"]:
                due.append(source)
                continue
            fresh = db.execute(
                "SELECT date(?) >= date('now', ?) AS fresh",
                (source["last_scanned_at"], f"-{days} days"),
            ).fetchone()["fresh"]
            if not fresh:
                due.append(source)
    # Oldest first, never-scanned before everything else, so a capped run works
    # its way through the backlog instead of re-reading the same few sources.
    due.sort(key=lambda s: s["last_scanned_at"] or "")
    return due


def apply_scan_cap(sources: list[dict]) -> list[dict]:
    """Bound what one nightly run costs.

    Every source is a model call with web search behind it, and the day a batch
    of sources is added they all fall due on the same night: uncapped, the first
    run would scan the whole list at once and drop a hundred proposals into the
    queue for review in one go. The rest is not dropped, only postponed — due
    sources come oldest-first, so the backlog drains over the following nights.
    The postponement is written to the scan log, because a silent cap reads
    exactly like a night with nothing to find.
    """
    limit = int(get_config("max_scans_per_run", "6") or 0)
    if not limit or len(sources) <= limit:
        return sources
    postponed = [s["name"] for s in sources[limit:]]
    with get_db() as db:
        db.execute(
            "INSERT INTO scan_log (source_id, finished_at, outcome, detail) "
            "VALUES (NULL, CURRENT_TIMESTAMP, 'ok', ?)",
            (json.dumps({"outcome": "capped", "limit": limit,
                         "postponed": postponed}, ensure_ascii=False),),
        )
    print(f"[scan] capped at {limit}, postponed: {', '.join(postponed)}")
    return sources[:limit]


def run_scan(source_id: int | None = None, only_due: bool = False) -> list[dict]:
    """Scan one source, every enabled source, or only the ones that are due.
    Called by the scheduler (only_due=True) and by the buttons in the UI."""
    if source_id:
        with get_db() as db:
            row = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
        sources = [dict(row)] if row else []
    elif only_due:
        sources = apply_scan_cap(due_sources())
    else:
        with get_db() as db:
            sources = [dict(r) for r in
                       db.execute("SELECT * FROM sources WHERE enabled=1")]

    results = []
    for n, source in enumerate(sources, start=1):
        # Which source, out of how many: on a nightly run of six this is the
        # difference between "something is happening" and knowing how long is left.
        jobs.progress("scan", f"{source['name']} ({n} of {len(sources)})")
        with get_db() as db:
            log_id = db.execute("INSERT INTO scan_log (source_id) VALUES (?)",
                                (source["id"],)).lastrowid
        try:
            result = scan_source(source)
        except anthropic.APIError as e:
            result = {"source": source["name"], "outcome": "error",
                      "detail": f"API error: {e}"}
        except Exception as e:  # one broken source must not kill the scheduler
            result = {"source": source["name"], "outcome": "error", "detail": repr(e)}
        with get_db() as db:
            db.execute(
                "UPDATE scan_log SET finished_at=CURRENT_TIMESTAMP, outcome=?, detail=? "
                "WHERE id=?",
                (result["outcome"], json.dumps(result, ensure_ascii=False), log_id),
            )
            if result["outcome"] == "ok":
                db.execute("UPDATE sources SET last_scanned_at=CURRENT_TIMESTAMP "
                           "WHERE id=?", (source["id"],))
        print(f"[scan] {result}")
        results.append(result)
    return results
