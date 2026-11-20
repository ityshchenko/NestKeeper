from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

# NOTE: nestkeeper must NOT be imported at module level here. Conftest files load before
# the typeguard plugin installs its import hook; importing early would disable runtime
# type checking. Import inside fixtures instead.
if TYPE_CHECKING:
    from nestkeeper.app import App
    from nestkeeper.settings import Settings
    from tests.fakes import FakeHttp, SqliteDatabase

GROUP_ID = -1001234567890
OTHER_GROUP_ID = -1009999999999
BOT_USERNAME = "NestKeeperTestBot"
MAIL_LIST = "list@example.org"
WEBHOOK_SECRET = "webhook-secret-0123456789"
ADMIN_TOKEN = "admin-token-0123456789"
USER_ID = 42

ENV: dict[str, str] = {
    "BOT_TOKEN": "123:abc",
    "BOT_USERNAME": BOT_USERNAME,
    "WEBHOOK_SECRET": WEBHOOK_SECRET,
    "MAIL_LIST": MAIL_LIST,
    "ALLOWED_CHAT_IDS": f"{GROUP_ID}",
    "CF_ACCOUNT_ID": "acc123",
    "CF_API_TOKEN": "cf-token",
    "ADMIN_TOKEN": ADMIN_TOKEN,
    "RESTRICT_SENDERS": "false",
}


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture(autouse=True, scope="session")
def _logging() -> None:
    from nestkeeper.logging import configure_logging

    configure_logging()


@pytest.fixture
def env() -> dict[str, str]:
    return dict(ENV)


@pytest.fixture
def settings(env: dict[str, str]) -> Settings:
    from nestkeeper.settings import Settings

    return Settings.from_env(env.get)


@pytest.fixture
def http() -> FakeHttp:
    from tests.fakes import FakeHttp

    return FakeHttp()


@pytest.fixture
def db() -> Iterator[SqliteDatabase]:
    from tests.fakes import SqliteDatabase

    database = SqliteDatabase()
    yield database
    database.conn.close()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def app(settings: Settings, http: FakeHttp, db: SqliteDatabase, clock: Clock) -> App:
    from nestkeeper.app import App

    return App(settings, http, db, clock)


_ids = iter(range(1, 10_000_000))


def message(
    text: str | None,
    *,
    chat_id: int = GROUP_ID,
    chat_type: str = "supergroup",
    user_id: int = USER_ID,
    username: str | None = "alice",
    is_bot: bool = False,
    reply_to: int | None = None,
    message_id: int | None = None,
) -> dict[str, Any]:
    msg: dict[str, Any] = {
        "message_id": message_id if message_id is not None else next(_ids),
        "chat": {"id": chat_id, "type": chat_type},
        "from": {"id": user_id, "is_bot": is_bot, "first_name": "A", "username": username},
        "date": 0,
    }
    if text is not None:
        msg["text"] = text
    if reply_to is not None:
        msg["reply_to_message"] = {
            "message_id": reply_to,
            "chat": {"id": chat_id, "type": chat_type},
            "from": {"id": 1, "is_bot": True, "first_name": "Bot"},
        }
    return {"update_id": next(_ids), "message": msg}


def private(text: str | None, **kwargs: Any) -> dict[str, Any]:
    user_id = kwargs.pop("user_id", USER_ID)
    return message(text, chat_id=user_id, chat_type="private", user_id=user_id, **kwargs)


Factory = Callable[..., dict[str, Any]]
