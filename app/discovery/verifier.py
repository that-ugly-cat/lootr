"""Per-opportunity verification: the model fetches the page (web fetch, with web
search as a fallback when the page moved or died), compares it against the
stored record, and either stamps the row as verified or files an `update`
proposal with the discrepancies.

This is about the record matching reality. Whether the opportunity is worth
pursuing is the evaluator's question, not this one."""
import json

import anthropic

from ..db import OPPORTUNITY_FIELDS, get_db
from .profile_context import opportunity_block
from .scanner import FIELD_SHAPE, client, model, turn

MAX_TURNS = 6

# Plain strings, "" for unchanged: a strict schema allows at most 16
# union-typed parameters and there are far more fields than that.
_FIELD_PROPS = {f: {"type": "string"} for f in OPPORTUNITY_FIELDS}

SUBMIT_TOOL = {
    "name": "submit_verification",
    "description": (
        "Submit the verification outcome. Call this exactly once, when you have checked "
        "the page. matches=true means every stored field is still accurate; matches=false "
        "means at least one should change — put ONLY those fields in `fields`, an empty "
        "string for the rest."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "matches": {"type": "boolean"},
            "fields": {
                "type": "object",
                "properties": _FIELD_PROPS,
                "required": list(_FIELD_PROPS.keys()),
                "additionalProperties": False,
            },
            "rationale": {"type": "string"},
            "source_url": {"type": "string",
                           "description": "The page you actually verified against"},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        },
        "required": ["matches", "fields", "rationale", "source_url", "confidence"],
        "additionalProperties": False,
    },
}

TOOLS = [
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 5},
    SUBMIT_TOOL,
]

SYSTEM = """You verify one record of a funding radar against reality.

Fetch the opportunity's link and check every stored field against the page: has a new edition \
opened, did the deadline pass, have the amounts or the coverage rate changed, is the scheme \
still running, do the eligibility conditions still read the way we recorded them. If the link \
is dead or the page moved, search for the scheme's current official page.

""" + FIELD_SHAPE + """

Rules:
- Compare against what you actually read; do not guess.
- Report ONLY fields whose stored value is wrong or outdated; leave everything else as an \
empty string. Never write "null" or "unknown" into a field.
- A deadline in the past with a known next edition: propose the new deadline.
- A scheme that was discontinued: say so in other_requirements or description. Do not change \
status — that is a human decision.
- Keep eligibility thresholds in the source's own words. Do not normalise them.
- If everything checks out, matches=true with every field empty.
- Call submit_verification exactly once when done."""


def _apply_result(opportunity: dict, result: dict) -> dict:
    """Stamp the check; file an update proposal if there are real differences.
    Separated from the model loop so it can be tested without an API call."""
    fields = {k: v for k, v in (result.get("fields") or {}).items()
              if k in OPPORTUNITY_FIELDS and v not in (None, "")}
    # Keep only what actually differs from the stored record: a proposal with an
    # empty diff is noise in the queue.
    fields = {k: v for k, v in fields.items()
              if str(opportunity.get(k) or "") != str(v or "")}
    matches = bool(result.get("matches")) or not fields

    with get_db() as db:
        db.execute("UPDATE opportunities SET last_verified_at=CURRENT_TIMESTAMP "
                   "WHERE id=?", (opportunity["id"],))
        if matches:
            return {"opportunity": opportunity["title"], "outcome": "verified", "changes": 0}
        if db.execute("SELECT id FROM proposals WHERE kind='update' AND opportunity_id=? "
                      "AND status='pending'", (opportunity["id"],)).fetchone():
            return {"opportunity": opportunity["title"], "outcome": "pending_exists",
                    "changes": len(fields)}
        db.execute(
            "INSERT INTO proposals (kind, opportunity_id, source_id, payload, rationale, "
            "source_url, confidence, method) "
            "VALUES ('update', ?, ?, ?, ?, ?, ?, 'llm_check')",
            (opportunity["id"], opportunity.get("source_id"),
             json.dumps(fields, ensure_ascii=False), result.get("rationale", ""),
             result.get("source_url", ""), result.get("confidence", "medium")),
        )
        return {"opportunity": opportunity["title"], "outcome": "diff_proposed",
                "changes": len(fields)}


def verify_opportunity(opportunity_id: int) -> dict:
    with get_db() as db:
        row = db.execute("SELECT * FROM opportunities WHERE id=?",
                         (opportunity_id,)).fetchone()
    if not row:
        return {"outcome": "error", "detail": f"opportunity {opportunity_id} not found"}
    opportunity = dict(row)

    api = client()
    messages = [{"role": "user", "content":
                 "# STORED RECORD\n" + opportunity_block(opportunity)}]
    result = None
    try:
        for _ in range(MAX_TURNS):
            response = turn(
                api, model=model(), max_tokens=12000, output_config={"effort": "high"},
                system=SYSTEM, tools=TOOLS, messages=messages,
            )
            if response.stop_reason == "refusal":
                return {"opportunity": opportunity["title"], "outcome": "error",
                        "detail": "refusal"}
            submit = next((b for b in response.content if b.type == "tool_use"
                           and b.name == "submit_verification"), None)
            if submit is not None:
                result = submit.input
                break
            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason not in ("pause_turn", "tool_use"):
                messages.append({"role": "user", "content":
                                 "Call submit_verification now with your outcome."})
    except anthropic.APIError as e:
        return {"opportunity": opportunity["title"], "outcome": "error",
                "detail": f"API error: {e}"}

    if result is None:
        return {"opportunity": opportunity["title"], "outcome": "error",
                "detail": "no submit_verification call"}

    summary = _apply_result(opportunity, result)
    print(f"[verify] {summary}")
    return summary
