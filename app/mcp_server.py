"""MCP surface for Ono (and any MCP client). Auth is enforced upstream by the
capability-URL middleware in main.py — tools here assume an authenticated caller.

Read tools cover the whole model: company profile, products, opportunities with
their caps and per-product fit, pipeline, contacts, cumulative counters, sources
and the proposals queue. Writes are deliberately narrow: opportunities can only
be *proposed* (a human approves in the UI), and the one direct write is the
activity diary, which is append-only and attributable.
"""
import json

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from .db import OPPORTUNITY_FIELDS, company_profile, get_db, status_condition
from .proposals import EQUITY_INSTRUMENTS, EQUITY_PROVIDERS

mcp = MCPServer(
    "lootr",
    instructions=(
        "Funding radar for a single company. Read the company profile and product "
        "lines, search tracked funding opportunities (public calls, prizes, "
        "programmes and investors), check deadlines and pending next actions, and "
        "file proposals that a human reviews in the web UI. Eligibility and fit are "
        "always evaluated against the company profile: read it before judging "
        "whether an opportunity is worth pursuing."
    ),
)


def build_asgi_app():
    """Streamable HTTP ASGI app, mounted at /mcp by main.py (so path here is '/').
    DNS-rebinding protection off: the app sits behind Caddy on a public hostname,
    and auth is enforced by the capability-URL middleware upstream."""
    return mcp.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _rows(sql: str, args: tuple | list = ()) -> list[dict]:
    with get_db() as db:
        return [dict(r) for r in db.execute(sql, args).fetchall()]


# ------------------------------------------------------------------ profile


@mcp.tool()
def get_company_profile() -> str:
    """The full company profile: legal and size data, registered locations,
    active qualifications, current team, product lines with their TRL, narrative
    sections (pitch, technology, IP, market, traction, track record, 12-month
    strategy, exclusions) and the cumulative funding counters.

    Derived values are computed here and never stored: company age, team
    composition gates (female founders, doctorate holders), de facto eligible
    geographies, highest active TRL, and a ledger cross-check on each counter.
    Read this before judging any opportunity."""
    return _dump(company_profile())


@mcp.tool()
def list_products() -> str:
    """Product lines with TRL, development status, IP status, regulatory
    framework and target segments. TRL belongs to the product, not to the
    company: a call asking for TRL 6-8 may fit one line and not another."""
    return _dump(_rows("SELECT * FROM products WHERE active=1 ORDER BY name"))


@mcp.tool()
def list_counters() -> str:
    """Cumulative funding caps the company is subject to: de minimis (with its
    ceiling and rolling window in years) plus lifetime counters for total raised,
    equity raised, public grants and EU cascade funding. `used_amount` is
    maintained by hand; `ceiling` is NULL where no universal ceiling exists and
    the limit is set by each individual call instead."""
    return _dump(_rows("SELECT * FROM funding_counters WHERE active=1"))


# ------------------------------------------------------- opportunities (read)


@mcp.tool()
def search_opportunities(
    q: str = "",
    view: str = "",
    instrument: str = "",
    provider_type: str = "",
    source_id: int | None = None,
    status: str = "open",
    min_fit: int | None = None,
) -> str:
    """Search tracked opportunities. q matches title, provider, description and
    notes fields (substring). view: 'calls' for everything with a deadline logic,
    'investors' for equity and convertible instruments and VC/angel providers,
    '' for both. instrument and provider_type filter exactly. status is
    deadline-aware: 'open' = not closed by hand and the deadline is absent or in
    the future (opportunities with no deadline, such as investors, count as
    open); 'expired' = still open but past due; or pass an exact state
    (watching, shortlisted, preparing, submitted, pending_outcome, won, lost,
    discarded); '' = any. min_fit filters on the stored fit score.
    Returns a JSON list sorted by next deadline."""
    sql = "SELECT * FROM opportunities WHERE 1=1"
    args: list = []
    if q:
        sql += (" AND (title LIKE ? OR provider LIKE ? OR description LIKE ? "
                "OR other_requirements LIKE ?)")
        args += [f"%{q}%"] * 4
    if view == "investors":
        sql += (f" AND (instrument IN {EQUITY_INSTRUMENTS} "
                f"OR provider_type IN {EQUITY_PROVIDERS})")
    elif view == "calls":
        sql += (f" AND instrument NOT IN {EQUITY_INSTRUMENTS} "
                f"AND (provider_type IS NULL OR provider_type NOT IN {EQUITY_PROVIDERS})")
    if instrument:
        sql += " AND instrument = ?"
        args.append(instrument)
    if provider_type:
        sql += " AND provider_type = ?"
        args.append(provider_type)
    if source_id is not None:
        sql += " AND source_id = ?"
        args.append(source_id)
    if min_fit is not None:
        sql += " AND fit_score IS NOT NULL AND fit_score >= ?"
        args.append(min_fit)
    cond, cond_args = status_condition(status)
    sql += cond
    args += cond_args
    sql += " ORDER BY deadline_date IS NULL, deadline_date"
    return _dump(_rows(sql, args))


@mcp.tool()
def get_opportunity(opportunity_id: int) -> str:
    """Everything known about one opportunity: the full record, the cumulative
    caps it imposes (with the verbatim wording of each perimeter), the per-product
    fit evaluations, any applications filed for it, the activity diary and the
    contacts attached to it."""
    with get_db() as db:
        row = db.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
        if not row:
            return _dump(None)
        out = dict(row)
        out["caps"] = [dict(r) for r in db.execute(
            "SELECT * FROM opportunity_caps WHERE opportunity_id=?", (opportunity_id,))]
        out["product_fit"] = [dict(r) for r in db.execute(
            "SELECT f.*, p.name AS product_name FROM opportunity_product_fit f "
            "LEFT JOIN products p ON p.id = f.product_id WHERE f.opportunity_id=?",
            (opportunity_id,))]
        out["applications"] = [dict(r) for r in db.execute(
            "SELECT a.*, (SELECT GROUP_CONCAT(p.name, ', ') FROM application_products ap "
            " JOIN products p ON p.id = ap.product_id WHERE ap.application_id = a.id) "
            "AS product_names FROM applications a WHERE a.opportunity_id=?",
            (opportunity_id,))]
        out["activities"] = [dict(r) for r in db.execute(
            "SELECT * FROM activities WHERE opportunity_id=? ORDER BY happened_at DESC",
            (opportunity_id,))]
        out["contacts"] = [dict(r) for r in db.execute(
            "SELECT * FROM contacts WHERE opportunity_id=?", (opportunity_id,))]
    return _dump(out)


@mcp.tool()
def upcoming_deadlines(days: int = 90) -> str:
    """Open opportunities with a deadline within the next `days` days, soonest
    first. Includes the deadline type, so a rolling or funds-exhausted scheme is
    not mistaken for a fixed date."""
    return _dump(_rows(
        "SELECT id, title, provider, instrument, deadline_type, deadline_date, "
        "deadline_text, amount_max, currency, fit_score, status, link "
        "FROM opportunities "
        "WHERE status NOT IN ('won','lost','expired','discarded') "
        "AND deadline_date IS NOT NULL AND deadline_date >= date('now') "
        "AND deadline_date <= date('now', ?) ORDER BY deadline_date",
        [f"+{int(days)} days"],
    ))


# ---------------------------------------------------------------- pipeline


@mcp.tool()
def next_actions(days: int = 30, overdue: bool = True) -> str:
    """Pipeline items with a next action due within `days` days, soonest first.
    This is how the investor branch is read: no deadline to sort by, only the
    next step. Set overdue=False to hide actions already past due."""
    sql = (
        "SELECT a.*, o.title, o.provider, o.instrument FROM applications a "
        "LEFT JOIN opportunities o ON o.id = a.opportunity_id "
        "WHERE a.next_action_due IS NOT NULL "
        "AND a.next_action_due <= date('now', ?) "
        "AND a.status NOT IN ('won','lost','withdrawn')"
    )
    args: list = [f"+{int(days)} days"]
    if not overdue:
        sql += " AND a.next_action_due >= date('now')"
    sql += " ORDER BY a.next_action_due"
    return _dump(_rows(sql, args))


@mcp.tool()
def list_applications(status: str = "") -> str:
    """Applications filed or being prepared (status: preparing, submitted,
    pending, won, lost, withdrawn; '' for all), with the opportunity and the
    product lines each one covers. An application with no products and
    is_general set is a company-level request rather than one about a line."""
    sql = (
        "SELECT a.*, o.title, o.provider, "
        "(SELECT GROUP_CONCAT(p.name, ', ') FROM application_products ap "
        " JOIN products p ON p.id = ap.product_id WHERE ap.application_id = a.id) "
        "AS product_names FROM applications a "
        "LEFT JOIN opportunities o ON o.id = a.opportunity_id"
    )
    args: list = []
    if status:
        sql += " WHERE a.status = ?"
        args.append(status)
    sql += " ORDER BY a.next_action_due IS NULL, a.next_action_due"
    return _dump(_rows(sql, args))


@mcp.tool()
def list_contacts(relationship: str = "") -> str:
    """People attached to opportunities, with how warm the relationship is
    (cold, contacted, met, engaged, passed) and who can make the introduction."""
    sql = ("SELECT c.*, o.title AS opportunity_title FROM contacts c "
           "LEFT JOIN opportunities o ON o.id = c.opportunity_id")
    args: list = []
    if relationship:
        sql += " WHERE c.relationship = ?"
        args.append(relationship)
    sql += " ORDER BY c.organisation, c.name"
    return _dump(_rows(sql, args))


# --------------------------------------------------------------- discovery


@mcp.tool()
def list_sources() -> str:
    """Configured discovery sources (id, name, url, hints, geography, instrument
    focus, cadence). Use the id as source_id when filing proposals that belong to
    one of these sources."""
    return _dump(_rows(
        "SELECT id, name, url, hints, geo_hint, instrument_hint, scan_cadence, "
        "enabled, last_scanned_at FROM sources ORDER BY name"))


@mcp.tool()
def list_proposals(status: str = "pending") -> str:
    """Proposals in the queue (status: pending, approved, rejected). Approval
    happens only in the web UI: nothing enters the opportunities table any
    other way."""
    return _dump(_rows(
        "SELECT p.*, o.title AS opportunity_title FROM proposals p "
        "LEFT JOIN opportunities o ON o.id = p.opportunity_id "
        "WHERE p.status=? ORDER BY p.created_at DESC", (status,)))


def _insert_proposal(kind: str, opportunity_id: int | None, fields: dict, rationale: str,
                     source_url: str, confidence: str, source_id: int | None) -> int:
    clean = {k: v for k, v in fields.items()
             if k in OPPORTUNITY_FIELDS and v not in (None, "")}
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO proposals (kind, opportunity_id, source_id, payload, rationale, "
            "source_url, confidence, method) VALUES (?, ?, ?, ?, ?, ?, ?, 'ono_mcp')",
            (kind, opportunity_id, source_id, json.dumps(clean, ensure_ascii=False),
             rationale, source_url, confidence),
        )
        return cur.lastrowid


@mcp.tool()
def propose_opportunity(fields: dict, rationale: str, source_url: str = "",
                        confidence: str = "medium", source_id: int | None = None) -> str:
    """Propose a NEW opportunity for the queue (needs human approval in the UI).

    `title` is required. Other fields, all optional: provider, provider_type,
    instrument, link, description, amount_min, amount_max, currency,
    funding_rate_pct, cofinancing_pct, advance_available, disbursement,
    aid_regime, call_total_budget, deadline_type (fixed | cutoffs | rolling |
    open_until_funds_exhausted | unknown), deadline_date (YYYY-MM-DD),
    deadline_text, cutoff_dates, recurrence_logic, opens_at,
    decision_lag_months, project_duration_months, eligible_geographies,
    requires_unit_in, max_company_age_years, eligible_sme_sizes,
    requires_qualification, requires_partners, partner_requirements, trl_min,
    trl_max, sector_tags, impact_focus, other_requirements, and for investors
    ticket_min, ticket_max, stage_focus, sector_focus, geo_focus, lead_or_follow.

    Record eligibility thresholds as written by the source rather than
    normalising them: the exact perimeter of a cap ("less than X raised to
    date") is what decides whether it applies. Put anything you are unsure
    about in other_requirements instead of guessing a structured value."""
    if not fields.get("title"):
        return _dump({"ok": False, "error": "fields.title is required"})
    pid = _insert_proposal("new", None, fields, rationale, source_url, confidence, source_id)
    return _dump({"ok": True, "proposal_id": pid})


@mcp.tool()
def propose_update(opportunity_id: int, fields: dict, rationale: str, source_url: str = "",
                   confidence: str = "medium", source_id: int | None = None) -> str:
    """Propose an UPDATE to a tracked opportunity (needs human approval in the
    UI). fields: only what should change. source_id is inherited by the
    opportunity on approval if it has none yet."""
    with get_db() as db:
        if not db.execute("SELECT id FROM opportunities WHERE id=?", (opportunity_id,)).fetchone():
            return _dump({"ok": False, "error": f"opportunity {opportunity_id} not found"})
    if not fields:
        return _dump({"ok": False, "error": "fields is empty"})
    pid = _insert_proposal("update", opportunity_id, fields, rationale, source_url,
                           confidence, source_id)
    return _dump({"ok": True, "proposal_id": pid})


@mcp.tool()
def log_activity(opportunity_id: int, kind: str, summary: str,
                 happened_at: str = "", contact_name: str = "") -> str:
    """Append an entry to the activity diary of an opportunity: kind is one of
    call, email, meeting, pitch, intro, submission. happened_at is YYYY-MM-DD
    and defaults to today. This is the one direct write in this surface — the
    diary is append-only and shows up in the UI attributed to the MCP caller."""
    with get_db() as db:
        if not db.execute("SELECT id FROM opportunities WHERE id=?", (opportunity_id,)).fetchone():
            return _dump({"ok": False, "error": f"opportunity {opportunity_id} not found"})
        cur = db.execute(
            "INSERT INTO activities (opportunity_id, kind, happened_at, contact_name, summary) "
            "VALUES (?, ?, COALESCE(NULLIF(?, ''), date('now')), ?, ?)",
            (opportunity_id, kind, happened_at, contact_name or None, summary),
        )
        return _dump({"ok": True, "activity_id": cur.lastrowid})
