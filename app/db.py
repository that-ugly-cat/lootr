"""SQLite layer: connection helper, schema, idempotent init, digests.

The schema here is authoritative. Migrations run inside `init_db` using
`PRAGMA table_info` + `ALTER TABLE`, so the database in ./data survives
redeploys. Anything company-, sector- or jurisdiction-specific lives in
data (config, funding_counters, company_qualifications, tag_vocabulary,
sources), never in column names or hardcoded constants.
"""
import json
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "LOOTR_DB", os.path.join(os.path.dirname(__file__), "..", "data", "lootr.db")
)

SCHEMA = """
-- ---------------------------------------------------------------- config

CREATE TABLE IF NOT EXISTS config (
    key    TEXT PRIMARY KEY,
    value  TEXT,
    note   TEXT
);

-- ------------------------------------------------------- company profile

CREATE TABLE IF NOT EXISTS company (
    id                  INTEGER PRIMARY KEY,
    legal_name          TEXT,
    legal_form          TEXT,
    country             TEXT,      -- ISO 3166-1 alpha-2
    vat_number          TEXT,
    registry_id         TEXT,
    industry_codes      TEXT,      -- JSON [{"system":"ATECO","code":"..."}]
    incorporation_date  DATE,      -- age is derived, never stored
    sme_size            TEXT,      -- micro | small | medium | large
    sme_size_definition TEXT,
    headcount           INTEGER,
    fte                 REAL,
    last_turnover       REAL,
    total_assets        REAL,
    currency            TEXT,
    revenue_stage       TEXT,      -- pre_revenue | first_sales | recurring
    funding_stage       TEXT,      -- pre_seed | seed | series_a | ...
    runway_months       INTEGER,
    impact_tags         TEXT,      -- JSON tag list
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_locations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT,      -- registered_office | operating_unit | lab | production
    city         TEXT,
    country      TEXT,
    region       TEXT,
    region_code  TEXT,
    code_system  TEXT,      -- NUTS | ISO-3166-2 | other
    registered   BOOLEAN DEFAULT 1,   -- formally filed, not just physically there
    active_from  DATE,
    active_until DATE,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS company_qualifications (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    key                  TEXT,   -- it_startup_innovativa | bcorp | eic_seal ...
    label                TEXT,
    jurisdiction         TEXT,
    status               TEXT,   -- active | expired | applied | none
    valid_from           DATE,
    valid_until          DATE,
    confirmed_at         DATE,
    renewal_every_months INTEGER,
    evidence             TEXT,
    notes                TEXT
);

CREATE TABLE IF NOT EXISTS team_members (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT,
    role              TEXT,
    is_founder        BOOLEAN DEFAULT 0,
    is_shareholder    BOOLEAN DEFAULT 0,
    shareholding_pct  REAL,
    gender            TEXT,
    birth_year        INTEGER,
    residence_country TEXT,
    residence_region  TEXT,
    highest_degree    TEXT,   -- phd | msc | bsc | other
    joined_at         DATE,
    left_at           DATE,   -- departures are kept: past track record used them
    fte               REAL,
    notes             TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT,
    description          TEXT,
    status               TEXT,   -- research | prototype | field_trials | pilot
                                 -- | pre_commercial | commercial | discontinued
    trl                  INTEGER,
    trl_updated_at       DATE,
    trl_evidence         TEXT,
    target_segments      TEXT,   -- JSON tag list
    target_markets       TEXT,   -- JSON
    impact_tags          TEXT,   -- JSON
    ip_status            TEXT,   -- none | filed | pct | granted
    ip_refs              TEXT,
    regulatory_framework TEXT,
    regulatory_status    TEXT,
    unit_economics       TEXT,
    active               BOOLEAN DEFAULT 1,
    notes                TEXT
);

CREATE TABLE IF NOT EXISTS company_funding (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument     TEXT,
    amount         REAL,
    currency       TEXT,
    investor       TEXT,
    closed_at      DATE,
    dilution_pct   REAL,
    converted      BOOLEAN,   -- convertibles: decides "equity raised" caps
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS company_aid (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT,
    provider       TEXT,
    entity         TEXT,
    regime         TEXT,   -- de_minimis | de_minimis_agri | block_exempted
                           -- | notified | market_terms | unknown
    nominal_amount REAL,
    gge_amount     REAL,   -- gross grant equivalent: this is what counts
    currency       TEXT,
    granted_at     DATE,   -- date of the AWARD decision, not of payment
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS company_narrative (
    section    TEXT PRIMARY KEY,
    content    TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tag_vocabulary (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    namespace TEXT,   -- segment | impact | sector | ...
    value     TEXT,
    label     TEXT,
    active    BOOLEAN DEFAULT 1
);

-- ------------------------------------------------------- cumulative caps

CREATE TABLE IF NOT EXISTS funding_counters (
    key          TEXT PRIMARY KEY,
    label        TEXT,
    used_amount  REAL DEFAULT 0,   -- maintained manually
    ceiling      REAL,             -- NULL when no universal ceiling exists
    currency     TEXT,
    window_years INTEGER,          -- NULL = lifetime; 3 = de minimis
    checked_at   DATE,
    source_note  TEXT,
    active       BOOLEAN DEFAULT 1
);

-- --------------------------------------------------------- opportunities

CREATE TABLE IF NOT EXISTS opportunities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    provider      TEXT,
    provider_type TEXT,
    instrument    TEXT,
    dilutive      BOOLEAN,
    is_general    BOOLEAN DEFAULT 0,   -- company-level, not about a product line
    link          TEXT,
    description   TEXT,
    source_id     INTEGER REFERENCES sources(id) ON DELETE SET NULL,

    amount_min        REAL,
    amount_max        REAL,
    currency          TEXT,
    funding_rate_pct  REAL,
    cofinancing_pct   REAL,
    advance_available BOOLEAN,
    disbursement      TEXT,   -- advance | milestones | reimbursement_on_report
    aid_regime        TEXT,
    call_total_budget TEXT,

    deadline_type           TEXT,   -- fixed | cutoffs | rolling
                                    -- | open_until_funds_exhausted | unknown
    deadline_date           DATE,
    deadline_text           TEXT,
    cutoff_dates            TEXT,   -- JSON
    recurrence_logic        TEXT,
    opens_at                DATE,
    decision_lag_months     INTEGER,
    project_duration_months INTEGER,

    eligible_geographies   TEXT,   -- JSON [{"code":"ITF4","system":"NUTS"}]
    requires_unit_in       TEXT,
    max_company_age_years  INTEGER,
    eligible_sme_sizes     TEXT,   -- JSON
    requires_qualification TEXT,   -- JSON of company_qualifications.key
    requires_partners      BOOLEAN,
    partner_requirements   TEXT,
    trl_min                INTEGER,
    trl_max                INTEGER,
    sector_tags            TEXT,   -- JSON
    impact_focus           TEXT,   -- JSON
    other_requirements     TEXT,

    ticket_min     REAL,
    ticket_max     REAL,
    stage_focus    TEXT,
    sector_focus   TEXT,
    geo_focus      TEXT,
    lead_or_follow TEXT,

    eligibility_verdict    TEXT,   -- eligible | not_eligible | uncertain
    eligibility_rationale  TEXT,
    eligibility_checked_at DATETIME,
    fit_score              INTEGER,
    fit_rationale          TEXT,
    best_fit_product_id    INTEGER REFERENCES products(id) ON DELETE SET NULL,
    effort                 TEXT,   -- low | medium | high | needs_consultant
    priority               TEXT,

    status           TEXT DEFAULT 'watching',
    owner_user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    origin           TEXT DEFAULT 'manual',
    last_checked_at  DATETIME,
    last_verified_at DATETIME,
    link_status      TEXT,
    content_hash     TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS opportunity_caps (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE CASCADE,
    counter_key    TEXT REFERENCES funding_counters(key),
    max_amount     REAL,
    currency       TEXT,
    comparator     TEXT,   -- lt | lte
    scope_note     TEXT,   -- verbatim wording: the perimeter is where it bites
    verdict        TEXT,   -- pass | fail | uncertain
    checked_at     DATETIME
);

CREATE TABLE IF NOT EXISTS opportunity_product_fit (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE CASCADE,
    product_id     INTEGER REFERENCES products(id) ON DELETE CASCADE,
    verdict        TEXT,
    fit_score      INTEGER,
    rationale      TEXT,
    evaluated_at   DATETIME
);

-- ---------------------------------------------------------------- pipeline

CREATE TABLE IF NOT EXISTS applications (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id   INTEGER REFERENCES opportunities(id) ON DELETE CASCADE,
    is_general       BOOLEAN DEFAULT 0,   -- not tied to any product line
    status           TEXT,
    amount_requested REAL,
    amount_awarded   REAL,
    currency         TEXT,
    submitted_at     DATE,
    outcome_at       DATE,
    owner_user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    next_action      TEXT,
    next_action_due  DATE,
    notes            TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- An application can cover more than one product line at once.
CREATE TABLE IF NOT EXISTS application_products (
    application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    product_id     INTEGER REFERENCES products(id) ON DELETE CASCADE,
    PRIMARY KEY (application_id, product_id)
);

CREATE TABLE IF NOT EXISTS activities (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE CASCADE,
    kind           TEXT,
    happened_at    DATE,
    contact_name   TEXT,
    summary        TEXT,
    created_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS contacts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT,
    organisation   TEXT,
    role           TEXT,
    email          TEXT,
    linkedin       TEXT,
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
    warm_intro_via TEXT,
    relationship   TEXT,   -- cold | contacted | met | engaged | passed
    notes          TEXT
);

-- --------------------------------------------------------------- discovery

CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    url             TEXT,
    hints           TEXT,
    geo_hint        TEXT,
    instrument_hint TEXT,
    scan_cadence    TEXT,   -- weekly | monthly | quarterly
    enabled         BOOLEAN DEFAULT 1,
    last_scanned_at DATETIME
);

CREATE TABLE IF NOT EXISTS proposals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    kind           TEXT NOT NULL,   -- new | update | flag
    opportunity_id INTEGER REFERENCES opportunities(id) ON DELETE SET NULL,
    source_id      INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    payload        TEXT,
    rationale      TEXT,
    source_url     TEXT,
    confidence     TEXT,
    method         TEXT,   -- llm_scan | link_monitor | ono_mcp | llm_check
    status         TEXT DEFAULT 'pending',
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    decided_at     DATETIME
);

CREATE TABLE IF NOT EXISTS scan_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER REFERENCES sources(id),
    started_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME,
    outcome     TEXT,   -- ok | error
    detail      TEXT
);

-- --------------------------------------------------------------- accounts

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'reader',   -- admin | editor | reader
    active        BOOLEAN DEFAULT 1,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_keys (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT NOT NULL,
    key          TEXT UNIQUE NOT NULL,
    active       BOOLEAN DEFAULT 1,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME
);

-- ---------------------------------------------------------------- indexes

CREATE INDEX IF NOT EXISTS idx_opp_deadline   ON opportunities(deadline_date);
CREATE INDEX IF NOT EXISTS idx_opp_status     ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opp_source     ON opportunities(source_id);
CREATE INDEX IF NOT EXISTS idx_opp_instrument ON opportunities(instrument);
CREATE INDEX IF NOT EXISTS idx_caps_opp       ON opportunity_caps(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_fit_opp        ON opportunity_product_fit(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_fit_product    ON opportunity_product_fit(product_id);
CREATE INDEX IF NOT EXISTS idx_app_opp        ON applications(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_app_due        ON applications(next_action_due);
CREATE INDEX IF NOT EXISTS idx_act_opp        ON activities(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_prop_status    ON proposals(status);
"""

# Bootstrap rows. Ceilings, windows and vocabularies are DATA: they are
# editable from the admin UI and must never be hardcoded elsewhere.
CONFIG_DEFAULTS = [
    ("base_currency", "EUR", "Reporting currency for aggregates"),
    ("company_display_name", "", "Shown in the UI header"),
    ("scan_model", "claude-opus-5", "Model used by scanner and evaluator"),
    ("default_scan_cadence", "monthly", "Fallback when a source has none"),
]

COUNTER_DEFAULTS = [
    ("de_minimis", "De minimis aid", 300000, "EUR", 3,
     "Authoritative figure: national state-aid register extract"),
    ("lifetime_total_raised", "Total funding raised", None, "EUR", None,
     "Sum of all instruments; each call defines its own perimeter"),
    ("lifetime_equity_raised", "Equity raised", None, "EUR", None,
     "Whether unconverted convertibles count depends on the call"),
    ("lifetime_public_grants", "Public grants received", None, "EUR", None,
     "Non-repayable public contributions"),
    ("eu_cascade_fstp", "EU cascade funding", None, "EUR", None,
     "Financial support to third parties, capped per beneficiary"),
]

NARRATIVE_SECTIONS = [
    "pitch", "technology", "ip", "market", "traction",
    "track_record", "strategy_12m", "exclusions",
]

# Fields a proposal may write onto an opportunity.
OPPORTUNITY_FIELDS = [
    "title", "provider", "provider_type", "instrument", "dilutive", "is_general", "link",
    "description", "amount_min", "amount_max", "currency", "funding_rate_pct",
    "cofinancing_pct", "advance_available", "disbursement", "aid_regime",
    "call_total_budget", "deadline_type", "deadline_date", "deadline_text",
    "cutoff_dates", "recurrence_logic", "opens_at", "decision_lag_months",
    "project_duration_months", "eligible_geographies", "requires_unit_in",
    "max_company_age_years", "eligible_sme_sizes", "requires_qualification",
    "requires_partners", "partner_requirements", "trl_min", "trl_max",
    "sector_tags", "impact_focus", "other_requirements", "ticket_min",
    "ticket_max", "stage_focus", "sector_focus", "geo_focus", "lead_or_follow",
]


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    with get_db() as db:
        db.executescript(SCHEMA)
        for key, value, note in CONFIG_DEFAULTS:
            db.execute(
                "INSERT OR IGNORE INTO config (key, value, note) VALUES (?,?,?)",
                (key, value, note),
            )
        for key, label, ceiling, currency, window, note in COUNTER_DEFAULTS:
            db.execute(
                "INSERT OR IGNORE INTO funding_counters "
                "(key, label, used_amount, ceiling, currency, window_years, source_note) "
                "VALUES (?,?,0,?,?,?,?)",
                (key, label, ceiling, currency, window, note),
            )
        for section in NARRATIVE_SECTIONS:
            db.execute(
                "INSERT OR IGNORE INTO company_narrative (section, content) VALUES (?, '')",
                (section,),
            )
        db.execute("INSERT OR IGNORE INTO company (id) VALUES (1)")

        # Migration 2026-08-18: an application can cover several product lines,
        # or none at all when the opportunity is company-level. The single FK
        # becomes a junction table; existing values are carried over first.
        acols = [r["name"] for r in db.execute("PRAGMA table_info(applications)")]
        if "is_general" not in acols:
            db.execute("ALTER TABLE applications ADD COLUMN is_general BOOLEAN DEFAULT 0")
        if "product_id" in acols:
            db.execute(
                "INSERT OR IGNORE INTO application_products (application_id, product_id) "
                "SELECT id, product_id FROM applications WHERE product_id IS NOT NULL")
            db.execute("ALTER TABLE applications DROP COLUMN product_id")
        ocols = [r["name"] for r in db.execute("PRAGMA table_info(opportunities)")]
        if "is_general" not in ocols:
            db.execute("ALTER TABLE opportunities ADD COLUMN is_general BOOLEAN DEFAULT 0")


# ------------------------------------------------------------------ helpers


def get_config(key: str, default: str = "") -> str:
    with get_db() as db:
        row = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    return row["value"] if row and row["value"] is not None else default


def status_condition(status: str, prefix: str = "") -> tuple[str, list]:
    """SQL condition for the status filter. 'open' and 'expired' are
    deadline-aware, as in Grant Radar: open = not yet closed by hand and the
    deadline is absent or in the future; expired = still open but past due.
    Opportunities with no deadline (investors, rolling schemes) count as open."""
    s, d = f"{prefix}status", f"{prefix}deadline_date"
    closed = ("won", "lost", "expired", "discarded")
    if status == "open":
        return (
            f" AND {s} NOT IN {closed} AND ({d} IS NULL OR date({d}) >= date('now'))",
            [],
        )
    if status == "expired":
        return (
            f" AND {s} NOT IN {closed} AND {d} IS NOT NULL AND date({d}) < date('now')",
            [],
        )
    if status:
        return f" AND {s}=?", [status]
    return "", []


def _rows(db, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in db.execute(sql, args).fetchall()]


def company_profile() -> dict:
    """The whole profile, assembled. Injected into every scan and evaluation
    prompt, and served as-is to the Ono layer. Derived values (age, team
    composition, eligible geographies, counter cross-checks) are computed
    here rather than stored, so they can never go stale."""
    with get_db() as db:
        company = db.execute("SELECT * FROM company WHERE id=1").fetchone()
        company = dict(company) if company else {}

        locations = _rows(db, "SELECT * FROM company_locations WHERE active_until IS NULL")
        team = _rows(db, "SELECT * FROM team_members WHERE left_at IS NULL")
        products = _rows(db, "SELECT * FROM products WHERE active=1")
        quals = _rows(db, "SELECT * FROM company_qualifications WHERE status='active'")
        narrative = {
            r["section"]: r["content"]
            for r in db.execute("SELECT section, content FROM company_narrative")
        }
        counters = _rows(db, "SELECT * FROM funding_counters WHERE active=1")

        # Ledger cross-checks. Each counter is maintained by hand; these are what
        # the two ledgers say, shown beside it so a stale figure becomes visible.
        def total(sql: str) -> float:
            return db.execute(sql).fetchone()["s"] or 0

        cross = {
            "de_minimis": total(
                "SELECT SUM(gge_amount) AS s FROM company_aid WHERE regime='de_minimis' "
                "AND granted_at IS NOT NULL AND date(granted_at) >= date('now','-3 years')"),
            "lifetime_total_raised": (
                total("SELECT SUM(amount) AS s FROM company_funding")
                + total("SELECT SUM(nominal_amount) AS s FROM company_aid")),
            # An unconverted convertible is not equity yet, and several calls
            # draw the line exactly there.
            "lifetime_equity_raised": total(
                "SELECT SUM(amount) AS s FROM company_funding WHERE instrument='equity' "
                "OR (instrument='convertible' AND converted=1)"),
            "lifetime_public_grants": total(
                "SELECT SUM(nominal_amount) AS s FROM company_aid WHERE regime IN "
                "('de_minimis','de_minimis_agri','block_exempted','notified')"),
        }

    age_years = None
    if company.get("incorporation_date"):
        with get_db() as db:
            age_years = db.execute(
                "SELECT CAST((julianday('now') - julianday(?)) / 365.25 AS INT) AS a",
                (company["incorporation_date"],),
            ).fetchone()["a"]

    for counter in counters:
        if counter["key"] in cross:
            counter["ledger_cross_check"] = cross[counter["key"]]
        if counter["ceiling"] is not None:
            counter["headroom"] = counter["ceiling"] - (counter["used_amount"] or 0)

    return {
        "company": company,
        "age_years": age_years,
        "locations": locations,
        "eligible_geographies": [
            {"region": l["region"], "code": l["region_code"],
             "system": l["code_system"], "country": l["country"], "kind": l["kind"]}
            for l in locations if l["registered"]
        ],
        "qualifications": quals,
        "team": team,
        "team_derived": {
            "headcount_active": len(team),
            "has_female_founder": any(
                m["is_founder"] and (m["gender"] or "").lower() == "f" for m in team
            ),
            "has_under35_founder": any(
                m["is_founder"] and m["birth_year"] for m in team
            ),
            "doctorate_holders": sum(
                1 for m in team if (m["highest_degree"] or "") == "phd"
            ),
        },
        "products": products,
        "max_active_trl": max(
            (p["trl"] for p in products if p["trl"] is not None), default=None
        ),
        "narrative": narrative,
        "counters": counters,
    }


def opportunities_digest(source_id: int | None = None, include_orphans: bool = True) -> list[dict]:
    """Compact dump used by the scanner prompt and by the Ono REST endpoint.
    Scoped to one source (plus orphans) so the scanner can tell a genuinely
    new opportunity from an update to one already tracked."""
    sql = (
        "SELECT id, title, provider, provider_type, instrument, deadline_type, "
        "deadline_date, deadline_text, amount_min, amount_max, currency, link, "
        "source_id, status, eligibility_verdict, fit_score "
        "FROM opportunities"
    )
    args: list = []
    if source_id is not None:
        sql += " WHERE (source_id=?" + (" OR source_id IS NULL)" if include_orphans else ")")
        args.append(source_id)
    sql += " ORDER BY deadline_date IS NULL, deadline_date"
    with get_db() as db:
        return _rows(db, sql, tuple(args))


def json_field(value, default=None):
    """JSON columns are written by the LLM and edited by hand; never let a
    malformed value break a page render."""
    if not value:
        return default if default is not None else []
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default if default is not None else []
