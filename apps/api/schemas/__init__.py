"""Pydantic request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(50.0, gt=0, le=200)
    historical_flood_count: int = Field(0, ge=0)
    historical_flood_source: str = Field("none")

    @field_validator("historical_flood_source")
    @classmethod
    def _src(cls, v: str) -> str:
        return (v or "none").strip().lower()


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str