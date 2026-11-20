"""Mail-list fan-out (Email Worker) and destination verification sync (cron)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from nestkeeper.clients.cloudflare import CloudflareClient
from nestkeeper.logging import get_logger
from nestkeeper.settings import Settings
from nestkeeper.storage import Repository

log = get_logger(__name__)

# SMTP rejection reasons are returned to the sending MTA, so they stay ASCII/English.
REJECT_WRONG_RECIPIENT = "Unknown recipient"
REJECT_NOT_SUBSCRIBER = "Only list subscribers may post to this list"


class IncomingEmail(Protocol):
    @property
    def sender(self) -> str: ...

    @property
    def recipient(self) -> str: ...

    async def forward(self, to: str) -> None: ...

    def reject(self, reason: str) -> None: ...


class FanOutResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rejected: str | None = None
    delivered: int = 0
    failed: int = 0


async def fan_out(message: IncomingEmail, settings: Settings, repo: Repository) -> FanOutResult:
    recipient = message.recipient.strip().lower()
    sender = message.sender.strip().lower()
    if recipient != settings.mail_list:
        message.reject(REJECT_WRONG_RECIPIENT)
        log.warning("email_rejected", reason="recipient", recipient=recipient)
        return FanOutResult(rejected=REJECT_WRONG_RECIPIENT)
    subscribers = await repo.list_verified_emails()
    if settings.restrict_senders and sender not in subscribers:
        message.reject(REJECT_NOT_SUBSCRIBER)
        log.warning("email_rejected", reason="sender", sender=sender)
        return FanOutResult(rejected=REJECT_NOT_SUBSCRIBER)
    delivered = failed = 0
    for address in subscribers:
        if address in {sender, settings.mail_list}:
            continue
        try:
            await message.forward(address)
        except Exception as exc:  # noqa: BLE001 - one bad recipient must not stop the fan-out
            failed += 1
            log.error("forward_failed", to=address, error=str(exc))
        else:
            delivered += 1
    log.info("email_fanned_out", sender=sender, delivered=delivered, failed=failed)
    return FanOutResult(delivered=delivered, failed=failed)


async def sync_verification(cf: CloudflareClient, repo: Repository, now: datetime) -> int:
    """Copy Cloudflare's verification state into D1; returns the number of updated rows."""
    changed = 0
    for address in await cf.list_destinations():
        if await repo.set_verification(
            address.email.lower(),
            verified=address.is_verified,
            cf_address_id=address.id,
            now=now,
        ):
            changed += 1
    log.info("verification_synced", changed=changed)
    return changed
