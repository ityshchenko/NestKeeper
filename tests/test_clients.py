from __future__ import annotations

import pytest
from pydantic import SecretStr

from nestkeeper.clients.cloudflare import PER_PAGE, CloudflareClient, CloudflareError
from nestkeeper.clients.telegram import TelegramClient, TelegramError
from nestkeeper.http import HttpError, HttpResponse
from nestkeeper.models.telegram import SendMessage
from tests.fakes import FakeHttp


@pytest.fixture
def cf(http: FakeHttp) -> CloudflareClient:
    return CloudflareClient(http, "acc", SecretStr("tok"))


@pytest.fixture
def tg(http: FakeHttp) -> TelegramClient:
    return TelegramClient(http, SecretStr("123:abc"))


async def test_cf_pagination_with_total_pages(cf: CloudflareClient, http: FakeHttp) -> None:
    for i in range(PER_PAGE + 3):
        http.add_destination(f"u{i}@example.com", verified=bool(i % 2))
    addresses = await cf.list_destinations()
    assert len(addresses) == PER_PAGE + 3
    assert len([c for c in http.calls if c.method == "GET"]) == 2
    assert http.calls[0].url.endswith("/accounts/acc/email/routing/addresses?page=1&per_page=50")


async def test_cf_pagination_without_total_pages(cf: CloudflareClient, http: FakeHttp) -> None:
    http.per_page_override = PER_PAGE
    for i in range(PER_PAGE):
        http.add_destination(f"u{i}@example.com", verified=False)
    assert len(await cf.list_destinations()) == PER_PAGE
    assert len(http.calls) == 2  # full page, then empty page


async def test_cf_find_destination(cf: CloudflareClient, http: FakeHttp) -> None:
    http.add_destination("a@example.com", verified=True)
    found = await cf.find_destination("A@Example.com")
    assert found is not None
    assert found.is_verified
    assert await cf.find_destination("z@example.com") is None


async def test_cf_conflict_raises(cf: CloudflareClient, http: FakeHttp) -> None:
    http.add_destination("a@example.com", verified=False)
    with pytest.raises(CloudflareError, match="2032: already exists") as info:
        await cf.create_destination("a@example.com")
    assert info.value.status == 409


async def test_cf_error_without_details(cf: CloudflareClient, http: FakeHttp) -> None:
    http.cf_create_error = (500, {"success": False, "errors": []})
    with pytest.raises(CloudflareError, match="no details"):
        await cf.create_destination("a@example.com")


async def test_cf_invalid_results(cf: CloudflareClient, http: FakeHttp) -> None:
    http.raw_override = HttpResponse(status=200, body='{"success": true, "result": null}')
    with pytest.raises(HttpError, match="invalid result"):
        await cf.create_destination("a@example.com")
    http.raw_override = HttpResponse(status=200, body='{"success": true, "result": [{"x": 1}]}')
    with pytest.raises(HttpError, match="invalid destination list"):
        await cf.list_destinations()
    http.raw_override = HttpResponse(status=502, body="<html>")
    with pytest.raises(HttpError, match="unexpected response"):
        await cf.list_destinations()


async def test_tg_errors(tg: TelegramClient, http: FakeHttp) -> None:
    http.telegram_failures["sendMessage"] = {"ok": False, "error_code": 403, "description": "no"}
    with pytest.raises(TelegramError, match="sendMessage failed: 403 no"):
        await tg.send_message(SendMessage(chat_id=1, text="x"))
    http.raw_override = HttpResponse(status=502, body="")
    with pytest.raises(HttpError, match="unexpected response"):
        await tg.send_message(SendMessage(chat_id=1, text="x"))


async def test_tg_delete_and_url(tg: TelegramClient, http: FakeHttp) -> None:
    assert await tg.delete_message(1, 2) is True
    assert http.calls[0].url == "https://api.telegram.org/bot123:abc/deleteMessage"
