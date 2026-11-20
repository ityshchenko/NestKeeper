"""HTTP abstraction so API clients can be tested without the Workers runtime."""

from __future__ import annotations

import json
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class HttpResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: int
    body: str

    def json_body(self) -> Any:
        return json.loads(self.body) if self.body else None


class HttpClient(Protocol):
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: Any = None,
    ) -> HttpResponse: ...


class HttpError(Exception):
    """Transport failure or non-JSON response."""
