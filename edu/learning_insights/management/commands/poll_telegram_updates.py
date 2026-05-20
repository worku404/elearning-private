from __future__ import annotations

import time

from django.core.cache import cache
from django.core.management.base import BaseCommand

from learning_insights.services.telegram import (
    TelegramUpdateProcessor,
    fetch_updates,
    get_bot_token,
)


class Command(BaseCommand):
    help = "Poll Telegram getUpdates and process /start <token> linking messages."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Poll once and exit (useful for schedulers).",
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
            help="Delay between polling loops in seconds.",
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

        processor = TelegramUpdateProcessor(token=token)
        run_once = bool(options["once"])
        timeout = int(options["timeout"] or 25)
        limit = int(options["limit"] or 100)
        sleep_seconds = float(options["sleep"] or 0)

        self.stdout.write(
            f"Polling Telegram updates (timeout={timeout}s, limit={limit}, offset={offset})."
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
                    processed = processor.process_updates(updates)
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

                    self.stdout.write(
                        f"Fetched {len(updates)} update(s), processed {processed}. Next offset: {offset}."
                    )
            except KeyboardInterrupt:
                self.stdout.write("Stopped.")
                return
            except Exception as exc:
                self.stderr.write(f"Telegram polling error: {exc}")

            if run_once:
                return

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
