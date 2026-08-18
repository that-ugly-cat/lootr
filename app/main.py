"""Lootr — funding radar for a single company.

- Web UI (HTMX + Jinja2) with JWT cookie auth, three roles (admin/editor/reader)
- REST /ono + /api with X-API-Key
- MCP mounted at /mcp, reachable either with an X-API-Key header or via a
  capability URL /mcp/k/{key} (pattern Contrarian): the middleware validates
  the key, rewrites the path, and the MCP app stays auth-unaware.
- Discovery inside the app, on a scheduler: a nightly link monitor with no model
  in the loop, a semantic scan that respects each source's own cadence, and a
  nightly pass over evaluations the profile has made stale.
"""
import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import bootstrap_admin, check_api_key
from .db import company_profile, init_db
from .discovery.evaluator import run_evaluations
from .discovery.link_monitor import run_link_monitor
from .discovery.scanner import run_scan
from .mcp_server import build_asgi_app, mcp
from .routers import api, ui
from .version import commit_hash

scheduler = BackgroundScheduler(timezone="Europe/Rome")


def _scheduled_scan():
    """Runs nightly but only touches sources whose own cadence has come round —
    weekly for competitions and batches, monthly for the rest."""
    run_scan(only_due=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    bootstrap_admin()
    if os.environ.get("LOOTR_SCHEDULER", "1") == "1":
        scheduler.add_job(run_link_monitor, CronTrigger(hour=3, minute=0),
                          id="link_monitor")
        scheduler.add_job(_scheduled_scan, CronTrigger(hour=4, minute=0), id="llm_scan")
        # Newly approved rows have no verdict yet, and a profile edit makes every
        # older verdict provisional. Both are picked up here.
        scheduler.add_job(lambda: run_evaluations(stale_only=True),
                          CronTrigger(hour=5, minute=0), id="evaluator")
        scheduler.start()
    async with mcp.session_manager.run():
        yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


# Built at import time: this also registers the session manager on `mcp`, which
# the parent lifespan starts (FastAPI mounts do not propagate lifespans).
mcp_asgi = build_asgi_app()

app = FastAPI(title="Lootr", lifespan=lifespan)


@app.middleware("http")
async def mcp_auth(request: Request, call_next):
    """Gate /mcp. Two ways in: X-API-Key header, or capability URL /mcp/k/{key}."""
    path = request.url.path
    if path == "/mcp" or path.startswith("/mcp/"):
        if path.startswith("/mcp/k/"):
            rest = path[len("/mcp/k/"):]
            key, _, tail = rest.partition("/")
            if not check_api_key(key):
                return JSONResponse({"error": "invalid key"}, status_code=401)
            # Rewrite the path: the MCP app knows nothing about authentication.
            request.scope["path"] = f"/mcp/{tail}"
        elif not check_api_key(request.headers.get("x-api-key", "")):
            return JSONResponse({"error": "missing or invalid X-API-Key"}, status_code=401)
        # Without the trailing slash the mount would answer 307, which MCP
        # clients do not follow on POST.
        if request.scope["path"] == "/mcp":
            request.scope["path"] = "/mcp/"
    return await call_next(request)


@app.get("/health")
def health():
    profile = company_profile()
    return {
        "status": "ok",
        "commit": commit_hash(),
        "company": profile["company"].get("legal_name") or "(not configured)",
        "products": len(profile["products"]),
    }


app.mount("/static", StaticFiles(
    directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
app.include_router(api.router)
app.include_router(ui.router)
app.mount("/mcp", mcp_asgi)
