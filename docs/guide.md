# User guide

Lootr is a funding radar for one company. It keeps every way of financing the
business on a single table — public calls, prizes, accelerators, subsidised
loans, cascade funding, investors — watches the sources on its own, and proposes
what it finds for a human to approve.

This guide is written in the order the tool is actually used: what it is, the
few ideas everything rests on, what you tell it, what it finds, how it finds it,
and how you run the work that follows.

---

## What it is

A tracker that maintains itself, up to a point.

The table is the product. Everything else — the profile, the sources, the
nightly engine, the proposals queue — exists to keep that table current without
anyone having to remember to check twenty websites every month.

Three things it does that a spreadsheet cannot:

- **It watches.** Every night it fetches the pages behind the rows it already
  tracks and notices when one dies or changes, and it searches its sources for
  things it has never seen.
- **It judges against you.** Not "is this a relevant call" in the abstract, but
  "may *this* company apply, for *which* product line, and is it worth the
  weeks it would take".
- **It shows its work.** Every judgement carries its reasoning, every threshold
  is quoted in the source's own words, and nothing enters the table without
  someone approving it.

Three things it deliberately does not do: apply on your behalf, decide anything
for you, or hide how it reached a conclusion.

---

## Fundamentals

Six ideas. Everything else follows from them.

### Nothing enters the table automatically

Every discovery — a new opportunity, a change to one, a dead link — lands in the
**proposals queue** and waits for a person. Approving is a human act, always,
including when the finding came from a machine that was right.

Decided proposals are never deleted. They are the record of what changed, when,
and why.

### Facts and judgements are different things

A **fact** is what a call says: the amount, the deadline, the eligibility
conditions. Facts enter only through an approved proposal.

A **judgement** is what the tool concludes: are you eligible, how well does this
fit, what would it cost. Judgements are written directly by the evaluator, are
always recomputable, and never touch a factual field, a status, or a priority
you set by hand.

The practical consequence: if a verdict looks wrong, re-run the evaluation. If a
*fact* looks wrong, that is an edit, and edits are yours.

### A verdict is only as current as the profile it was measured against

Change the profile and every earlier verdict becomes stale by definition —
the tool says so at the top of the table and offers to redo them. The day a
round closes or the company passes an age threshold, half the table means
something different.

### Derived values are never stored

Company age, whether the founding team is under 35 or women-led, which
geographies you qualify for, the company's highest TRL, how much room is left
under a ceiling: all computed when read, never saved. So they cannot quietly go
stale when the underlying fact changes.

This is why you record the incorporation date and not the age, birth years and
not "under 35", the date a partner left and not a smaller team.

### The wording of a threshold is part of the threshold

"Open to companies that have raised less than €500k" may or may not count public
contributions, prize money, an unconverted convertible, or money the founders
put in. Different calls count different things, and the difference decides
whether you are eligible.

So the perimeter of every ceiling is recorded **verbatim**, and when the wording
does not settle the question the verdict stays *uncertain* rather than being
guessed into place.

### A gate is not a commitment

A **gate** must hold on the day you apply. Fail one and the opportunity is out
of reach.

A **commitment** falls due only if the money is won: opening an operating unit
in the region within N months of the award, hiring, putting up matching funds,
obtaining a certification, incorporating a new company. A commitment never makes
you ineligible — it makes the verdict *conditional* and puts a decision in front
of you.

Italian schemes lean heavily on commitments. Reading one as a gate throws away a
call you could have won, in silence, which is the worst mistake this tool could
make.

---

## What you tell it: profile and products

Everything the tool judges, it judges against the profile. A thin profile does
not produce cautious answers, it produces vague ones.

### Company

The core record: legal form, country, incorporation date, size, stage, headcount
and money. Only fields that are a hard eligibility filter, an ingredient of the
scan prompt, or an input to the fit score. Everything else belongs in the
narrative sections.

Around it sit five child tables:

- **Locations.** Registered office, operating units, labs, production sites —
  each with the region code and, crucially, whether it is **registered**. A site
  you physically use but have not filed is not a site as far as a call is
  concerned, and the tool treats it that way.
- **Qualifications.** Innovative-startup register, B-Corp, ISO, an EIC Seal of
  Excellence. These are keys to other funding, not decoration.
- **Team.** Founders and staff, with birth years, residence, degree, and the
  date anyone left. Departures stay: the track record you are judged on was
  built with them.
- **Funding history.** Every round, prize and grant already received, with
  whether a convertible has actually converted.
- **Aid ledger.** Every public contribution with its **regime** and its
  **gross grant equivalent** — the benefit, not the headline figure — and the
  date of the award decision, not of the payment.

Counters sit alongside: de minimis and the other cumulative ceilings, each with
its window and its ceiling, maintained by hand and cross-checked against the
ledger. When the two disagree, the profile page says so.

### Narrative

Eight free-text sections that go into every scan and evaluation prompt: pitch,
technology, IP, market, traction, track record, **strategy for the next twelve
months**, and exclusions.

Two of them earn their keep faster than the rest. **Strategy** is what points
the search at what you need now rather than at funding in general. **Exclusions**
is the cheapest way to reduce noise: say what you do not want and you stop being
shown it.

### Products

Maturity belongs to a product line, not to a company. A call wanting TRL 6-8 can
suit one line and exclude another, so eligibility and fit are evaluated per pair
of opportunity and product line.

Each line carries its TRL, the **evidence** for that number — reused across
applications, so writing it once is worth it — its IP position, its regulatory
framework, and its target segments. The company's TRL, where it is needed, is
the highest among active lines: derived, not stored.

---

## Opportunities: the table

One row is one way of getting money. Rows arrive two ways: the engine proposes
them and you approve, or you add them by hand. Once in the table there is no
difference between the two.

### Calls and investors

Two kinds of row, one table, a filter between them.

**Calls** have a deadline logic: grants, prizes, subsidised loans, programmes,
vouchers, cascade funding. **Investors** are equity and convertibles, where
there is no deadline at all — only a thesis to match and a next step to take.

The columns change with the filter, because the difference is real: a call has
an amount and a deadline, an investor a ticket and a next action. Unfiltered you
see both, sorted by whatever happens next, with rows that have neither date at
the bottom. The split is derived from the instrument and the provider type, not
typed by hand.

### Reading a row

**Eligibility verdict** — four values:

| Verdict | Means | What to do |
|---|---|---|
| `eligible` | Every hard condition is met | Decide whether it is worth the work |
| `not_eligible` | At least one gate fails | Nothing, unless a fact is wrong |
| `conditional` | You may apply *if* you take something on | A decision: see the commitments |
| `uncertain` | A condition could not be established | Research: the rationale says what to check |

The last two look similar and are not. **Uncertain is ignorance**, and the fix
is to go and read something. **Conditional is a decision**, and the fix is
someone in the company saying yes or no.

**Fit score**, 0-100, is a different question from eligibility. Eligibility says
you *may* apply; fit says whether you *should* — is the theme right, is the
amount worth the effort, does the timing suit, is the track record competitive.
It weighs how the money actually arrives: an award paid only on reimbursement
after the spend can be useless on a short runway, while a smaller one with an
advance is not.

**Caps** are the ceilings this call imposes on what you have already received —
de minimis, or a lifetime-raised threshold. Each one names the counter, the
threshold, and the perimeter quoted from the source.

**Commitments** are what you would take on if funded, each with the requirement
in the call's own words, when it falls due, and an estimate of what it would
cost this company.

**Product fit** scores each active line separately, with its own reasoning.
Company-level money — a round, a hire, a certification, advice — is marked
*general* and is not scored per line at all.

### Status and priority

`status` tracks where a row is in your process, from *watching* to *won* or
*lost*. `priority` is yours alone: no automated process ever touches it, unlike
the fit score, which is a machine estimate and gets recomputed.

Two buttons on each row do work on demand: **verify** re-reads the call's page
and files any discrepancy as a proposal, and **evaluate** re-runs the judgement
against the current profile.

---

## Sources

A source is a **publisher**, not a call: Invitalia, the EIC, a regional agency,
a bucket of investors. The engine reads the hints and finds the individual
opportunities underneath.

Each source carries a name, a URL, a geography and instrument hint, free-text
search hints, and a **cadence**.

**Cadence is a cost decision as much as an editorial one.** Every source that
falls due is one model call with web search behind it. Weekly is for channels
with short windows — cascade calls, competitions. Monthly suits a body that
publishes one call a year. Quarterly suits publishers that move once a season,
investors above all, where there is no deadline to miss.

Two things worth knowing:

- **A source can be switched off without being deleted.** A channel that is
  closed for a reason — a region where you have no registered unit — is better
  kept as a disabled row with the reason written in its hints than removed and
  forgotten. It greys out in the list and switches back on with one click.
- **The hints are where you steer.** If a source keeps returning things you do
  not want, the fix is almost always a sentence in its hints, not a change to
  the engine.

---

## The discovery engine and the queue

Four processes, three of them nightly.

**Link monitor**, 03:00, no model involved. Fetches every tracked link, hashes
the page, and files a `flag` proposal when one dies or its content changes. It
costs nothing, so it runs every night and tells you where to look first.

**Semantic scan**, 04:00. One model call per due source, with web search. It
reads the company profile and the digest of what is already tracked for that
source, then files `new` and `update` proposals. It records facts **as written**,
thresholds included, and does not interpret them.

A run is capped — six sources by default, oldest first. Adding a batch of
sources makes them all fall due on the same night; without a ceiling the next
run would scan the lot and bury the queue. What gets postponed is written to the
scan log, so a capped night does not read like a quiet one.

**Verifier**, on demand. Does the page still say what we recorded? Differences
become an `update` proposal.

**Evaluations**, 05:00, over the rows the last profile change made stale.

### The queue

Every proposal shows what it would change, why, the page it came from, and a
confidence. Updates show a field-by-field diff against what is stored.

Approve and the facts enter the table. Reject and the proposal stays in the
record, marked rejected. Nothing is ever lost, including the things you decided
against — a call rejected twice for the same reason is worth a line in the
exclusions narrative.

A rough rule for reading confidence: `low` means the engine could not establish
something and said so in the rationale. Read the rationale before the fields.

---

## Pipeline

The table says what exists. The pipeline says what you are doing about it.

An **application** ties an opportunity to the product lines it covers — or to
none, when the money is company-level — and carries its status, the amounts
requested and awarded, the submission and outcome dates, and the **next action**
with its due date. The page sorts by that date, so what is late is at the top.

**Activities** are an append-only diary per opportunity: a call, an email, a
meeting, a pitch, an intro, a submission. On the investor side this is the whole
game, because there is no deadline to organise around — only the record of what
was said and what comes next.

**Contacts** are the people: name, organisation, role, and how warm the
relationship is, optionally tied to an opportunity, with a note on who could
introduce you. A warm introduction is worth more than a good application, and it
is the piece most often kept in someone's head instead of the tool.

---

## MCP integration

The whole model is reachable from an assistant, over MCP.

**Reading is wide.** Fourteen tools cover the company profile with its derived
values, the product lines, the counters, opportunity search with a fit floor,
the full detail of one opportunity including caps, commitments, product fit,
applications, diary and contacts, upcoming deadlines, next actions, sources and
the pending queue.

**Writing is deliberately narrow.** `propose_opportunity` and `propose_update`
enter the same queue as everything the engine finds, tagged as coming from the
assistant. The only direct write is `log_activity`, which is append-only,
because without it the investor side would be unusable from a conversation.

**Approving is only ever done in the UI.** No exception, and no tool for it.

The connection is a capability URL — a single revocable address that carries its
own key — generated in the admin page. Anyone holding it can read the whole
radar, so it is treated like a password: one per client, revoked rather than
reused. There are also two plain REST dumps for scripts, and a JSON CRUD
endpoint for the table.

---

## Admin

Three things live here.

**Users and roles.** `reader` looks, `editor` edits and decides proposals,
`admin` also manages users, keys, configuration and deletions. With several
people around one table the distinction is worth keeping: deciding a proposal is
an editorial act, and deleting a row is not something to do by accident.

**API keys**, for MCP and the REST dumps. Shown once at creation, revocable at
any time.

**Configuration**, which is data rather than constants:

| Key | What it does |
|---|---|
| `scan_model` | The model the engine runs on. New models can be typed in; the field suggests the current ones |
| `default_scan_cadence` | Fallback for a source with none |
| `max_scans_per_run` | How many sources one nightly run may touch. `0` removes the limit |
| `base_currency` | Reporting currency |
| `company_display_name` | Shown in the header; empty falls back to the legal name |

---

## In short

Tell it who you are, honestly and in detail. Tell it where to look. Read the
queue every few days and approve what belongs. Then use the table to decide, and
the pipeline to remember.

The tool is good at watching and at arguing a case against your profile. It is
not good at knowing what you have not written down.
