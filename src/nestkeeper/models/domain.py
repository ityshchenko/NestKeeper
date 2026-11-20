"""Domain models stored in D1."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

# Pragmatic address check: local@domain.tld, no spaces, single "@".
_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}$")
MAX_EMAIL_LENGTH = 254


def normalise_email(value: str) -> str:
    """Strip and lower-case an e-mail address, raising ``ValueError`` if invalid."""
    candidate = value.strip().lower()
    if len(candidate) > MAX_EMAIL_LENGTH or not _EMAIL_RE.fullmatch(candidate):
        raise ValueError("invalid e-mail address")
    local, _, domain = candidate.partition("@")
    if local.startswith(".") or local.endswith(".") or ".." in local:
        raise ValueError("invalid e-mail address")
    if any(label.startswith("-") or label.endswith("-") for label in domain.split(".")):
        raise ValueError("invalid e-mail address")
    return candidate


EmailAddress = Annotated[str, AfterValidator(normalise_email)]


def utcnow() -> datetime:
    return datetime.now(UTC)


class Subscriber(BaseModel):
    model_config = ConfigDict(frozen=True)

    tg_user_id: int
    tg_username: str | None = None
    email: EmailAddress
    source_chat_id: int
    verified: bool = False
    cf_address_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PendingPrompt(BaseModel):
    """An open "send me your e-mail" prompt for a user in a chat (group or private)."""

    model_config = ConfigDict(frozen=True)

    tg_user_id: int
    chat_id: int
    source_chat_id: int
    prompt_message_id: int
    created_at: datetime = Field(default_factory=utcnow)

    def is_expired(self, now: datetime, ttl_seconds: int) -> bool:
        return (now - self.created_at).total_seconds() > ttl_seconds


class Member(BaseModel):
    model_config = ConfigDict(frozen=True)

    tg_user_id: int
    chat_id: int
