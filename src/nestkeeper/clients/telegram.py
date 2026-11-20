"""Minimal Telegram Bot API client."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, SecretStr, ValidationError

from nestkeeper.http import HttpClient, HttpError
from nestkeeper.logging import get_logger
from nestkeeper.models.telegram import (
    DeleteMessage,
    SendMessage,
    SentMessage,
    SetMyCommands,
    SetWebhook,
    TelegramResponse,
)

log = get_logger(__name__)

API_BASE = "https://api.telegram.org"


class TelegramError(Exception):
    def __init__(self, method: str, description: str | None, error_code: int | None) -> None:
        super().__init__(f"{method} failed: {error_code} {description}")
        self.method = method
        self.description = description
        self.error_code = error_code


class TelegramClient:
    def __init__(self, http: HttpClient, token: SecretStr) -> None:
        self._http = http
        self._token = token

    async def _call(self, method: str, payload: BaseModel) -> Any:
        url = f"{API_BASE}/bot{self._token.get_secret_value()}/{method}"
        body = payload.model_dump(mode="json", exclude_none=True, by_alias=True)
        response = await self._http.request("POST", url, json_body=body)
        try:
            parsed = TelegramResponse.model_validate(response.json_body())
        except (ValueError, ValidationError) as exc:
            raise HttpError(f"{method}: unexpected response (HTTP {response.status})") from exc
        if not parsed.ok:
            raise TelegramError(method, parsed.description, parsed.error_code)
        return parsed.result

    async def send_message(self, message: SendMessage) -> SentMessage:
        result = await self._call("sendMessage", message)
        return SentMessage.model_validate(result)

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        """Delete a message; returns ``False`` (and logs) if the bot lacks rights."""
        try:
            await self._call("deleteMessage", DeleteMessage(chat_id=chat_id, message_id=message_id))
        except TelegramError as exc:
            log.warning("delete_message_failed", chat_id=chat_id, error=exc.description)
            return False
        return True

    async def set_my_commands(self, request: SetMyCommands) -> None:
        await self._call("setMyCommands", request)

    async def set_webhook(self, request: SetWebhook) -> None:
        await self._call("setWebhook", request)
