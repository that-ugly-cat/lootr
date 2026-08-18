"""HTMX/Jinja2 web UI: two opportunity views, company profile, pipeline,
proposals queue, sources, admin, auth."""
import json
import markdown
import os
import threading
from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from ..auth import (COOKIE_NAME, get_user_or_none, hash_password, make_token,
                    new_api_key, require_admin, require_editor, require_user,
                    verify_password)
from ..db import (CONDITION_TIMING, OPPORTUNITY_FIELDS, TAG_NAMESPACES,
                  company_profile, get_config, get_db, json_field,
                  remember_tags, status_condition)
from ..discovery.evaluator import evaluate_opportunity, run_evaluations, stale_evaluations
from ..discovery.link_monitor import run_link_monitor
from ..discovery.scanner import run_scan
from ..discovery.verifier import verify_opportunity
from ..help import HELP
from ..help import get as get_help
from ..proposals import (EQUITY_INSTRUMENTS, EQUITY_PROVIDERS, approve,
                         compute_diff, default_dilutive, reject)
from ..version import commit_hash

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))
templates.env.globals["commit"] = commit_hash()
templates.env.filters["fromjson"] = json_field


def _money(value, blank: str = "?") -> str:
    """Amounts are stored as REAL, so a plain render shows 1500000.0."""
    if value is None or value == "":
        return blank
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


def _pct(value) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{float(value):g}%"
    except (TypeError, ValueError):
        return str(value)


templates.env.filters["money"] = _money
templates.env.filters["pct"] = _pct


def _help_button(key: str) -> Markup:
    """The `?` affordance. A Jinja global rather than a macro so it also works
    inside other macros. An unknown key renders nothing instead of breaking."""
    if key not in HELP:
        return Markup("")
    return Markup(
        f'<button type="button" class="help" aria-label="What is this?" '
        f'title="What is this?" hx-get="/help/{key}" hx-target="#help-modal">?</button>')


templates.env.globals["help"] = _help_button

DEADLINE_LABELS = {
    "open_until_funds_exhausted": "while funds last",
    "rolling": "rolling",
    "cutoffs": "cut-off dates",
    "unknown": "date unknown",
}


def _deadline_label(o) -> str:
    """A short label for the table cell. `deadline_text` is the call's own
    wording and can run to a paragraph — that belongs in the modal, not in a
    column. The date wins when there is one; otherwise the type says the useful
    thing, and only as a last resort do we show a clipped quotation."""
    if o.get("deadline_date"):
        return str(o["deadline_date"])
    kind = o.get("deadline_type")
    if kind in DEADLINE_LABELS:
        return DEADLINE_LABELS[kind]
    text = (o.get("deadline_text") or "").strip()
    if not text:
        return "—"
    return text if len(text) <= 42 else text[:42].rstrip() + "…"


templates.env.globals["deadline_label"] = _deadline_label

INSTRUMENTS = [
    "grant", "subsidized_loan", "tax_credit", "guarantee", "prize", "programme",
    "hiring_support", "voucher", "cascade_grant", "equity", "convertible", "in_kind",
]
PROVIDER_TYPES = [
    "public_supranational", "public_national", "public_regional", "foundation",
    "corporate", "vc", "angel", "accelerator", "bank", "other",
]
OPPORTUNITY_STATES = [
    "watching", "shortlisted", "preparing", "submitted", "pending_outcome",
    "won", "lost", "expired", "discarded",
]
APPLICATION_STATES = ["preparing", "submitted", "pending", "won", "lost", "withdrawn"]

CURRENCIES = ["EUR", "USD", "CHF", "GBP"]
SME_SIZES = ["micro", "small", "medium", "large"]
TRL_LEVELS = [str(n) for n in range(1, 10)]

# Multi-value fields hold a JSON array of flat tags, and a datalist cannot serve
# one: it completes the whole box, not the next item in it. So they get a real
# multi-select over a known vocabulary, plus a box for values the vocabulary has
# never seen. What is typed there is written back to `tag_vocabulary`, so the set
# stays open and grows by use instead of being retyped from memory every time.
# The field-to-namespace mapping lives in db.py: the forms are one writer, the
# approval of a proposal is the other, and they must agree.
TAG_FIELDS = TAG_NAMESPACES
# Closed multi-value sets: the code reads these, so nothing new may be invented
# in a text box. Sizes are the EU definition; qualification keys are whatever the
# company actually holds.
CLOSED_TAG_FIELDS = {"eligible_sme_sizes", "requires_qualification"}
MULTI_FIELDS = set(TAG_FIELDS) | CLOSED_TAG_FIELDS

# The config rows, offered as their value sets deserve. Anything not listed is a
# plain text box.
CONFIG_CHOICES = {
    # Deliberately a datalist and not a select: new models ship regularly, and
    # nothing in the code branches on the value — it is handed to the API as
    # written. A closed list would age into a cage.
    "scan_model": ("datalist", ["claude-opus-5", "claude-sonnet-5",
                                "claude-haiku-4-5", "claude-fable-5"]),
    # Closed, and read by code: CADENCE_DAYS knows exactly these three.
    "default_scan_cadence": ("select", ["weekly", "monthly", "quarterly"]),
    "max_scans_per_run": ("number", []),
    "base_currency": ("datalist", CURRENCIES),
}

# How each field is offered in the forms.
#   select   — a closed set the code branches on. Typing something else would
#              silently break a derived gate, so it is not offered.
#   datalist — an open set with common values: pick one or write your own.
#   bool     — yes / no / not recorded, stored as 1 / 0 / NULL.
#   date, number — the right input type, nothing more.
# Anything absent is a plain text box.
CHILD_CHOICES = {
    "locations": {
        "kind": ("datalist", ["registered_office", "operating_unit", "lab",
                              "production", "warehouse"]),
        "country": ("datalist", ["IT", "CH", "DE", "FR", "ES", "AT", "SI", "NL"]),
        "code_system": ("datalist", ["NUTS", "ISO-3166-2"]),
        "registered": ("bool", []),
        "active_from": ("date", []), "active_until": ("date", []),
    },
    "qualifications": {
        "key": ("datalist", ["it_startup_innovativa", "it_pmi_innovativa", "bcorp",
                             "iso_9001", "iso_14001", "eic_seal_of_excellence",
                             "women_led_certification"]),
        "jurisdiction": ("datalist", ["IT", "EU", "CH", "global"]),
        # company_profile() selects on status='active', so this one is closed.
        "status": ("select", ["active", "applied", "expired", "none"]),
        "valid_from": ("date", []), "valid_until": ("date", []),
        "confirmed_at": ("date", []),
        "renewal_every_months": ("number", []),
    },
    "team": {
        # The derived gates compare these exactly; a free-text "PhD" or "female"
        # would read as neither.
        "highest_degree": ("select", ["phd", "md", "msc", "bsc", "other"]),
        "gender": ("select", ["f", "m", "other", "not_recorded"]),
        "is_founder": ("bool", []), "is_shareholder": ("bool", []),
        "residence_country": ("datalist", ["IT", "CH", "DE", "FR", "ES"]),
        "birth_year": ("number", []), "shareholding_pct": ("number", []),
        "fte": ("number", []),
        "joined_at": ("date", []), "left_at": ("date", []),
    },
    "funding": {
        "instrument": ("datalist", ["equity", "convertible", "safe", "grant",
                                    "prize", "programme", "loan"]),
        "currency": ("datalist", CURRENCIES),
        "converted": ("bool", []),
        "closed_at": ("date", []),
        "amount": ("number", []), "dilution_pct": ("number", []),
    },
    "aid": {
        # The counter cross-check filters on these exact values.
        "regime": ("select", ["de_minimis", "de_minimis_agri", "block_exempted",
                              "notified", "market_terms", "unknown"]),
        "currency": ("datalist", CURRENCIES),
        "granted_at": ("date", []),
        "nominal_amount": ("number", []), "gge_amount": ("number", []),
    },
    "contacts": {
        "relationship": ("select", ["cold", "contacted", "met", "engaged", "passed"]),
        "opportunity_id": ("number", []),
    },
}

# Datalists that cannot be written down in advance, because they are made of what
# is already in the database. Built at render time, so a form opened after a row
# was added already offers that row's values.
DYNAMIC_CHILD_OPTIONS = {
    "locations": {
        "region": lambda: _distinct("region", "company_locations"),
        "region_code": lambda: _distinct("region_code", "company_locations"),
        "city": lambda: _distinct("city", "company_locations"),
    },
    "qualifications": {
        "label": lambda: _distinct("label", "company_qualifications"),
    },
    "team": {
        "role": lambda: _distinct("role", "team_members",
                                  ["CEO", "CTO", "COO", "advisor", "employee"]),
        # Nobody has a region recorded on a fresh instance, so fall back to the
        # regions the company itself sits in: that is where people usually live.
        "residence_region": lambda: _distinct(
            "residence_region", "team_members", _distinct("region", "company_locations")),
    },
    "funding": {
        "investor": lambda: _distinct("investor", "company_funding"),
    },
    "aid": {
        "provider": lambda: _distinct("provider", "company_aid"),
        "entity": lambda: _distinct("entity", "company_aid"),
    },
    "contacts": {
        "organisation": lambda: _distinct("organisation", "contacts"),
        "role": lambda: _distinct("role", "contacts",
                                  ["programme officer", "partner", "analyst",
                                   "principal", "grant office"]),
        # Who could introduce you is, almost always, someone already recorded.
        "warm_intro_via": lambda: _distinct("name", "contacts"),
    },
}


def _child_choices(child: str) -> dict:
    """The static widget spec, plus the datalists built from existing rows."""
    choices = dict(CHILD_CHOICES.get(child, {}))
    for name, build in DYNAMIC_CHILD_OPTIONS.get(child, {}).items():
        options = build()
        if options:
            choices[name] = ("datalist", options)
    return choices


def _opportunity_options() -> dict:
    """Datalists for the single-value text fields of the opportunity form."""
    return {
        "provider": _distinct("provider", "opportunities"),
        # Where a unit is required: the codes the company already uses, plus the
        # two coarse ones, plus whatever other calls have asked for.
        "requires_unit_in": _distinct(
            "requires_unit_in", "opportunities",
            _distinct("region_code", "company_locations", ["IT", "EU"])),
        "sector_focus": _distinct("sector_focus", "opportunities"),
        "geo_focus": _distinct("geo_focus", "opportunities"),
        "recurrence_logic": _distinct(
            "recurrence_logic", "opportunities",
            ["annual", "twice a year", "reopened when refinanced", "one-off"]),
    }


def _next_actions() -> list[str]:
    return _distinct("next_action", "applications",
                     ["draft the application", "collect quotes", "ask the office",
                      "submit", "follow up", "send the report"])


# Simple child tables of the profile, handled by one generic pair of routes.
# The whitelist is what keeps the dynamic SQL safe.
CHILD_TABLES = {
    "locations": ("company_locations", [
        "kind", "city", "country", "region", "region_code", "code_system",
        "registered", "active_from", "active_until", "notes"]),
    "qualifications": ("company_qualifications", [
        "key", "label", "jurisdiction", "status", "valid_from", "valid_until",
        "confirmed_at", "renewal_every_months", "evidence", "notes"]),
    "team": ("team_members", [
        "name", "role", "is_founder", "is_shareholder", "shareholding_pct",
        "gender", "birth_year", "residence_country", "residence_region",
        "highest_degree", "joined_at", "left_at", "fte", "notes"]),
    "funding": ("company_funding", [
        "instrument", "amount", "currency", "investor", "closed_at",
        "dilution_pct", "converted", "notes"]),
    "aid": ("company_aid", [
        "name", "provider", "entity", "regime", "nominal_amount", "gge_amount",
        "currency", "granted_at", "notes"]),
    "contacts": ("contacts", [
        "name", "organisation", "role", "email", "linkedin", "opportunity_id",
        "warm_intro_via", "relationship", "notes"]),
}


def _render(request: Request, name: str, **ctx) -> HTMLResponse:
    ctx.setdefault("user", get_user_or_none(request))
    with get_db() as db:
        ctx.setdefault("pending_count", db.execute(
            "SELECT COUNT(*) AS n FROM proposals WHERE status='pending'").fetchone()["n"])
        # The display name is what the header shows; the legal name is the
        # fallback, so a fresh instance is never nameless and nobody has to fill
        # in a config row to get a sensible header.
        legal = db.execute(
            "SELECT legal_name FROM company WHERE id=1").fetchone()["legal_name"] or ""
    ctx.setdefault("company_name", get_config("company_display_name") or legal)
    return templates.TemplateResponse(request, name, ctx)


def _form_values(form, fields: list[str]) -> dict:
    """Empty strings become NULL; checkboxes arrive only when ticked."""
    out = {}
    for f in fields:
        if f in MULTI_FIELDS:
            out[f] = _multi_value(form, f)
            continue
        raw = form.get(f)
        out[f] = None if raw in (None, "") else raw
    return out


def _multi_value(form, field: str) -> str | None:
    """A multi-select plus its 'add' box, back into one JSON array. Order is
    preserved and duplicates dropped, so ticking a tag that was also typed does
    not store it twice."""
    picked = [v.strip() for v in form.getlist(field) if v and v.strip()]
    typed = [t.strip() for t in (form.get(field + "__new") or "")
             .replace(";", ",").split(",") if t.strip()]
    if typed and field in TAG_FIELDS:
        _remember_tags(TAG_FIELDS[field], typed)
    values = list(dict.fromkeys(picked + typed))
    return json.dumps(values, ensure_ascii=False) if values else None


def _remember_tags(namespace: str, values: list[str]) -> None:
    """A tag typed once is in the vocabulary from then on. Without this the
    'add' box would be a synonym generator: soil_health today, soil health
    tomorrow, and two tags that mean one thing."""
    with get_db() as db:
        remember_tags(db, namespace, values)


def _vocabulary(namespace: str, used=()) -> list[str]:
    with get_db() as db:
        known = [r["value"] for r in db.execute(
            "SELECT value FROM tag_vocabulary WHERE namespace=? "
            "AND COALESCE(active, 1) = 1 ORDER BY value", (namespace,))]
    return list(dict.fromkeys(known + [u for u in used if u]))


def _distinct(column: str, table: str, extra=()) -> list[str]:
    """Datalist options drawn from what is already recorded. A provider typed
    once should cost one keystroke the second time — and, more to the point,
    come out spelled the same way, because these columns get filtered on."""
    with get_db() as db:
        seen = [r[0] for r in db.execute(
            f"SELECT DISTINCT {column} FROM {table} "
            f"WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}")]
    return list(dict.fromkeys(list(extra) + seen))


def _tag_options(record: dict) -> dict:
    """Options for every multi-value field on a form: the vocabulary, plus what
    this record already carries. Without that second half, a tag written before
    the vocabulary knew about it would quietly disappear from the widget — and
    then from the record, the first time someone pressed Save."""
    options = {field: _vocabulary(ns, json_field(record.get(field)))
               for field, ns in TAG_FIELDS.items()}
    options["eligible_sme_sizes"] = list(dict.fromkeys(
        SME_SIZES + json_field(record.get("eligible_sme_sizes"))))
    options["requires_qualification"] = list(dict.fromkeys(
        _distinct("key", "company_qualifications")
        + json_field(record.get("requires_qualification"))))
    return options


# --- the guide --------------------------------------------------------------

GUIDE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "guide.md")
_guide_cache: dict = {}


def _guide() -> tuple[str, str]:
    """The guide, rendered from its markdown source, with a table of contents.

    Markdown is the source of truth because it reviews well in a diff — the
    guide changes with the tool, and a paragraph that quietly stopped being true
    should be visible in a commit. Cached on the file's modification time, so an
    edit shows up without a restart but the parse does not run per request.
    """
    stamp = os.path.getmtime(GUIDE_PATH)
    if _guide_cache.get("stamp") != stamp:
        with open(GUIDE_PATH, encoding="utf-8") as fh:
            text = fh.read()
        # toc_depth skips the h1: the page already carries the title, and a
        # table of contents whose first entry is the document itself is noise.
        md = markdown.Markdown(extensions=["tables", "toc", "attr_list"],
                               extension_configs={"toc": {"toc_depth": "2-3"}})
        _guide_cache.update(stamp=stamp, html=md.convert(text), toc=md.toc)
    return _guide_cache["html"], _guide_cache["toc"]


@router.get("/guide", response_class=HTMLResponse)
def guide_page(request: Request, user=Depends(require_user)):
    html, toc = _guide()
    return _render(request, "guide.html", guide=Markup(html), toc=Markup(toc))


# --- landing & auth ---------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return _render(request, "landing.html")


@router.get("/help/{key}", response_class=HTMLResponse)
def help_modal(request: Request, key: str, user=Depends(require_user)):
    entry = get_help(key)
    if not entry:
        return HTMLResponse("")
    title, body = entry
    return templates.TemplateResponse(request, "_help_modal.html",
                                      {"title": title, "body": body})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request, "login.html", {"error": None, "user": None, "pending_count": 0})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "Invalid credentials", "user": None, "pending_count": 0},
            status_code=401)
    token = make_token(row["id"], row["username"], row["role"])
    resp = RedirectResponse("/opportunities", status_code=303)
    resp.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=3600 * 24 * 30)
    return resp


@router.get("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp


# --- opportunities ----------------------------------------------------------

OPPORTUNITY_VIEWS = ["all", "calls", "investors"]


def _view_condition(view: str, p: str = "o.") -> str:
    """Calls and Investors are two readings of one table, and `all` is the table
    itself. Investors have no deadline to sort by, only a next action."""
    if view == "investors":
        return (f" AND ({p}instrument IN {EQUITY_INSTRUMENTS} "
                f"OR {p}provider_type IN {EQUITY_PROVIDERS})")
    if view == "calls":
        return (f" AND {p}instrument NOT IN {EQUITY_INSTRUMENTS} "
                f"AND ({p}provider_type IS NULL OR {p}provider_type NOT IN {EQUITY_PROVIDERS})")
    return ""


def _is_investor(o) -> bool:
    """The same rule as the SQL above, per row — the combined view needs it to
    decide whether a row is showing a ticket or an amount."""
    return (o.get("instrument") in EQUITY_INSTRUMENTS
            or o.get("provider_type") in EQUITY_PROVIDERS)


templates.env.globals["is_investor"] = _is_investor


def _query_opportunities(view, q, instrument, provider_type, source, status):
    sql = (
        "SELECT o.*, s.name AS source_name, p.name AS product_name, "
        "a.next_action, a.next_action_due, a.status AS application_status "
        "FROM opportunities o "
        "LEFT JOIN sources s ON s.id = o.source_id "
        "LEFT JOIN products p ON p.id = o.best_fit_product_id "
        "LEFT JOIN applications a ON a.opportunity_id = o.id "
        "WHERE 1=1"
    )
    args: list = []
    sql += _view_condition(view)
    if q:
        sql += " AND (o.title LIKE ? OR o.provider LIKE ? OR o.description LIKE ?)"
        args += [f"%{q}%"] * 3
    if instrument:
        sql += " AND o.instrument = ?"
        args.append(instrument)
    if provider_type:
        sql += " AND o.provider_type = ?"
        args.append(provider_type)
    if source == "__none__":
        sql += " AND o.source_id IS NULL"
    elif source:
        sql += " AND o.source_id = ?"
        args.append(int(source))
    cond, cond_args = status_condition(status, prefix="o.")
    sql += cond
    args += cond_args
    # Each view sorts by the clock it actually has. Combined, the honest reading
    # is "whatever happens next": a deadline for a call, a next action for an
    # investor, and rows with neither at the bottom.
    if view == "investors":
        sql += " ORDER BY a.next_action_due IS NULL, a.next_action_due"
    elif view == "calls":
        sql += " ORDER BY o.deadline_date IS NULL, o.deadline_date"
    else:
        sql += (" ORDER BY COALESCE(o.deadline_date, a.next_action_due) IS NULL, "
                "COALESCE(o.deadline_date, a.next_action_due)")
    # The dropdowns list only what exists *in this view*: offering "equity" as a
    # filter under Calls would just be a way to get an empty table.
    scope = _view_condition(view, p="")
    with get_db() as db:
        rows = [dict(r) for r in db.execute(sql, args).fetchall()]
        instruments = [r["instrument"] for r in db.execute(
            "SELECT DISTINCT instrument FROM opportunities "
            "WHERE instrument IS NOT NULL AND instrument != ''" + scope + " ORDER BY instrument")]
        providers = [r["provider_type"] for r in db.execute(
            "SELECT DISTINCT provider_type FROM opportunities "
            "WHERE provider_type IS NOT NULL AND provider_type != ''" + scope
            + " ORDER BY provider_type")]
        sources = [dict(r) for r in db.execute("SELECT id, name FROM sources ORDER BY name")]
    return rows, instruments, providers, sources


def _opportunities_page(request: Request, view: str, q: str, instrument: str,
                        provider_type: str, source: str, status: str):
    rows, instruments, providers, sources = _query_opportunities(
        view, q, instrument, provider_type, source, status)
    ctx = {"opportunities": rows, "instruments": instruments, "providers": providers,
           "sources": sources, "view": view, "q": q, "f_instrument": instrument,
           "f_provider": provider_type, "f_source": source, "f_status": status,
           "today": date.today().isoformat()}
    if request.headers.get("HX-Request"):
        return _render(request, "_opportunities_table.html", **ctx)
    ctx["stale_count"] = len(stale_evaluations())
    ctx["started"] = request.query_params.get("started")
    return _render(request, "opportunities.html", **ctx)


@router.get("/opportunities", response_class=HTMLResponse)
def opportunities_page(request: Request, view: str = "all", q: str = "", instrument: str = "",
                       provider_type: str = "", source: str = "", status: str = "open",
                       user=Depends(require_user)):
    """One table. Calls and Investors are a filter on it, not two pages: the
    distinction is real — one has deadlines, the other has next actions — but it
    is a property of the rows, and splitting the navigation on it meant every
    look at the funding picture was half a look."""
    if view not in OPPORTUNITY_VIEWS:
        view = "all"
    return _opportunities_page(request, view, q, instrument, provider_type, source, status)


# The old addresses stay, as redirects: they are in bookmarks, in the wiki, and
# in half a session's worth of links.
@router.get("/calls")
def calls_page(request: Request):
    return RedirectResponse(f"/opportunities?view=calls&{request.url.query}", status_code=307)


@router.get("/investors")
def investors_page(request: Request):
    return RedirectResponse(f"/opportunities?view=investors&{request.url.query}",
                            status_code=307)


def _all_sources() -> list[dict]:
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT id, name FROM sources ORDER BY name")]


def _all_products() -> list[dict]:
    with get_db() as db:
        return [dict(r) for r in db.execute(
            "SELECT id, name, trl FROM products WHERE active=1 ORDER BY name")]


def _form_int(form, key) -> int | None:
    raw = (form.get(key) or "").strip()
    return int(raw) if raw.isdigit() else None


@router.get("/opportunities/new", response_class=HTMLResponse)
def opportunity_new(request: Request, view: str = "calls", user=Depends(require_editor)):
    return _render(request, "opportunity_form.html", o={}, view=view,
                   action="/opportunities/new", instruments=INSTRUMENTS,
                   provider_types=PROVIDER_TYPES, states=OPPORTUNITY_STATES,
                   sources=_all_sources(), products=_all_products(),
                   condition_timing=CONDITION_TIMING, trl_levels=TRL_LEVELS,
                   opts=_opportunity_options(), tag_options=_tag_options({}))


@router.post("/opportunities/new")
async def opportunity_create(request: Request, user=Depends(require_editor)):
    form = await request.form()
    fields = _form_values(form, OPPORTUNITY_FIELDS)
    if not fields.get("title"):
        raise HTTPException(status_code=422, detail="Title is required")
    if fields.get("dilutive") is None:
        fields["dilutive"] = default_dilutive(fields.get("instrument"))
    cols = list(fields) + ["source_id", "status"]
    vals = list(fields.values()) + [_form_int(form, "source_id"),
                                    form.get("status") or "watching"]
    with get_db() as db:
        db.execute(
            f"INSERT INTO opportunities ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(vals))})", vals)
    return RedirectResponse(f"/opportunities?view={form.get('view') or 'all'}", status_code=303)


@router.get("/opportunities/{opportunity_id}/detail", response_class=HTMLResponse)
def opportunity_detail(request: Request, opportunity_id: int, user=Depends(require_user)):
    with get_db() as db:
        row = db.execute(
            "SELECT o.*, s.name AS source_name, p.name AS product_name "
            "FROM opportunities o LEFT JOIN sources s ON s.id = o.source_id "
            "LEFT JOIN products p ON p.id = o.best_fit_product_id WHERE o.id=?",
            (opportunity_id,)).fetchone()
        if not row:
            return HTMLResponse("")
        caps = [dict(r) for r in db.execute(
            "SELECT c.*, f.label AS counter_label, f.ceiling, f.used_amount "
            "FROM opportunity_caps c LEFT JOIN funding_counters f ON f.key = c.counter_key "
            "WHERE c.opportunity_id=?", (opportunity_id,))]
        commitments = [dict(r) for r in db.execute(
            "SELECT * FROM opportunity_commitments WHERE opportunity_id=? ORDER BY id",
            (opportunity_id,))]
        fits = [dict(r) for r in db.execute(
            "SELECT f.*, p.name AS product_name, p.trl FROM opportunity_product_fit f "
            "LEFT JOIN products p ON p.id = f.product_id WHERE f.opportunity_id=?",
            (opportunity_id,))]
        apps = [dict(r) for r in db.execute(
            f"SELECT a.*, {PRODUCTS_SQL} AS product_names FROM applications a "
            "WHERE a.opportunity_id=?", (opportunity_id,))]
        acts = [dict(r) for r in db.execute(
            "SELECT * FROM activities WHERE opportunity_id=? ORDER BY happened_at DESC LIMIT 20",
            (opportunity_id,))]
        contacts = [dict(r) for r in db.execute(
            "SELECT * FROM contacts WHERE opportunity_id=?", (opportunity_id,))]
    return templates.TemplateResponse(
        request, "_opportunity_modal.html",
        {"o": dict(row), "caps": caps, "commitments": commitments,
         "fits": fits, "applications": apps,
         "activities": acts, "contacts": contacts, "user": user,
         "today": date.today().isoformat()})


@router.get("/opportunities/{opportunity_id}/edit", response_class=HTMLResponse)
def opportunity_edit(request: Request, opportunity_id: int, view: str = "calls",
                     user=Depends(require_editor)):
    with get_db() as db:
        row = db.execute("SELECT * FROM opportunities WHERE id=?", (opportunity_id,)).fetchone()
    if not row:
        return RedirectResponse("/opportunities", status_code=303)
    opportunity = dict(row)
    return _render(request, "opportunity_form.html", o=opportunity, view=view,
                   action=f"/opportunities/{opportunity_id}/edit", instruments=INSTRUMENTS,
                   provider_types=PROVIDER_TYPES, states=OPPORTUNITY_STATES,
                   sources=_all_sources(), products=_all_products(),
                   condition_timing=CONDITION_TIMING, trl_levels=TRL_LEVELS,
                   opts=_opportunity_options(), tag_options=_tag_options(opportunity))


@router.post("/opportunities/{opportunity_id}/edit")
async def opportunity_update(request: Request, opportunity_id: int,
                             user=Depends(require_editor)):
    form = await request.form()
    fields = _form_values(form, OPPORTUNITY_FIELDS)
    sets = ", ".join(f"{k}=?" for k in fields)
    with get_db() as db:
        db.execute(
            f"UPDATE opportunities SET {sets}, source_id=?, status=?, priority=?, "
            f"effort=?, best_fit_product_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            list(fields.values()) + [
                _form_int(form, "source_id"), form.get("status") or "watching",
                form.get("priority") or None, form.get("effort") or None,
                _form_int(form, "best_fit_product_id"), opportunity_id])
    return RedirectResponse(f"/opportunities?view={form.get('view') or 'all'}", status_code=303)


# --- discovery, on demand -----------------------------------------------------
# Every one of these can take a minute or more, so they run on a thread and the
# page comes straight back. Results land in the queue, the scan log, or the
# record itself, and the next page load shows them.

def _background(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True).start()


@router.post("/opportunities/{opportunity_id}/check")
def opportunity_check(opportunity_id: int, view: str = Form("calls"),
                      user=Depends(require_editor)):
    """Verifier: does the stored record still match the page?"""
    _background(verify_opportunity, opportunity_id)
    return RedirectResponse(f"/opportunities?view={view}&started=check", status_code=303)


@router.post("/opportunities/{opportunity_id}/evaluate")
def opportunity_evaluate(opportunity_id: int, view: str = Form("calls"),
                         user=Depends(require_editor)):
    """Evaluator: eligibility, caps and fit against the current profile."""
    _background(evaluate_opportunity, opportunity_id)
    return RedirectResponse(f"/opportunities?view={view}&started=evaluate", status_code=303)


@router.post("/evaluate-stale")
def evaluate_stale(user=Depends(require_editor)):
    _background(run_evaluations, True)
    return RedirectResponse("/calls?started=evaluate", status_code=303)


@router.post("/scan-now")
def scan_now(source_id: int | None = Form(None), user=Depends(require_editor)):
    _background(run_scan, source_id)
    return RedirectResponse("/sources?started=scan", status_code=303)


@router.post("/check-links-now")
def check_links_now(user=Depends(require_editor)):
    _background(run_link_monitor)
    return RedirectResponse("/sources?started=links", status_code=303)


@router.post("/opportunities/{opportunity_id}/delete")
def opportunity_delete(opportunity_id: int, view: str = Form("calls"),
                       user=Depends(require_admin)):
    with get_db() as db:
        db.execute("DELETE FROM proposals WHERE opportunity_id=?", (opportunity_id,))
        db.execute("DELETE FROM opportunities WHERE id=?", (opportunity_id,))
    return RedirectResponse(f"/opportunities?view={view}", status_code=303)


# --- company profile --------------------------------------------------------

COMPANY_FIELDS = [
    "legal_name", "legal_form", "country", "vat_number", "registry_id",
    "industry_codes", "incorporation_date", "sme_size", "sme_size_definition",
    "headcount", "fte", "last_turnover", "total_assets", "currency",
    "revenue_stage", "funding_stage", "runway_months", "impact_tags",
]


@router.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request, user=Depends(require_user)):
    profile = company_profile()
    with get_db() as db:
        profile["all_locations"] = [dict(r) for r in db.execute(
            "SELECT * FROM company_locations ORDER BY kind")]
        profile["all_qualifications"] = [dict(r) for r in db.execute(
            "SELECT * FROM company_qualifications ORDER BY key")]
        profile["all_team"] = [dict(r) for r in db.execute(
            "SELECT * FROM team_members ORDER BY left_at IS NOT NULL, name")]
        profile["all_funding"] = [dict(r) for r in db.execute(
            "SELECT * FROM company_funding ORDER BY closed_at DESC")]
        profile["all_aid"] = [dict(r) for r in db.execute(
            "SELECT * FROM company_aid ORDER BY granted_at DESC")]
    meta = {slug: {"fields": fields, "choices": _child_choices(slug)}
            for slug, (_, fields) in CHILD_TABLES.items()}
    return _render(request, "profile.html", p=profile, child_meta=meta)


@router.get("/profile/edit", response_class=HTMLResponse)
def company_edit(request: Request, user=Depends(require_editor)):
    with get_db() as db:
        row = db.execute("SELECT * FROM company WHERE id=1").fetchone()
    company = dict(row) if row else {}
    return _render(request, "company_form.html", c=company,
                   fields=COMPANY_FIELDS, tag_options=_tag_options(company))


@router.post("/profile/edit")
async def company_update(request: Request, user=Depends(require_editor)):
    form = await request.form()
    fields = _form_values(form, COMPANY_FIELDS)
    sets = ", ".join(f"{k}=?" for k in fields)
    with get_db() as db:
        db.execute(f"UPDATE company SET {sets}, "
                   f"updated_at=strftime('%Y-%m-%d %H:%M:%f','now') WHERE id=1",
                   list(fields.values()))
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/narrative")
async def narrative_update(request: Request, user=Depends(require_editor)):
    form = await request.form()
    section, content = form.get("section"), form.get("content") or ""
    with get_db() as db:
        if not db.execute("SELECT 1 FROM company_narrative WHERE section=?",
                          (section,)).fetchone():
            raise HTTPException(status_code=404, detail="Unknown section")
        db.execute("UPDATE company_narrative SET content=?, updated_at=CURRENT_TIMESTAMP "
                   "WHERE section=?", (content, section))
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/counters/{key}")
async def counter_update(request: Request, key: str, user=Depends(require_editor)):
    form = await request.form()
    with get_db() as db:
        cur = db.execute(
            "UPDATE funding_counters SET used_amount=?, ceiling=?, checked_at=?, "
            "source_note=? WHERE key=?",
            (form.get("used_amount") or 0, form.get("ceiling") or None,
             form.get("checked_at") or None, form.get("source_note") or None, key))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Unknown counter")
    return RedirectResponse("/profile", status_code=303)


@router.post("/profile/{child}/new")
async def child_create(request: Request, child: str, user=Depends(require_editor)):
    if child not in CHILD_TABLES:
        raise HTTPException(status_code=404, detail="Unknown section")
    table, fields = CHILD_TABLES[child]
    form = await request.form()
    values = _form_values(form, fields)
    with get_db() as db:
        db.execute(
            f"INSERT INTO {table} ({', '.join(values)}) "
            f"VALUES ({', '.join('?' * len(values))})", list(values.values()))
    return RedirectResponse(form.get("back") or "/profile", status_code=303)


@router.get("/profile/{child}/{row_id}/edit", response_class=HTMLResponse)
def child_edit(request: Request, child: str, row_id: int, user=Depends(require_editor)):
    """Generic edit form for a profile child row, in the shared modal. Without
    it, correcting a typo or filling in an aid regime would mean deleting the
    row and losing its notes."""
    if child not in CHILD_TABLES:
        raise HTTPException(status_code=404, detail="Unknown section")
    table, fields = CHILD_TABLES[child]
    with get_db() as db:
        row = db.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()
    if not row:
        return HTMLResponse("")
    return templates.TemplateResponse(request, "_child_form_modal.html", {
        "child": child, "row": dict(row), "fields": fields,
        "choices": _child_choices(child),
        "title": child.replace("_", " ").title()})


@router.post("/profile/{child}/{row_id}/edit")
async def child_update(request: Request, child: str, row_id: int,
                       user=Depends(require_editor)):
    if child not in CHILD_TABLES:
        raise HTTPException(status_code=404, detail="Unknown section")
    table, fields = CHILD_TABLES[child]
    form = await request.form()
    values = _form_values(form, fields)
    sets = ", ".join(f"{k}=?" for k in values)
    with get_db() as db:
        db.execute(f"UPDATE {table} SET {sets} WHERE id=?",
                   list(values.values()) + [row_id])
    return RedirectResponse(form.get("back") or "/profile", status_code=303)


@router.post("/profile/{child}/{row_id}/delete")
async def child_delete(request: Request, child: str, row_id: int,
                       user=Depends(require_editor)):
    if child not in CHILD_TABLES:
        raise HTTPException(status_code=404, detail="Unknown section")
    table, _ = CHILD_TABLES[child]
    form = await request.form()
    with get_db() as db:
        db.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
    return RedirectResponse(form.get("back") or "/profile", status_code=303)


# --- products ---------------------------------------------------------------

PRODUCT_FIELDS = [
    "name", "description", "status", "trl", "trl_updated_at", "trl_evidence",
    "target_segments", "target_markets", "impact_tags", "ip_status", "ip_refs",
    "regulatory_framework", "regulatory_status", "unit_economics", "notes",
]
PRODUCT_STATES = ["research", "prototype", "field_trials", "pilot",
                  "pre_commercial", "commercial", "discontinued"]


@router.get("/products", response_class=HTMLResponse)
def products_page(request: Request, user=Depends(require_user)):
    with get_db() as db:
        rows = [dict(r) for r in db.execute("SELECT * FROM products ORDER BY active DESC, name")]
    return _render(request, "products.html", products=rows)


@router.get("/products/new", response_class=HTMLResponse)
def product_new(request: Request, user=Depends(require_editor)):
    return _render(request, "product_form.html", p={}, action="/products/new",
                   states=PRODUCT_STATES, tag_options=_tag_options({}))


@router.post("/products/new")
async def product_create(request: Request, user=Depends(require_editor)):
    form = await request.form()
    values = _form_values(form, PRODUCT_FIELDS)
    with get_db() as db:
        db.execute(f"INSERT INTO products ({', '.join(values)}) "
                   f"VALUES ({', '.join('?' * len(values))})", list(values.values()))
    return RedirectResponse("/products", status_code=303)


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
def product_edit(request: Request, product_id: int, user=Depends(require_editor)):
    with get_db() as db:
        row = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not row:
        return RedirectResponse("/products", status_code=303)
    product = dict(row)
    return _render(request, "product_form.html", p=product,
                   action=f"/products/{product_id}/edit", states=PRODUCT_STATES,
                   tag_options=_tag_options(product))


@router.post("/products/{product_id}/edit")
async def product_update(request: Request, product_id: int, user=Depends(require_editor)):
    form = await request.form()
    values = _form_values(form, PRODUCT_FIELDS)
    sets = ", ".join(f"{k}=?" for k in values)
    with get_db() as db:
        db.execute(f"UPDATE products SET {sets}, active=? WHERE id=?",
                   list(values.values()) + [1 if form.get("active") else 0, product_id])
    return RedirectResponse("/products", status_code=303)


@router.post("/products/{product_id}/delete")
def product_delete(product_id: int, user=Depends(require_admin)):
    with get_db() as db:
        db.execute("DELETE FROM products WHERE id=?", (product_id,))
    return RedirectResponse("/products", status_code=303)


# --- pipeline ---------------------------------------------------------------

APPLICATION_FIELDS = [
    "opportunity_id", "status", "amount_requested", "amount_awarded",
    "currency", "submitted_at", "outcome_at", "next_action", "next_action_due", "notes",
]

# An application covers zero, one or several product lines. Zero plus the
# general flag means the request is about the company, not a line.
PRODUCTS_SQL = (
    "(SELECT GROUP_CONCAT(p.name, ', ') FROM application_products ap "
    " JOIN products p ON p.id = ap.product_id WHERE ap.application_id = a.id)"
)


def _set_application_products(db, application_id: int, product_ids: list[str]) -> None:
    db.execute("DELETE FROM application_products WHERE application_id=?", (application_id,))
    for raw in product_ids:
        if str(raw).isdigit():
            db.execute("INSERT OR IGNORE INTO application_products "
                       "(application_id, product_id) VALUES (?, ?)",
                       (application_id, int(raw)))


@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(request: Request, status: str = "", user=Depends(require_user)):
    sql = (f"SELECT a.*, o.title, o.provider, o.instrument, o.deadline_date, "
           f"{PRODUCTS_SQL} AS product_names, u.username AS owner "
           "FROM applications a LEFT JOIN opportunities o ON o.id = a.opportunity_id "
           "LEFT JOIN users u ON u.id = a.owner_user_id")
    args: list = []
    if status:
        sql += " WHERE a.status=?"
        args.append(status)
    sql += " ORDER BY a.next_action_due IS NULL, a.next_action_due"
    with get_db() as db:
        rows = [dict(r) for r in db.execute(sql, args).fetchall()]
        opportunities = [dict(r) for r in db.execute(
            "SELECT id, title FROM opportunities ORDER BY title")]
        activities = [dict(r) for r in db.execute(
            "SELECT a.*, o.title FROM activities a "
            "LEFT JOIN opportunities o ON o.id = a.opportunity_id "
            "ORDER BY a.happened_at DESC LIMIT 30")]
        contacts = [dict(r) for r in db.execute(
            "SELECT c.*, o.title AS opportunity_title FROM contacts c "
            "LEFT JOIN opportunities o ON o.id = c.opportunity_id "
            "ORDER BY c.organisation, c.name")]
    return _render(request, "pipeline.html", applications=rows, f_status=status,
                   opportunities=opportunities, products=_all_products(),
                   activities=activities, contacts=contacts,
                   states=APPLICATION_STATES, today=date.today().isoformat(),
                   next_actions=_next_actions(),
                   contact_choices=_child_choices("contacts"),
                   contact_names=_distinct("name", "contacts"))


@router.post("/pipeline/new")
async def application_create(request: Request, user=Depends(require_editor)):
    form = await request.form()
    values = _form_values(form, APPLICATION_FIELDS)
    if not values.get("opportunity_id"):
        raise HTTPException(status_code=422, detail="An opportunity is required")
    values["owner_user_id"] = int(user["sub"])
    values["is_general"] = 1 if form.get("is_general") else 0
    with get_db() as db:
        cur = db.execute(f"INSERT INTO applications ({', '.join(values)}) "
                         f"VALUES ({', '.join('?' * len(values))})", list(values.values()))
        _set_application_products(db, cur.lastrowid, form.getlist("product_ids"))
    return RedirectResponse("/pipeline", status_code=303)


@router.get("/pipeline/{application_id}/edit", response_class=HTMLResponse)
def application_edit(request: Request, application_id: int, user=Depends(require_editor)):
    with get_db() as db:
        row = db.execute("SELECT * FROM applications WHERE id=?", (application_id,)).fetchone()
        if not row:
            return HTMLResponse("")
        selected = [r["product_id"] for r in db.execute(
            "SELECT product_id FROM application_products WHERE application_id=?",
            (application_id,))]
        opportunities = [dict(r) for r in db.execute(
            "SELECT id, title FROM opportunities ORDER BY title")]
    return templates.TemplateResponse(request, "_application_modal.html", {
        "a": dict(row), "selected": selected, "opportunities": opportunities,
        "products": _all_products(), "states": APPLICATION_STATES,
        "next_actions": _next_actions()})


@router.post("/pipeline/{application_id}/edit")
async def application_update(request: Request, application_id: int,
                             user=Depends(require_editor)):
    form = await request.form()
    values = _form_values(form, APPLICATION_FIELDS)
    values["is_general"] = 1 if form.get("is_general") else 0
    sets = ", ".join(f"{k}=?" for k in values)
    with get_db() as db:
        db.execute(f"UPDATE applications SET {sets} WHERE id=?",
                   list(values.values()) + [application_id])
        _set_application_products(db, application_id, form.getlist("product_ids"))
    return RedirectResponse("/pipeline", status_code=303)


@router.post("/pipeline/{application_id}/status")
def application_set_status(application_id: int, status: str = Form(...),
                           user=Depends(require_editor)):
    """The inline dropdown in the table. Its own endpoint so that changing a
    status cannot quietly blank the fields it does not carry."""
    if status not in APPLICATION_STATES:
        raise HTTPException(status_code=422, detail="Unknown status")
    with get_db() as db:
        db.execute("UPDATE applications SET status=? WHERE id=?", (status, application_id))
    return RedirectResponse("/pipeline", status_code=303)


@router.post("/pipeline/{application_id}/delete")
def application_delete(application_id: int, user=Depends(require_editor)):
    with get_db() as db:
        db.execute("DELETE FROM applications WHERE id=?", (application_id,))
    return RedirectResponse("/pipeline", status_code=303)


@router.post("/activities/new")
async def activity_create(request: Request, user=Depends(require_editor)):
    form = await request.form()
    with get_db() as db:
        db.execute(
            "INSERT INTO activities (opportunity_id, kind, happened_at, contact_name, "
            "summary, created_by) VALUES (?, ?, COALESCE(NULLIF(?, ''), date('now')), ?, ?, ?)",
            (_form_int(form, "opportunity_id"), form.get("kind"),
             form.get("happened_at") or "", form.get("contact_name") or None,
             form.get("summary") or "", int(user["sub"])))
    return RedirectResponse(form.get("back") or "/pipeline", status_code=303)


# --- proposals --------------------------------------------------------------

@router.get("/proposals", response_class=HTMLResponse)
def proposals_page(request: Request, status: str = "pending", user=Depends(require_user)):
    with get_db() as db:
        rows = db.execute(
            "SELECT p.*, o.title AS opportunity_title FROM proposals p "
            "LEFT JOIN opportunities o ON o.id = p.opportunity_id "
            "WHERE p.status=? ORDER BY p.created_at DESC", (status,)).fetchall()
    items = []
    for r in rows:
        p = dict(r)
        p["diff"] = compute_diff(p)
        items.append(p)
    return _render(request, "proposals.html", proposals=items, f_status=status)


@router.post("/proposals/{proposal_id}/approve")
def proposal_approve(proposal_id: int, user=Depends(require_editor)):
    approve(proposal_id)
    return RedirectResponse("/proposals", status_code=303)


@router.post("/proposals/{proposal_id}/reject")
def proposal_reject(proposal_id: int, user=Depends(require_editor)):
    reject(proposal_id)
    return RedirectResponse("/proposals", status_code=303)


# --- sources ----------------------------------------------------------------

SOURCE_FIELDS = ["name", "url", "hints", "geo_hint", "instrument_hint", "scan_cadence"]


@router.get("/sources", response_class=HTMLResponse)
def sources_page(request: Request, user=Depends(require_user)):
    with get_db() as db:
        sources = [dict(r) for r in db.execute("SELECT * FROM sources ORDER BY name")]
        log = [dict(r) for r in db.execute(
            "SELECT l.*, s.name AS source_name FROM scan_log l "
            "LEFT JOIN sources s ON s.id = l.source_id "
            "ORDER BY l.started_at DESC LIMIT 20")]
    return _render(request, "sources.html", sources=sources, scan_log=log)


@router.post("/sources/new")
async def source_create(request: Request, user=Depends(require_editor)):
    form = await request.form()
    values = _form_values(form, SOURCE_FIELDS)
    if not values.get("name"):
        raise HTTPException(status_code=422, detail="Name is required")
    with get_db() as db:
        db.execute(f"INSERT INTO sources ({', '.join(values)}) "
                   f"VALUES ({', '.join('?' * len(values))})", list(values.values()))
    return RedirectResponse("/sources", status_code=303)


@router.get("/sources/{source_id}/edit", response_class=HTMLResponse)
def source_edit(request: Request, source_id: int, user=Depends(require_editor)):
    with get_db() as db:
        row = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
    if not row:
        return RedirectResponse("/sources", status_code=303)
    return _render(request, "source_form.html", source=dict(row))


@router.post("/sources/{source_id}/edit")
async def source_update(request: Request, source_id: int, user=Depends(require_editor)):
    form = await request.form()
    values = _form_values(form, SOURCE_FIELDS)
    sets = ", ".join(f"{k}=?" for k in values)
    with get_db() as db:
        db.execute(f"UPDATE sources SET {sets} WHERE id=?",
                   list(values.values()) + [source_id])
    return RedirectResponse("/sources", status_code=303)


@router.post("/sources/{source_id}/toggle")
def source_toggle(source_id: int, user=Depends(require_editor)):
    with get_db() as db:
        db.execute("UPDATE sources SET enabled = 1 - enabled WHERE id=?", (source_id,))
    return RedirectResponse("/sources", status_code=303)


@router.post("/sources/{source_id}/delete")
def source_delete(source_id: int, user=Depends(require_admin)):
    with get_db() as db:
        db.execute("DELETE FROM sources WHERE id=?", (source_id,))
    return RedirectResponse("/sources", status_code=303)


# --- admin ------------------------------------------------------------------

@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user=Depends(require_admin)):
    with get_db() as db:
        users = [dict(r) for r in db.execute(
            "SELECT id, username, email, role, active FROM users ORDER BY username")]
        keys = [dict(r) for r in db.execute("SELECT * FROM api_keys ORDER BY created_at DESC")]
        cfg = [dict(r) for r in db.execute("SELECT * FROM config ORDER BY key")]
    return _render(request, "admin.html", users=users, api_keys=keys, config=cfg,
                   config_choices=CONFIG_CHOICES,
                   new_key=request.query_params.get("new_key"))


@router.post("/admin/config/{key}")
async def config_update(request: Request, key: str, user=Depends(require_admin)):
    form = await request.form()
    with get_db() as db:
        cur = db.execute("UPDATE config SET value=? WHERE key=?", (form.get("value") or "", key))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Unknown key")
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/users/new")
def user_create(username: str = Form(...), email: str = Form(...), password: str = Form(...),
                role: str = Form("reader"), user=Depends(require_admin)):
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password too short (min 8 chars)")
    with get_db() as db:
        db.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                   (username, email, hash_password(password),
                    role if role in ("reader", "editor", "admin") else "reader"))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/users/{user_id}/password")
def user_set_password(user_id: int, password: str = Form(...), user=Depends(require_admin)):
    if len(password) < 8:
        raise HTTPException(status_code=422, detail="Password too short (min 8 chars)")
    with get_db() as db:
        cur = db.execute("UPDATE users SET password_hash=? WHERE id=?",
                         (hash_password(password), user_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/users/{user_id}/role")
def user_set_role(user_id: int, role: str = Form(...), user=Depends(require_admin)):
    if role not in ("reader", "editor", "admin"):
        raise HTTPException(status_code=422, detail="Unknown role")
    with get_db() as db:
        db.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/users/{user_id}/toggle")
def user_toggle(user_id: int, user=Depends(require_admin)):
    with get_db() as db:
        db.execute("UPDATE users SET active = 1 - active WHERE id=?", (user_id,))
    return RedirectResponse("/admin", status_code=303)


@router.post("/admin/keys/new")
def key_create(label: str = Form(...), user=Depends(require_admin)):
    key = new_api_key()
    with get_db() as db:
        db.execute("INSERT INTO api_keys (label, key) VALUES (?, ?)", (label, key))
    # Shown once, in the query string on the admin page.
    return RedirectResponse(f"/admin?new_key={key}", status_code=303)


@router.post("/admin/keys/{key_id}/revoke")
def key_revoke(key_id: int, user=Depends(require_admin)):
    with get_db() as db:
        db.execute("UPDATE api_keys SET active=0 WHERE id=?", (key_id,))
    return RedirectResponse("/admin", status_code=303)
