"""REST layer: /ono dumps for LLM consumption (API key) + JSON CRUD for scripts."""
from fastapi import APIRouter, Header, HTTPException

from ..auth import check_api_key
from ..db import OPPORTUNITY_FIELDS, company_profile, get_db, opportunities_digest
from ..proposals import default_dilutive

router = APIRouter()


def _require_key(x_api_key: str | None):
    if not check_api_key(x_api_key or ""):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@router.get("/ono/profile")
def ono_profile(x_api_key: str | None = Header(None)):
    """The assembled company profile, derived values included."""
    _require_key(x_api_key)
    return company_profile()


@router.get("/ono/opportunities")
def ono_opportunities(x_api_key: str | None = Header(None)):
    """Compact JSON dump optimized for LLM consumption."""
    _require_key(x_api_key)
    return opportunities_digest()


@router.get("/api/opportunities")
def api_opportunities(x_api_key: str | None = Header(None)):
    _require_key(x_api_key)
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM opportunities ORDER BY deadline_date IS NULL, deadline_date"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/api/opportunities/{opportunity_id}")
def api_opportunity(opportunity_id: int, x_api_key: str | None = Header(None)):
    _require_key(x_api_key)
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM opportunities WHERE id=?", (opportunity_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    return dict(row)


@router.post("/api/opportunities")
def api_opportunity_create(payload: dict, x_api_key: str | None = Header(None)):
    _require_key(x_api_key)
    fields = {k: v for k, v in payload.items()
              if k in OPPORTUNITY_FIELDS and v not in (None, "")}
    if not fields.get("title"):
        raise HTTPException(status_code=422, detail="title is required")
    fields.setdefault("dilutive", default_dilutive(fields.get("instrument")))
    with get_db() as db:
        cur = db.execute(
            f"INSERT INTO opportunities ({', '.join(fields)}) "
            f"VALUES ({', '.join('?' * len(fields))})",
            list(fields.values()),
        )
        return {"id": cur.lastrowid}


@router.put("/api/opportunities/{opportunity_id}")
def api_opportunity_update(opportunity_id: int, payload: dict,
                           x_api_key: str | None = Header(None)):
    _require_key(x_api_key)
    fields = {k: v for k, v in payload.items()
              if k in OPPORTUNITY_FIELDS + ["status", "priority", "effort"]}
    if not fields:
        raise HTTPException(status_code=422, detail="No valid fields")
    sets = ", ".join(f"{k}=?" for k in fields)
    with get_db() as db:
        cur = db.execute(
            f"UPDATE opportunities SET {sets}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            list(fields.values()) + [opportunity_id],
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}
