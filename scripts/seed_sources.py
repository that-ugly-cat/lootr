"""Seed the discovery sources for BeadRoots.

    python scripts/seed_sources.py      # run from the repo root

A source is a *publisher*, not a single call: the scanner reads the hints and
finds the individual opportunities underneath. Rows are matched by name, so the
script is idempotent — running it again refreshes url, hints and cadence and
leaves `enabled` and `last_scanned_at` alone. That way a source switched off in
the UI stays off, and re-seeding never re-scans everything from scratch.

Cadence is a cost decision as much as an editorial one: every due source is one
model call with server-side web search on the nightly run. Weekly is for
channels with short windows (cascade calls, competitions); quarterly is for
publishers that move once a season (investors, annual EU programmes).

Two geographies are deliberate:

* Puglia is open — the registered office is in Lecce.
* Veneto is seeded **disabled**, because the Solagna lab is not registered.
  The row exists so the channel is one click away the day it is, rather than
  something to remember from scratch.
"""
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from app.db import get_db, init_db  # noqa: E402

# Recurring caveats, written once and pasted into the hints that need them.
UNIT_RULE = (
    "Record verbatim whether an operating unit in the region must already exist "
    "at application or may be opened within N months of the award: the company "
    "has its registered office in Lecce and an operating unit in Milan only."
)
NOT_A_FARM = (
    "The company sells soil inputs to growers, it is not a farm and holds no "
    "agricultural land: measures reserved to imprese agricole do not apply, "
    "measures open to the wider agri-food supply chain may."
)

SOURCES = [
    # --- Italy, national ----------------------------------------------------
    {
        "name": "Invitalia",
        "url": "https://www.invitalia.it/cosa-facciamo/creiamo-nuove-aziende",
        "geo_hint": "Italy, national",
        "instrument_hint": "grant, subsidized_loan, programme",
        "scan_cadence": "monthly",
        "hints": (
            "Smart&Start Italia (rolling, 30% grant portion in the Mezzogiorno, "
            "registered office in Lecce qualifies), ON/Nuove Imprese a Tasso Zero, "
            "Fondo Impresa Femminile, Brevetti+, Contratto di Sviluppo. Watch for "
            "refinancing of schemes whose window is closed. " + UNIT_RULE
        ),
    },
    {
        "name": "MIMIT - business incentives",
        "url": "https://www.mimit.gov.it/it/incentivi",
        "geo_hint": "Italy, national",
        "instrument_hint": "grant, subsidized_loan, tax_credit",
        "scan_cadence": "monthly",
        "hints": (
            "Accordi per l'Innovazione, Fondo per la Crescita Sostenibile, national "
            "R&D and industrial transition calls, tax credits for R&D and Transizione "
            "5.0. Report the aid regime as the decree words it. " + UNIT_RULE
        ),
    },
    {
        "name": "UIBM - patent and trademark incentives",
        "url": "https://uibm.mise.gov.it/index.php/it/incentivi",
        "geo_hint": "Italy, national",
        "instrument_hint": "voucher, grant",
        "scan_cadence": "monthly",
        "hints": (
            "Brevetti+, Voucher 3i, Disegni+, Marchi+ and their reopenings. Directly "
            "useful: two patent applications are pending, one filed by the company and "
            "one by Tezi, and the br.1O patent is already filed. These schemes run out "
            "of money fast, so a reopening date matters more than the amount."
        ),
    },
    {
        "name": "ISMEA",
        "url": "https://www.ismea.it/flex/cm/pages/ServeBLOB.php/L/IT/IDPagina/10923",
        "geo_hint": "Italy, national, agri-food supply chain",
        "instrument_hint": "grant, subsidized_loan, guarantee",
        "scan_cadence": "monthly",
        "hints": (
            "ISMEA Investe, Piu Impresa, Fondo Innovazione, Generazione Terra. "
            + NOT_A_FARM
        ),
    },
    {
        "name": "MASAF - agriculture innovation and PNRR",
        "url": "https://www.politicheagricole.it/",
        "geo_hint": "Italy, national, agri-food supply chain",
        "instrument_hint": "grant, cascade_grant",
        "scan_cadence": "monthly",
        "hints": (
            "Ministry calls on agricultural innovation, PNRR agri measures, national "
            "operational groups and supply-chain contracts. " + NOT_A_FARM
        ),
    },
    {
        "name": "CDP Venture Capital - funds and accelerators",
        "url": "https://www.cdpventurecapital.it/",
        "geo_hint": "Italy, national",
        "instrument_hint": "programme, equity, prize",
        "scan_cadence": "monthly",
        "hints": (
            "Terra Next, the bioeconomy accelerator run with Intesa Sanpaolo Innovation "
            "Center and Cariplo Factory, plus the other accelerators of the Rete "
            "Nazionale and CDP's thematic funds touching agritech and industrial "
            "biotech. Record the call for applications, the ticket, and whether the "
            "place comes with equity."
        ),
    },
    {
        "name": "SIMEST",
        "url": "https://www.simest.it/",
        "geo_hint": "Italy, national, with a foreign-market component",
        "instrument_hint": "subsidized_loan, grant",
        "scan_cadence": "quarterly",
        "hints": (
            "Subsidised loans with a non-repayable portion for digital and ecological "
            "transition, fairs and foreign-market entry. Note the disbursement shape: "
            "these arrive as an advance, which matters on a short runway."
        ),
    },
    # --- Puglia (registered office, Lecce) -----------------------------------
    {
        "name": "Puglia Sviluppo",
        "url": "https://pugliasviluppo.eu/it/finanziamenti-per-la-creazione-di-impresa",
        "geo_hint": "Puglia (NUTS ITF4)",
        "instrument_hint": "grant, subsidized_loan",
        "scan_cadence": "monthly",
        "hints": (
            "TecnoNidi (up to 80% on plans of 50k-350k, wants a validated technology, "
            "a working prototype and coherence with the Puglia S3 areas), Nuove "
            "Iniziative d'Impresa, PIA, Innolabs and Innoprocess, plus the Just "
            "Transition Fund window for the Taranto province. " + UNIT_RULE
        ),
    },
    {
        "name": "Galattica / ARTI Puglia",
        "url": "https://galattica.regione.puglia.it/opportunita",
        "geo_hint": "Puglia (NUTS ITF4)",
        "instrument_hint": "grant, prize, programme",
        "scan_cadence": "monthly",
        "hints": (
            "Regional aggregator of opportunities for young and innovative companies, "
            "including measures announced before Puglia Sviluppo opens the window. "
            "Also carries Start Cup Puglia, which the company has already won."
        ),
    },
    # --- Lombardia (operating unit, Milan) -----------------------------------
    {
        "name": "Regione Lombardia - Bandi e Servizi",
        "url": "https://www.bandi.regione.lombardia.it/servizi/servizio/catalogo/target/IMPRESE",
        "geo_hint": "Lombardia (NUTS ITC4)",
        "instrument_hint": "grant, voucher",
        "scan_cadence": "monthly",
        "hints": (
            "The FESR 1.3.3 call for innovative startups (window 28 Sep - 25 Nov 2026, "
            "36 months from incorporation, extended to 60 for TRL 6 or below: the "
            "company was incorporated on 7 December 2023 and br.1O sits at TRL 6), "
            "Rafforza & Innova, Competenze & Innovazione, Nuova Impresa. " + UNIT_RULE
        ),
    },
    {
        "name": "CCIAA Milano Monza Brianza Lodi",
        "url": "https://www.milomb.camcom.it/bandi-e-contributi",
        "geo_hint": "Milano, Monza Brianza, Lodi",
        "instrument_hint": "voucher, grant",
        "scan_cadence": "monthly",
        "hints": (
            "Voucher Doppia Transizione, Bando Impresa Sostenibile and the other "
            "chamber vouchers. Small tickets on a de minimis regime, but the operating "
            "unit in Milan already qualifies and the paperwork is light. Check the "
            "recurring exclusion for firms that won the previous edition."
        ),
    },
    {
        "name": "Fondazione Cariplo",
        "url": "https://www.fondazionecariplo.it/",
        "geo_hint": "Lombardia and provinces of Novara and Verbano-Cusio-Ossola",
        "instrument_hint": "grant",
        "scan_cadence": "quarterly",
        "hints": (
            "Circular economy, environmental research and technology transfer calls. "
            "Many require a research organisation as lead or partner: record who may "
            "apply verbatim, and flag the ones where a company can only join as partner."
        ),
    },
    # --- EU ------------------------------------------------------------------
    {
        "name": "EIC - European Innovation Council",
        "url": "https://eic.ec.europa.eu/eic-funding-opportunities_en",
        "geo_hint": "EU and Horizon Europe associated countries",
        "instrument_hint": "grant, equity",
        "scan_cadence": "monthly",
        "hints": (
            "EIC Accelerator Open and Challenges (the 2026 work programme carries a "
            "challenge on biotech for agricultural soils, which is squarely on target), "
            "EIC Transition, EIC Pathfinder. TRL 5-8 for the Accelerator, and the "
            "blended option mixes a grant with an equity investment: record the split "
            "and the cut-off dates, not just the annual deadline."
        ),
    },
    {
        "name": "EU Funding & Tenders Portal",
        "url": "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home",
        "geo_hint": "EU and Horizon Europe associated countries",
        "instrument_hint": "grant",
        "scan_cadence": "monthly",
        "hints": (
            "Horizon Europe Cluster 6 (food, bioeconomy, natural resources, agriculture "
            "and environment), CBE JU on bio-based industries, the SMP-COSME agri-food "
            "biotech line, Innovation Fund small-scale. Most topics need a consortium: "
            "set requires_partners and say so in the rationale, because a two-person "
            "team joining a consortium is a different decision from applying alone."
        ),
    },
    {
        "name": "EU cascade funding (FSTP)",
        # The official portal, not an aggregator. A directory whose value is a
        # live list is a poor source for a scanner that works by web search: it
        # finds articles about calls rather than the calls. The portal's own
        # filter is a page the model can actually interrogate.
        "url": ("https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/"
                "opportunities/calls-for-proposals"),
        "geo_hint": "EU and Horizon Europe associated countries",
        "instrument_hint": "cascade_grant",
        "scan_cadence": "weekly",
        "hints": (
            "Open calls issued by EU-funded projects to third parties, typically "
            "20k-200k with windows of a few weeks, which is why this is scanned weekly. "
            "Start from the Funding & Tenders Portal and its filter under type of grants "
            "calls, 'Calls for funding in cascade (issued by funded projects)': projects "
            "register their cascade calls there. Search by named programme rather than by "
            "category — a query for the concept returns articles about cascade funding, "
            "a query for a project acronym plus 'open call' returns the call. Names worth "
            "trying: GATE 5.0, agrifood and bioeconomy Horizon projects running FSTP, "
            "Digital Innovation Hubs with agri strands, and any project whose name "
            "appears alongside soil, water or biopolymers. Aggregators such as "
            "cascadefunding.eu, kaila.eu and eucalls.net are useful as a cross-check "
            "only: the record must come from the call's own page, with its own deadline. "
            "The company has already won I3-4-SEAWEED, so this channel is proven. Check "
            "the cascade counter: some calls cap what one company may receive across all "
            "FSTP. Mid-summer is genuinely quiet — if everything is closed, say so in "
            "the search notes rather than stretching to fill the queue."
        ),
    },
    {
        "name": "EIT Food",
        "url": "https://www.eitfood.eu/open-calls",
        "geo_hint": "EU and Horizon Europe associated countries",
        "instrument_hint": "programme, prize, grant",
        "scan_cadence": "monthly",
        "hints": (
            "Accelerator Network (the Catania hub works on water-smart agrifood "
            "systems), TeamUp, Test Farm, Empowering Women in Agrifood. The company has "
            "already won TeamUp and Test Farm, so report new editions as updates and "
            "check whether previous winners may reapply."
        ),
    },
    {
        "name": "PRIMA",
        "url": "https://prima-med.org/",
        "geo_hint": "Mediterranean, PRIMA participating states",
        "instrument_hint": "grant",
        "scan_cadence": "quarterly",
        "hints": (
            "Annual calls on water management, farming systems and agri-food value "
            "chains in the Mediterranean. Water retention in soil under drought is the "
            "core of the thesis here, so relevance is high even though the calls are "
            "consortium-based."
        ),
    },
    {
        "name": "LIFE / CINEA",
        "url": "https://cinea.ec.europa.eu/programmes/life_en",
        "geo_hint": "EU",
        "instrument_hint": "grant",
        "scan_cadence": "quarterly",
        "hints": (
            "LIFE Environment and Climate Action, in particular close-to-market "
            "projects on circular economy, water and climate adaptation. One annual "
            "cycle: the useful output is the opening date and the topic list."
        ),
    },
    # --- Prizes and competitions --------------------------------------------
    {
        "name": "PNICube - Start Cup and PNI",
        "url": "https://www.pnicube.it/",
        "geo_hint": "Italy, national and regional heats",
        "instrument_hint": "prize",
        "scan_cadence": "monthly",
        "hints": (
            "Regional Start Cup heats and the national PNI final (2026 edition in Bari, "
            "3-4 December), plus Premio IMSA. The company has already won Start Cup "
            "Puglia: check the rules on whether past winners may re-enter, and record "
            "which category fits (Cleantech & Energy or Industrial)."
        ),
    },
    {
        "name": "Prizes and competitions - agrifood and climate (international)",
        "url": "",
        "geo_hint": "Europe and international",
        "instrument_hint": "prize, programme",
        "scan_cadence": "weekly",
        "hints": (
            "Open search, no fixed portal. Look for prizes and competitions with money "
            "or a programme place attached on soil health, water scarcity, biopolymers, "
            "regenerative agriculture and climate adaptation: EcoTrophelia, Thought For "
            "Food, Hello Tomorrow, Falling Walls, Premio Gaetano Marzotto, water and "
            "soil prizes from foundations and corporates. Skip anything that is only "
            "visibility with no money, no equity-free cash and no programme place."
        ),
    },
    {
        "name": "Corporate and bank accelerators (IT)",
        "url": "",
        "geo_hint": "Italy",
        "instrument_hint": "programme, prize, in_kind",
        "scan_cadence": "monthly",
        "hints": (
            "UniCredit Start Lab (already won, watch for alumni-only calls), Intesa "
            "Sanpaolo Innovation Center, Cariplo Factory, and the open innovation calls "
            "of agrichemical, seed, water and food corporates operating in Italy. "
            "Record what the place actually gives: cash, pilot access, or only mentoring."
        ),
    },
    # --- Investors -----------------------------------------------------------
    {
        "name": "Agrifood VC (Europe)",
        "url": "",
        "geo_hint": "Europe",
        "instrument_hint": "equity, convertible",
        "scan_cadence": "quarterly",
        "hints": (
            "Five Seasons Ventures, Astanor, Peakbridge, Yield Lab Europe, Capagro, "
            "ICOS Capital, Blue Horizon, Eatable Adventures (already in the cap table "
            "through the FoodSeed convertible). No deadlines here: what matters is the "
            "thesis, the stage and ticket, whether they lead, and the next concrete "
            "action. Report a newly closed fund or a stated appetite for soil and water "
            "inputs as an update, and set is_general."
        ),
    },
    {
        "name": "Climate and deep tech VC (Europe)",
        "url": "",
        "geo_hint": "Europe",
        "instrument_hint": "equity, convertible",
        "scan_cadence": "quarterly",
        "hints": (
            "World Fund, Planet A, Pale Blue Dot, 2150, Extantia and comparable funds "
            "underwriting climate impact. Many require a quantified emissions or "
            "resilience case: record what evidence they ask for, because that is the "
            "work the company would have to do before pitching."
        ),
    },
    {
        "name": "Italian early-stage and tech-transfer funds",
        "url": "",
        "geo_hint": "Italy",
        "instrument_hint": "equity, convertible",
        "scan_cadence": "quarterly",
        "hints": (
            "Eureka! Venture, Progress Tech Transfer, Vertis, P101, Indaco and the CDP "
            "Venture Capital vehicles. The tech-transfer funds are the closest fit: "
            "materials science out of a doctorate, patent filed, TRL 6. Record whether "
            "they invest pre-revenue and whether they require a university licence."
        ),
    },
    {
        "name": "Italian business angel networks",
        "url": "",
        "geo_hint": "Italy",
        "instrument_hint": "equity, convertible",
        "scan_cadence": "quarterly",
        "hints": (
            "Italian Angels for Growth, Club degli Investitori, Doorway, IBAN affiliates "
            "and Angels4Women, which invests only in women-led startups and is worth "
            "checking against how the company defines its leadership. Record the "
            "application route and the review cycle, since these run on submission "
            "windows rather than deadlines."
        ),
    },
    # --- Closed channel, seeded off -----------------------------------------
    {
        "name": "Regione Veneto",
        "url": "https://www.regione.veneto.it/",
        "geo_hint": "Veneto (NUTS ITH3)",
        "instrument_hint": "grant, voucher",
        "scan_cadence": "monthly",
        "enabled": 0,
        "hints": (
            "DISABLED ON PURPOSE. The Solagna laboratory is not registered as an "
            "operating unit, so calls requiring a unit in Veneto are out of reach. "
            "Enable this source the day the lab is registered, and not before."
        ),
    },
]

FIELDS = ("url", "hints", "geo_hint", "instrument_hint", "scan_cadence")

init_db()

added = updated = 0
with get_db() as db:
    for s in SOURCES:
        row = db.execute("SELECT id FROM sources WHERE name = ?", (s["name"],)).fetchone()
        values = [s.get(f, "") for f in FIELDS]
        if row:
            # Leave `enabled` and `last_scanned_at` alone: a source switched off
            # in the UI stays off, and re-seeding never re-scans from scratch.
            db.execute(
                f"UPDATE sources SET {', '.join(f + '=?' for f in FIELDS)} WHERE id = ?",
                values + [row["id"]],
            )
            updated += 1
        else:
            db.execute(
                f"INSERT INTO sources (name, {', '.join(FIELDS)}, enabled) "
                f"VALUES (?, {', '.join('?' * len(FIELDS))}, ?)",
                [s["name"]] + values + [s.get("enabled", 1)],
            )
            added += 1

    by_cadence = {r["scan_cadence"]: r["n"] for r in db.execute(
        "SELECT scan_cadence, COUNT(*) n FROM sources WHERE enabled = 1 "
        "GROUP BY scan_cadence")}
    total = db.execute("SELECT COUNT(*) n FROM sources").fetchone()["n"]

print(f"{added} added, {updated} refreshed, {total} sources in total.")
print("Enabled by cadence: " + ", ".join(
    f"{k or 'unset'}: {v}" for k, v in sorted(by_cadence.items())))
print("Roughly "
      f"{by_cadence.get('weekly', 0) * 4 + by_cadence.get('monthly', 0) + round(by_cadence.get('quarterly', 0) / 3)}"
      " scans a month.")
