"""Proposals queue: diff computation and human decision (approve/reject).
Approving is the ONLY path from discovery output to the opportunities table."""
import json

from .db import OPPORTUNITY_FIELDS, get_db

# Instruments that put the opportunity in the Investors view rather than in
# Calls: no deadline to sort by, a relationship to advance instead.
EQUITY_INSTRUMENTS = ("equity", "convertible")
EQUITY_PROVIDERS = ("vc", "angel")

# Instruments that do not dilute. Used to default `dilutive` when a proposal
# does not say; always overridable by hand.
NON_DILUTIVE = (
    "grant", "subsidized_loan", "tax_credit", "guarantee", "prize",
    "hiring_support", "voucher", "cascade_grant", "in_kind",
)


def is_equity(row: dict) -> bool:
    return (row.get("instrument") in EQUITY_INSTRUMENTS
            or row.get("provider_type") in EQUITY_PROVIDERS)


def default_dilutive(instrument: str | None) -> int | None:
    if not instrument:
        return None
    return 0 if instrument in NON_DILUTIVE else 1


def compute_diff(proposal: dict) -> list[dict]:
    """[{field, old, new}] for the UI. For kind=new, old is always None."""
    payload = json.loads(proposal["payload"] or "{}")
    current = {}
    if proposal["opportunity_id"]:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM opportunities WHERE id=?", (proposal["opportunity_id"],)
            ).fetchone()
            current = dict(row) if row else {}
    diff = []
    for field in OPPORTUNITY_FIELDS:
        if field in payload:
            old = current.get(field)
            if str(old if old is not None else "") != str(payload[field] if payload[field] is not None else ""):
                diff.append({"field": field, "old": old, "new": payload[field]})
    return diff


def approve(proposal_id: int) -> bool:
    with get_db() as db:
        p = db.execute(
            "SELECT * FROM proposals WHERE id=? AND status='pending'", (proposal_id,)
        ).fetchone()
        if not p:
            return False
        payload = json.loads(p["payload"] or "{}")
        fields = {k: v for k, v in payload.items() if k in OPPORTUNITY_FIELDS}

        if p["kind"] == "new":
            if not fields.get("title"):
                return False
            fields.setdefault("dilutive", default_dilutive(fields.get("instrument")))
            cols = list(fields.keys()) + ["origin", "source_id"]
            vals = list(fields.values()) + ["discovery", p["source_id"]]
            db.execute(
                f"INSERT INTO opportunities ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' * len(vals))})",
                vals,
            )
        elif p["kind"] == "update" and p["opportunity_id"] and fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            db.execute(
                f"UPDATE opportunities SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                list(fields.values()) + [p["opportunity_id"]],
            )
            # An opportunity with no source yet inherits the proposal's.
            if p["source_id"]:
                db.execute(
                    "UPDATE opportunities SET source_id=? WHERE id=? AND source_id IS NULL",
                    (p["source_id"], p["opportunity_id"]),
                )
        # kind=flag: approving just acknowledges it; nothing to write.

        db.execute(
            "UPDATE proposals SET status='approved', decided_at=CURRENT_TIMESTAMP WHERE id=?",
            (proposal_id,),
        )
    return True


def reject(proposal_id: int) -> bool:
    with get_db() as db:
        cur = db.execute(
            "UPDATE proposals SET status='rejected', decided_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND status='pending'",
            (proposal_id,),
        )
        return cur.rowcount > 0
