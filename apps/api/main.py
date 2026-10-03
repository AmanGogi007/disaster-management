"""FastAPI app for the Location Hazard Intelligence Engine (V0.3).

Evidence-first architecture: no fabricated flood depths, no risk scores.
The frontend only consumes evidence states and gate statuses.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import router


app = FastAPI(
    title="Location Hazard Intelligence Engine",
    version="0.3.0",
    description="V0.3 — Evidence-first flood-risk assessment. No fabricated depths.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "name": "Location Hazard Intelligence Engine",
        "version": "0.3.0",
        "architecture": "evidence-first",
        "docs": "/docs",
        "endpoints": [
            "/api/health",
            "/api/assessments (POST)",
            "/api/assessments/:id (GET)",
            "/api/assessments/:id/evidence (GET)",
            "/api/assessments/:id/map-layers (GET)",
            "/api/assessments/:id/gather (POST)",
            "/api/assessments/:id/reassess (POST)",
            "/api/assessments/:id/solver (POST)",
        ],
    }
