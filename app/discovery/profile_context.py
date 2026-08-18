"""The company profile, rendered for a prompt.

Every discovery process judges against the profile, so they all render it the
same way. Empty fields are dropped rather than shown as null: a prompt full of
`null` teaches the model that not knowing is normal, and here it is the thing we
most want it to notice.
"""
import json
from datetime import date

from ..db import company_profile, get_db, json_field


def _tags(raw) -> str:
    values = json_field(raw)
    return ", ".join(str(v) for v in values) if values else ""


def _line(label: str, value) -> str:
    return f"- {label}: {value}\n" if value not in (None, "", []) else ""


def products_block(products: list[dict]) -> str:
    if not products:
        return "No product lines recorded.\n"
    out = ""
    for p in products:
        out += f"\n### Product {p['id']}: {p['name']}\n"
        out += _line("TRL", p["trl"])
        out += _line("TRL evidence", p["trl_evidence"])
        out += _line("development status", p["status"])
        out += _line("IP", f"{p['ip_status'] or 'unknown'} — {p['ip_refs']}"
                     if p["ip_refs"] else p["ip_status"])
        out += _line("regulatory framework", p["regulatory_framework"])
        out += _line("regulatory status", p["regulatory_status"])
        out += _line("target segments", _tags(p["target_segments"]))
        out += _line("impact", _tags(p["impact_tags"]))
        out += _line("description", p["description"])
    return out


def profile_block(profile: dict | None = None) -> str:
    """Markdown block describing the company. Injected into every scan and
    every evaluation."""
    p = profile or company_profile()
    c = p["company"]

    out = f"# COMPANY PROFILE (today is {date.today().isoformat()})\n\n"
    out += _line("legal name", c.get("legal_name"))
    out += _line("legal form", c.get("legal_form"))
    out += _line("country", c.get("country"))
    out += _line("VAT", c.get("vat_number"))
    out += _line("industry codes", c.get("industry_codes"))
    out += _line("incorporated", c.get("incorporation_date"))
    out += _line("age in years", p.get("age_years"))
    out += _line("size", c.get("sme_size"))
    out += _line("headcount", c.get("headcount"))
    out += _line("last turnover", c.get("last_turnover"))
    out += _line("revenue stage", c.get("revenue_stage"))
    out += _line("funding stage", c.get("funding_stage"))
    out += _line("runway in months", c.get("runway_months"))
    out += _line("impact tags", _tags(c.get("impact_tags")))

    if p["locations"]:
        out += "\n## Locations\n"
        for loc in p["locations"]:
            flag = "registered" if loc["registered"] else "NOT REGISTERED"
            out += (f"- {loc['kind']}: {loc['city']}, {loc['region']} "
                    f"({loc['region_code']}, {loc['code_system']}) — {flag}\n")
        out += ("\nOnly registered locations open a region's calls. A site marked "
                "NOT REGISTERED does not satisfy a requirement for a unit in that region.\n")

    if p["qualifications"]:
        out += "\n## Active qualifications\n"
        for q in p["qualifications"]:
            until = f", valid until {q['valid_until']}" if q["valid_until"] else ""
            out += f"- {q['key']} ({q['jurisdiction']}){until}\n"

    d = p["team_derived"]
    out += (f"\n## Team\n- {d['headcount_active']} active people\n"
            f"- female founder: {'yes' if d['has_female_founder'] else 'no'}\n"
            f"- doctorate holders: {d['doctorate_holders']}\n")

    out += "\n## Product lines\n" + products_block(p["products"])

    out += "\n## Cumulative caps\n"
    for counter in p["counters"]:
        ceiling = (f"ceiling {counter['ceiling']:,.0f}"
                   if counter["ceiling"] else "no universal ceiling")
        window = (f"{counter['window_years']}-year rolling window"
                  if counter["window_years"] else "lifetime")
        out += (f"- {counter['key']}: used {counter['used_amount'] or 0:,.0f} "
                f"{counter['currency'] or ''}, {ceiling}, {window}\n")

    # The tags already in use, so a scan reuses them instead of coining a
    # synonym. Two tags meaning one thing never filter together, and nobody
    # notices until a search comes back half empty.
    with get_db() as db:
        vocabulary: dict[str, list[str]] = {}
        for row in db.execute(
                "SELECT namespace, value FROM tag_vocabulary "
                "WHERE COALESCE(active, 1) = 1 ORDER BY namespace, value"):
            vocabulary.setdefault(row["namespace"], []).append(row["value"])
    if vocabulary:
        out += "\n## Tags already in use\n"
        for namespace, values in vocabulary.items():
            out += f"- {namespace}: {', '.join(values)}\n"
        out += ("Reuse one of these whenever it fits; coin a new tag only when "
                "none does.\n")

    narrative = {k: v for k, v in p["narrative"].items() if v}
    if narrative:
        out += "\n## Narrative\n"
        for section, content in narrative.items():
            out += f"\n### {section.replace('_', ' ')}\n{content}\n"
    missing = [k for k, v in p["narrative"].items() if not v]
    if missing:
        out += f"\nNot recorded: {', '.join(missing)}.\n"

    return out


def opportunity_block(o: dict) -> str:
    """The stored record of one opportunity, for the evaluator and the verifier."""
    keep = [
        "id", "title", "provider", "provider_type", "instrument", "dilutive",
        "is_general", "link", "description", "amount_min", "amount_max", "currency",
        "funding_rate_pct", "cofinancing_pct", "advance_available", "disbursement",
        "aid_regime", "call_total_budget", "deadline_type", "deadline_date",
        "deadline_text", "cutoff_dates", "recurrence_logic", "opens_at",
        "decision_lag_months", "project_duration_months", "eligible_geographies",
        "requires_unit_in", "unit_required_by", "unit_deadline_months",
        "max_company_age_years", "eligible_sme_sizes",
        "requires_qualification", "requires_partners", "partner_requirements",
        "trl_min", "trl_max", "sector_tags", "impact_focus", "other_requirements",
        "ticket_min", "ticket_max", "stage_focus", "sector_focus", "geo_focus",
        "lead_or_follow", "status",
    ]
    record = {k: o.get(k) for k in keep if o.get(k) not in (None, "")}
    return json.dumps(record, ensure_ascii=False, default=str, indent=1)
