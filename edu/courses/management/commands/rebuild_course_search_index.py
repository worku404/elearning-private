from django.core.management.base import BaseCommand

from courses.search import rebuild_course_search_index


class Command(BaseCommand):
    help = "Rebuild denormalized PostgreSQL search documents for courses."

    def add_arguments(self, parser):
        parser.add_argument(
            "--course-id",
            action="append",
            type=int,
            dest="course_ids",
            help="Optional course id filter. Repeat for multiple ids.",
        )

    def handle(self, *args, **options):
        course_ids = options.get("course_ids") or None
        result = rebuild_course_search_index(course_ids=course_ids)
        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Course search index rebuilt: "
                    f"processed={result['processed']}, "
                    f"created={result['created']}, "
                    f"updated={result['updated']}"
                )
            )
        )
