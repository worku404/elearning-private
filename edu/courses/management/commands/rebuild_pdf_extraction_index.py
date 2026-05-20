from django.core.management.base import BaseCommand

from courses.models import File
from courses.pdf_indexing import update_pdf_index_for_file


class Command(BaseCommand):
    help = "Rebuild extracted PDF text index fields for uploaded files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file-id",
            action="append",
            type=int,
            dest="file_ids",
            help="Optional file id filter. Repeat for multiple ids.",
        )

    def handle(self, *args, **options):
        file_ids = options.get("file_ids") or list(File.objects.values_list("id", flat=True))
        processed = 0
        indexed = 0
        failed = 0
        skipped = 0

        for file_id in file_ids:
            result = update_pdf_index_for_file(file_id)
            if result is None:
                continue
            processed += 1
            if result.status == "indexed":
                indexed += 1
            elif result.status == "failed":
                failed += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "PDF extraction rebuild complete: "
                    f"processed={processed}, indexed={indexed}, failed={failed}, skipped={skipped}"
                )
            )
        )
