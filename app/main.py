"""Lootr — funding radar for a single company.

Foundation only at this stage: database bootstrap and a health endpoint.
The UI, the Ono layer (MCP + REST) and the three discovery processes
(link monitor, semantic scan, fit evaluator) land on top of this.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import company_profile, get_config, init_db
from .version import commit_hash


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Lootr", lifespan=lifespan)


@app.get("/health")
def health():
    profile = company_profile()
    return {
        "status": "ok",
        "commit": commit_hash(),
        "company": profile["company"].get("legal_name") or "(not configured)",
        "products": len(profile["products"]),
        "counters": len(profile["counters"]),
    }
