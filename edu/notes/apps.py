from django.apps import AppConfig


class NotesConfig(AppConfig):
    name = 'notes'

    def ready(self):
        from . import signals  # noqa: F401
