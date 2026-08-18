# Lootr

Funding radar for a single company. Not just a register: the table is edited
by hand, but the tool finds new opportunities and changes to known ones on its
own and files them in a queue a human approves or rejects.

Descends from [Grant Radar](https://github.com/that-ugly-cat/grant-radar),
which does the same job for an academic. Same discovery loop, different domain
model: a company profile, product lines with their own TRL, structured
eligibility, cumulative funding caps, and a pipeline that covers investors as
well as calls.

## Design

**One deployment per company.** No multi-tenancy. The schema is domain-neutral
so a second company means a second empty database, not a fork: everything
sector- or jurisdiction-specific lives in data (`config`, `funding_counters`,
`company_qualifications`, `tag_vocabulary`, `sources`), never in column names
or hardcoded constants.

**Nothing enters the table automatically.** Every discovery output lands in
`proposals` and is approved by a human in the UI. Decided proposals are never
deleted: they are the audit log of what changed, when and why.

**The company profile is a first-class object.** It is injected into every scan
and evaluation prompt, and it is what makes a fit score possible rather than a
generic relevance guess.

**TRL lives on products, not on the company.** A call asking for TRL 6-8 may
fit one product line and not another, so eligibility is evaluated per pair of
opportunity and product.

**Cumulative caps are generalised.** De minimis is one row in
`funding_counters` alongside lifetime-raised, lifetime-equity and cascade
funding counters. A single call can impose several caps at once. The perimeter
of each cap is recorded verbatim from the call, because that wording is where
these thresholds actually bite; when it is ambiguous the verdict stays
`uncertain` rather than guessing.

**Derived values are never stored.** Company age, team composition gates,
eligible geographies, company-level TRL and counter cross-checks are computed
on read, so they cannot go stale when the underlying facts change.

## Stack

FastAPI, SQLite, HTMX + Jinja2, JWT auth, Claude with server-side web search
for discovery, Docker behind Caddy.

## Layout

```
app/
  db.py            authoritative schema, idempotent migrations, digests
  main.py          FastAPI entrypoint
  version.py       commit hash shown in the footer
  auth.py          JWT cookie auth, API keys            (to come)
  proposals.py     diff and approval logic              (to come)
  mcp_server.py    Ono layer, capability URL            (to come)
  discovery/
    link_monitor.py  nightly, no LLM                    (to come)
    scanner.py       per-source semantic scan           (to come)
    verifier.py      single-record check                (to come)
    evaluator.py     eligibility, caps and fit score    (to come)
  routers/
    ui.py            web UI                             (to come)
    api.py           REST                               (to come)
scripts/
  seed_*.py        company-specific seed, kept out of the schema
```

## Development

```bash
python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8016
```

The database is created on first boot at `./data/lootr.db`, override with
`LOOTR_DB`.

## Deployment

Runs on borant at port 8016, `/opt/apps/lootr`, behind Caddy. Copy
`.env.example` to `.env` on the server and fill it in.

```bash
docker compose build --build-arg GIT_COMMIT=$(git rev-parse --short=12 HEAD)
docker compose up -d
```
