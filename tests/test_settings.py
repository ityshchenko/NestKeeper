from __future__ import annotations

import pytest
from pydantic import ValidationError

from nestkeeper.settings import Settings
from tests.conftest import GROUP_ID


def test_from_env_parses_values(env: dict[str, str]) -> None:
    env["ALLOWED_CHAT_IDS"] = f"{GROUP_ID}, -100777 ,"
    env["BOT_USERNAME"] = "@SomeBot"
    env["MAIL_LIST"] = " List@Example.ORG "
    env["RESTRICT_SENDERS"] = "Yes"
    settings = Settings.from_env(env.get)
    assert settings.allowed_chat_ids == frozenset({GROUP_ID, -100777})
    assert settings.bot_username == "SomeBot"
    assert settings.mail_list == "list@example.org"
    assert settings.restrict_senders is True
    assert "123:abc" not in repr(settings)


def test_restrict_senders_defaults_false(env: dict[str, str]) -> None:
    del env["RESTRICT_SENDERS"]
    assert Settings.from_env(env.get).restrict_senders is False


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("MAIL_LIST", "not-an-email"),
        ("ALLOWED_CHAT_IDS", "abc"),
        ("WEBHOOK_SECRET", "short"),
        ("ADMIN_TOKEN", "short"),
        ("BOT_USERNAME", ""),
    ],
)
def test_invalid_values_rejected(env: dict[str, str], key: str, value: str) -> None:
    env[key] = value
    with pytest.raises(ValidationError):
        Settings.from_env(env.get)


def test_missing_required_value(env: dict[str, str]) -> None:
    del env["BOT_TOKEN"]
    with pytest.raises(ValidationError, match="bot_token"):
        Settings.from_env(env.get)
