from django.apps import AppConfig


class CoursesConfig(AppConfig):
    name = 'courses'

    def ready(self):
        # Register signal handlers at app startup.
        from . import signals  # noqa: F401
