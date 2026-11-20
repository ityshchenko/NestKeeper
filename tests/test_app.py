from __future__ import annotations

import csv
import io

import pytest

from nestkeeper import texts
from nestkeeper.app import App, HttpRequest
from nestkeeper.models.domain import Member
from tests.conftest import ADMIN_TOKEN, GROUP_ID, USER_ID, WEBHOOK_SECRET, message, private
from tests.fakes import FakeHttp
from tests.helpers import BASE, post_update


def admin_request(method: str, path: str, token: str | None = ADMIN_TOKEN) -> HttpRequest:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return HttpRequest(method=method, url=f"{BASE}{path}", headers=headers)


async def test_webhook_rejects_bad_secret(app: App, http: FakeHttp) -> None:
    reply = await post_update(app, message("/get_mail_list"), secret="wrong")
    assert reply.status == 403
    no_header = HttpRequest(method="POST", url=f"{BASE}/webhook", headers={}, body="{}")
    assert (await app.handle_http(no_header)).status == 403
    assert http.calls == []


async def test_webhook_invalid_body_returns_200(app: App, http: FakeHttp) -> None:
    for body in ["not json", '{"no_update_id": 1}']:
        reply = await app.handle_http(
            HttpRequest(
                method="POST",
                url=f"{BASE}/webhook/",
                headers={"x-telegram-bot-api-secret-token": WEBHOOK_SECRET},
                body=body,
            )
        )
        assert (reply.status, reply.body) == (200, "ignored")
    assert http.calls == []


async def test_webhook_handler_crash_returns_200(app: App, http: FakeHttp) -> None:
    http.telegram_failures["sendMessage"] = {"ok": False, "error_code": 500, "description": "x"}
    reply = await post_update(app, message("/add_me_to_mail_list"))
    assert reply.status == 200


async def test_unknown_route(app: App) -> None:
    reply = await app.handle_http(HttpRequest(method="GET", url=f"{BASE}/", headers={}))
    assert reply.status == 404
    reply = await app.handle_http(HttpRequest(method="GET", url=f"{BASE}/webhook", headers={}))
    assert reply.status == 404


@pytest.mark.parametrize("path", ["/admin/setup", "/admin/export"])
@pytest.mark.parametrize("token", [None, "wrong-token-0123456789", ""])
async def test_admin_requires_token(app: App, http: FakeHttp, path: str, token: str | None) -> None:
    method = "POST" if path == "/admin/setup" else "GET"
    reply = await app.handle_http(admin_request(method, path, token))
    assert reply.status == 401
    assert http.calls == []


async def test_admin_setup(app: App, http: FakeHttp) -> None:
    reply = await app.handle_http(admin_request("POST", "/admin/setup"))
    assert (reply.status, reply.body) == (200, "ok")
    (webhook,) = http.telegram_calls("setWebhook")
    assert webhook.body == {
        "url": f"{BASE}/webhook",
        "secret_token": "webhook-secret-0123456789",
        "allowed_updates": ["message"],
        "drop_pending_updates": False,
    }
    commands = http.telegram_calls("setMyCommands")
    assert [c.body.get("language_code") for c in commands] == [None, "uk"]
    expected = [
        {"command": "get_mail_list", "description": "Отримати адресу розсилки"},
        {"command": "add_me_to_mail_list", "description": "Додати мене до розсилки"},
    ]
    for call in commands:
        assert call.body["commands"] == expected
        assert call.body["scope"] == {"type": "all_group_chats"}
    assert expected[0]["description"] == texts.COMMAND_DESCRIPTIONS["get_mail_list"]


async def test_admin_export_csv(app: App, http: FakeHttp) -> None:
    await app.repo.add_member(Member(tg_user_id=USER_ID, chat_id=GROUP_ID))
    await post_update(app, private(f"/start add_{GROUP_ID}"))
    await post_update(app, private("alice@example.com"))
    await app.repo.add_member(Member(tg_user_id=7, chat_id=GROUP_ID))
    await post_update(app, private(f"/start add_{GROUP_ID}", user_id=7, username=None))
    await post_update(app, private("bob@example.com", user_id=7, username=None))
    reply = await app.handle_http(admin_request("GET", "/admin/export"))
    assert reply.status == 200
    assert reply.content_type.startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(reply.body)))
    by_email = {r["email"]: r for r in rows}
    assert set(by_email) == {"alice@example.com", "bob@example.com"}
    assert by_email["alice@example.com"]["tg_username"] == "alice"
    assert by_email["bob@example.com"]["tg_username"] == ""
    assert by_email["alice@example.com"]["verified"] == "0"
