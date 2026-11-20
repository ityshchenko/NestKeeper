from __future__ import annotations

from datetime import timedelta

from nestkeeper.app import App
from nestkeeper.emailing import REJECT_NOT_SUBSCRIBER, REJECT_WRONG_RECIPIENT
from nestkeeper.models.domain import PendingPrompt, Subscriber
from nestkeeper.settings import Settings
from tests.conftest import GROUP_ID, MAIL_LIST, Clock
from tests.fakes import FakeEmail, FakeHttp, SqliteDatabase


async def _seed(app: App) -> None:
    for uid, email, verified in [
        (1, "a@example.com", True),
        (2, "b@example.com", True),
        (3, "c@example.com", False),
    ]:
        await app.repo.upsert_subscriber(
            Subscriber(tg_user_id=uid, email=email, source_chat_id=GROUP_ID, verified=verified)
        )


async def test_fan_out_to_verified_except_sender(app: App) -> None:
    await _seed(app)
    mail = FakeEmail(sender="A@example.com", recipient=MAIL_LIST.upper())
    result = await app.handle_email(mail)
    assert mail.forwarded == ["b@example.com"]
    assert mail.rejected is None
    assert (result.delivered, result.failed) == (1, 0)


async def test_fan_out_from_outsider_when_unrestricted(app: App) -> None:
    await _seed(app)
    mail = FakeEmail(sender="stranger@example.net", recipient=MAIL_LIST)
    await app.handle_email(mail)
    assert mail.forwarded == ["a@example.com", "b@example.com"]


async def test_rejects_wrong_recipient(app: App) -> None:
    await _seed(app)
    mail = FakeEmail(sender="a@example.com", recipient="other@example.org")
    result = await app.handle_email(mail)
    assert mail.rejected == REJECT_WRONG_RECIPIENT == result.rejected
    assert mail.forwarded == []


async def test_restrict_senders(
    env: dict[str, str], http: FakeHttp, db: SqliteDatabase, clock: Clock
) -> None:
    env["RESTRICT_SENDERS"] = "true"
    app = App(Settings.from_env(env.get), http, db, clock)
    await _seed(app)
    outsider = FakeEmail(sender="stranger@example.net", recipient=MAIL_LIST)
    await app.handle_email(outsider)
    assert outsider.rejected == REJECT_NOT_SUBSCRIBER
    unverified = FakeEmail(sender="c@example.com", recipient=MAIL_LIST)
    await app.handle_email(unverified)
    assert unverified.rejected == REJECT_NOT_SUBSCRIBER
    member = FakeEmail(sender="b@example.com", recipient=MAIL_LIST)
    await app.handle_email(member)
    assert member.forwarded == ["a@example.com"]


async def test_forward_failure_does_not_stop_fan_out(app: App) -> None:
    await _seed(app)
    mail = FakeEmail(sender="x@example.net", recipient=MAIL_LIST, fail_for={"a@example.com"})
    result = await app.handle_email(mail)
    assert mail.forwarded == ["b@example.com"]
    assert (result.delivered, result.failed) == (1, 1)


async def test_scheduled_syncs_verification_and_purges(
    app: App, http: FakeHttp, clock: Clock
) -> None:
    await _seed(app)
    http.add_destination("c@example.com", verified=True)
    http.add_destination("a@example.com", verified=False)
    http.add_destination("unknown@example.com", verified=True)
    await app.repo.save_pending(
        PendingPrompt(
            tg_user_id=9,
            chat_id=9,
            source_chat_id=GROUP_ID,
            prompt_message_id=1,
            created_at=clock.now - timedelta(hours=1),
        )
    )
    changed = await app.handle_scheduled()
    assert changed == 2
    assert await app.repo.list_verified_emails() == ["b@example.com", "c@example.com"]
    c = await app.repo.get_subscriber(3)
    assert c is not None
    assert c.cf_address_id == "id-c@example.com"
    assert await app.repo.get_pending(9, 9) is None
    assert await app.handle_scheduled() == 0
