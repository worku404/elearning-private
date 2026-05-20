import datetime
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mass_mail
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone


User = get_user_model()


class Command(BaseCommand):
    help = (
        "Send an email reminder to users who registered more than N days ago "
        "and are not enrolled in any courses."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=0,
            help="Send reminders to users registered more than N days ago.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        cutoff_date = timezone.now() - datetime.timedelta(days=days)

        users = (
            User.objects.annotate(
                course_count=Count("courses_joined", distinct=True)
            )
            .filter(
                course_count=0,
                date_joined__lte=cutoff_date,
                is_active=True,
            )
            .exclude(email="")
        )

        emails = []
        subject = "Enroll in a course"

        for user in users:
            recipient_name = user.first_name or user.username

            message = (
                f"Dear {recipient_name},\n\n"
                "We noticed that you have not enrolled in any courses yet.\n"
                "Browse our catalog and start learning today.\n\n"
                "Best regards,\n"
                "The Team"
            )

            emails.append(
                (
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                )
            )

        if emails:
            send_mass_mail(emails, fail_silently=False)

        self.stdout.write(
            self.style.SUCCESS(f"Sent {len(emails)} reminders.")
        )