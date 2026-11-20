"""Persistence: a tiny ``Database`` protocol (D1-shaped) and the typed ``Repository``."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from nestkeeper.models.domain import Member, PendingPrompt, Subscriber

Param = str | int | None
Row = dict[str, Any]


class Database(Protocol):
    async def execute(self, sql: str, params: Sequence[Param] = ()) -> None: ...

    async def query(self, sql: str, params: Sequence[Param] = ()) -> list[Row]: ...


class EmailTakenError(Exception):
    """The e-mail address already belongs to another Telegram user."""


def _ts(value: datetime) -> str:
    return value.isoformat()


_SUBSCRIBER_COLUMNS = (
    "tg_user_id, tg_username, email, source_chat_id, verified, cf_address_id, "
    "created_at, updated_at"
)


def _subscriber(row: Row) -> Subscriber:
    return Subscriber.model_validate({**row, "verified": bool(row["verified"])})


class Repository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # --- subscribers -------------------------------------------------------
    async def get_subscriber(self, tg_user_id: int) -> Subscriber | None:
        rows = await self._db.query(
            f"SELECT {_SUBSCRIBER_COLUMNS} FROM subscribers WHERE tg_user_id = ?",  # noqa: S608
            [tg_user_id],
        )
        return _subscriber(rows[0]) if rows else None

    async def get_subscriber_by_email(self, email: str) -> Subscriber | None:
        rows = await self._db.query(
            f"SELECT {_SUBSCRIBER_COLUMNS} FROM subscribers WHERE email = ?",  # noqa: S608
            [email],
        )
        return _subscriber(rows[0]) if rows else None

    async def upsert_subscriber(self, sub: Subscriber) -> None:
        """Insert or replace the user's single subscription (one e-mail per user)."""
        owner = await self.get_subscriber_by_email(sub.email)
        if owner is not None and owner.tg_user_id != sub.tg_user_id:
            raise EmailTakenError(sub.email)
        await self._db.execute(
            f"INSERT INTO subscribers ({_SUBSCRIBER_COLUMNS}) "  # noqa: S608
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(tg_user_id) DO UPDATE SET "
            "tg_username = excluded.tg_username, email = excluded.email, "
            "source_chat_id = excluded.source_chat_id, verified = excluded.verified, "
            "cf_address_id = excluded.cf_address_id, updated_at = excluded.updated_at",
            [
                sub.tg_user_id,
                sub.tg_username,
                sub.email,
                sub.source_chat_id,
                int(sub.verified),
                sub.cf_address_id,
                _ts(sub.created_at),
                _ts(sub.updated_at),
            ],
        )

    async def list_subscribers(self) -> list[Subscriber]:
        rows = await self._db.query(
            f"SELECT {_SUBSCRIBER_COLUMNS} FROM subscribers ORDER BY created_at, tg_user_id"  # noqa: S608
        )
        return [_subscriber(r) for r in rows]

    async def list_verified_emails(self) -> list[str]:
        rows = await self._db.query(
            "SELECT email FROM subscribers WHERE verified = 1 ORDER BY email"
        )
        return [str(r["email"]) for r in rows]

    async def set_verification(
        self, email: str, *, verified: bool, cf_address_id: str, now: datetime
    ) -> bool:
        """Update verification state; returns ``True`` if a row changed."""
        rows = await self._db.query(
            "SELECT verified, cf_address_id FROM subscribers WHERE email = ?", [email]
        )
        if not rows:
            return False
        row = rows[0]
        if bool(row["verified"]) == verified and row["cf_address_id"] == cf_address_id:
            return False
        await self._db.execute(
            "UPDATE subscribers SET verified = ?, cf_address_id = ?, updated_at = ? "
            "WHERE email = ?",
            [int(verified), cf_address_id, _ts(now), email],
        )
        return True

    # --- pending prompts ---------------------------------------------------
    async def save_pending(self, prompt: PendingPrompt) -> None:
        await self._db.execute(
            "INSERT INTO pending (tg_user_id, chat_id, source_chat_id, prompt_message_id, "
            "created_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(tg_user_id, chat_id) DO UPDATE SET "
            "source_chat_id = excluded.source_chat_id, "
            "prompt_message_id = excluded.prompt_message_id, created_at = excluded.created_at",
            [
                prompt.tg_user_id,
                prompt.chat_id,
                prompt.source_chat_id,
                prompt.prompt_message_id,
                _ts(prompt.created_at),
            ],
        )

    async def get_pending(self, tg_user_id: int, chat_id: int) -> PendingPrompt | None:
        rows = await self._db.query(
            "SELECT tg_user_id, chat_id, source_chat_id, prompt_message_id, created_at "
            "FROM pending WHERE tg_user_id = ? AND chat_id = ?",
            [tg_user_id, chat_id],
        )
        return PendingPrompt.model_validate(rows[0]) if rows else None

    async def delete_pending(self, tg_user_id: int, chat_id: int) -> None:
        await self._db.execute(
            "DELETE FROM pending WHERE tg_user_id = ? AND chat_id = ?", [tg_user_id, chat_id]
        )

    async def purge_pending(self, older_than: datetime) -> None:
        await self._db.execute("DELETE FROM pending WHERE created_at < ?", [_ts(older_than)])

    # --- members -----------------------------------------------------------
    async def add_member(self, member: Member) -> None:
        await self._db.execute(
            "INSERT OR IGNORE INTO members (tg_user_id, chat_id) VALUES (?, ?)",
            [member.tg_user_id, member.chat_id],
        )

    async def is_member(self, tg_user_id: int, chat_id: int) -> bool:
        rows = await self._db.query(
            "SELECT 1 AS present FROM members WHERE tg_user_id = ? AND chat_id = ?",
            [tg_user_id, chat_id],
        )
        return bool(rows)
