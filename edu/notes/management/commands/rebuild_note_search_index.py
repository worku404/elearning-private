from django.core.management.base import BaseCommand

from notes.search import rebuild_note_search_index


class Command(BaseCommand):
    help = "Rebuild denormalized PostgreSQL search documents for notes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--note-id",
            action="append",
            type=int,
            dest="note_ids",
            help="Optional note id filter. Repeat for multiple ids.",
        )

    def handle(self, *args, **options):
        note_ids = options.get("note_ids") or None
        result = rebuild_note_search_index(note_ids=note_ids)
        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Note search index rebuilt: "
                    f"processed={result['processed']}, "
                    f"created={result['created']}, "
                    f"updated={result['updated']}"
                )
            )
        )
