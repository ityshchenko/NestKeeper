from __future__ import annotations

import pytest

from nestkeeper import texts
from nestkeeper.app import App
from nestkeeper.handlers import deep_link, parse_command, parse_start_payload
from nestkeeper.models.domain import Member
from tests.conftest import (
    BOT_USERNAME,
    GROUP_ID,
    MAIL_LIST,
    OTHER_GROUP_ID,
    USER_ID,
    Clock,
    message,
    private,
)
from tests.fakes import FakeHttp
from tests.helpers import post_update

UKRAINIAN_TEXTS = {
    value
    for name, value in vars(texts).items()
    if name.isupper() and isinstance(value, str) and not name.startswith("CMD")
}


def assert_all_ukrainian(http: FakeHttp) -> None:
    """Every outgoing message must come from texts.py (modulo format placeholders)."""
    for text in http.sent_texts():
        assert text in UKRAINIAN_TEXTS or text == texts.MAIL_LIST_REPLY.format(
            mail_list=MAIL_LIST
        ), text


# --- parsing ---------------------------------------------------------------
@pytest.mark.parametrize(
    ("text", "name", "args"),
    [
        ("/get_mail_list", "get_mail_list", ""),
        (f"/get_mail_list@{BOT_USERNAME}", "get_mail_list", ""),
        (f"/Get_Mail_List@{BOT_USERNAME.lower()}", "get_mail_list", ""),
        ("/start add_-100123", "start", "add_-100123"),
    ],
)
def test_parse_command(text: str, name: str, args: str) -> None:
    command = parse_command(text, BOT_USERNAME)
    assert command is not None
    assert (command.name, command.args) == (name, args)


@pytest.mark.parametrize("text", [None, "", "hello", "/", "/get_mail_list@OtherBot", "/@x"])
def test_parse_command_rejects(text: str | None) -> None:
    assert parse_command(text, BOT_USERNAME) is None


def test_start_payload() -> None:
    assert parse_start_payload("add_-100123") == -100123
    assert parse_start_payload("add_x") is None
    assert parse_start_payload("other") is None
    assert deep_link("Bot", -5) == "https://t.me/Bot?start=add_-5"


# --- group commands ----------------------------------------------------------
async def test_get_mail_list(app: App, http: FakeHttp) -> None:
    reply = await post_update(app, message(f"/get_mail_list@{BOT_USERNAME}"))
    assert reply.status == 200
    assert http.sent_texts() == [f"Адреса розсилки: {MAIL_LIST}"]
    assert await app.repo.is_member(USER_ID, GROUP_ID)


async def test_command_for_other_bot_ignored(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/get_mail_list@OtherBot"))
    assert http.calls == []


async def test_group_not_allowed_is_ignored(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/get_mail_list", chat_id=OTHER_GROUP_ID))
    await post_update(app, message("/add_me_to_mail_list", chat_id=OTHER_GROUP_ID))
    assert http.calls == []


async def test_unknown_command_and_plain_text_ignored(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/help"))
    await post_update(app, message("just chatting"))
    await post_update(app, message(None))
    assert http.calls == []


async def test_bots_and_channels_ignored(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/get_mail_list", is_bot=True))
    await post_update(app, message("/get_mail_list", chat_type="channel"))
    await post_update(app, {"update_id": 1})
    assert http.calls == []


async def test_add_me_sends_prompt_with_private_button(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/add_me_to_mail_list"))
    (call,) = http.telegram_calls("sendMessage")
    assert call.body["text"] == texts.ASK_EMAIL_GROUP
    button = call.body["reply_markup"]["inline_keyboard"][0][0]
    assert button == {
        "text": "Надіслати приватно",
        "url": f"https://t.me/{BOT_USERNAME}?start=add_{GROUP_ID}",
    }
    pending = await app.repo.get_pending(USER_ID, GROUP_ID)
    assert pending is not None
    assert pending.prompt_message_id == 1000
    assert await app.repo.is_member(USER_ID, GROUP_ID)


# --- group reply path ----------------------------------------------------------
async def test_group_reply_registers_and_deletes_message(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/add_me_to_mail_list"))
    await post_update(app, message(" Alice@Example.com ", reply_to=1000, message_id=77))
    (delete,) = http.telegram_calls("deleteMessage")
    assert delete.body == {"chat_id": GROUP_ID, "message_id": 77}
    assert http.sent_texts()[-1] == texts.SUCCESS_VERIFY
    assert "alice@example.com" not in " ".join(http.sent_texts())
    sub = await app.repo.get_subscriber(USER_ID)
    assert sub is not None
    assert sub.email == "alice@example.com"
    assert sub.source_chat_id == GROUP_ID
    assert not sub.verified
    assert sub.cf_address_id == "id-alice@example.com"
    assert await app.repo.get_pending(USER_ID, GROUP_ID) is None
    create = [c for c in http.calls if "api.cloudflare.com" in c.url and c.method == "POST"]
    assert create[0].body == {"email": "alice@example.com"}
    assert create[0].headers["Authorization"] == "Bearer cf-token"
    assert_all_ukrainian(http)


async def test_group_reply_from_other_user_ignored(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/add_me_to_mail_list"))
    await post_update(app, message("bob@example.com", reply_to=1000, user_id=99))
    assert len(http.calls) == 1
    assert await app.repo.get_subscriber(99) is None


async def test_group_reply_to_other_message_ignored(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/add_me_to_mail_list"))
    await post_update(app, message("alice@example.com", reply_to=5))
    await post_update(app, message(None, reply_to=1000))
    assert len(http.calls) == 1


async def test_group_reply_invalid_email_keeps_pending(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/add_me_to_mail_list"))
    await post_update(app, message("not an email", reply_to=1000))
    assert http.sent_texts()[-1] == texts.INVALID_EMAIL
    assert await app.repo.get_pending(USER_ID, GROUP_ID) is not None
    await post_update(app, message("alice@example.com", reply_to=1000))
    assert http.sent_texts()[-1] == texts.SUCCESS_VERIFY


async def test_group_reply_expired(app: App, http: FakeHttp, clock: Clock) -> None:
    await post_update(app, message("/add_me_to_mail_list"))
    clock.advance(minutes=16)
    await post_update(app, message("alice@example.com", reply_to=1000))
    assert http.sent_texts()[-1] == texts.PROMPT_EXPIRED
    assert await app.repo.get_pending(USER_ID, GROUP_ID) is None
    assert await app.repo.get_subscriber(USER_ID) is None


async def test_delete_without_rights_still_registers(app: App, http: FakeHttp) -> None:
    http.telegram_failures["deleteMessage"] = {
        "ok": False,
        "error_code": 400,
        "description": "Bad Request: message can't be deleted",
    }
    await post_update(app, message("/add_me_to_mail_list"))
    await post_update(app, message("alice@example.com", reply_to=1000))
    assert http.sent_texts()[-1] == texts.SUCCESS_VERIFY


# --- private (deep-link) path -----------------------------------------------------
async def test_private_flow(app: App, http: FakeHttp) -> None:
    await post_update(app, message("/add_me_to_mail_list"))
    await post_update(app, private(f"/start add_{GROUP_ID}"))
    prompt = http.telegram_calls("sendMessage")[-1]
    assert prompt.body["text"] == texts.ASK_EMAIL_PRIVATE
    assert prompt.body["chat_id"] == USER_ID
    assert prompt.body["reply_markup"]["force_reply"] is True
    await post_update(app, private("alice@example.com"))
    assert http.sent_texts()[-1] == texts.SUCCESS_VERIFY
    assert http.telegram_calls("deleteMessage") == []
    sub = await app.repo.get_subscriber(USER_ID)
    assert sub is not None
    assert sub.source_chat_id == GROUP_ID
    assert await app.repo.get_pending(USER_ID, USER_ID) is None
    assert_all_ukrainian(http)


@pytest.mark.parametrize(
    "text", ["/start", "/start hello", f"/start add_{OTHER_GROUP_ID}", "/help", "hi there"]
)
async def test_private_ignored_outside_flow(app: App, http: FakeHttp, text: str) -> None:
    await app.repo.add_member(Member(tg_user_id=USER_ID, chat_id=GROUP_ID))
    await post_update(app, private(text))
    await post_update(app, private(None))
    assert http.calls == []


async def test_private_start_requires_membership(app: App, http: FakeHttp) -> None:
    await post_update(app, private(f"/start add_{GROUP_ID}"))
    assert http.calls == []


async def test_private_expired(app: App, http: FakeHttp, clock: Clock) -> None:
    await app.repo.add_member(Member(tg_user_id=USER_ID, chat_id=GROUP_ID))
    await post_update(app, private(f"/start add_{GROUP_ID}"))
    clock.advance(minutes=20)
    await post_update(app, private("alice@example.com"))
    assert http.sent_texts()[-1] == texts.PROMPT_EXPIRED


# --- registration edge cases ----------------------------------------------------------
async def _register_via_dm(app: App, text: str, user_id: int = USER_ID) -> None:
    await app.repo.add_member(Member(tg_user_id=user_id, chat_id=GROUP_ID))
    await post_update(app, private(f"/start add_{GROUP_ID}", user_id=user_id))
    await post_update(app, private(text, user_id=user_id))


async def test_existing_verified_destination(app: App, http: FakeHttp) -> None:
    http.add_destination("alice@example.com", verified=True)
    await _register_via_dm(app, "alice@example.com")
    assert http.sent_texts()[-1] == texts.SUCCESS_ALREADY_VERIFIED
    sub = await app.repo.get_subscriber(USER_ID)
    assert sub is not None
    assert sub.verified


async def test_cf_error_without_existing_destination(app: App, http: FakeHttp) -> None:
    http.cf_create_error = (403, {"success": False, "errors": [{"code": 10000, "message": "x"}]})
    await _register_via_dm(app, "alice@example.com")
    assert http.sent_texts()[-1] == texts.REGISTRATION_FAILED
    assert await app.repo.get_subscriber(USER_ID) is None
    assert await app.repo.get_pending(USER_ID, USER_ID) is not None


async def test_cf_garbage_response(app: App, http: FakeHttp) -> None:
    await app.repo.add_member(Member(tg_user_id=USER_ID, chat_id=GROUP_ID))
    await post_update(app, private(f"/start add_{GROUP_ID}"))
    http.cf_create_error = (502, {"unexpected": True})
    await post_update(app, private("alice@example.com"))
    assert http.sent_texts()[-1] == texts.REGISTRATION_FAILED


async def test_email_taken_by_other_user(app: App, http: FakeHttp) -> None:
    await _register_via_dm(app, "alice@example.com", user_id=1)
    await _register_via_dm(app, "alice@example.com", user_id=2)
    assert http.sent_texts()[-1] == texts.EMAIL_TAKEN
    assert await app.repo.get_subscriber(2) is None


async def test_change_email_keeps_single_row(app: App, http: FakeHttp, clock: Clock) -> None:
    await _register_via_dm(app, "alice@example.com")
    first = await app.repo.get_subscriber(USER_ID)
    clock.advance(minutes=1)
    await _register_via_dm(app, "alice2@example.com")
    subs = await app.repo.list_subscribers()
    assert [s.email for s in subs] == ["alice2@example.com"]
    assert first is not None
    assert subs[0].created_at == first.created_at
    assert subs[0].updated_at > first.updated_at


async def test_send_failure_is_swallowed(app: App, http: FakeHttp) -> None:
    await app.repo.add_member(Member(tg_user_id=USER_ID, chat_id=GROUP_ID))
    await post_update(app, private(f"/start add_{GROUP_ID}"))
    http.telegram_failures["sendMessage"] = {"ok": False, "error_code": 403, "description": "b"}
    reply = await post_update(app, private("alice@example.com"))
    assert reply.status == 200
    assert await app.repo.get_subscriber(USER_ID) is not None
