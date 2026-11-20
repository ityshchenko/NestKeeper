from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nestkeeper.models.cloudflare import ApiResponse, DestinationAddress
from nestkeeper.models.domain import PendingPrompt, normalise_email
from nestkeeper.models.telegram import Update


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Alice@Example.COM ", "alice@example.com"),
        ("a.b+tag@sub.example.co.uk", "a.b+tag@sub.example.co.uk"),
    ],
)
def test_normalise_email_valid(raw: str, expected: str) -> None:
    assert normalise_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "plain",
        "a@b",
        "a @example.com",
        "a@@example.com",
        ".a@example.com",
        "a.@example.com",
        "a..b@example.com",
        "a@-example.com",
        "a@example-.com",
        f"{'a' * 250}@example.com",
    ],
)
def test_normalise_email_invalid(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid"):
        normalise_email(raw)


def test_pending_expiry() -> None:
    created = datetime(2026, 1, 1, tzinfo=UTC)
    prompt = PendingPrompt(
        tg_user_id=1, chat_id=2, source_chat_id=2, prompt_message_id=3, created_at=created
    )
    assert not prompt.is_expired(created + timedelta(seconds=60), 900)
    assert prompt.is_expired(created + timedelta(seconds=901), 900)


def test_update_ignores_unknown_fields_and_maps_from() -> None:
    update = Update.model_validate(
        {
            "update_id": 1,
            "unknown": True,
            "message": {
                "message_id": 5,
                "chat": {"id": -1, "type": "group", "extra": 1},
                "from": {"id": 7, "is_bot": False, "first_name": "X"},
                "text": "hi",
            },
        }
    )
    assert update.message is not None
    assert update.message.from_user is not None
    assert update.message.from_user.id == 7
    assert update.message.is_group
    assert not update.message.is_private


def test_destination_verified_flag() -> None:
    parsed = ApiResponse.model_validate(
        {"success": True, "result": {"id": "x", "email": "a@b.cd", "verified": None}}
    )
    address = DestinationAddress.model_validate(parsed.result)
    assert not address.is_verified
