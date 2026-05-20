from __future__ import annotations

import time
from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from learning_insights.models import InsightNotification
from learning_insights.models import TelegramSubscription
from learning_insights.services.common import get_or_create_notification_preference
from learning_insights.services.common import get_local_now
from learning_insights.services.notifications import (
    ensure_due_notifications,
    maybe_create_inactivity_warning_notification,
)
from learning_insights.services.telegram import (
    TelegramUpdateProcessor,
    fetch_updates,
    get_bot_token,
    send_notification,
)


class Command(BaseCommand):
    help = (
        "Run a single background worker: poll Telegram updates (getUpdates) and "
        "send scheduled + event-based Learning Insights notifications."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single loop iteration and exit (useful for schedulers).",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=25,
            help="Long polling timeout in seconds (Telegram getUpdates timeout).",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=1.0,
            help="Delay between loops in seconds.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum updates to fetch per request.",
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=None,
            help="Override the stored offset for the next poll.",
        )
        parser.add_argument(
            "--reset-offset",
            action="store_true",
            help="Forget the stored offset and start from the latest available updates.",
        )
        parser.add_argument(
            "--notify-every",
            type=float,
            default=60.0,
            help="How often to evaluate notification rules (seconds).",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="Only process a single user id (useful for local testing).",
        )

    def handle(self, *args, **options):
        token = get_bot_token()
        if not token:
            self.stderr.write(
                "TELEGRAM_BOT_TOKEN is not configured. Set it in your environment or .env."
            )
            return

        cache_key = "li_telegram_update_offset"
        if options["reset_offset"]:
            cache.delete(cache_key)

        offset = options["offset"]
        if offset is None:
            offset = cache.get(cache_key)

        timeout = int(options["timeout"] or 25)
        limit = int(options["limit"] or 100)
        sleep_seconds = float(options["sleep"] or 0)
        notify_every = float(options["notify_every"] or 60.0)
        run_once = bool(options["once"])
        target_user_id = options.get("user_id")

        processor = TelegramUpdateProcessor(token=token)
        last_notify_at = 0.0

        self.stdout.write(
            "Learning Insights worker started "
            f"(timeout={timeout}s, limit={limit}, offset={offset}, notify_every={notify_every}s)."
        )

        while True:
            try:
                updates = fetch_updates(
                    token=token,
                    offset=offset,
                    timeout=timeout,
                    limit=limit,
                )
                if updates:
                    processor.process_updates(updates)
                    max_update_id = max(
                        (
                            update.get("update_id")
                            for update in updates
                            if isinstance(update.get("update_id"), int)
                        ),
                        default=None,
                    )
                    if isinstance(max_update_id, int):
                        offset = max_update_id + 1
                        cache.set(cache_key, offset, timeout=None)
            except KeyboardInterrupt:
                self.stdout.write("Stopped.")
                return
            except Exception as exc:
                self.stderr.write(f"Worker polling error: {exc}")

            now = time.time()
            if now - last_notify_at >= notify_every:
                last_notify_at = now
                self._dispatch_notifications(user_id=target_user_id)

            if run_once:
                return

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    def _dispatch_notifications(self, *, user_id: int | None = None) -> None:
        qs = TelegramSubscription.objects.select_related("user").order_by("id")
        if user_id:
            qs = qs.filter(user_id=int(user_id))

        sent_count = 0
        daily_summary_count = 0

        for subscription in qs:
            user = subscription.user
            preference = get_or_create_notification_preference(user)

            if not getattr(preference, "telegram_enabled", False):
                continue

            local_now = get_local_now(preference=preference)
            maybe_create_inactivity_warning_notification(
                user=user,
                preference=preference,
                local_now=local_now,
            )

            ensure_due_notifications(user)

            sent_count += self._send_pending_notifications(
                subscription=subscription,
                limit=12,
            )
            if self._send_daily_summary(subscription=subscription):
                daily_summary_count += 1

        if sent_count or daily_summary_count:
            self.stdout.write(
                f"Telegram sent: notifications={sent_count}, daily_summary={daily_summary_count}."
            )

    def _format_notification_message(self, notification: InsightNotification) -> str:
        title = (notification.title or "").strip()
        body = (notification.body or "").strip()
        if title and body:
            return f"{title}\n\n{body}"
        return title or body or "Learning Insights update"

    def _send_pending_notifications(
        self,
        *,
        subscription: TelegramSubscription,
        limit: int = 10,
    ) -> int:
        user = subscription.user
        preference = get_or_create_notification_preference(user)

        if not getattr(preference, "telegram_enabled", False):
            return 0

        now = timezone.now()
        pending = (
            InsightNotification.objects.filter(
                user=user,
                telegram_sent_at__isnull=True,
                dismissed_at__isnull=True,
                scheduled_for__lte=now,
                created__gte=subscription.created_at - timedelta(seconds=5),
            )
            .exclude(category=InsightNotification.CATEGORY_DAILY_ACHIEVEMENT)
            .order_by("scheduled_for", "id")
        )

        sent_ids: list[int] = []
        for notification in pending[: max(1, int(limit or 10))]:
            ok = send_notification(
                user=user,
                message=self._format_notification_message(notification),
            )
            if ok:
                sent_ids.append(notification.id)

        if sent_ids:
            InsightNotification.objects.filter(id__in=sent_ids).update(telegram_sent_at=now)
        return len(sent_ids)

    def _send_daily_summary(self, *, subscription: TelegramSubscription) -> bool:
        user = subscription.user
        preference = get_or_create_notification_preference(user)
        if not getattr(preference, "telegram_enabled", False):
            return False

        local_now = get_local_now(preference=preference)
        now_time = local_now.time()

        evening_start = getattr(preference, "telegram_evening_summary_start", None)
        evening_end = getattr(preference, "telegram_evening_summary_end", None)
        morning_start = getattr(preference, "telegram_morning_summary_start", None)
        morning_end = getattr(preference, "telegram_morning_summary_end", None)

        def within_window(current, start, end) -> bool:
            if start is None or end is None:
                return False
            if start <= end:
                return start <= current <= end
            return current >= start or current <= end

        target_date = None
        if within_window(now_time, evening_start, evening_end):
            target_date = local_now.date()
        elif within_window(now_time, morning_start, morning_end):
            target_date = local_now.date() - timedelta(days=1)
        else:
            return False

        dedupe_key = f"daily-achievement:{target_date.isoformat()}"
        notification = (
            InsightNotification.objects.filter(
                user=user,
                category=InsightNotification.CATEGORY_DAILY_ACHIEVEMENT,
                dedupe_key=dedupe_key,
                telegram_sent_at__isnull=True,
                dismissed_at__isnull=True,
            )
            .order_by("-scheduled_for", "-id")
            .first()
        )
        if notification is None:
            # Ensure we create it when we're inside a valid window.
            ensure_due_notifications(user)
            notification = (
                InsightNotification.objects.filter(
                    user=user,
                    category=InsightNotification.CATEGORY_DAILY_ACHIEVEMENT,
                    dedupe_key=dedupe_key,
                    telegram_sent_at__isnull=True,
                    dismissed_at__isnull=True,
                )
                .order_by("-scheduled_for", "-id")
                .first()
            )

        if notification is None:
            return False

        ok = send_notification(
            user=user,
            message=self._format_notification_message(notification),
        )
        if ok:
            notification.telegram_sent_at = timezone.now()
            notification.save(update_fields=["telegram_sent_at"])
        return ok
