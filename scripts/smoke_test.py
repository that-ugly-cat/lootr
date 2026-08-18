"""End-to-end smoke test: pages, roles, CRUD, proposals, REST and MCP.

    python scripts/smoke_test.py .    # run from the repo root

Uses a throwaway database in a temp directory; touches nothing in ./data.
"""
import json
import os
import sys
import tempfile

DB = os.path.join(tempfile.mkdtemp(), "smoke.db")
os.environ["LOOTR_DB"] = DB
os.environ["ADMIN_USERNAME"] = "spit"
os.environ["ADMIN_PASSWORD"] = "test-password-123"
os.environ["JWT_SECRET"] = "smoke-secret-smoke-secret-smoke-secret"
os.environ["LOOTR_SCHEDULER"] = "0"   # no background jobs during the test
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-not-used-in-tests")
sys.path.insert(0, os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "."))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.db import OPPORTUNITY_FIELDS as OPPORTUNITY_FIELDS_FOR_TEST  # noqa: E402
from app.db import get_db  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + label + (f"  {extra}" if extra and not cond else ""))
    if not cond:
        fails.append(label)


with TestClient(app) as c:
    print("\n== public ==")
    check("landing 200", c.get("/").status_code == 200)
    check("login page 200", c.get("/login").status_code == 200)
    check("calls gated", c.get("/calls").status_code == 401)
    check("profile gated", c.get("/profile").status_code == 401)
    check("health", c.get("/health").json()["status"] == "ok")

    print("\n== auth ==")
    bad = c.post("/login", data={"username": "spit", "password": "wrong"})
    check("bad password 401", bad.status_code == 401)
    r = c.post("/login", data={"username": "spit", "password": "test-password-123"},
               follow_redirects=False)
    check("login redirects to /calls", r.status_code == 303 and r.headers["location"] == "/calls")
    check("session cookie set", "lootr_session" in c.cookies)

    print("\n== company profile ==")
    r = c.post("/profile/edit", data={
        "legal_name": "BeadRoots S.r.l.", "legal_form": "srl", "country": "IT",
        "incorporation_date": "2023-03-01", "sme_size": "micro", "headcount": "2",
        "funding_stage": "pre_seed", "revenue_stage": "pre_revenue",
        "impact_tags": '["water","climate_adaptation"]'}, follow_redirects=False)
    check("company saved", r.status_code == 303)
    r = c.get("/profile")
    check("profile page renders", r.status_code == 200)
    check("company name on page", "BeadRoots" in r.text)
    check("derived age shown", "years old" in r.text)

    r = c.post("/profile/locations/new", data={
        "kind": "registered_office", "city": "Lecce", "country": "IT",
        "region": "Puglia", "region_code": "ITF4", "code_system": "NUTS",
        "registered": "1"}, follow_redirects=False)
    check("location added", r.status_code == 303)
    r = c.post("/profile/team/new", data={
        "name": "Angela Bonato", "role": "CTO", "is_founder": "1", "gender": "f",
        "highest_degree": "phd", "joined_at": "2023-03-01"}, follow_redirects=False)
    check("team member added", r.status_code == 303)
    r = c.post("/profile/team/new", data={
        "name": "Paolo Pezzolla", "role": "Agronomist", "is_founder": "1",
        "joined_at": "2023-03-01", "left_at": "2026-06-01"}, follow_redirects=False)
    check("departed member added", r.status_code == 303)
    r = c.post("/profile/qualifications/new", data={
        "key": "it_startup_innovativa", "label": "Innovative startup register",
        "jurisdiction": "IT", "status": "active", "confirmed_at": "2026-01-15",
        "renewal_every_months": "12"}, follow_redirects=False)
    check("qualification added", r.status_code == 303)
    r = c.post("/profile/aid/new", data={
        "name": "Start Cup Puglia", "provider": "ARTI", "regime": "de_minimis",
        "nominal_amount": "10000", "gge_amount": "10000", "currency": "EUR",
        "granted_at": "2024-11-01"}, follow_redirects=False)
    check("aid ledger entry added", r.status_code == 303)
    r = c.post("/profile/counters/de_minimis", data={
        "used_amount": "0", "ceiling": "300000", "checked_at": "2026-08-18"},
        follow_redirects=False)
    check("counter updated", r.status_code == 303)
    r = c.post("/profile/narrative", data={
        "section": "pitch", "content": "Natural superabsorbent hydrogels."},
        follow_redirects=False)
    check("narrative saved", r.status_code == 303)
    bad = c.post("/profile/narrative", data={"section": "nope", "content": "x"})
    check("unknown narrative section 404", bad.status_code == 404)
    bad = c.post("/profile/nonexistent/new", data={})
    check("unknown child table 404", bad.status_code == 404)

    r = c.get("/profile")
    check("active team counted, departed excluded", "1 active" in r.text)
    check("ledger drift flagged", "ledger says" in r.text)

    print("\n== products ==")
    r = c.post("/products/new", data={
        "name": "Beads for open field", "status": "field_trials", "trl": "7",
        "trl_evidence": "Two seasons of trials on vine and horticulture.",
        "ip_status": "filed", "regulatory_framework": "EU fertilising products",
        "target_segments": '["viticulture","horticulture"]'}, follow_redirects=False)
    check("product created", r.status_code == 303)
    r = c.post("/products/new", data={
        "name": "Lab formulation B", "status": "research", "trl": "3"},
        follow_redirects=False)
    check("second product created", r.status_code == 303)
    r = c.get("/products")
    check("products page", r.status_code == 200 and "Beads for open field" in r.text)
    r = c.get("/profile")
    check("company TRL derived as max", "highest active TRL: 7" in r.text)

    print("\n== sources & opportunities ==")
    r = c.post("/sources/new", data={
        "name": "Invitalia", "url": "https://www.invitalia.it", "geo_hint": "IT",
        "instrument_hint": "grant", "scan_cadence": "monthly"}, follow_redirects=False)
    check("source created", r.status_code == 303)
    check("sources page", c.get("/sources").status_code == 200)

    r = c.post("/opportunities/new", data={
        "view": "calls", "title": "Smart&Start Italia", "provider": "Invitalia",
        "provider_type": "public_national", "instrument": "subsidized_loan",
        "amount_max": "1500000", "currency": "EUR", "deadline_type": "rolling",
        "aid_regime": "de_minimis", "trl_min": "5", "trl_max": "9",
        "status": "shortlisted", "source_id": "1"}, follow_redirects=False)
    check("call created", r.status_code == 303)
    r = c.post("/opportunities/new", data={
        "view": "investors", "title": "Eatable Adventures", "provider": "Eatable Adventures",
        "provider_type": "vc", "instrument": "equity", "ticket_min": "100000",
        "ticket_max": "500000", "stage_focus": "pre-seed", "status": "watching"},
        follow_redirects=False)
    check("investor created", r.status_code == 303)

    with get_db() as db:
        rows = {r["title"]: dict(r) for r in db.execute("SELECT * FROM opportunities")}
    check("dilutive defaulted false for loan", rows["Smart&Start Italia"]["dilutive"] == 0)
    check("dilutive defaulted true for equity", rows["Eatable Adventures"]["dilutive"] == 1)
    call_id = rows["Smart&Start Italia"]["id"]
    vc_id = rows["Eatable Adventures"]["id"]

    r = c.get("/calls")
    check("calls view shows the loan", "Smart&amp;Start" in r.text)
    check("calls view hides the VC", "Eatable Adventures" not in r.text)
    r = c.get("/investors")
    check("investors view shows the VC", "Eatable Adventures" in r.text)
    check("investors view hides the loan", "Smart&amp;Start" not in r.text)

    r = c.get("/calls", headers={"HX-Request": "true"})
    check("htmx partial has no header", r.status_code == 200 and "<nav>" not in r.text)
    r = c.get("/calls?q=smart&instrument=subsidized_loan&status=open")
    check("combined filters keep the row", "Smart&amp;Start" in r.text)
    r = c.get("/calls?q=nothingmatches")
    check("filter can empty the table", "Nothing here yet" in r.text)

    r = c.get(f"/opportunities/{call_id}/detail")
    check("detail modal renders", r.status_code == 200 and "modal-card" in r.text)

    print("\n== caps and per-product fit (written directly, evaluator to come) ==")
    with get_db() as db:
        db.execute("INSERT INTO opportunity_caps (opportunity_id, counter_key, max_amount, "
                   "comparator, scope_note, verdict) VALUES (?,?,?,?,?,?)",
                   (call_id, "lifetime_equity_raised", 500000, "lt",
                    "equity raised to date, excluding grants", "uncertain"))
        db.execute("INSERT INTO opportunity_product_fit (opportunity_id, product_id, verdict, "
                   "fit_score, rationale) VALUES (?,?,?,?,?)",
                   (call_id, 1, "eligible", 82, "TRL 7 sits inside the 5-9 window."))
        db.execute("INSERT INTO opportunity_product_fit (opportunity_id, product_id, verdict, "
                   "fit_score, rationale) VALUES (?,?,?,?,?)",
                   (call_id, 2, "not_eligible", 10, "TRL 3 is below the floor."))
        db.execute("UPDATE opportunities SET fit_score=82, best_fit_product_id=1, "
                   "eligibility_verdict='eligible' WHERE id=?", (call_id,))
    r = c.get(f"/opportunities/{call_id}/detail")
    check("cap shown with verbatim scope", "excluding grants" in r.text)
    check("both product verdicts shown", "TRL 7 sits inside" in r.text and "below the floor" in r.text)
    r = c.get("/calls")
    check("fit score in table", "82" in r.text)

    print("\n== pipeline ==")
    r = c.post("/pipeline/new", data={
        "opportunity_id": str(vc_id), "status": "preparing",
        "next_action": "Send updated deck", "next_action_due": "2026-09-01"},
        follow_redirects=False)
    check("application created", r.status_code == 303)
    r = c.post("/activities/new", data={
        "opportunity_id": str(vc_id), "kind": "call", "happened_at": "2026-08-10",
        "contact_name": "M. Rossi", "summary": "Intro call, asked for traction data."},
        follow_redirects=False)
    check("activity logged", r.status_code == 303)
    r = c.get("/pipeline")
    check("pipeline shows the action", "Send updated deck" in r.text)
    check("pipeline shows the diary", "Intro call" in r.text)
    r = c.get("/investors")
    check("investors view sorts on next action", "Send updated deck" in r.text)

    r = c.post("/pipeline/new", data={
        "opportunity_id": str(call_id), "status": "preparing",
        "product_ids": ["1", "2"], "amount_requested": "50000"},
        follow_redirects=False)
    check("multi-product application created", r.status_code == 303)
    r = c.post("/pipeline/new", data={
        "opportunity_id": str(call_id), "status": "preparing",
        "is_general": "1"}, follow_redirects=False)
    check("general application created", r.status_code == 303)
    r = c.get("/pipeline")
    check("both product lines listed on one row",
          "Beads for open field, Lab formulation B" in r.text)
    check("general application shows as general", ">general<" in r.text)
    with get_db() as db:
        links = db.execute("SELECT COUNT(*) n FROM application_products").fetchone()["n"]
        gen = db.execute("SELECT COUNT(*) n FROM applications WHERE is_general=1").fetchone()["n"]
    check("junction rows written", links == 2, str(links))
    check("general flag stored", gen == 1)

    r = c.get("/pipeline/2/edit")
    check("application edit modal renders", r.status_code == 200 and "product_ids" in r.text)
    check("edit modal preselects the products", r.text.count("selected") >= 2)
    r = c.post("/pipeline/2/edit", data={
        "opportunity_id": str(call_id), "status": "submitted", "product_ids": ["2"]},
        follow_redirects=False)
    check("application edited", r.status_code == 303)
    with get_db() as db:
        left = [r["product_id"] for r in db.execute(
            "SELECT product_id FROM application_products WHERE application_id=2")]
    check("product set replaced, not appended", left == [2], str(left))

    r = c.post("/pipeline/1/status", data={"status": "submitted"}, follow_redirects=False)
    check("inline status change", r.status_code == 303)
    with get_db() as db:
        row = db.execute("SELECT status, next_action FROM applications WHERE id=1").fetchone()
    check("status endpoint does not blank other fields",
          row["status"] == "submitted" and row["next_action"] == "Send updated deck")
    check("status endpoint rejects an unknown state",
          c.post("/pipeline/1/status", data={"status": "nonsense"}).status_code == 422)

    print("\n== profile child editing ==")
    r = c.get("/profile/locations/1/edit")
    check("child edit modal renders", r.status_code == 200 and "Lecce" in r.text)
    r = c.post("/profile/locations/1/edit", data={
        "kind": "registered_office", "city": "Solagna", "country": "IT",
        "region": "Veneto", "region_code": "ITH3", "code_system": "NUTS",
        "registered": "1", "notes": "kept"}, follow_redirects=False)
    check("child row edited", r.status_code == 303)
    with get_db() as db:
        row = db.execute("SELECT city, notes FROM company_locations WHERE id=1").fetchone()
    check("edit keeps the notes it was given", row["city"] == "Solagna" and row["notes"] == "kept")
    check("unknown child table on edit 404", c.get("/profile/nope/1/edit").status_code == 404)

    print("\n== proposals ==")
    with get_db() as db:
        db.execute("INSERT INTO proposals (kind, payload, rationale, confidence, method, source_id) "
                   "VALUES ('new', ?, 'Found on the ministry page.', 'high', 'llm_scan', 1)",
                   (json.dumps({"title": "Bando Macchinari Innovativi", "provider": "MIMIT",
                                "instrument": "grant", "amount_max": 400000}),))
        db.execute("INSERT INTO proposals (kind, opportunity_id, payload, rationale, confidence, method) "
                   "VALUES ('update', ?, ?, 'Deadline moved.', 'medium', 'llm_check')",
                   (call_id, json.dumps({"deadline_date": "2026-12-31"})))
    r = c.get("/proposals")
    check("queue lists both", "Bando Macchinari" in r.text and "Deadline moved" in r.text)
    check("diff shows new value", "2026-12-31" in r.text)
    check("pending badge in nav", 'class="badge"' in r.text)

    r = c.post("/proposals/1/approve", follow_redirects=False)
    check("approve new", r.status_code == 303)
    r = c.post("/proposals/2/approve", follow_redirects=False)
    check("approve update", r.status_code == 303)
    with get_db() as db:
        n = db.execute("SELECT COUNT(*) n FROM opportunities").fetchone()["n"]
        upd = db.execute("SELECT deadline_date, origin, source_id FROM opportunities WHERE id=?",
                         (call_id,)).fetchone()
        created = db.execute("SELECT origin, source_id FROM opportunities "
                             "WHERE title='Bando Macchinari Innovativi'").fetchone()
    check("approval created the row", n == 3)
    check("update applied", upd["deadline_date"] == "2026-12-31")
    check("origin marked discovery", created["origin"] == "discovery")
    check("source inherited on approval", created["source_id"] == 1)
    check("decided proposals kept", c.get("/proposals?status=approved").text.count("chip kind") == 2)

    print("\n== roles ==")
    c.post("/admin/users/new", data={"username": "reader", "email": "r@x.it",
                                     "password": "reader-password", "role": "reader"})
    c.post("/admin/users/new", data={"username": "editor", "email": "e@x.it",
                                     "password": "editor-password", "role": "editor"})
    admin_cookie = dict(c.cookies)
    c.cookies.clear()
    c.post("/login", data={"username": "reader", "password": "reader-password"})
    check("reader can read", c.get("/calls").status_code == 200)
    check("reader cannot edit", c.post("/products/new", data={"name": "x"}).status_code == 403)
    check("reader cannot reach admin", c.get("/admin").status_code == 403)
    c.cookies.clear()
    c.post("/login", data={"username": "editor", "password": "editor-password"})
    check("editor can edit", c.post("/products/new", data={"name": "Line C"},
                                    follow_redirects=False).status_code == 303)
    check("editor cannot delete products", c.post("/products/3/delete").status_code == 403)
    check("editor cannot reach admin", c.get("/admin").status_code == 403)
    c.cookies.clear()
    c.cookies.update(admin_cookie)

    print("\n== api keys, REST ==")
    r = c.post("/admin/keys/new", data={"label": "ono"}, follow_redirects=False)
    key = r.headers["location"].split("new_key=")[1]
    check("key created", len(key) > 20)
    check("REST needs a key", c.get("/ono/opportunities").status_code == 401)
    check("REST rejects a wrong key",
          c.get("/ono/opportunities", headers={"X-API-Key": "nope"}).status_code == 401)
    r = c.get("/ono/opportunities", headers={"X-API-Key": key})
    check("REST dump works", r.status_code == 200 and len(r.json()) == 3)
    r = c.get("/ono/profile", headers={"X-API-Key": key})
    check("REST profile has derived values",
          r.json()["age_years"] is not None and r.json()["max_active_trl"] == 7)
    r = c.post("/api/opportunities", headers={"X-API-Key": key},
               json={"title": "Via REST", "instrument": "prize"})
    check("REST create", r.status_code == 200 and "id" in r.json())
    r = c.post("/api/opportunities", headers={"X-API-Key": key}, json={"provider": "no title"})
    check("REST rejects missing title", r.status_code == 422)

    print("\n== MCP ==")
    H = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}

    def rpc(method, params=None, path=None, headers=None):
        body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        return c.post(path or f"/mcp/k/{key}", json=body, headers={**H, **(headers or {})})

    check("MCP rejects no key", c.post("/mcp/", json={}, headers=H).status_code == 401)
    check("MCP rejects bad capability key",
          c.post("/mcp/k/wrong", json={}, headers=H).status_code == 401)

    r = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "smoke", "version": "0"}})
    check("initialize", r.status_code == 200 and "lootr" in r.text)

    r = rpc("tools/list")
    body = r.text
    payload = json.loads(body.split("data: ", 1)[1]) if "data: " in body else r.json()
    names = sorted(t["name"] for t in payload["result"]["tools"])
    expected = sorted([
        "get_company_profile", "list_products", "list_counters", "search_opportunities",
        "get_opportunity", "upcoming_deadlines", "next_actions", "list_applications",
        "list_contacts", "list_sources", "list_proposals", "propose_opportunity",
        "propose_update", "log_activity"])
    check(f"tools/list has all {len(expected)} tools", names == expected, str(names))

    def call(name, args=None):
        r = rpc("tools/call", {"name": name, "arguments": args or {}})
        b = r.text
        p = json.loads(b.split("data: ", 1)[1]) if "data: " in b else r.json()
        return json.loads(p["result"]["content"][0]["text"])

    prof = call("get_company_profile")
    check("MCP profile: name", prof["company"]["legal_name"] == "BeadRoots S.r.l.")
    check("MCP profile: derived age", prof["age_years"] == 3)
    check("MCP profile: only active team", len(prof["team"]) == 1)
    check("MCP profile: narrative present", "hydrogels" in prof["narrative"]["pitch"])
    check("MCP profile: counters", len(prof["counters"]) == 5)

    check("MCP products", len(call("list_products")) == 3)
    check("MCP counters", call("list_counters")[0]["ceiling"] == 300000)
    check("MCP search all", len(call("search_opportunities", {"status": ""})) == 4)
    check("MCP search investors view",
          [o["title"] for o in call("search_opportunities", {"view": "investors", "status": ""})]
          == ["Eatable Adventures"])
    check("MCP search min_fit", len(call("search_opportunities", {"min_fit": 80, "status": ""})) == 1)

    one = call("get_opportunity", {"opportunity_id": call_id})
    check("MCP get_opportunity: caps", one["caps"][0]["counter_key"] == "lifetime_equity_raised")
    check("MCP get_opportunity: product fit", len(one["product_fit"]) == 2)
    check("MCP get_opportunity: fit carries product name",
          one["product_fit"][0]["product_name"] == "Beads for open field")

    check("MCP upcoming_deadlines", len(call("upcoming_deadlines", {"days": 2000})) == 1)
    na = call("next_actions", {"days": 365})
    check("MCP next_actions", len(na) == 1 and na[0]["title"] == "Eatable Adventures")
    apps = call("list_applications")
    check("MCP list_applications", len(apps) == 3, str(len(apps)))
    check("MCP applications carry the product set",
          any(a.get("product_names") == "Lab formulation B" for a in apps),
          str([a.get("product_names") for a in apps]))
    check("MCP applications carry the general flag",
          any(a.get("is_general") == 1 for a in apps))
    check("MCP list_sources", len(call("list_sources")) == 1)
    check("MCP list_proposals pending", call("list_proposals") == [])
    check("MCP list_proposals approved", len(call("list_proposals", {"status": "approved"})) == 2)

    res = call("propose_opportunity", {
        "fields": {"title": "PNRR call", "instrument": "grant"},
        "rationale": "Found by Ono.", "confidence": "low"})
    check("MCP propose_opportunity", res["ok"] is True)
    res = call("propose_opportunity", {"fields": {"provider": "x"}, "rationale": "y"})
    check("MCP propose rejects missing title", res["ok"] is False)
    res = call("propose_update", {"opportunity_id": call_id,
                                  "fields": {"amount_max": 2000000}, "rationale": "Raised."})
    check("MCP propose_update", res["ok"] is True)
    res = call("propose_update", {"opportunity_id": 9999, "fields": {"amount_max": 1},
                                  "rationale": "x"})
    check("MCP propose_update rejects unknown id", res["ok"] is False)
    res = call("log_activity", {"opportunity_id": vc_id, "kind": "email",
                                "summary": "Sent the deck."})
    check("MCP log_activity", res["ok"] is True)
    res = call("log_activity", {"opportunity_id": 9999, "kind": "email", "summary": "x"})
    check("MCP log_activity rejects unknown id", res["ok"] is False)

    r = c.get("/proposals")
    check("MCP proposals land in the queue", "Found by Ono" in r.text and "ono_mcp" in r.text)
    check("MCP activity lands in the diary", "Sent the deck" in c.get("/pipeline").text)

    print("\n== MCP via header instead of capability URL ==")
    r = rpc("tools/list", path="/mcp/", headers={"X-API-Key": key})
    check("header auth works", r.status_code == 200 and "search_opportunities" in r.text)
    r = rpc("tools/list", path="/mcp", headers={"X-API-Key": key})
    check("path without trailing slash normalised", r.status_code == 200)

    r = c.post("/admin/keys/1/revoke", follow_redirects=False)
    check("key revoked", r.status_code == 303)
    check("revoked key rejected on REST",
          c.get("/ono/opportunities", headers={"X-API-Key": key}).status_code == 401)
    check("revoked key rejected on MCP", c.post(f"/mcp/k/{key}", json={}, headers=H).status_code == 401)


    print("\n== help ==")
    from app.help import HELP  # noqa: E402
    broken = [k for k in HELP if "help-body" not in c.get(f"/help/{k}").text]
    check(f"all {len(HELP)} help entries render", not broken, str(broken))
    check("unknown help key renders nothing", c.get("/help/nope").text == "")
    check("help is gated", TestClient(app).get("/help/de_minimis").status_code == 401)
    thin = [path for path in ["/calls", "/investors", "/profile", "/products",
                              "/pipeline", "/proposals", "/sources", "/admin",
                              "/opportunities/new"]
            if 'class="help"' not in c.get(path).text]
    check("every page carries help affordances", not thin, str(thin))

    print("\n== discovery: gates and wiring ==")
    for path in ["/scan-now", "/check-links-now", "/evaluate-stale",
                 f"/opportunities/{call_id}/check", f"/opportunities/{call_id}/evaluate"]:
        code = TestClient(app).post(path).status_code
        check(f"{path} needs a login", code == 401, str(code))
    with get_db() as db:
        db.execute("UPDATE opportunities SET link=? WHERE id=?",
                   ("https://example.org/call", call_id))
    r = c.get(f"/opportunities/{call_id}/detail")
    check("modal offers Evaluate", ">Evaluate<" in r.text)
    check("modal offers Check when there is a link", ">Check<" in r.text)
    r = c.get("/sources")
    check("sources page offers Scan all / Check links",
          "Scan all now" in r.text and "Check links" in r.text)

    print("\n== discovery: prompt context ==")
    from app.discovery.profile_context import opportunity_block, profile_block
    block = profile_block()
    check("profile block carries the company", "BeadRoots S.r.l." in block)
    check("profile block carries derived age", "age in years" in block)
    check("profile block flags unregistered sites", "NOT REGISTERED" in block)
    check("profile block carries products with TRL",
          "Beads for open field" in block and "TRL" in block)
    check("profile block carries the counters", "de_minimis" in block)
    check("profile block names the empty narrative sections", "Not recorded:" in block)
    check("profile block drops empty fields", ": None" not in block)
    with get_db() as db:
        opp = dict(db.execute("SELECT * FROM opportunities WHERE id=?", (call_id,)).fetchone())
    ob = opportunity_block(opp)
    check("opportunity block is JSON with no nulls",
          '"title"' in ob and "null" not in ob)

    print("\n== discovery: cadence ==")
    from app.discovery.scanner import SUBMIT_TOOL, due_sources
    check("a never-scanned source is due", any(s["id"] == 1 for s in due_sources()))
    with get_db() as db:
        db.execute("UPDATE sources SET last_scanned_at=CURRENT_TIMESTAMP WHERE id=1")
    check("a just-scanned monthly source is not due", not any(s["id"] == 1 for s in due_sources()))
    with get_db() as db:
        db.execute("UPDATE sources SET last_scanned_at=date('now','-40 days') WHERE id=1")
    check("a monthly source is due again after 40 days",
          any(s["id"] == 1 for s in due_sources()))
    with get_db() as db:
        db.execute("UPDATE sources SET scan_cadence='quarterly' WHERE id=1")
    check("the same source is not due yet on a quarterly cadence",
          not any(s["id"] == 1 for s in due_sources()))
    with get_db() as db:
        db.execute("UPDATE sources SET enabled=0, scan_cadence='monthly', "
                   "last_scanned_at=NULL WHERE id=1")
    check("a disabled source is never due", not any(s["id"] == 1 for s in due_sources()))
    with get_db() as db:
        db.execute("UPDATE sources SET enabled=1 WHERE id=1")

    print("\n== discovery: strict schemas ==")
    from app.discovery.evaluator import _submit_tool
    from app.discovery.verifier import SUBMIT_TOOL as VERIFY_TOOL

    def well_formed(tool):
        def walk(node):
            if not isinstance(node, dict):
                return True
            if node.get("type") == "object":
                props = set(node.get("properties", {}))
                if node.get("additionalProperties") is not False:
                    return False
                if set(node.get("required", [])) != props:
                    return False
            return all(walk(v) for v in node.values() if isinstance(v, (dict, list))) and all(
                walk(i) for v in node.values() if isinstance(v, list) for i in v)
        json.dumps(tool)  # must serialise
        return tool.get("strict") is True and walk(tool["input_schema"])

    def union_count(node):
        """The API rejects a strict schema with more than 16 union-typed
        parameters. Caught in production once; caught here from now on."""
        n = 0
        if isinstance(node, dict):
            t = node.get("type")
            if isinstance(t, list) or "anyOf" in node:
                n += 1
            for v in node.values():
                n += union_count(v)
        elif isinstance(node, list):
            for v in node:
                n += union_count(v)
        return n

    check("scanner tool schema is strict-clean", well_formed(SUBMIT_TOOL))
    check("verifier tool schema is strict-clean", well_formed(VERIFY_TOOL))
    eval_tool = _submit_tool(["de_minimis", "lifetime_equity_raised"], [1, 2])
    check("evaluator tool schema is strict-clean", well_formed(eval_tool))
    check("evaluator enumerates only real counters",
          eval_tool["input_schema"]["properties"]["caps"]["items"]["properties"]
          ["counter_key"]["enum"] == ["de_minimis", "lifetime_equity_raised"])
    check("evaluator enumerates only real products",
          eval_tool["input_schema"]["properties"]["product_fit"]["items"]["properties"]
          ["product_id"]["enum"] == [1, 2])
    for name, tool in [("scanner", SUBMIT_TOOL), ("verifier", VERIFY_TOOL),
                       ("evaluator", eval_tool)]:
        n = union_count(tool["input_schema"])
        check(f"{name} schema stays under the 16 union-type limit", n <= 16, f"{n} unions")

    print("\n== discovery: writing results (no API call) ==")
    from app.discovery.evaluator import _write_result, stale_evaluations
    from app.discovery.verifier import _apply_result

    with get_db() as db:  # clear the MCP-filed pending update first
        db.execute("UPDATE proposals SET status='rejected' WHERE kind='update' "
                   "AND opportunity_id=? AND status='pending'", (call_id,))
        opp = dict(db.execute("SELECT * FROM opportunities WHERE id=?",
                              (call_id,)).fetchone())
    verdict = _apply_result(opp, {
        "matches": False,
        "fields": {k: None for k in OPPORTUNITY_FIELDS_FOR_TEST}
        | {"amount_max": "1500000", "title": opp["title"]},
        "rationale": "The page now states a higher ceiling.",
        "source_url": "https://example.org/call", "confidence": "high"})
    check("verifier files a diff proposal", verdict["outcome"] == "diff_proposed")
    check("verifier ignores fields that did not change", verdict["changes"] == 1)
    with get_db() as db:
        payload = json.loads(db.execute(
            "SELECT payload FROM proposals WHERE method='llm_check' "
            "ORDER BY id DESC LIMIT 1").fetchone()["payload"])
    check("only the changed field is in the payload", list(payload) == ["amount_max"])
    again = _apply_result(opp, {"matches": False, "fields": {"amount_max": "1500000"},
                                "rationale": "", "source_url": "", "confidence": "low"})
    check("verifier does not stack a second pending diff", again["outcome"] == "pending_exists")

    written = _write_result(opp, {
        "eligibility_verdict": "eligible",
        "eligibility_rationale": "Registered office in the eligible region; age within range.",
        "caps": [{"counter_key": "de_minimis", "max_amount": None, "comparator": "lte",
                  "scope_note": "the gross grant equivalent counts against de minimis",
                  "verdict": "pass"}],
        "product_fit": [
            {"product_id": 1, "verdict": "eligible", "fit_score": 88, "rationale": "TRL fits."},
            {"product_id": 2, "verdict": "not_eligible", "fit_score": 5, "rationale": "Too early."}],
        "overall_fit_score": 88, "fit_rationale": "Squarely on theme.",
        "best_fit_product_id": 1, "effort": "high"})
    check("evaluator writes a verdict", written["outcome"] == "eligible")
    with get_db() as db:
        row = dict(db.execute("SELECT * FROM opportunities WHERE id=?", (call_id,)).fetchone())
        caps = db.execute("SELECT * FROM opportunity_caps WHERE opportunity_id=?",
                          (call_id,)).fetchall()
        fits = db.execute("SELECT * FROM opportunity_product_fit WHERE opportunity_id=?",
                          (call_id,)).fetchall()
    check("evaluator replaces caps rather than appending", len(caps) == 1)
    check("evaluator replaces product fit rather than appending", len(fits) == 2)
    check("evaluator keeps the verbatim perimeter",
          "gross grant equivalent" in caps[0]["scope_note"])
    check("evaluator stamps the advisory columns",
          row["fit_score"] == 88 and row["best_fit_product_id"] == 1
          and row["effort"] == "high" and row["eligibility_checked_at"])
    check("evaluator leaves status alone", row["status"] == "shortlisted")
    check("evaluator leaves factual fields alone", row["amount_max"] == 1500000)

    check("a freshly evaluated row is not stale",
          not any(s["id"] == call_id for s in stale_evaluations()))
    c.post("/profile/edit", data={"legal_name": "BeadRoots S.r.l.", "headcount": "3"})
    check("a profile edit makes every older verdict stale",
          any(s["id"] == call_id for s in stale_evaluations()))
print("\n" + ("ALL GREEN" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
