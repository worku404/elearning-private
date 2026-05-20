from django.core.management.base import BaseCommand

from courses.search import rebuild_content_search_index


class Command(BaseCommand):
    help = "Rebuild denormalized PostgreSQL search documents for course content."

    def add_arguments(self, parser):
        parser.add_argument(
            "--content-id",
            action="append",
            type=int,
            dest="content_ids",
            help="Optional content id filter. Repeat for multiple ids.",
        )

    def handle(self, *args, **options):
        content_ids = options.get("content_ids") or None
        result = rebuild_content_search_index(content_ids=content_ids)
        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Content search index rebuilt: "
                    f"processed={result['processed']}, "
                    f"created={result['created']}"
                )
            )
        )
