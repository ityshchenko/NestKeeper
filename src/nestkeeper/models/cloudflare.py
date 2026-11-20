"""Cloudflare API v4 envelope and Email Routing models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class _CfModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class ApiError(_CfModel):
    code: int
    message: str


class ResultInfo(_CfModel):
    page: int = 1
    per_page: int = 0
    count: int = 0
    total_count: int = 0
    total_pages: int | None = None


class ApiResponse(_CfModel):
    """API v4 envelope; ``result`` is validated by the caller into a concrete model."""

    success: bool
    errors: list[ApiError] = []
    result: Any = None
    result_info: ResultInfo | None = None


class DestinationAddress(_CfModel):
    id: str
    email: str
    verified: datetime | None = None

    @property
    def is_verified(self) -> bool:
        return self.verified is not None
