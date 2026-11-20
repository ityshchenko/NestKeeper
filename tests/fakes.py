"""Test doubles: sqlite-backed Database and a fake HTTP layer for Telegram + Cloudflare."""

from __future__ import annotations

import itertools
import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from nestkeeper.http import HttpResponse
from nestkeeper.storage import Param, Row

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


class SqliteDatabase:
    """D1 is SQLite, so the real migrations run unchanged against an in-memory DB."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        for migration in sorted(MIGRATIONS.glob("*.sql")):
            self.conn.executescript(migration.read_text())

    async def execute(self, sql: str, params: Sequence[Param] = ()) -> None:
        self.conn.execute(sql, tuple(params))
        self.conn.commit()

    async def query(self, sql: str, params: Sequence[Param] = ()) -> list[Row]:
        return [dict(r) for r in self.conn.execute(sql, tuple(params)).fetchall()]


@dataclass
class Call:
    method: str
    url: str
    headers: dict[str, str]
    body: Any

    @property
    def api_method(self) -> str:
        return self.url.rsplit("/", 1)[-1]


@dataclass
class FakeHttp:
    calls: list[Call] = field(default_factory=list)
    destinations: dict[str, dict[str, Any]] = field(default_factory=dict)
    telegram_failures: dict[str, dict[str, Any]] = field(default_factory=dict)
    cf_create_error: tuple[int, dict[str, Any]] | None = None
    raw_override: HttpResponse | None = None
    per_page_override: int | None = None
    _ids: itertools.count[int] = field(default_factory=lambda: itertools.count(1000))

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: Any = None,
    ) -> HttpResponse:
        self.calls.append(Call(method, url, dict(headers or {}), json_body))
        if self.raw_override is not None:
            return self.raw_override
        if url.startswith("https://api.telegram.org/"):
            return self._telegram(url.rsplit("/", 1)[-1])
        return self._cloudflare(method, url, json_body)

    # --- helpers for assertions -------------------------------------------
    def telegram_calls(self, api_method: str) -> list[Call]:
        return [c for c in self.calls if "api.telegram.org" in c.url and c.api_method == api_method]

    def sent_texts(self) -> list[str]:
        return [str(c.body["text"]) for c in self.telegram_calls("sendMessage")]

    def add_destination(self, email: str, *, verified: bool) -> None:
        self.destinations[email] = {
            "id": f"id-{email}",
            "email": email,
            "verified": "2026-01-01T00:00:00Z" if verified else None,
        }

    # --- fake APIs -----------------------------------------------------------
    def _telegram(self, api_method: str) -> HttpResponse:
        if api_method in self.telegram_failures:
            return HttpResponse(status=400, body=json.dumps(self.telegram_failures[api_method]))
        result: Any = True
        if api_method == "sendMessage":
            result = {"message_id": next(self._ids), "chat": {"id": 1, "type": "private"}}
        return HttpResponse(status=200, body=json.dumps({"ok": True, "result": result}))

    def _cloudflare(self, method: str, url: str, body: Any) -> HttpResponse:
        if method == "POST":
            if self.cf_create_error is not None:
                status, payload = self.cf_create_error
                return HttpResponse(status=status, body=json.dumps(payload))
            email = str(body["email"])
            if email in self.destinations:
                return _cf(409, None, errors=[{"code": 2032, "message": "already exists"}])
            self.add_destination(email, verified=False)
            return _cf(200, self.destinations[email])
        query = parse_qs(urlsplit(url).query)
        page = int(query["page"][0])
        per_page = self.per_page_override or int(query["per_page"][0])
        items = list(self.destinations.values())
        chunk = items[(page - 1) * per_page : page * per_page]
        total_pages = max(1, -(-len(items) // per_page))
        info: dict[str, Any] = {"page": page, "per_page": per_page, "count": len(chunk)}
        if self.per_page_override is None:
            info["total_pages"] = total_pages
        return _cf(200, chunk, result_info=info)


def _cf(
    status: int,
    result: Any,
    *,
    errors: list[dict[str, Any]] | None = None,
    result_info: dict[str, Any] | None = None,
) -> HttpResponse:
    payload: dict[str, Any] = {
        "success": not errors,
        "errors": errors or [],
        "messages": [],
        "result": result,
    }
    if result_info is not None:
        payload["result_info"] = result_info
    return HttpResponse(status=status, body=json.dumps(payload))


@dataclass
class FakeEmail:
    sender: str
    recipient: str
    forwarded: list[str] = field(default_factory=list)
    rejected: str | None = None
    fail_for: set[str] = field(default_factory=set)

    async def forward(self, to: str) -> None:
        if to in self.fail_for:
            raise RuntimeError("forward failed")
        self.forwarded.append(to)

    def reject(self, reason: str) -> None:
        self.rejected = reason
