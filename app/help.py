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

    "warm_intro": ("Warm introduction", """
        <p>Who can introduce you. For most funds a cold approach and an
        introduction from someone they already back are not the same channel,
        and the difference is larger than anything in the deck.</p>"""),
}


def get(key: str) -> tuple[str, str] | None:
    return HELP.get(key)
