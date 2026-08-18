"""Nightly link monitor: no model in the loop. Fetches every opportunity link,
updates link_status and content_hash, and files a `flag` proposal when a link
dies or its page changes. Costs nothing, so it runs every night and tells the
semantic scan where to look first."""
import hashlib
import json
import re

import httpx

from ..db import get_db

TIMEOUT = 20.0
HEADERS = {"User-Agent": "Lootr/1.0 (+https://lootr.borant.eu)"}


def _normalize(html: str) -> str:
    """Strip tags and collapse whitespace so cosmetic changes don't trip the hash."""
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _file_flag(db, opportunity_id: int, rationale: str, source_url: str) -> None:
    """One pending flag per opportunity: a page that changes every night should
    not produce a new proposal every night."""
    existing = db.execute(
        "SELECT id FROM proposals WHERE kind='flag' AND opportunity_id=? AND status='pending'",
        (opportunity_id,),
    ).fetchone()
    if existing:
        return
    row = db.execute("SELECT source_id FROM opportunities WHERE id=?",
                     (opportunity_id,)).fetchone()
    db.execute(
        "INSERT INTO proposals (kind, opportunity_id, source_id, payload, rationale, "
        "source_url, confidence, method) "
        "VALUES ('flag', ?, ?, ?, ?, ?, 'high', 'link_monitor')",
        (opportunity_id, row["source_id"] if row else None, json.dumps({}),
         rationale, source_url),
    )


def run_link_monitor() -> dict:
    """Returns a summary dict; safe to call from the scheduler or the UI."""
    checked = dead = changed = 0
    with get_db() as db:
        rows = db.execute(
            "SELECT id, link, content_hash FROM opportunities "
            "WHERE link IS NOT NULL AND link != '' "
            "AND status NOT IN ('won','lost','discarded')"
        ).fetchall()

    with httpx.Client(timeout=TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        for o in rows:
            checked += 1
            status, new_hash = "ok", None
            try:
                resp = client.get(o["link"])
                if resp.status_code >= 400:
                    status = "dead"
                else:
                    new_hash = hashlib.sha256(_normalize(resp.text).encode()).hexdigest()
                    if o["content_hash"] and new_hash != o["content_hash"]:
                        status = "changed"
            except httpx.HTTPError:
                status = "dead"

            with get_db() as db:
                db.execute(
                    "UPDATE opportunities SET link_status=?, "
                    "content_hash=COALESCE(?, content_hash), "
                    "last_checked_at=CURRENT_TIMESTAMP WHERE id=?",
                    (status, new_hash, o["id"]),
                )
                if status == "dead":
                    dead += 1
                    _file_flag(db, o["id"],
                               "Link unreachable (HTTP or network error).", o["link"])
                elif status == "changed":
                    changed += 1
                    _file_flag(db, o["id"],
                               "The page has changed since the last check.", o["link"])

    summary = {"checked": checked, "dead": dead, "changed": changed}
    print(f"[link-monitor] {summary}")
    return summary
