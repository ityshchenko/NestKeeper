"""Worker configuration validated from the Worker environment (vars + secrets)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from nestkeeper.models.domain import EmailAddress

ENV_KEYS: tuple[str, ...] = (
    "BOT_TOKEN",
    "BOT_USERNAME",
    "WEBHOOK_SECRET",
    "MAIL_LIST",
    "ALLOWED_CHAT_IDS",
    "CF_ACCOUNT_ID",
    "CF_API_TOKEN",
    "ADMIN_TOKEN",
    "RESTRICT_SENDERS",
)

NonEmpty = Annotated[str, Field(min_length=1)]


class Settings(BaseModel):
    """Runtime settings. Field names match the Worker env keys (lower-cased)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bot_token: SecretStr
    bot_username: NonEmpty
    webhook_secret: SecretStr = Field(min_length=16)
    mail_list: EmailAddress
    allowed_chat_ids: frozenset[int]
    cf_account_id: NonEmpty
    cf_api_token: SecretStr
    admin_token: SecretStr = Field(min_length=16)
    restrict_senders: bool = False

    @field_validator("bot_username")
    @classmethod
    def _strip_at(cls, value: str) -> str:
        return value.strip().removeprefix("@")

    @field_validator("allowed_chat_ids", mode="before")
    @classmethod
    def _parse_chat_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return frozenset(int(part) for part in value.split(",") if part.strip())
        return value

    @field_validator("restrict_senders", mode="before")
    @classmethod
    def _parse_bool(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return value

    @classmethod
    def from_env(cls, getter: Callable[[str], object | None]) -> Settings:
        """Build settings from a key getter (e.g. ``lambda k: getattr(env, k, None)``)."""
        raw: dict[str, object] = {}
        for key in ENV_KEYS:
            value = getter(key)
            if value is not None:
                raw[key.lower()] = str(value)
        return cls.model_validate(raw)
