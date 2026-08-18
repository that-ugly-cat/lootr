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
    check("eligibility offers conditional, product fit does not",
          "conditional" in eval_tool["input_schema"]["properties"]
          ["eligibility_verdict"]["enum"]
          and "conditional" not in eval_tool["input_schema"]["properties"]
          ["product_fit"]["items"]["properties"]["verdict"]["enum"])
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
        "commitments": [],
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

    # A requirement the company cannot meet today is not automatically a gate:
    # most Italian schemes let the unit be opened after the award, and reading
    # that as not_eligible throws away a fundable call in silence.
    conditional = _write_result(opp, {
        "eligibility_verdict": "conditional",
        "eligibility_rationale": "Every gate passes; the unit may be opened after the award.",
        "caps": [],
        "commitments": [
            {"kind": "operating_unit",
             "requirement": "sede operativa nella regione entro 12 mesi dalla concessione",
             "due_when": "at_award", "due_months": "12",
             "cost_note": "A registered unit in a region with no current presence."},
            {"kind": "co_funding", "requirement": "cofinanziamento del 20%",
             "due_when": "at_first_payment", "due_months": "",
             "cost_note": "About 40k of own money."}],
        "product_fit": [],
        "overall_fit_score": 60, "fit_rationale": "Worth it if the unit is wanted anyway.",
        "best_fit_product_id": None, "effort": "medium"})
    check("evaluator can return a conditional verdict", conditional["outcome"] == "conditional")
    with get_db() as db:
        commitments = [dict(r) for r in db.execute(
            "SELECT * FROM opportunity_commitments WHERE opportunity_id=? ORDER BY id",
            (call_id,))]
        caps_now = db.execute("SELECT COUNT(*) n FROM opportunity_caps "
                              "WHERE opportunity_id=?", (call_id,)).fetchone()["n"]
    check("evaluator writes the commitments", len(commitments) == 2)
    check("a commitment keeps the requirement verbatim",
          "entro 12 mesi" in commitments[0]["requirement"])
    check("a commitment records when it falls due",
          commitments[0]["due_when"] == "at_award" and commitments[0]["due_months"] == 12)
    check("a commitment with no stated deadline stores none",
          commitments[1]["due_months"] is None)
    check("a re-evaluation replaces the caps of the previous one", caps_now == 0)

    print("\n== the nightly scan is capped ==")
    from app.discovery.scanner import apply_scan_cap, due_sources
    with get_db() as db:
        for i in range(9):
            db.execute("INSERT INTO sources (name, scan_cadence, enabled) VALUES (?,?,1)",
                       (f"Capped source {i}", "monthly"))
        db.execute("UPDATE sources SET last_scanned_at='2020-01-01' WHERE name='Capped source 0'")
    due = due_sources()
    check("never-scanned sources come before ones scanned long ago",
          due and due[0]["last_scanned_at"] is None
          and due[-1]["name"] == "Capped source 0")
    capped = apply_scan_cap(due)
    check("one night touches at most max_scans_per_run sources", len(capped) == 6)
    with get_db() as db:
        note = db.execute("SELECT detail FROM scan_log WHERE source_id IS NULL "
                          "ORDER BY id DESC LIMIT 1").fetchone()
    check("what was postponed is logged, not silently dropped",
          note is not None and "postponed" in note["detail"])
    with get_db() as db:
        db.execute("DELETE FROM sources WHERE name LIKE 'Capped source %'")

    check("a freshly evaluated row is not stale",
          not any(s["id"] == call_id for s in stale_evaluations()))
    c.post("/profile/edit", data={"legal_name": "BeadRoots S.r.l.", "headcount": "3"})
    check("a profile edit makes every older verdict stale",
          any(s["id"] == call_id for s in stale_evaluations()))

    print("\n== form widgets ==")
    r = c.get("/profile/aid/1/edit")
    check("aid regime is a closed select",
          '<select name="regime">' in r.text and 'value="de_minimis"' in r.text
          and 'value="market_terms"' in r.text)
    check("regime does not offer a free text box", '<input name="regime"' not in r.text)
    check("award date is a date input", 'type="date" name="granted_at"' in r.text)
    check("gge is a number input", 'type="number" step="any" name="gge_amount"' in r.text)
    check("currency is an input with suggestions",
          'list="dl-aid-currency"' in r.text and '<option value="EUR">' in r.text)
    check("edit fields carry their own help", 'hx-get="/help/regime"' in r.text)

    r = c.get("/profile/team/1/edit")
    check("degree is a closed select",
          '<select name="highest_degree">' in r.text and 'value="phd"' in r.text)
    check("founder is a yes/no with a not-recorded state",
          '<select name="is_founder">' in r.text and ">not recorded<" in r.text)
    check("the stored yes is preselected", 'value="1" selected' in r.text)

    r = c.get("/profile/locations/1/edit")
    check("location kind suggests but does not constrain",
          'list="dl-locations-kind"' in r.text
          and '<option value="registered_office">' in r.text)

    r = c.get("/profile")
    check("every profile section has a collapsed add form",
          r.text.count('class="addrow"') == 5, str(r.text.count('class="addrow"')))
    check("the add form uses the same widgets", '<select name="regime">' in r.text)
    for section in ["pitch", "technology", "ip", "market", "traction",
                    "track_record", "strategy_12m", "exclusions"]:
        if f"/help/narrative_{section}" not in r.text:
            check(f"narrative section {section} has its own help", False)
    check("every narrative section has its own help",
          all(f"/help/narrative_{s}" in r.text for s in
              ["pitch", "technology", "ip", "market", "traction",
               "track_record", "strategy_12m", "exclusions"]))

    r = c.get("/products/new")
    check("TRL is a 1-9 select", '<select name="trl">' in r.text and '>9<' in r.text)
    check("regulatory framework suggests known regimes",
          'list="dl-regframework"' in r.text)
    r = c.get("/opportunities/new")
    check("aid regime on the opportunity form is a select",
          '<select name="aid_regime">' in r.text)
    check("disbursement is a select",
          '<select name="disbursement">' in r.text
          and 'value="reimbursement_on_report"' in r.text)
    check("currency on the opportunity form suggests codes",
          'list="dl-o-currency"' in r.text)
    check("TRL bounds are selects, not free text",
          '<select name="trl_min">' in r.text and '<input type="text" name="trl_min"' not in r.text)
    check("amounts are number inputs", 'type="number" step="any"\n           name="amount_max"'
          in r.text or 'type="number"' in r.text)
    check("the provider box suggests providers already recorded",
          'list="dl-o-provider"' in r.text)
    check("where a unit is required suggests the codes in use",
          'list="dl-o-requires_unit_in"' in r.text and '<option value="IT">' in r.text)

    print("\n== multi-value fields ==")
    # A datalist cannot serve a list: it completes the whole box. These are
    # multi-selects over a vocabulary, with a way to add to it.
    check("sizes are a multi-select over the closed set",
          '<select name="eligible_sme_sizes" multiple' in r.text
          and '<option value="micro"' in r.text)
    check("a closed set offers no way to invent a value",
          'name="eligible_sme_sizes__new"' not in r.text)
    check("required qualifications come from the ones the company holds",
          '<select name="requires_qualification" multiple' in r.text
          and 'value="it_startup_innovativa"' in r.text)
    # An empty vocabulary must not render an empty list box: on a fresh instance
    # that reads as a broken widget rather than as a set nobody has filled yet.
    check("an empty vocabulary shows the add box and no empty list",
          '<select name="sector_tags" multiple' not in r.text
          and 'name="sector_tags__new"' in r.text)
    with get_db() as db:
        for value in ["agrifood", "biotech"]:
            db.execute("INSERT OR IGNORE INTO tag_vocabulary (namespace, value, label) "
                       "VALUES ('sector', ?, ?)", (value, value))
    r = c.get("/opportunities/new")
    check("an open tag set lists the vocabulary and can still be added to",
          '<select name="sector_tags" multiple' in r.text
          and '<option value="agrifood"' in r.text
          and 'name="sector_tags__new"' in r.text)

    with get_db() as db:  # the vocabulary a real deployment gets from its seed
        for value in ["soil_health", "water_efficiency"]:
            db.execute("INSERT OR IGNORE INTO tag_vocabulary (namespace, value, label) "
                       "VALUES ('impact', ?, ?)", (value, value.replace("_", " ")))
    r = c.get("/products/1/edit")
    check("product tags read the seeded vocabulary",
          '<select name="impact_tags" multiple' in r.text and 'value="soil_health"' in r.text)
    with get_db() as db:
        before = db.execute("SELECT COUNT(*) n FROM tag_vocabulary "
                            "WHERE namespace='impact'").fetchone()["n"]
    c.post("/products/1/edit", data={
        "name": "br.1O", "status": "field_trials", "trl": "6",
        "impact_tags": ["soil_health", "water_efficiency"],
        "impact_tags__new": "salinity_tolerance, soil_health", "active": "1"})
    with get_db() as db:
        stored = db.execute("SELECT impact_tags FROM products WHERE id=1").fetchone()[0]
        vocab = [r["value"] for r in db.execute(
            "SELECT value FROM tag_vocabulary WHERE namespace='impact' ORDER BY value")]
    check("picked and typed tags land in one JSON array",
          json.loads(stored) == ["soil_health", "water_efficiency", "salinity_tolerance"],
          stored)
    check("a tag typed once joins the vocabulary", "salinity_tolerance" in vocab)
    check("a tag that was already known is not duplicated",
          vocab.count("soil_health") == 1 and len(vocab) == before + 1)

    r = c.get("/products/1/edit")
    check("the new tag comes back as an option, selected",
          'value="salinity_tolerance" selected' in r.text)

    # The dangerous case: a value written before the vocabulary knew it must not
    # disappear from the widget, because disappearing from the widget means
    # disappearing from the record on the next save.
    with get_db() as db:
        db.execute("UPDATE products SET target_segments='[\"orchards\"]' WHERE id=1")
        db.execute("DELETE FROM tag_vocabulary WHERE value='orchards'")
    r = c.get("/products/1/edit")
    check("a tag the vocabulary never heard of is still offered and ticked",
          'value="orchards" selected' in r.text)

    r = c.get("/pipeline")
    check("contacts can be created from the pipeline",
          'action="/profile/contacts/new"' in r.text)
    r = c.post("/profile/contacts/new", data={
        "name": "M. Rossi", "organisation": "Eatable Adventures", "role": "Partner",
        "relationship": "met", "opportunity_id": str(vc_id),
        "warm_intro_via": "FoodSeed cohort", "back": "/pipeline"},
        follow_redirects=False)
    check("contact created", r.status_code == 303)
    r = c.get("/pipeline")
    check("contact listed with its opportunity",
          "M. Rossi" in r.text and "Eatable Adventures" in r.text)
    r = c.get(f"/opportunities/{vc_id}/detail")
    check("contact shows on the opportunity too",
          "M. Rossi" in r.text and "FoodSeed cohort" in r.text)

    print("\n== a very long deadline does not break the table ==")
    from app.routers.ui import _deadline_label
    long_text = ("Nessuna scadenza: misura a sportello, le domande possono essere "
                 "presentate fino a quando vi sono risorse finanziarie disponibili; "
                 "non ci sono graduatorie.")
    check("a date wins over everything",
          _deadline_label({"deadline_date": "2026-10-15", "deadline_type": "fixed",
                           "deadline_text": long_text}) == "2026-10-15")
    check("the type speaks when there is no date",
          _deadline_label({"deadline_type": "open_until_funds_exhausted",
                           "deadline_text": long_text}) == "while funds last")
    label = _deadline_label({"deadline_text": long_text})
    check("a bare quotation is clipped", len(label) <= 43 and label.endswith("…"),
          f"{len(label)} chars")
    check("nothing at all reads as a dash", _deadline_label({}) == "—")

    with get_db() as db:
        db.execute("UPDATE opportunities SET deadline_date=NULL, "
                   "deadline_type='open_until_funds_exhausted', deadline_text=? "
                   "WHERE id=?", (long_text, call_id))
    r = c.get("/calls")
    check("the table shows the short label", "while funds last" in r.text)
    check("the table does not carry the paragraph",
          "non ci sono graduatorie" not in r.text.split("<title>")[0]
          or r.text.count("non ci sono graduatorie") == 1)
    check("the full wording is still reachable as a tooltip",
          'title="Nessuna scadenza' in r.text)
    r = c.get(f"/opportunities/{call_id}/detail")
    check("the modal carries the full wording", "non ci sono graduatorie" in r.text)
print("\n" + ("ALL GREEN" if not fails else f"{len(fails)} FAILURES: {fails}"))
sys.exit(1 if fails else 0)
