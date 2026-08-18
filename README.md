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

**A gate is not a commitment.** A condition that must hold on the day you apply
is a gate, and failing one makes the company ineligible. A condition that falls
due only if the money is won — opening an operating unit in the region, hiring,
matching funds, a certification, a newco — is a commitment: it never makes the
company ineligible, it makes the verdict `conditional` and puts a decision in
front of a human. Italian schemes lean heavily on commitments, so conflating the
two would discard fundable calls in silence. `unit_required_by` on the record
carries the *when*, and `opportunity_commitments` carries what the company would
be signing up for and what it would cost.

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
  help.py          the text behind every `?`
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
  templates/
    _fields.html     one macro that renders a field with the right widget
scripts/
  seed_beadroots.py  the real profile, from confirmed facts
  seed_demo.py       invented data, for looking at the UI
  seed_sources.py    the discovery sources, idempotent by name
  smoke_test.py      end-to-end check of everything above
```

## Interface conventions

**Every `?` is a modal.** The text lives in one place (`help.py`), is served from
`/help/{key}`, and is reachable from templates as a Jinja global rather than a
macro so it also works inside other macros. An unknown key renders nothing.
The entries carry the things that are obvious only after thirty applications —
de minimis and its rolling window, gross grant equivalent, why a cap's perimeter
is quoted verbatim, how the money actually arrives, eligibility versus fit — and
each of the eight narrative sections has one saying what to write in it.

**Widgets follow one rule.** A closed set the code branches on gets a `select`;
an open set with common values gets an input plus a `datalist`, so you pick or
you type. The case that motivates it: the derived gate compares
`highest_degree == "phd"`, so a free-text "PhD" would silently drop out of the
doctorate count. One place decides (`CHILD_CHOICES`), one macro renders
(`_fields.html`), and the same macro serves both the edit modal and the add form.

**Verbatim text is kept but is not column material.** A call's own deadline
wording can run to a paragraph. The table cell shows a short label — the date if
there is one, else the type in readable words, else a clipped quotation — and the
full wording stays in the tooltip and the modal.

## The three discovery processes

**Link monitor**, nightly, no model in the loop. Fetches every link, hashes the
page, files a `flag` proposal when one dies or changes. Costs nothing, so it
runs every night and tells the scan where to look first.

**Semantic scan**, one Claude call per source with server-side web search. Runs
nightly but only touches sources whose own cadence has come round — weekly for
competitions and accelerator batches, monthly for bodies that publish one call a
year. It records facts *as written*, thresholds included, and files proposals.
A run is capped at `max_scans_per_run` sources, oldest first: adding a batch of
sources makes them all fall due on the same night, and without a ceiling the
next run would scan the lot and bury the queue. What was postponed goes to the
scan log rather than passing for a quiet night.

**Evaluator**, the one process that writes outside the queue. What it writes are
judgements, not facts: eligibility with its reasoning, the caps a call imposes
with their perimeter quoted verbatim, the commitments it would ask the company
to take on, a fit score per product line, and an effort estimate. They are advisory and recomputable; it never touches a factual
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
