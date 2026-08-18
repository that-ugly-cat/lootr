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
  main.py          FastAPI entrypoint, MCP capability-URL middleware
  version.py       commit hash shown in the footer
  auth.py          JWT cookie auth, three roles, API keys
  proposals.py     diff and approval logic
  mcp_server.py    Ono layer: 14 tools over the whole model
  routers/
    ui.py            web UI
    api.py           REST dumps and JSON CRUD
  discovery/
    profile_context.py  the profile, rendered for a prompt
    link_monitor.py     nightly, no model in the loop
    scanner.py          per-source semantic scan, per-source cadence
    verifier.py         does the record still match the page
    evaluator.py        eligibility, caps and fit per product line
scripts/
  seed_demo.py     invented data, for looking at the UI
  smoke_test.py    end-to-end check of everything above
```

## The three discovery processes

**Link monitor**, nightly, no model in the loop. Fetches every link, hashes the
page, files a `flag` proposal when one dies or changes. Costs nothing, so it
runs every night and tells the scan where to look first.

**Semantic scan**, one Claude call per source with server-side web search. Runs
nightly but only touches sources whose own cadence has come round — weekly for
competitions and accelerator batches, monthly for bodies that publish one call a
year. It records facts *as written*, thresholds included, and files proposals.

**Evaluator**, the one process that writes outside the queue. What it writes are
judgements, not facts: eligibility with its reasoning, the caps a call imposes
with their perimeter quoted verbatim, a fit score per product line, and an
effort estimate. They are advisory and recomputable; it never touches a factual
field, a status, or a manual priority. Because a verdict is only meaningful
relative to the profile it was measured against, a profile edit marks every
older verdict stale and the UI offers to re-run them.

## Roles

`reader` sees everything and changes nothing. `editor` edits the table, the
profile and the pipeline, and decides proposals. `admin` also manages users,
API keys, configuration and deletions.

## The Ono layer

MCP at `/mcp`, behind either an `X-API-Key` header or a revocable capability
URL `/mcp/k/{key}`. Read tools cover the whole model: company profile with its
derived values, products, opportunities with caps and per-product fit, pipeline,
contacts, counters, sources, proposals. Writes are deliberately narrow —
opportunities can only be *proposed*, and the one direct write is the
append-only activity diary. Approval never leaves the UI.

REST: `GET /ono/profile` and `GET /ono/opportunities` are compact dumps for LLM
consumption; `/api/opportunities` is CRUD for scripts.

## Development

```bash
python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt
python scripts/seed_demo.py
uvicorn app.main:app --reload --port 8016
```

The database is created on first boot at `./data/lootr.db`, override with
`LOOTR_DB`. Run `python scripts/smoke_test.py .` before pushing: it exercises
pages, roles, the proposals queue, REST and MCP against a throwaway database.

## Deployment

Runs on borant at port 8016, `/opt/apps/lootr`, behind Caddy. Copy
`.env.example` to `.env` on the server and fill it in.

```bash
docker compose build --build-arg GIT_COMMIT=$(git rev-parse --short=12 HEAD)
docker compose up -d
```
