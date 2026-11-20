"""Telegram update routing: group commands, deep-link /start, e-mail replies."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from nestkeeper import texts
from nestkeeper.clients.cloudflare import CloudflareClient, CloudflareError
from nestkeeper.clients.telegram import TelegramClient, TelegramError
from nestkeeper.http import HttpError
from nestkeeper.logging import get_logger
from nestkeeper.models.cloudflare import DestinationAddress
from nestkeeper.models.domain import Member, PendingPrompt, Subscriber, normalise_email, utcnow
from nestkeeper.models.telegram import (
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyParameters,
    SendMessage,
    Update,
    User,
)
from nestkeeper.settings import Settings
from nestkeeper.storage import EmailTakenError, Repository

log = get_logger(__name__)

PENDING_TTL_SECONDS = 15 * 60
START_PAYLOAD_PREFIX = "add_"


class Command(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    args: str = ""


def parse_command(text: str | None, bot_username: str) -> Command | None:
    """Parse ``/cmd[@bot] args``; commands addressed to another bot return ``None``."""
    if not text or not text.startswith("/"):
        return None
    head, _, args = text.strip().partition(" ")
    name, _, target = head[1:].partition("@")
    if not name or (target and target.lower() != bot_username.lower()):
        return None
    return Command(name=name.lower(), args=args.strip())


def deep_link(bot_username: str, source_chat_id: int) -> str:
    return f"https://t.me/{bot_username}?start={START_PAYLOAD_PREFIX}{source_chat_id}"


def parse_start_payload(args: str) -> int | None:
    if not args.startswith(START_PAYLOAD_PREFIX):
        return None
    try:
        return int(args.removeprefix(START_PAYLOAD_PREFIX))
    except ValueError:
        return None


class Bot:
    def __init__(
        self,
        settings: Settings,
        telegram: TelegramClient,
        cloudflare: CloudflareClient,
        repo: Repository,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._settings = settings
        self._tg = telegram
        self._cf = cloudflare
        self._repo = repo
        self._clock = clock

    # --- entry point -------------------------------------------------------
    async def handle_update(self, update: Update) -> None:
        message = update.message
        if message is None or message.from_user is None or message.from_user.is_bot:
            return
        if message.is_group:
            await self._handle_group(message, message.from_user)
        elif message.is_private:
            await self._handle_private(message, message.from_user)

    # --- group -------------------------------------------------------------
    async def _handle_group(self, message: Message, user: User) -> None:
        chat_id = message.chat.id
        if chat_id not in self._settings.allowed_chat_ids:
            log.info("group_not_allowed", chat_id=chat_id)
            return
        command = parse_command(message.text, self._settings.bot_username)
        if command is not None:
            if command.name == texts.CMD_GET_MAIL_LIST:
                await self._repo.add_member(Member(tg_user_id=user.id, chat_id=chat_id))
                await self._reply(
                    message, texts.MAIL_LIST_REPLY.format(mail_list=self._settings.mail_list)
                )
            elif command.name == texts.CMD_ADD_ME:
                await self._start_group_prompt(message, user)
            return
        reply_to = message.reply_to_message
        if reply_to is None or message.text is None:
            return
        pending = await self._repo.get_pending(user.id, chat_id)
        if pending is None or pending.prompt_message_id != reply_to.message_id:
            return
        await self._tg.delete_message(chat_id, message.message_id)
        await self._submit_email(message, user, pending, reply_to_id=reply_to.message_id)

    async def _start_group_prompt(self, message: Message, user: User) -> None:
        chat_id = message.chat.id
        await self._repo.add_member(Member(tg_user_id=user.id, chat_id=chat_id))
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=texts.SEND_PRIVATELY_BUTTON,
                        url=deep_link(self._settings.bot_username, chat_id),
                    )
                ]
            ]
        )
        sent = await self._tg.send_message(
            SendMessage(
                chat_id=chat_id,
                text=texts.ASK_EMAIL_GROUP,
                reply_parameters=ReplyParameters(message_id=message.message_id),
                reply_markup=keyboard,
            )
        )
        await self._repo.save_pending(
            PendingPrompt(
                tg_user_id=user.id,
                chat_id=chat_id,
                source_chat_id=chat_id,
                prompt_message_id=sent.message_id,
                created_at=self._clock(),
            )
        )

    # --- private -----------------------------------------------------------
    async def _handle_private(self, message: Message, user: User) -> None:
        command = parse_command(message.text, self._settings.bot_username)
        if command is not None:
            if command.name == "start":
                await self._start_private_prompt(message, user, command.args)
            return
        if message.text is None:
            return
        pending = await self._repo.get_pending(user.id, message.chat.id)
        if pending is None:
            return
        await self._submit_email(message, user, pending, reply_to_id=message.message_id)

    async def _start_private_prompt(self, message: Message, user: User, args: str) -> None:
        source_chat_id = parse_start_payload(args)
        if source_chat_id is None or source_chat_id not in self._settings.allowed_chat_ids:
            return
        if not await self._repo.is_member(user.id, source_chat_id):
            log.info("dm_from_unknown_member", source_chat_id=source_chat_id)
            return
        sent = await self._tg.send_message(
            SendMessage(
                chat_id=message.chat.id,
                text=texts.ASK_EMAIL_PRIVATE,
                reply_markup=ForceReply(input_field_placeholder=texts.EMAIL_PLACEHOLDER),
            )
        )
        await self._repo.save_pending(
            PendingPrompt(
                tg_user_id=user.id,
                chat_id=message.chat.id,
                source_chat_id=source_chat_id,
                prompt_message_id=sent.message_id,
                created_at=self._clock(),
            )
        )

    # --- e-mail submission -------------------------------------------------
    async def _submit_email(
        self, message: Message, user: User, pending: PendingPrompt, *, reply_to_id: int
    ) -> None:
        chat_id = message.chat.id
        if pending.is_expired(self._clock(), PENDING_TTL_SECONDS):
            await self._repo.delete_pending(user.id, chat_id)
            await self._send(chat_id, texts.PROMPT_EXPIRED, reply_to_id)
            return
        try:
            email = normalise_email(message.text or "")
        except ValueError:
            await self._send(chat_id, texts.INVALID_EMAIL, reply_to_id)
            return
        reply, done = await self.register(user, email, pending.source_chat_id)
        if done:
            await self._repo.delete_pending(user.id, chat_id)
        await self._send(chat_id, reply, reply_to_id)

    async def register(self, user: User, email: str, source_chat_id: int) -> tuple[str, bool]:
        """Register ``email`` for ``user``; returns (reply text, finished?)."""
        owner = await self._repo.get_subscriber_by_email(email)
        if owner is not None and owner.tg_user_id != user.id:
            return texts.EMAIL_TAKEN, True
        try:
            destination = await self._ensure_destination(email)
        except (CloudflareError, HttpError) as exc:
            log.error("register_failed", user_id=user.id, error=str(exc))
            return texts.REGISTRATION_FAILED, False
        current = await self._repo.get_subscriber(user.id)
        now = self._clock()
        subscriber = Subscriber(
            tg_user_id=user.id,
            tg_username=user.username,
            email=email,
            source_chat_id=source_chat_id,
            verified=destination.is_verified,
            cf_address_id=destination.id,
            created_at=current.created_at if current else now,
            updated_at=now,
        )
        try:
            await self._repo.upsert_subscriber(subscriber)
        except EmailTakenError:
            return texts.EMAIL_TAKEN, True
        log.info("subscriber_registered", user_id=user.id, email=email)
        if destination.is_verified:
            return texts.SUCCESS_ALREADY_VERIFIED, True
        return texts.SUCCESS_VERIFY, True

    async def _ensure_destination(self, email: str) -> DestinationAddress:
        try:
            return await self._cf.create_destination(email)
        except CloudflareError as exc:
            # Most likely the address already exists (e.g. re-registration): look it up.
            existing = await self._cf.find_destination(email)
            if existing is None:
                raise
            log.info("destination_exists", email=email, status=exc.status)
            return existing

    # --- helpers -----------------------------------------------------------
    async def _reply(self, message: Message, text: str) -> None:
        await self._send(message.chat.id, text, message.message_id)

    async def _send(self, chat_id: int, text: str, reply_to_id: int | None) -> None:
        params = ReplyParameters(message_id=reply_to_id) if reply_to_id is not None else None
        try:
            await self._tg.send_message(
                SendMessage(chat_id=chat_id, text=text, reply_parameters=params)
            )
        except (TelegramError, HttpError) as exc:
            log.error("send_message_failed", chat_id=chat_id, error=str(exc))
