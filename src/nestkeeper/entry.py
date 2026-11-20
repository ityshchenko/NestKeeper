"""Cloudflare Workers entrypoint: thin adapters from runtime objects to ``nestkeeper.app``.

This module only runs inside the Pyodide Workers runtime and is excluded from unit-test
coverage; all logic lives in runtime-independent modules.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from workers import Request, Response, WorkerEntrypoint, fetch

from nestkeeper.app import App, HttpReply, HttpRequest
from nestkeeper.http import HttpResponse
from nestkeeper.logging import configure_logging, get_logger
from nestkeeper.settings import Settings
from nestkeeper.storage import Param, Row

configure_logging()
log = get_logger(__name__)


class WorkersHttpClient:
    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: Any = None,
    ) -> HttpResponse:
        all_headers = {"content-type": "application/json", **(headers or {})}
        if json_body is None:
            response = await fetch(url, method=method, headers=all_headers)  # type: ignore[arg-type]
        else:
            response = await fetch(
                url,
                method=method,  # type: ignore[arg-type]
                headers=all_headers,
                body=json.dumps(json_body),
            )
        return HttpResponse(status=int(response.status), body=await response.text())


def _to_rows(result: Any) -> list[Row]:
    rows = result["results"] if isinstance(result, dict) else result.results
    if hasattr(rows, "to_py"):
        rows = rows.to_py()
    return [dict(row) for row in rows or []]


class D1Database:
    def __init__(self, binding: Any) -> None:
        self._binding = binding

    async def execute(self, sql: str, params: Sequence[Param] = ()) -> None:
        await self._binding.prepare(sql).bind(*params).run()

    async def query(self, sql: str, params: Sequence[Param] = ()) -> list[Row]:
        return _to_rows(await self._binding.prepare(sql).bind(*params).all())


class WorkersEmail:
    """Adapter for the runtime ``ForwardableEmailMessage``."""

    def __init__(self, message: Any) -> None:
        self._message = message

    @property
    def sender(self) -> str:
        return str(getattr(self._message, "from"))

    @property
    def recipient(self) -> str:
        return str(self._message.to)

    async def forward(self, to: str) -> None:
        await self._message.forward(to)

    def reject(self, reason: str) -> None:
        self._message.setReject(reason)


class Default(WorkerEntrypoint):
    def _app(self) -> App:
        settings = Settings.from_env(lambda key: getattr(self.env, key, None))
        return App(settings, WorkersHttpClient(), D1Database(self.env.DB))

    async def fetch(self, request: Request) -> Response:
        body = await request.text() if request.method.value in {"POST", "PUT"} else ""
        reply: HttpReply = await self._app().handle_http(
            HttpRequest(
                method=request.method.value,
                url=request.url,
                headers=dict(request.headers.items()),
                body=body,
            )
        )
        return Response(
            reply.body, status=reply.status, headers={"content-type": reply.content_type}
        )

    async def email(self, message: Any, *_args: Any) -> None:
        await self._app().handle_email(WorkersEmail(message))

    async def scheduled(self, *_args: Any) -> None:
        await self._app().handle_scheduled()
