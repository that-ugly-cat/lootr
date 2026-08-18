"""Seed the BeadRoots profile from confirmed facts.

    python scripts/seed_beadroots.py      # run from the repo root

Everything here was given by the company or taken from its own public
material. Where a fact is not known, the field is left empty rather than
guessed, and the script prints what is still missing when it finishes.

Two conventions worth knowing:

* Prizes are recorded with 31 December of their year, because only the year
  was given. For a rolling ceiling window a later date is the conservative
  error: it keeps the amount inside the window longer.
* Every aid regime is left `unknown`. Whether a prize counts against the de
  minimis ceiling depends on who granted it and under which rule, and that is
  read off the award decision, not inferred. Each row carries a note with the
  reading to confirm.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from app.db import get_db, init_db  # noqa: E402

init_db()

# The tag vocabulary is what the multi-value widgets offer, so it is seeded
# before the guard below and on every run: adding a namespace here reaches an
# instance that was seeded months ago, and re-running costs nothing because the
# unique index on (namespace, value) makes each insert idempotent.
VOCABULARY = {
    "segment": ["viticulture", "horticulture", "legumes", "open_field",
                "arable", "nursery", "turf", "landscaping"],
    "impact": ["water_efficiency", "drought_resilience", "soil_health",
               "climate_adaptation", "circular_bioeconomy", "biodiversity"],
    "sector": ["agrifood", "agritech", "biotech", "advanced_materials",
               "water", "climate", "circular_economy", "deeptech",
               "bioeconomy", "manufacturing"],
    "market": ["IT", "EU", "MENA", "north_america", "latin_america"],
}

# In its own transaction, and before the guard: `get_db` commits when the block
# ends normally, and the guard below leaves by sys.exit — which would take the
# vocabulary down with it.
with get_db() as db:
    for namespace, values in VOCABULARY.items():
        for value in values:
            db.execute(
                "INSERT OR IGNORE INTO tag_vocabulary (namespace, value, label) "
                "VALUES (?, ?, ?)", (namespace, value, value.replace("_", " ")))

with get_db() as db:
    if db.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]:
        print("Already seeded (products exist). Tag vocabulary refreshed.")
        sys.exit()

    # --- company ---------------------------------------------------------

    db.execute("""UPDATE company SET
        legal_name       = 'BeadRoots S.r.l.',
        legal_form       = 'srl',
        country          = 'IT',
        vat_number       = '05317740750',
        incorporation_date = '2023-12-07',
        industry_codes   = ?,
        sme_size         = 'micro',
        sme_size_definition = 'EU Recommendation 2003/361',
        headcount        = 2,
        currency         = 'EUR',
        funding_stage    = 'pre_seed',
        impact_tags      = ?
        WHERE id = 1""",
        (json.dumps([{"system": "ATECO", "code": "72.11.00"}]),
         json.dumps(["water_efficiency", "drought_resilience", "soil_health",
                     "climate_adaptation"])))

    # --- locations -------------------------------------------------------
    # The registered flag is a real gate: a laboratory that is not filed with
    # the company register does not open that region's calls.

    db.execute("""INSERT INTO company_locations
        (kind, city, country, region, region_code, code_system, registered, notes)
        VALUES ('registered_office', 'Lecce', 'IT', 'Puglia', 'ITF4', 'NUTS', 1,
        'Registered office. Opens the Puglia regional channel and the instruments
        reserved to the South.')""")
    db.execute("""INSERT INTO company_locations
        (kind, city, country, region, region_code, code_system, registered, notes)
        VALUES ('operating_unit', 'Milano', 'IT', 'Lombardia', 'ITC4', 'NUTS', 1,
        'Operating unit.')""")
    db.execute("""INSERT INTO company_locations
        (kind, city, country, region, region_code, code_system, registered, notes)
        VALUES ('lab', 'Solagna', 'IT', 'Veneto', 'ITH3', 'NUTS', 0,
        'Laboratory only, not formally registered. Until it is filed, calls that
        require an operating unit in Veneto are out of reach.')""")

    # --- qualifications --------------------------------------------------

    db.execute("""INSERT INTO company_qualifications
        (key, label, jurisdiction, status, renewal_every_months, notes)
        VALUES ('it_startup_innovativa', 'Innovative startup register (special section)',
        'IT', 'active', 12,
        'Confirmed annually. Date of the last confirmation still to record, and the
        outer horizon of the status is worth asking the accountant for: losing it
        closes a whole band of instruments.')""")

    # --- team ------------------------------------------------------------

    db.execute("""INSERT INTO team_members
        (name, role, is_founder, is_shareholder, gender, highest_degree)
        VALUES ('Angela Bonato', 'CTO', 1, 1, 'f', 'phd')""")
    db.execute("""INSERT INTO team_members
        (name, role, is_founder, is_shareholder, gender)
        VALUES ('Valerio Vincenzo De Luca', 'CEO', 1, 1, 'm')""")
    db.execute("""INSERT INTO team_members
        (name, role, is_founder, gender, left_at, notes)
        VALUES ('Paolo Pezzolla', 'Agronomist', 1, 'm', '2026-08-18',
        'Departed. Exact date to correct: the one recorded here is the date it was
        entered. Agronomy and field-trial analysis are the capability now missing.')""")

    # --- products --------------------------------------------------------

    db.execute("""INSERT INTO products
        (name, status, trl, ip_status, ip_refs, regulatory_framework,
         regulatory_status, target_segments, impact_tags, active, notes)
        VALUES ('br.1O', NULL, 6, 'filed', 'BeadRoots patent application, pending.',
        'IT: product with a specific action on soil',
        'Marketed under the Italian category; move to EU plant biostimulant planned.',
        ?, ?, 1,
        'TRL evidence still to write: it is asked for in every application and is
        worth writing once here.')""",
        (json.dumps(["viticulture", "horticulture", "legumes", "open_field"]),
         json.dumps(["water_efficiency", "drought_resilience", "soil_health"])))

    db.execute("""INSERT INTO products
        (name, status, trl, ip_status, ip_refs, regulatory_framework,
         regulatory_status, target_segments, impact_tags, active, notes)
        VALUES ('br.2O', NULL, NULL, 'filed',
        'No standalone BeadRoots IP: depends on two pending applications, one filed by
        BeadRoots and one filed by Tezi.',
        'EU plant biostimulant', NULL, ?, ?, 1,
        'TRL not recorded yet. Also worth recording: the licensing position on the Tezi
        application, because the right to use it is a question both assessors and
        investors ask.')""",
        (json.dumps(["viticulture", "horticulture", "legumes", "open_field"]),
         json.dumps(["water_efficiency", "drought_resilience", "soil_health"])))

    # --- funding ---------------------------------------------------------

    db.execute("""INSERT INTO company_funding
        (instrument, amount, currency, investor, closed_at, converted, notes)
        VALUES ('convertible', 170000, 'EUR',
        'FoodSeed (CDP Venture Capital, Fondazione Cariverona, UniCredit,
        Eatable Adventures)', '2024-12-31', 0,
        'Not converted. Several calls cap the equity raised to date, and an
        unconverted note usually sits outside that count — which is why the flag is
        its own field. Exact closing date to correct.')""")

    # --- public aid and prizes -------------------------------------------

    PRIZES = [
        ("EIT Food TeamUp", "EIT Food", 2023, 40000,
         "EIT Food is an EU body. EU-level funding is generally not Member State aid, "
         "so this probably sits outside the de minimis ceiling. Confirm."),
        ("EIT Food Test Farm", "EIT Food", 2023, 4000,
         "Same reading as the other EIT Food awards. Confirm."),
        ("Encubator", "Encubator (Corepla)", 2024, 40000,
         "Check the award decision for whether it was granted as de minimis."),
        ("Start Cup Puglia", "ARTI / Regione Puglia", 2024, 10000,
         "Regional prize: de minimis is the likely regime. Check the award decision."),
        ("Basilicata Open Lab", "Regione Basilicata", 2025, 20000,
         "Regional programme: de minimis is the likely regime. Check the award decision."),
        ("I3-4-SEAWEED", "European programme", 2025, 60000,
         "European prize. If it was paid as financial support to a third party it "
         "counts against the EU cascade cap rather than against de minimis. Confirm "
         "which, because the two ceilings are separate."),
        ("UniCredit Start Lab", "UniCredit", 2026, 10000,
         "Private bank programme: probably not state aid at all."),
        ("EIT FAN", "EIT Food", 2026, 3000,
         "Same reading as the other EIT Food awards. Confirm."),
    ]
    for name, provider, year, amount, note in PRIZES:
        db.execute("""INSERT INTO company_aid
            (name, provider, entity, regime, nominal_amount, gge_amount, currency,
             granted_at, notes) VALUES (?, ?, 'BeadRoots S.r.l.', 'unknown', ?, ?,
            'EUR', ?, ?)""",
            (name, provider, amount, amount, f"{year}-12-31",
             f"Year only, exact date to correct. {note}"))

    # --- counters --------------------------------------------------------
    # Maintained by hand; the profile page shows what the ledgers say beside them.

    prize_total = sum(p[3] for p in PRIZES)
    db.execute("""UPDATE funding_counters SET used_amount = 0, source_note = ?
        WHERE key = 'de_minimis'""",
        ("Reported as fully available. Nothing in the aid ledger is classified as de "
         "minimis yet, so this figure and the ledger agree by default. The "
         "authoritative number is the extract from the national state-aid register.",))
    db.execute("""UPDATE funding_counters SET used_amount = ?, source_note = ?
        WHERE key = 'lifetime_total_raised'""",
        (170000 + prize_total,
         "Convertible plus every prize and programme award to date."))
    db.execute("""UPDATE funding_counters SET used_amount = 0, source_note = ?
        WHERE key = 'lifetime_equity_raised'""",
        ("Zero: the only investment so far is a convertible that has not converted. "
         "Some calls count unconverted notes anyway, which is why the perimeter of "
         "each cap is recorded in the call's own words.",))
    db.execute("""UPDATE funding_counters SET used_amount = 0, source_note = ?
        WHERE key = 'lifetime_public_grants'""",
        ("Not classified yet. Which of the prizes count as public aid follows from "
         "the regime on each ledger row, and those are still unknown.",))
    db.execute("""UPDATE funding_counters SET used_amount = 0, source_note = ?
        WHERE key = 'eu_cascade_fstp'""",
        ("Not classified yet. I3-4-SEAWEED may belong here rather than under de "
         "minimis.",))

    # --- narrative -------------------------------------------------------
    # Only what is verifiable is written. The sections that only the founders
    # can write are left empty on purpose, and the UI shows them as empty.

    db.execute("UPDATE company_narrative SET content = ? WHERE section = 'pitch'", (
        "BeadRoots makes naturally derived superabsorbent hydrogels that hold water in "
        "the soil and release it slowly to plant roots, so that crops survive drought "
        "with less irrigation. The polymers are seaweed-derived and fully "
        "biodegradable, leaving no residue in the soil.",))
    db.execute("UPDATE company_narrative SET content = ? WHERE section = 'technology'", (
        "Hydrogel beads applied at transplanting. Two product lines: br.1O, at TRL 6, "
        "currently placed under the Italian category of products with a specific "
        "action on soil and heading for the EU plant-biostimulant route; and br.2O, "
        "aimed directly at the EU biostimulant category, which depends on two pending "
        "patent applications, one filed by BeadRoots and one by Tezi.",))
    db.execute("UPDATE company_narrative SET content = ? WHERE section = 'ip'", (
        "One BeadRoots patent application pending, covering br.1O. br.2O has no "
        "standalone BeadRoots IP: it rests on two pending applications, one filed by "
        "BeadRoots and one filed by Tezi.",))
    db.execute("UPDATE company_narrative SET content = ? WHERE section = 'track_record'", (
        "EIT Food TeamUp (first prize) and EIT Food Test Farm in 2023. Encubator and "
        "Start Cup Puglia 2024, the regional innovation prize run by ARTI with Regione "
        "Puglia. Selected in 2024 for FoodSeed, the agrifood acceleration programme "
        "backed by CDP Venture Capital, Fondazione Cariverona, UniCredit and Eatable "
        "Adventures. Basilicata Open Lab and the European I3-4-SEAWEED prize in 2025. "
        "First place in the Innovative Made in Italy category of UniCredit Start Lab "
        "2026, and EIT FAN. Academic partners: Universities of Pavia, Verona and Bari.",))

    # The tag vocabulary is seeded above, before the guard, so that adding a
    # namespace reaches instances that were seeded long ago.

print("""BeadRoots profile seeded.

Left empty on purpose, because nobody has told us yet:

  company     revenue stage, runway, FTE, total assets, last turnover
  br.1O       development status, TRL evidence
  br.2O       TRL, development status, regulatory status, licensing position
              on the Tezi application
  team        birth years and regions of residence — under-35 and Mezzogiorno
              gates cannot be evaluated without them
              Paolo Pezzolla's actual departure date
  aid ledger  the regime of every row, and the exact award dates
  narrative   market, traction, 12-month strategy, exclusions

The 12-month strategy is the one that most changes what discovery brings back:
it is what points the search at what is needed now rather than at funding in
general.

Sources are deliberately empty: that list is its own piece of work.""")
