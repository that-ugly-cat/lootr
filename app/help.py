"""Explanations behind the `?` buttons.

This is where the institutional knowledge lives: the things that are obvious
once someone has written thirty applications and opaque before that. Keep each
entry short enough to read standing up, and say what the field is *for*, not
just what it contains.

Bodies are HTML fragments. Keys are referenced from templates via the `help()`
macro in _macros.html.
"""

HELP: dict[str, tuple[str, str]] = {

    # --- the tool itself ---------------------------------------------------

    "proposals_queue": ("The proposals queue", """
        <p>Discovery never edits the table. Everything it finds — a new
        opportunity, a changed deadline, a dead link — is filed here as a
        proposal, showing what it would change and why, and waits for a person.</p>
        <p>Approving is the only path into the opportunities table. Decided
        proposals are never deleted: together they are the record of what
        changed, when, and on what evidence.</p>"""),

    "roles": ("Roles", """
        <p><strong>Reader</strong> sees everything and changes nothing.
        <strong>Editor</strong> edits the table, the profile and the pipeline,
        and decides proposals. <strong>Admin</strong> also manages users, API
        keys, configuration and deletions.</p>"""),

    "api_keys": ("API keys and the capability URL", """
        <p>One key opens both the REST dumps (as an <code>X-API-Key</code>
        header) and the MCP surface. MCP clients that cannot send headers can
        use the capability URL instead: the key sits in the path, so the URL
        <em>is</em> the credential. Treat it like a password and revoke it if it
        leaks — revoking takes effect immediately.</p>"""),

    "sources": ("Sources", """
        <p>Where discovery looks. Each source is a funding body or portal plus
        hints about what to look for there.</p>
        <p>A source is only useful if its pages are public and indexed. A
        directory behind a paywall cannot be searched, however rich it is.</p>"""),

    "scan_cadence": ("Scan cadence", """
        <p>How often this source is swept. Monthly suits bodies that publish one
        call a year. Competitions and accelerator batches move faster and open
        windows that can be two weeks wide, so they deserve weekly.</p>"""),

    "calls_vs_investors": ("Calls and Investors", """
        <p>Two readings of the same table.</p>
        <p><strong>Calls</strong> is everything with a deadline logic: grants,
        prizes, subsidised loans, programmes. Sorted by the next date.</p>
        <p><strong>Investors</strong> is equity and convertibles, where there is
        no deadline at all — only a thesis to match and a next step to take. It
        is sorted by the next action, because that is the only clock there is.</p>"""),

    # --- the company profile -----------------------------------------------

    "profile": ("Why the profile matters", """
        <p>Every judgement the tool makes is made against this profile: whether
        you are eligible, which product line a call fits, how much of a ceiling
        the money would eat. It is injected verbatim into every scan and every
        evaluation.</p>
        <p>What is missing here is missing from the judgement.</p>"""),

    "derived": ("Derived, not stored", """
        <p>Company age, team composition gates, eligible geographies and the
        highest active TRL are computed every time they are read, from the
        underlying rows.</p>
        <p>They are never saved as fields, so they cannot quietly go stale: the
        day someone leaves the team or a product advances, everything that
        depends on it changes with it.</p>"""),

    "locations": ("Locations", """
        <p>Regional eligibility is decided here. Many schemes require not just a
        presence in the region but a <strong>formally registered</strong>
        operating unit, filed with the company register.</p>
        <p>A laboratory you use but have not registered does not open that
        region's calls, so the registered flag is a real gate, not paperwork.</p>"""),

    "location_kind": ("Kind of location", """
        <p>What this address <em>is</em>, in the eyes of the company register: the
        registered office, an operating unit, a laboratory, a production site.</p>
        <p>Calls almost never ask for "a presence". They ask for a registered
        office in the territory, or an operating unit, and those are different
        filings with different consequences.</p>"""),

    "region_code": ("Region code", """
        <p>The machine-readable identifier of the region, so eligibility can be
        matched without depending on how a name is spelled.</p>
        <p>Italian examples: <code>ITF4</code> is Puglia, <code>ITH3</code> is
        Veneto, <code>ITC4</code> is Lombardia. A call that says it is open to
        <code>ITF</code> means the whole South, and a code that starts with the
        same letters is inside it.</p>"""),

    "code_system": ("Code system", """
        <p>Which catalogue the code above comes from. <strong>NUTS</strong> is the
        EU's statistical hierarchy of regions and it is what European and Italian
        calls use. <strong>ISO 3166-2</strong> is the international alternative.</p>
        <p>Recording the system alongside the code is what keeps the field
        portable: a company outside the EU has regions too, they are just not
        numbered by Eurostat.</p>"""),

    "registered": ("Registered", """
        <p>Whether this location is formally filed with the company register, not
        merely used.</p>
        <p>It is a hard gate. A laboratory you work in every day but have never
        registered does not open that region's calls, and the tool leaves that
        region out of the eligible list until the flag is set.</p>"""),

    "is_general": ("General", """
        <p>Some money is not about a product at all: an investor round, support
        for a hire, a voucher for advice, a certification cost. Marking an
        opportunity as general says there is no product line to match it
        against, so it is judged at company level instead.</p>
        <p>On an application it means the same thing: the request covers the
        company, not one line.</p>"""),

    "qualifications": ("Qualifications", """
        <p>Legal statuses, certifications and labels that have a validity
        window: an innovative-startup registration, a B-Corp certification, an
        ISO standard, an EIC Seal of Excellence.</p>
        <p>They live in their own table rather than as fixed fields because they
        differ by country and because they expire. Some of them are themselves
        keys to other funding, which is why a call can require one by name.</p>"""),

    "team_gates": ("Team gates", """
        <p>A surprising number of calls turn on who is on the team: a female
        founder, founders under 35, residence in a given region, staff holding a
        doctorate. Some of these are hard eligibility conditions, others are
        scoring points.</p>
        <p>They are computed from the team table counting only people who have
        not left, so a departure changes them the moment it is recorded.</p>"""),

    "products": ("Product lines", """
        <p>Maturity belongs to the product, not to the company. A call asking for
        TRL 6–8 may fit the line that is in field trials and exclude the one
        still in the lab.</p>
        <p>So eligibility and fit are evaluated for each pair of opportunity and
        product line, and an application is always filed for one specific line.</p>"""),

    "trl": ("TRL", """
        <p>Technology Readiness Level, 1 to 9: from a basic principle observed
        (1) to a system proven in its operational environment (9). Roughly, 4–5
        is validated in the lab, 6–7 demonstrated in the real setting, 8–9 on the
        market.</p>
        <p>Most public instruments state the TRL band they fund, and it is one of
        the few filters that is genuinely mechanical.</p>"""),

    "trl_evidence": ("TRL evidence", """
        <p>Every application asks you to justify the level you claim, and the
        same paragraph gets rewritten from scratch each time.</p>
        <p>Write it once here and reuse it. It is also a defence: claiming TRL 7
        without being able to document it is a well-worn way to fail an
        assessment.</p>"""),

    "regulatory": ("Regulatory framework and status", """
        <p>Two different things. The <strong>framework</strong> is which regime
        the product falls under; the <strong>status</strong> is how far along
        that path you are.</p>
        <p>It matters twice: it gates market access, and the work of getting
        through it is an activity that several instruments will happily fund.</p>"""),

    "ip": ("IP status", """
        <p>Filed, granted, or nothing yet — and for whom. Where a product depends
        on someone else's application as well as your own, record that here: the
        right to use it is a question an assessor and an investor will both
        ask.</p>"""),

    "narrative": ("Narrative sections", """
        <p>Free text, injected verbatim into the prompts.</p>
        <p><strong>Track record</strong> earns its place because many calls score
        the applicant's history. <strong>12-month strategy</strong> points the
        search at what is needed now rather than at funding in general.
        <strong>Exclusions</strong> is what you do not want, and it cuts noise
        before it reaches the queue.</p>"""),

    # --- the narrative sections, one each: these are the fields nobody knows
    # how to fill in until someone says what they are for.

    "narrative_pitch": ("Pitch", """
        <p>What the company does, in the words you would use to someone who has
        never heard of it. Two or three sentences: the problem, what you make,
        what it changes.</p>
        <p>This is the first thing the search reads, and it decides what counts
        as "relevant" for everything that follows. Write it plainly — a pitch
        heavy with slogans searches worse than one that says what the thing
        is.</p>"""),

    "narrative_technology": ("Technology", """
        <p>How it actually works, and where each product line stands. Materials,
        process, what is proven and what is not.</p>
        <p>It matters because thematic calls are written in technical vocabulary.
        A call about biobased materials, or water use efficiency, or circular
        bioeconomy will only match you if the words that describe your technology
        are here.</p>"""),

    "narrative_ip": ("IP", """
        <p>What is filed, what is granted, what is somebody else's. Include
        dependencies on third-party applications and any licence you rely on.</p>
        <p>Two uses: instruments that fund patenting and IP extension can only be
        matched if the position is written down, and an assessor or an investor
        will ask the freedom-to-operate question early.</p>"""),

    "narrative_market": ("Market", """
        <p>Who buys, how they buy, and how big that is. Segments, channel,
        pricing if you have it, the geography you sell into now versus the one
        you are aiming at.</p>
        <p>Public instruments increasingly score commercial credibility, not just
        technical merit — and the difference between a domestic and an export
        ambition opens or closes a whole family of internationalisation
        schemes.</p>"""),

    "narrative_traction": ("Traction", """
        <p>The evidence that this is working: field trials and their results,
        pilots, letters of intent, first sales, partnerships, users.</p>
        <p>Almost every application has a section that this text answers, and
        keeping it current here means writing it once instead of reconstructing
        it under deadline.</p>"""),

    "narrative_track_record": ("Track record", """
        <p>Prizes, programmes, accelerators, grants already won, academic
        partners, the founders' credentials.</p>
        <p>A great many calls score the applicant's history explicitly. This is
        also how the fit score can tell you that you would be competitive for a
        particular competition rather than merely eligible for it.</p>"""),

    "narrative_strategy_12m": ("12-month strategy", """
        <p>What the money is actually for, over the coming year. A pilot plant, a
        hire, extending the IP, a regulatory step, a round, first revenue.</p>
        <p><strong>This is the highest-value section in the profile.</strong>
        Without it the search looks for funding in general; with it, it looks for
        what you need now. A call that fits the company but funds something you
        are not doing this year is a bad find, and only this section lets the
        tool tell the difference.</p>"""),

    "narrative_exclusions": ("Exclusions", """
        <p>What you do <em>not</em> want, so it stops arriving. Anything you would
        reject on sight, whatever its merits.</p>
        <p>Typical entries: no equity below a certain valuation; nothing that
        requires relocating or opening an office elsewhere; no scheme paid only
        on reimbursement, given the runway; nothing that needs a paid consultant
        to file; no defence or dual-use funders; nothing under a certain amount,
        because the paperwork costs more than the money.</p>
        <p>It is the cheapest section to fill and the one that most reduces
        noise: an exclusion written here is a proposal that never reaches the
        queue, rather than one you reject over and over.</p>"""),

    "funding_history": ("Funding history", """
        <p>Rounds and investments received. Whether a convertible has actually
        converted is a separate flag because several calls cap the equity raised
        to date, and an unconverted note usually does not count as equity yet.</p>"""),

    "aid_ledger": ("Public aid ledger", """
        <p>Every public contribution received, with the regime it was granted
        under and its gross grant equivalent.</p>
        <p>It fills up on its own as applications are won through the tool, and
        it is what the cumulative counters are checked against.</p>"""),

    # --- money and ceilings -------------------------------------------------

    "counters": ("Cumulative caps", """
        <p>Ceilings that apply across everything you have received, rather than
        to one call. De minimis is one of them; the others track how much you
        have raised in total, in equity, in public grants, and in EU cascade
        funding.</p>
        <p>Most have no universal ceiling of their own: each call sets its own
        threshold against them. The figures here are maintained by hand, with
        what the ledgers say shown beside them as a cross-check.</p>"""),

    "de_minimis": ("De minimis", """
        <p>EU law forbids public aid that distorts competition unless it is
        authorised. De minimis is the exception for amounts small enough to be
        presumed harmless: below the ceiling, a state can grant them freely.
        Most small and mid-sized national and regional contributions run on
        this track.</p>
        <p>The ceiling applies to a rolling window counted backwards from the
        date of each new award, not to a calendar year — so headroom
        regenerates continuously as old aid ages out of the window.</p>
        <p>Two things people get wrong: what counts is the gross grant
        equivalent rather than the face value, and the clock starts at the
        award decision rather than at payment.</p>
        <p>The authoritative figure is the extract from the national state-aid
        register, not this field. What you see here is a working estimate.</p>"""),

    "gge": ("Gross grant equivalent", """
        <p>The actual advantage an aid confers, expressed as if it had been a
        straight cash grant.</p>
        <p>For a non-repayable contribution it equals the amount. For a
        subsidised loan or a guarantee it is only the benefit component,
        computed against market rates — which is why a large soft loan can eat
        far less of a ceiling than its headline figure suggests.</p>"""),

    "opportunity_caps": ("Caps on this opportunity", """
        <p>Thresholds this particular call imposes on a cumulative counter: it
        consumes de minimis, or it is open only to companies that have raised
        less than a stated amount. One call can carry several at once.</p>"""),

    # --- the opportunity form, field by field ---------------------------------
    # Written for the person filling a row in by hand after the scanner got
    # something wrong. Each one carries the thing that is obvious only after a
    # few applications, not a restatement of the label.

    "title": ("Title", """
        <p>The scheme's own name, as the call writes it — <em>Smart&amp;Start
        Italia</em>, not <em>Invitalia loan</em>.</p>
        <p>It is what the scanner matches against when it decides whether
        something it found is already tracked, so a name of your own invention
        produces a duplicate the next time the source is scanned.</p>"""),

    "provider": ("Provider", """
        <p>Who actually grants the money, not who publicises it. A regional
        call announced by a chamber of commerce but decided by the region is
        the region's.</p>
        <p>The box suggests providers already recorded: pick one rather than
        retyping, or the two spellings become two providers when you filter.</p>"""),

    "link": ("Link", """
        <p>The call's own page — not a news article about it, not the
        provider's home page.</p>
        <p>This is the page the nightly link monitor fetches and hashes: a link
        to a press release means it watches the press release, and the day the
        call's terms change nothing is flagged.</p>"""),

    "description": ("Description", """
        <p>What the money is for, in a couple of sentences, in your own words.
        Prose belongs here — the structured fields around it are read by
        code.</p>"""),

    "amount_min": ("Amount range", """
        <p>What a single beneficiary can receive, not the call's total budget —
        that has its own field.</p>
        <p>Leave blank rather than guessing: an invented range distorts the fit
        score, which weighs the amount against the work of applying.</p>"""),

    "amount_max": ("Amount range", """
        <p>The ceiling per beneficiary. Read it against the funding rate: a
        scheme paying 50% of costs up to 200k means a 400k project, and the
        other 200k is yours to find.</p>"""),

    "currency": ("Currency", """
        <p>Three-letter code for the amounts on this row. Nothing converts
        automatically; a row in one currency compared against a counter in
        another is your own arithmetic to do.</p>"""),

    "funding_rate_pct": ("Funding rate", """
        <p>The share of eligible costs the scheme pays. 80% means you fund the
        other 20% yourself, which is what the co-financing field records.</p>
        <p>Watch for rates that vary by region or by company profile — the
        headline rate is often the best case. Put the conditions in other
        requirements, verbatim.</p>"""),

    "cofinancing_pct": ("Co-financing", """
        <p>What you must put in, as a share of the project. Cash you have to
        find before the money arrives, so it decides whether an award is
        actually usable.</p>
        <p>Some schemes accept own labour or in-kind contributions here and
        some demand cash: that distinction lives in other requirements.</p>"""),

    "advance_available": ("Advance available", """
        <p>Whether any of the money arrives before you spend it.</p>
        <p>On a short runway this decides more than the amount does: a smaller
        award paid up front is usable, a larger one paid on reimbursement after
        the spend may not be. The conditions attached to an advance — a bank
        guarantee, a milestone, a signed contract — go in other requirements,
        not in this flag.</p>"""),

    "call_total_budget": ("Total call budget", """
        <p>How much the call is handing out overall. Free text, because sources
        write it in wildly different ways.</p>
        <p>Read together with the deadline type: a large per-company amount out
        of a small total budget on a first-come basis is a race, not a
        deadline.</p>"""),

    "deadline_date": ("Next deadline", """
        <p>The next date that actually closes a submission window. For a
        rolling scheme leave it empty — a made-up date sorts the table
        wrongly and produces false urgency.</p>"""),

    "deadline_text": ("Deadline as written", """
        <p>The call's own wording, however long. Sportello formulations often
        run to a paragraph, and the paragraph is where the conditions live.</p>
        <p>The table shows a short label and keeps this text in the tooltip and
        the modal: verbatim is preserved, but it is not column material.</p>"""),

    "cutoff_dates": ("Cut-off dates", """
        <p>A JSON array of dates, for schemes that stay open but evaluate in
        batches: <code>["2026-03-31","2026-09-30"]</code>.</p>
        <p>Missing a cut-off usually costs months rather than the
        opportunity — which is exactly why it is worth recording.</p>"""),

    "recurrence_logic": ("Recurrence", """
        <p>Whether this comes back, and on what rhythm. A call that reopens
        every year is worth preparing for even after the current window
        closes.</p>"""),

    "opens_at": ("Opens at", """
        <p>When submissions start. A window that opens in two months and closes
        two weeks later is a preparation deadline today.</p>"""),

    "decision_lag_months": ("Decision lag", """
        <p>How long from submission to an answer. This, plus the disbursement
        shape, is when the money could realistically arrive — usually much
        later than the deadline suggests.</p>"""),

    "project_duration_months": ("Project duration", """
        <p>How long the funded project must run. A short runway plus a long
        mandatory duration is a commitment, not just a timeline.</p>"""),

    "eligible_geographies": ("Eligible geographies", """
        <p>Where the money can be spent or the beneficiary must be, as a JSON
        array with the coding system named:
        <code>[{"code":"ITF","system":"NUTS"}]</code>.</p>
        <p>The system matters: <em>ITF</em> is a NUTS macro-region, not a
        country code, and comparing the two silently produces nonsense.</p>"""),

    "requires_unit_in": ("Requires a unit in", """
        <p>The region or country where the scheme wants an operating unit.
        Whether it must already exist is the next field, and that is the
        distinction that decides eligibility.</p>"""),

    "unit_deadline_months": ("Months to open it", """
        <p>How long after the award you would have to open the required unit.
        Only meaningful when the requirement is a commitment rather than a
        gate — see the field above.</p>"""),

    "max_company_age_years": ("Max company age", """
        <p>The age ceiling for applicants. Company age is derived from the
        incorporation date, never stored, so this comparison stays true as
        time passes.</p>
        <p>Check what the call counts from: incorporation, VAT registration, or
        entry in a special register are three different dates.</p>"""),

    "requires_partners": ("Partners required", """
        <p>Whether you must apply with someone else — a research organisation,
        another company, a consortium.</p>
        <p>For a two-person team this usually changes the answer more than the
        amount does: it turns a form into months of partner-finding.</p>"""),

    "partner_requirements": ("Partner requirements", """
        <p>Who those partners must be, in the call's own terms: how many, from
        which countries, what kind of organisation, who may lead.</p>"""),

    "trl_min": ("TRL range", """
        <p>The maturity band the call funds. Compared against each product
        line's own TRL, not the company's — a call wanting TRL 6-8 can suit one
        line and exclude another.</p>
        <p>A line below the range is often the more fixable case: the evidence
        for a higher TRL may already exist and simply not be written down.</p>"""),

    "trl_max": ("TRL range", """
        <p>The top of the maturity band. Above it, the call considers the
        technology already market-ready and will fund something else.</p>"""),

    "eligible_sme_sizes": ("Eligible sizes", """
        <p>Which company sizes may apply, in the EU definition — micro, small,
        medium, large.</p>
        <p>The definition counts headcount <em>and</em> turnover or balance
        sheet, and it counts linked and partner companies too: an investor with
        a large holding can push a small company out of the category.</p>"""),

    "sector_tags": ("Sector tags", """
        <p>What the call is about, in the shared vocabulary. Used to spot
        thematic fit at a glance and to search the table.</p>
        <p>Pick from the list where you can. A tag typed fresh every time
        becomes three near-synonyms that never filter together.</p>"""),

    "impact_focus": ("Impact focus", """
        <p>The outcome the call is buying — water efficiency, soil health,
        climate adaptation. Often the deciding factor in scoring, and the place
        where an application is won or lost on framing rather than merit.</p>"""),

    "other_requirements": ("Other requirements", """
        <p>Everything the structured fields cannot hold, <strong>in the source's
        own words</strong>: cumulative ceilings, conditions attached to an
        advance, obligations that fall due after the award, exclusions.</p>
        <p>Do not paraphrase. The evaluator reads this text to build the caps
        and commitments, and the exact wording is what decides whether a
        threshold bites.</p>"""),

    "ticket_min": ("Ticket size", """
        <p>What this investor actually writes, per company. Only relevant on
        equity and convertible rows.</p>
        <p>A fund whose ticket starts well above what you are raising is not a
        near miss — it is a different stage, and worth recording as such rather
        than chasing.</p>"""),

    "ticket_max": ("Ticket size", """
        <p>The upper end of the cheque. Together with the minimum it says
        whether you are the right size for this investor at all.</p>"""),

    "stage_focus": ("Stage focus", """
        <p>The stage this investor backs. Stage labels mean different things to
        different funds: what one calls seed another calls pre-seed, so read it
        with the ticket size rather than on its own.</p>"""),

    "sector_focus": ("Sector focus", """
        <p>What the fund invests in, in its own words. Useful for the honest
        version of the question: are you in their thesis, or would you be the
        exception they have to argue for internally?</p>"""),

    "geo_focus": ("Geography focus", """
        <p>Where the fund invests. Some are restricted by their own mandate —
        a fund with public money behind it often cannot invest outside its
        region, whatever it thinks of the company.</p>"""),

    "lead_or_follow": ("Lead or follow", """
        <p>Whether they can set terms and price a round, or only join one
        someone else leads.</p>
        <p>A round with no lead does not close. A list of enthusiastic
        followers is not a round.</p>"""),

    "source_id": ("Source", """
        <p>Which tracked source this came from. It scopes the nightly scan: the
        source sees its own rows in the digest, so it can tell a genuinely new
        find from something already recorded.</p>
        <p>A row with no source is still scanned against, but nothing goes
        looking for updates to it on its own.</p>"""),

    "priority": ("Priority", """
        <p>Your call, not the tool's. The fit score is a machine estimate and
        gets recomputed; this field is never touched by any automated
        process.</p>"""),

    "best_fit_product_id": ("Best-fit product", """
        <p>Which product line this opportunity suits best. Set by the evaluator
        when it scores the lines, and overridable here.</p>
        <p>Left empty on company-level money — a round, a hire, a
        certification — which is what the <em>general</em> flag marks.</p>"""),

    "requires_qualification": ("Required qualifications", """
        <p>Registrations and certifications a call takes as a precondition:
        innovative-startup status, a B-Corp certificate, an ISO standard, an EIC
        Seal of Excellence.</p>
        <p>The list offers what the company profile actually records, so a call
        cannot ask for something the tool has no way of checking. If a call
        requires a qualification that is missing from the list, add it to the
        profile first — that is also where its expiry date lives.</p>"""),

    "commitments": ("Commitments, not gates", """
        <p>What the company would have to take on if this money were won:
        opening an operating unit in the region, hiring, putting up matching
        funds, obtaining a certification, incorporating a new company.</p>
        <p>A <em>gate</em> has to hold on the day you apply, and failing one
        makes the opportunity out of reach. A <em>commitment</em> falls due
        later, so it never makes you ineligible — it makes the verdict
        <em>conditional</em> and puts a decision in front of you. Reading a
        commitment as a gate silently throws away calls you could win, which is
        why the two are kept apart.</p>
        <p>Each one carries the requirement in the call's own words, when it
        falls due, and an estimate of what taking it on would cost.</p>"""),

    "unit_required_by": ("When the unit has to exist", """
        <p>Most Italian schemes do not require an operating unit in the region
        on the day you apply: they require an undertaking to open one within a
        set number of months of the award.</p>
        <p><em>At application</em> is the only value that makes the requirement
        a gate. Anything later makes it a commitment, and the months are how
        long you would have. When a call does not say, this stays empty and the
        eligibility verdict stays <em>uncertain</em> rather than assuming in
        either direction.</p>"""),

    "scope_note": ("Why the wording is quoted", """
        <p>The trap in these thresholds is not the number, it is the
        definition. "Less than €500k raised" may or may not include public
        contributions, prize money, unconverted convertibles or founder
        contributions, and different calls count different things.</p>
        <p>So the perimeter is recorded in the source's own words rather than
        normalised, and when it is ambiguous the verdict stays
        <em>uncertain</em> instead of guessing.</p>"""),

    "aid_regime": ("Aid regime", """
        <p>Which state-aid track the money travels on. De minimis consumes that
        ceiling; block-exempted and individually notified schemes have their own,
        much higher limits and leave de minimis untouched; an investment on
        market terms is not aid at all.</p>
        <p>This is what decides whether the de minimis check even applies, so it
        is worth getting right.</p>"""),

    "funding_rate": ("Funding rate and co-financing", """
        <p>The funding rate is the share of eligible costs the instrument
        covers. Co-financing is what you have to put in yourself — in cash,
        usually, and on your own timetable.</p>"""),

    "disbursement": ("How the money actually arrives", """
        <p>Often the field that decides. An advance means cash up front; payment
        on milestones means cash in tranches against reported progress;
        reimbursement on report means you spend everything first and are repaid
        afterwards, sometimes a year later.</p>
        <p>A large award paid only on reimbursement can be out of reach for a
        company with a short runway, while a smaller one with an advance is
        not.</p>"""),

    "dilutive": ("Dilutive", """
        <p>Whether taking the money costs you equity. Grants, prizes, subsidised
        loans and vouchers do not; investors and most accelerator programmes
        do. It is defaulted from the instrument and can be overridden.</p>"""),

    # --- the opportunity record ---------------------------------------------

    "instrument": ("Instrument", """
        <p>What kind of money it is: a grant, a subsidised loan, a tax credit, a
        guarantee, a prize, a programme place, hiring support, a voucher,
        cascade funding, equity, a convertible, or support in kind.</p>
        <p>It drives which view the opportunity appears in and whether it
        dilutes.</p>"""),

    "provider_type": ("Provider type", """
        <p>Who is behind the money: a supranational body, a national or regional
        authority, a foundation, a corporate, a fund, an angel, an accelerator or
        a bank. It is a useful filter because providers of the same type tend to
        behave alike in timing, paperwork and what they ask for.</p>"""),

    "deadline_type": ("Deadline type", """
        <p><strong>Fixed</strong> is a single closing date. <strong>Cut-offs</strong>
        means several evaluation windows across the year.
        <strong>Rolling</strong> means applications are taken continuously.
        <strong>Open until funds are exhausted</strong> looks like no deadline
        and behaves like an urgent one: the money runs out when it runs out.</p>"""),

    "eligibility": ("Eligibility verdict", """
        <p>Whether the company qualifies at all, judged against the profile, with
        the reasoning spelled out point by point.</p>
        <p>Four values. <em>Eligible</em> and <em>not eligible</em> speak for
        themselves. <em>Conditional</em> means you may apply provided you take
        something on — see the commitments listed below it. <em>Uncertain</em>
        means a condition could not be established, and the rationale says what
        to go and check.</p>
        <p>It is re-run when the profile changes, because the day a round closes
        or the company passes an age threshold, half the table means something
        different.</p>"""),

    "fit_score": ("Fit score", """
        <p>How well this opportunity matches the company and its products,
        beyond bare eligibility: whether the theme is right, whether the amount
        and the timing are useful, whether the track record is competitive.</p>
        <p>Eligibility says you <em>may</em> apply. Fit says whether it is worth
        the weeks it would take.</p>"""),

    "product_fit": ("Fit per product line", """
        <p>The same call can suit one product line and exclude another, most
        often on TRL. Each line is evaluated separately, and the score shown in
        the table is the best of them.</p>"""),

    "effort": ("Effort", """
        <p>What applying would actually cost you in work. A small award with a
        heavy dossier is a bad trade for a team of two, and it also burns
        ceiling headroom that a larger one could have used.</p>"""),

    "status": ("Status", """
        <p>Where this opportunity stands for you: watching, shortlisted, being
        prepared, submitted, awaiting an outcome, won, lost, expired or
        discarded.</p>
        <p>The <em>open</em> filter means not closed by hand and not past due.
        Rows with no deadline at all — investors, rolling schemes — count as
        open.</p>"""),

    # --- pipeline -------------------------------------------------------------

    "applications": ("Applications", """
        <p>An opportunity is a thing in the world. An application is your attempt
        at it: for one product line, with an amount, an owner and a next step.</p>
        <p>The same opportunity can be attempted more than once, in different
        years or for different lines.</p>"""),

    "activities": ("The diary", """
        <p>What was said and when: calls, emails, meetings, pitches,
        introductions, submissions.</p>
        <p>It carries the investor branch, where there is no deadline to sort
        by and the only state that matters is the history of contact and the
        next step. Entries are append-only.</p>"""),

    # --- aliases, so the generic profile forms can ask for help by field name

    "kind": ("Kind of location", """
        <p>What this address <em>is</em>, in the eyes of the company register: the
        registered office, an operating unit, a laboratory, a production site.</p>
        <p>Calls almost never ask for "a presence". They ask for a registered
        office in the territory, or an operating unit, and those are different
        filings with different consequences.</p>"""),

    "regime": ("Aid regime", """
        <p>Which state-aid rule this contribution was granted under. It decides
        which ceiling it counts against — and whether it counts at all.</p>
        <p><strong>de_minimis</strong> consumes the de minimis allowance.
        <strong>block_exempted</strong> and <strong>notified</strong> have their
        own, much higher limits and leave that allowance untouched.
        <strong>market_terms</strong> means it was not aid: an investment made on
        the same terms a private investor would accept.
        <strong>unknown</strong> is the honest answer until someone reads the
        award decision, and it is better than a guess.</p>"""),

    "gge_amount": ("Gross grant equivalent", """
        <p>The actual advantage the aid conferred, expressed as if it had been a
        straight cash grant. For a non-repayable contribution or a cash prize it
        equals the amount; for a subsidised loan or a guarantee it is only the
        benefit component, computed against market rates.</p>
        <p>This, not the headline figure, is what counts against a ceiling.</p>"""),

    "granted_at": ("Date of award", """
        <p>The date of the award decision — the decree, the letter, the
        resolution — not the date the money arrived. The clock on a rolling
        ceiling starts there, often a year before payment.</p>"""),

    "converted": ("Converted", """
        <p>Whether a convertible instrument has actually converted into equity.
        Several calls cap the equity raised to date, and an unconverted note
        usually sits outside that count — which is why this is its own flag
        rather than a note.</p>"""),

    "highest_degree": ("Highest degree", """
        <p>Recorded because it is a hard condition in more places than you would
        expect. The Italian innovative-startup status can be held on the strength
        of the share of staff with a doctorate, and several calls score or
        require research qualifications in the team.</p>"""),

    "left_at": ("Left on", """
        <p>Set this instead of deleting the person. A departure changes the
        team-composition gates from the day it is recorded, but the track record
        the company is judged on was built with them, and an application may
        still need to name who did the work.</p>"""),

    "warm_intro": ("Warm introduction", """
        <p>Who can introduce you. For most funds a cold approach and an
        introduction from someone they already back are not the same channel,
        and the difference is larger than anything in the deck.</p>"""),
}


def get(key: str) -> tuple[str, str] | None:
    return HELP.get(key)
