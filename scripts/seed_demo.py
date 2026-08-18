"""Demo data, for looking at the UI with something in it.

EVERY NUMBER IN HERE IS INVENTED. TRL values, runway, amounts, fit scores and
verdicts are placeholders chosen to exercise the templates. This is NOT the
BeadRoots seed: the real one waits on facts we do not have yet (product lines
and their IP status, the regulatory framework, whether the convertible has
converted, the exact aid history).

    python scripts/seed_demo.py       # run from the repo root

Login: spit / demo-password
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))
os.makedirs("data", exist_ok=True)

from app.auth import hash_password  # noqa: E402
from app.db import get_db, init_db  # noqa: E402

init_db()
with get_db() as db:
    if not db.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]:
        db.execute("INSERT INTO users (username, email, password_hash, role) "
                   "VALUES ('spit', 's@x.it', ?, 'admin')", (hash_password("demo-password"),))
    if db.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]:
        print("already seeded")
        sys.exit()

    db.execute("""UPDATE company SET legal_name='BeadRoots S.r.l.', legal_form='srl',
        country='IT', incorporation_date='2023-03-01', sme_size='micro', headcount=2, fte=2,
        funding_stage='pre_seed', revenue_stage='pre_revenue', runway_months=9,
        sme_size_definition='EU Recommendation 2003/361',
        impact_tags='["water","climate_adaptation","soil_health"]' WHERE id=1""")

    for row in [("registered_office", "Lecce", "IT", "Puglia", "ITF4", "NUTS", 1),
                ("lab", "Verona", "IT", "Veneto", "ITH3", "NUTS", 1),
                ("operating_unit", "Milano", "IT", "Lombardia", "ITC4", "NUTS", 1)]:
        db.execute("INSERT INTO company_locations (kind, city, country, region, region_code, "
                   "code_system, registered) VALUES (?,?,?,?,?,?,?)", row)

    for row in [("Angela Bonato", "CTO", 1, "f", "phd", "2023-03-01", None),
                ("Valerio V. De Luca", "CEO", 1, "m", "msc", "2023-03-01", None),
                ("Paolo Pezzolla", "Agronomist", 1, "m", "msc", "2023-03-01", "2026-06-01")]:
        db.execute("INSERT INTO team_members (name, role, is_founder, gender, highest_degree, "
                   "joined_at, left_at) VALUES (?,?,?,?,?,?,?)", row)

    db.execute("INSERT INTO company_qualifications (key, label, jurisdiction, status, "
               "confirmed_at, renewal_every_months) VALUES ('it_startup_innovativa', "
               "'Innovative startup register', 'IT', 'active', '2026-01-15', 12)")
    db.execute("INSERT INTO company_aid (name, provider, regime, nominal_amount, gge_amount, "
               "currency, granted_at) VALUES ('Start Cup Puglia 2024', 'ARTI Puglia', "
               "'de_minimis', 10000, 10000, 'EUR', '2024-11-01')")
    db.execute("INSERT INTO company_funding (instrument, amount, currency, investor, closed_at, "
               "converted) VALUES ('convertible', 250000, 'EUR', 'FoodSeed / CDP VC', "
               "'2024-10-01', 0)")

    db.execute("UPDATE company_narrative SET content=? WHERE section='pitch'",
               ("Natural superabsorbent hydrogels from seaweed-derived biopolymers that hold "
                "water in the soil and release it slowly to plant roots. Fully biodegradable.",))
    db.execute("UPDATE company_narrative SET content=? WHERE section='track_record'",
               ("Start Cup Puglia 2024, Basilicata Open Lab, EIT Food TeamUp first prize, "
                "UniCredit Start Lab 2026 (Innovative Made in Italy, first place). Academic "
                "partners: Pavia, Verona, Bari.",))
    db.execute("UPDATE company_narrative SET content=? WHERE section='strategy_12m'",
               ("Pilot plant, IP extension, replace the agronomist, close a seed round.",))

    db.execute("""INSERT INTO products (name, description, status, trl, trl_updated_at,
        trl_evidence, target_segments, ip_status, regulatory_framework, regulatory_status)
        VALUES ('Beads for open field', 'Alginate hydrogel beads applied at transplanting.',
        'field_trials', 7, '2026-06-01', 'Two seasons of formal trials on vine and horticulture
        with independent yield data.', '["viticulture","horticulture","legumes"]', 'filed',
        'EU fertilising products', 'classification under review')""")
    db.execute("INSERT INTO products (name, description, status, trl) VALUES "
               "('Lab formulation B', 'Higher-retention formulation, lab stage.', 'research', 3)")

    db.execute("INSERT INTO sources (name, url, hints, geo_hint, instrument_hint, scan_cadence) "
               "VALUES ('Invitalia', 'https://www.invitalia.it', 'National instruments for "
               "innovative startups and SMEs', 'IT', 'grant', 'monthly')")
    db.execute("INSERT INTO sources (name, url, hints, geo_hint, instrument_hint, scan_cadence) "
               "VALUES ('Regione Puglia / ARTI', 'https://www.sistema.puglia.it', 'Regional "
               "calls: TecnoNidi, PIA, innovation vouchers', 'IT-Puglia', 'grant', 'monthly')")

    db.execute("""INSERT INTO opportunities (title, provider, provider_type, instrument, dilutive,
        link, description, amount_max, currency, funding_rate_pct, advance_available,
        disbursement, aid_regime, deadline_type, trl_min, trl_max, status, source_id, fit_score,
        best_fit_product_id, eligibility_verdict, eligibility_rationale, effort, origin)
        VALUES ('Smart&Start Italia', 'Invitalia', 'public_national', 'subsidized_loan', 0,
        'https://www.invitalia.it/smart-start', 'Zero-interest loan for innovative startups,
        higher coverage in the South.', 1500000, 'EUR', 80, 1, 'milestones', 'de_minimis',
        'open_until_funds_exhausted', 5, 9, 'shortlisted', 1, 84, 1, 'eligible',
        'Innovative startup register active, registered office in the South, lead product at
        TRL 7 inside the 5-9 window.', 'high', 'manual')""")
    db.execute("""INSERT INTO opportunities (title, provider, provider_type, instrument, dilutive,
        description, amount_max, currency, deadline_type, deadline_date, status, source_id,
        fit_score, best_fit_product_id, eligibility_verdict, effort, origin)
        VALUES ('TecnoNidi Puglia', 'Regione Puglia', 'public_regional', 'grant', 0,
        'Grant for innovative micro and small enterprises with a unit in Puglia.', 150000, 'EUR',
        'fixed', '2026-10-15', 'watching', 2, 71, 1, 'eligible', 'medium', 'discovery')""")
    db.execute("""INSERT INTO opportunities (title, provider, provider_type, instrument, dilutive,
        description, ticket_min, ticket_max, currency, stage_focus, sector_focus, geo_focus,
        lead_or_follow, status, origin)
        VALUES ('Eatable Adventures', 'Eatable Adventures', 'vc', 'equity', 1, 'Global foodtech
        accelerator and co-investor, already on the cap table via FoodSeed.', 100000, 500000,
        'EUR', 'pre-seed to seed', 'agrifoodtech', 'Europe', 'follow', 'watching', 'manual')""")

    db.execute("""INSERT INTO opportunity_caps (opportunity_id, counter_key, currency, comparator,
        scope_note, verdict, checked_at) VALUES (1, 'de_minimis', 'EUR', 'lte',
        'the loan carries a gross grant equivalent that counts against the de minimis ceiling',
        'pass', CURRENT_TIMESTAMP)""")
    db.execute("""INSERT INTO opportunity_caps (opportunity_id, counter_key, max_amount, currency,
        comparator, scope_note, verdict, checked_at) VALUES (3, 'lifetime_equity_raised', 500000,
        'EUR', 'lt', 'equity subscribed to date; the call does not say whether unconverted
        convertibles count', 'uncertain', CURRENT_TIMESTAMP)""")
    db.execute("""INSERT INTO opportunity_product_fit (opportunity_id, product_id, verdict,
        fit_score, rationale, evaluated_at) VALUES (1, 1, 'eligible', 84, 'TRL 7 sits inside the
        5-9 window and the pilot plant is exactly what the instrument funds.', CURRENT_TIMESTAMP)""")
    db.execute("""INSERT INTO opportunity_product_fit (opportunity_id, product_id, verdict,
        fit_score, rationale, evaluated_at) VALUES (1, 2, 'not_eligible', 15,
        'TRL 3 is below the floor of 5.', CURRENT_TIMESTAMP)""")

    db.execute("""INSERT INTO applications (opportunity_id, product_id, status, amount_requested,
        currency, next_action, next_action_due, owner_user_id) VALUES (3, 1, 'preparing', 300000,
        'EUR', 'Send updated deck and traction data', '2026-09-01', 1)""")
    db.execute("""INSERT INTO activities (opportunity_id, kind, happened_at, contact_name,
        summary, created_by) VALUES (3, 'call', '2026-08-10', 'M. Rossi', 'Intro call. Asked for
        field-trial yield data and the pilot plant budget.', 1)""")
    db.execute("""INSERT INTO contacts (name, organisation, role, opportunity_id, warm_intro_via,
        relationship) VALUES ('M. Rossi', 'Eatable Adventures', 'Investment manager', 3,
        'FoodSeed cohort', 'met')""")

    db.execute("INSERT INTO proposals (kind, payload, rationale, source_url, confidence, method, "
               "source_id) VALUES ('new', ?, ?, 'https://www.mimit.gov.it', 'high', 'llm_scan', 1)",
               (json.dumps({"title": "Bando Macchinari Innovativi", "provider": "MIMIT",
                            "instrument": "grant", "amount_max": 400000,
                            "deadline_type": "fixed", "deadline_date": "2026-11-30"}),
                "New call for innovative machinery, opens in October. Matches the pilot plant "
                "need in the 12-month strategy."))
    db.execute("INSERT INTO proposals (kind, opportunity_id, payload, rationale, source_url, "
               "confidence, method) VALUES ('update', 2, ?, ?, "
               "'https://www.sistema.puglia.it', 'medium', 'llm_check')",
               (json.dumps({"deadline_date": "2026-12-01", "amount_max": 200000}),
                "The regional page now shows a later closing date and a higher ceiling."))
    db.execute("INSERT INTO scan_log (source_id, finished_at, outcome, detail) "
               "VALUES (1, CURRENT_TIMESTAMP, 'ok', '2 proposals filed')")

print("demo DB ready")
