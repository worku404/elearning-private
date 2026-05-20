from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from typing import Any, Iterable

import requests
from django.conf import settings
from django.db import IntegrityError
from django.db import transaction

from learning_insights.models import TelegramConnectToken, TelegramSubscription

logger = logging.getLogger(__name__)

TELEGRAM_TEXT_LIMIT = 4096


class TelegramApiError(RuntimeError):
    pass


def get_bot_token() -> str | None:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", None) or os.getenv("TELEGRAM_BOT_TOKEN")
    token = (token or "").strip()
    return token or None


def get_bot_username() -> str | None:
    username = getattr(settings, "TELEGRAM_BOT_USERNAME", None) or os.getenv(
        "TELEGRAM_BOT_USERNAME"
    )
    username = (username or "").strip().lstrip("@")
    return username or None


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def fetch_updates(
    *,
    token: str,
    offset: int | None = None,
    timeout: int = 25,
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"timeout": timeout, "limit": limit}
    if offset is not None:
        params["offset"] = offset

    response = requests.get(
        _api_url(token, "getUpdates"),
        params=params,
        timeout=max(timeout + 10, 15),
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise TelegramApiError(f"Telegram getUpdates failed: {payload!r}")
    result = payload.get("result") or []
    if not isinstance(result, list):
        return []
    return [item for item in result if isinstance(item, dict)]


def send_message(*, token: str, chat_id: int, text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Telegram message text cannot be empty.")

    if len(text) > TELEGRAM_TEXT_LIMIT:
        text = text[: TELEGRAM_TEXT_LIMIT - 1] + "…"

    response = requests.post(
        _api_url(token, "sendMessage"),
        data={
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise TelegramApiError(f"Telegram sendMessage failed: {payload!r}")
    return payload


def send_notification(*, user, message: str) -> bool:
    """
    Send a Telegram message to the given user if Telegram is configured and linked.

    Returns True if the message was sent successfully.
    """

    message = (message or "").strip()
    if not message:
        return False

    token = get_bot_token()
    if not token:
        return False

    subscription = get_subscription_for_user(user=user)
    if subscription is None:
        return False

    try:
        send_message(token=token, chat_id=int(subscription.chat_id), text=message)
    except Exception:
        logger.exception(
            "Failed sending Telegram message (user_id=%s).",
            getattr(user, "id", None),
        )
        return False

    return True


def generate_connect_token(*, user) -> TelegramConnectToken:
    with transaction.atomic():
        TelegramConnectToken.objects.filter(user=user, is_used=False).update(is_used=True)

        for _ in range(6):
            token_value = secrets.token_urlsafe(18)
            try:
                return TelegramConnectToken.objects.create(
                    user=user,
                    token=token_value,
                    is_used=False,
                )
            except IntegrityError:
                # Rare collision; retry with a new token value.
                continue

    raise TelegramApiError("Unable to generate a unique connect token.")


def get_active_connect_token(*, user) -> TelegramConnectToken | None:
    return (
        TelegramConnectToken.objects.filter(user=user, is_used=False)
        .order_by("-created_at", "-id")
        .first()
    )


def get_subscription_for_user(*, user) -> TelegramSubscription | None:
    try:
        return TelegramSubscription.objects.get(user=user)
    except TelegramSubscription.DoesNotExist:
        return None


def link_chat_id_to_user(*, user, chat_id: int) -> TelegramSubscription:
    with transaction.atomic():
        subscription, _ = TelegramSubscription.objects.get_or_create(
            user=user,
            defaults={"chat_id": chat_id},
        )
        if subscription.chat_id != chat_id:
            subscription.chat_id = chat_id
            subscription.save(update_fields=["chat_id"])
        return subscription


def _parse_start_token(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None

    parts = raw.split()
    if not parts:
        return None

    command = parts[0].split("@", 1)[0].lower()
    if command != "/start":
        return None

    if len(parts) < 2:
        return None
    return parts[1].strip()


@dataclass(slots=True)
class TelegramUpdateProcessor:
    """
    Stateless update processor shared by polling and future webhook entrypoints.
    """

    token: str | None = None

    def process_updates(self, updates: Iterable[dict[str, Any]]) -> int:
        processed = 0
        for update in updates:
            try:
                if self.process_update(update):
                    processed += 1
            except Exception:
                logger.exception("Failed processing Telegram update: %s", update)
        return processed

    def process_update(self, update: dict[str, Any]) -> bool:
        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict):
            return False

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return False

        text = (message.get("text") or "").strip()
        if not text:
            return False

        token_value = _parse_start_token(text)
        if not token_value:
            return False

        return self._handle_start(chat_id=int(chat_id), token_value=token_value)

    def _handle_start(self, *, chat_id: int, token_value: str) -> bool:
        connect_token = (
            TelegramConnectToken.objects.select_related("user")
            .filter(token=token_value, is_used=False)
            .first()
        )
        if connect_token is None:
            logger.info("Telegram /start with invalid token: %s", token_value)
            return False

        with transaction.atomic():
            connect_token.is_used = True
            connect_token.save(update_fields=["is_used"])

            link_chat_id_to_user(user=connect_token.user, chat_id=chat_id)

        if self.token:
            try:
                send_message(
                    token=self.token,
                    chat_id=chat_id,
                    text="Telegram connected. You will receive Learning Insights notifications here.",
                )
            except Exception:
                logger.exception(
                    "Failed sending Telegram connect confirmation (chat_id=%s).",
                    chat_id,
                )
        return True
