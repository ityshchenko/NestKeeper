"""Admin operations: webhook/commands setup and subscriber CSV export."""

from __future__ import annotations

import csv
import hmac
import io

from pydantic import SecretStr

from nestkeeper import texts
from nestkeeper.clients.telegram import TelegramClient
from nestkeeper.models.telegram import BotCommand, BotCommandScope, SetMyCommands, SetWebhook
from nestkeeper.settings import Settings
from nestkeeper.storage import Repository

ALLOWED_UPDATES = ["message"]
COMMAND_LANGUAGES: tuple[str | None, ...] = (None, "uk")
EXPORT_COLUMNS = (
    "tg_user_id",
    "tg_username",
    "email",
    "source_chat_id",
    "verified",
    "cf_address_id",
    "created_at",
    "updated_at",
)


def check_bearer(header: str | None, token: SecretStr) -> bool:
    if not header or not header.startswith("Bearer "):
        return False
    supplied = header.removeprefix("Bearer ").strip().encode()
    return hmac.compare_digest(supplied, token.get_secret_value().encode())


def bot_commands() -> list[BotCommand]:
    return [
        BotCommand(command=name, description=description)
        for name, description in texts.COMMAND_DESCRIPTIONS.items()
    ]


async def setup(settings: Settings, telegram: TelegramClient, webhook_url: str) -> None:
    await telegram.set_webhook(
        SetWebhook(
            url=webhook_url,
            secret_token=settings.webhook_secret.get_secret_value(),
            allowed_updates=ALLOWED_UPDATES,
        )
    )
    for language in COMMAND_LANGUAGES:
        await telegram.set_my_commands(
            SetMyCommands(
                commands=bot_commands(),
                scope=BotCommandScope(type="all_group_chats"),
                language_code=language,
            )
        )


async def export_csv(repo: Repository) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(EXPORT_COLUMNS)
    for sub in await repo.list_subscribers():
        writer.writerow(
            [
                sub.tg_user_id,
                sub.tg_username or "",
                sub.email,
                sub.source_chat_id,
                int(sub.verified),
                sub.cf_address_id or "",
                sub.created_at.isoformat(),
                sub.updated_at.isoformat(),
            ]
        )
    return buffer.getvalue()
