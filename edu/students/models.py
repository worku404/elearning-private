from django.db import models
from django.conf import settings
from courses.models import Content, Course, Module


class CourseProgress(models.Model):
    """
    Stores one progress row per (user, course).

    Why keep this model when course progress can be calculated on the fly?
    - We need a persistent "completed" status in the database.
    - We also keep the latest computed percentage so pages can render quickly.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_progress",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="student_progress",
    )

    # Cached aggregate value built from all module percentages in this course.
    progress_percent = models.FloatField(default=0.0)

    # True only when all modules in the course are completed for this user.
    completed = models.BooleanField(default=False)

    # Timestamp of when the course first became completed.
    completed_at = models.DateTimeField(null=True, blank=True)

    # Updated automatically each time we save this row.
    last_accessed = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "course")

    def __str__(self):
        return f"{self.user} - {self.course} ({self.progress_percent:.1f}%)"


class ModuleProgress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='module_progress'
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='module_progress'
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='progress_records'
    )

    completed = models.BooleanField(default=False)
    progress_percent = models.FloatField(default=0.0)
    time_spent = models.PositiveIntegerField(default=0)  # seconds
    last_accessed = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'module')

    def __str__(self):
        return f"{self.user} - {self.module}"


class ContentProgress(models.Model):
    CONTENT_KIND_TEXT = "text"
    CONTENT_KIND_PDF = "pdf"
    CONTENT_KIND_VIDEO = "video"
    CONTENT_KIND_CHOICES = (
        (CONTENT_KIND_TEXT, "Text"),
        (CONTENT_KIND_PDF, "PDF"),
        (CONTENT_KIND_VIDEO, "Video"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="content_progress",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="content_progress",
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="content_progress",
    )
    content = models.ForeignKey(
        Content,
        on_delete=models.CASCADE,
        related_name="progress_records",
    )

    content_type = models.CharField(max_length=12, choices=CONTENT_KIND_CHOICES)
    progress_percent = models.FloatField(default=0.0)
    completed = models.BooleanField(default=False)
    seconds_spent = models.PositiveIntegerField(default=0)
    last_position = models.JSONField(default=dict, blank=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "content")

    def __str__(self):
        return f"{self.user} - content:{self.content_id} ({self.progress_percent:.1f}%)"
