from django.apps import AppConfig


class LearningInsightsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "learning_insights"
    verbose_name = "Learning Insights"

    def ready(self):
        from . import receivers  # noqa: F401
