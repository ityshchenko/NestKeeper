"""Runtime-independent application: HTTP routing, e-mail and cron handlers.

``entry.py`` adapts Workers objects (Request, D1, EmailMessage) to these plain interfaces.
"""

from __future__ import annotations

import hmac
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, ValidationError

from nestkeeper import admin, emailing
from nestkeeper.clients.cloudflare import CloudflareClient
from nestkeeper.clients.telegram import TelegramClient
from nestkeeper.handlers import PENDING_TTL_SECONDS, Bot
from nestkeeper.http import HttpClient
from nestkeeper.logging import get_logger
from nestkeeper.models.domain import utcnow
from nestkeeper.models.telegram import Update
from nestkeeper.settings import Settings
from nestkeeper.storage import Database, Repository

log = get_logger(__name__)

SECRET_HEADER = "x-telegram-bot-api-secret-token"  # noqa: S105 - header name


class HttpRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: str
    url: str
    headers: Mapping[str, str]
    body: str = ""

    def header(self, name: str) -> str | None:
        lowered = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lowered:
                return value
        return None


class HttpReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: int = 200
    body: str = ""
    content_type: str = "text/plain; charset=utf-8"


class App:
    def __init__(
        self,
        settings: Settings,
        http: HttpClient,
        db: Database,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.settings = settings
        self.repo = Repository(db)
        self.telegram = TelegramClient(http, settings.bot_token)
        self.cloudflare = CloudflareClient(http, settings.cf_account_id, settings.cf_api_token)
        self.bot = Bot(settings, self.telegram, self.cloudflare, self.repo, clock)
        self._clock = clock

    async def handle_http(self, request: HttpRequest) -> HttpReply:
        parts = urlsplit(request.url)
        route = (request.method.upper(), parts.path.rstrip("/") or "/")
        match route:
            case ("POST", "/webhook"):
                return await self._webhook(request)
            case ("POST", "/admin/setup"):
                if not admin.check_bearer(
                    request.header("authorization"), self.settings.admin_token
                ):
                    return HttpReply(status=401, body="unauthorized")
                webhook_url = f"{parts.scheme}://{parts.netloc}/webhook"
                await admin.setup(self.settings, self.telegram, webhook_url)
                log.info("admin_setup_done", webhook_url=webhook_url)
                return HttpReply(body="ok")
            case ("GET", "/admin/export"):
                if not admin.check_bearer(
                    request.header("authorization"), self.settings.admin_token
                ):
                    return HttpReply(status=401, body="unauthorized")
                log.info("admin_export")
                return HttpReply(
                    body=await admin.export_csv(self.repo), content_type="text/csv; charset=utf-8"
                )
            case _:
                return HttpReply(status=404, body="not found")

    async def _webhook(self, request: HttpRequest) -> HttpReply:
        supplied = (request.header(SECRET_HEADER) or "").encode()
        expected = self.settings.webhook_secret.get_secret_value().encode()
        if not hmac.compare_digest(supplied, expected):
            log.warning("webhook_forbidden")
            return HttpReply(status=403, body="forbidden")
        try:
            update = Update.model_validate_json(request.body)
        except ValidationError as exc:
            log.warning("webhook_invalid_update", errors=exc.error_count())
            return HttpReply(body="ignored")
        try:
            await self.bot.handle_update(update)
        except Exception:
            # Always 200 so Telegram does not retry a poison update forever.
            log.exception("update_failed", update_id=update.update_id)
        return HttpReply(body="ok")

    async def handle_email(self, message: emailing.IncomingEmail) -> emailing.FanOutResult:
        return await emailing.fan_out(message, self.settings, self.repo)

    async def handle_scheduled(self) -> int:
        now = self._clock()
        await self.repo.purge_pending(now - timedelta(seconds=PENDING_TTL_SECONDS))
        return await emailing.sync_verification(self.cloudflare, self.repo, now)
