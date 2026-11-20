"""Subset of the Telegram Bot API used by the bot."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Incoming(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)


class _Outgoing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True, by_alias=True)


class User(_Incoming):
    id: int
    is_bot: bool = False
    first_name: str = ""
    username: str | None = None
    language_code: str | None = None


class Chat(_Incoming):
    id: int
    type: Literal["private", "group", "supergroup", "channel"]
    title: str | None = None


class Message(_Incoming):
    message_id: int
    chat: Chat
    from_user: User | None = Field(default=None, alias="from")
    text: str | None = None
    reply_to_message: Message | None = None

    @property
    def is_private(self) -> bool:
        return self.chat.type == "private"

    @property
    def is_group(self) -> bool:
        return self.chat.type in {"group", "supergroup"}


class Update(_Incoming):
    update_id: int
    message: Message | None = None


class InlineKeyboardButton(_Outgoing):
    text: str
    url: str


class InlineKeyboardMarkup(_Outgoing):
    inline_keyboard: list[list[InlineKeyboardButton]]


class ForceReply(_Outgoing):
    force_reply: Literal[True] = True
    selective: bool = True
    input_field_placeholder: str | None = None


class ReplyParameters(_Outgoing):
    message_id: int
    allow_sending_without_reply: bool = True


class SendMessage(_Outgoing):
    chat_id: int
    text: str
    reply_parameters: ReplyParameters | None = None
    reply_markup: InlineKeyboardMarkup | ForceReply | None = None
    disable_notification: bool | None = None


class DeleteMessage(_Outgoing):
    chat_id: int
    message_id: int


class BotCommand(_Outgoing):
    command: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    description: str = Field(min_length=1, max_length=256)


class BotCommandScope(_Outgoing):
    type: Literal["default", "all_private_chats", "all_group_chats"]


class SetMyCommands(_Outgoing):
    commands: list[BotCommand]
    scope: BotCommandScope | None = None
    language_code: str | None = None


class SetWebhook(_Outgoing):
    url: str
    secret_token: str
    allowed_updates: list[str]
    drop_pending_updates: bool = False


class SentMessage(_Incoming):
    message_id: int


class TelegramResponse(_Incoming):
    ok: bool
    result: Any = None
    description: str | None = None
    error_code: int | None = None
