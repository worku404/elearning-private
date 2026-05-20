from __future__ import annotations

from datetime import time
from decimal import Decimal

from courses.models import Course, Module
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

ZERO_DECIMAL = Decimal("0.00")


class TimestampAliasQuerySet(models.QuerySet):
    field_aliases: dict[str, str] = {}

    def _normalize_field_name(self, field_name):
        if not isinstance(field_name, str):
            return field_name

        prefix = ""
        raw_name = field_name
        if raw_name.startswith("-"):
            prefix = "-"
            raw_name = raw_name[1:]

        mapped_name = self.field_aliases.get(raw_name, raw_name)
        return f"{prefix}{mapped_name}"

    def order_by(self, *field_names):
        normalized = [self._normalize_field_name(name) for name in field_names]
        return super().order_by(*normalized)


class GoalQuerySet(TimestampAliasQuerySet):
    field_aliases = {
        "created_at": "created",
        "updated_at": "updated",
    }


class InsightNotificationQuerySet(TimestampAliasQuerySet):
    field_aliases = {
        "created_at": "created",
    }


class StudyTimeEvent(models.Model):
    SOURCE_MODULE = "module"
    SOURCE_CHOICES = ((SOURCE_MODULE, "Module"),)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="study_time_events",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="study_time_events",
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name="study_time_events",
    )
    seconds_delta = models.PositiveIntegerField(default=0)
    source = models.CharField(
        max_length=16,
        choices=SOURCE_CHOICES,
        default=SOURCE_MODULE,
    )
    session_end_at = models.DateTimeField(default=timezone.now)
    local_date = models.DateField()
    local_hour = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(23)],
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-session_end_at", "-id"]
        indexes = [
            models.Index(fields=["user", "local_date"], name="li_evt_user_date_idx"),
            models.Index(
                fields=["user", "course", "local_date"],
                name="li_evt_user_course_date_idx",
            ),
            models.Index(fields=["session_end_at"], name="li_evt_end_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.course} · {self.seconds_delta}s"


class DailyCourseStat(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_course_stats",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="daily_insight_stats",
    )
    date = models.DateField()
    module_seconds = models.PositiveIntegerField(default=0)
    content_active_seconds = models.PositiveIntegerField(default=0)
    completed_content_count = models.PositiveIntegerField(default=0)
    session_count = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        unique_together = ("user", "course", "date")
        indexes = [
            models.Index(fields=["user", "date"], name="li_dcs_user_date_idx"),
            models.Index(
                fields=["user", "course", "date"],
                name="li_dcs_user_course_date_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.course} · {self.date}"


class DailySiteStat(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_site_stats",
    )
    date = models.DateField()
    active_seconds = models.PositiveIntegerField(default=0)
    ping_count = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        unique_together = ("user", "date")
        indexes = [
            models.Index(fields=["user", "date"], name="li_dss_user_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.date} · {self.active_seconds}s"


class Goal(models.Model):
    PERIOD_DAILY = "daily"
    PERIOD_WEEKLY = "weekly"
    PERIOD_MONTHLY = "monthly"
    PERIOD_LONG_TERM = "long_term"
    PERIOD_CHOICES = (
        (PERIOD_DAILY, "Daily"),
        (PERIOD_WEEKLY, "Weekly"),
        (PERIOD_MONTHLY, "Monthly"),
        (PERIOD_LONG_TERM, "Long term"),
    )

    TARGET_MINUTES = "minutes"
    TARGET_TASKS = "tasks"
    TARGET_COMPLETION_PERCENT = "completion_percent"
    TARGET_TYPE_CHOICES = (
        (TARGET_MINUTES, "Minutes"),
        (TARGET_TASKS, "Tasks"),
        (TARGET_COMPLETION_PERCENT, "Completion percent"),
    )

    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_CHOICES = (
        (PRIORITY_LOW, "Low"),
        (PRIORITY_MEDIUM, "Medium"),
        (PRIORITY_HIGH, "High"),
    )

    STATUS_NOT_STARTED = "not_started"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_MISSED = "missed"
    STATUS_OVERDUE = "overdue"
    STATUS_CHOICES = (
        (STATUS_NOT_STARTED, "Not started"),
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_MISSED, "Missed"),
        (STATUS_OVERDUE, "Overdue"),
    )

    # Compatibility aliases used elsewhere in the app.
    TARGET_TYPE_MINUTES = TARGET_MINUTES
    TARGET_TYPE_TASKS = TARGET_TASKS
    TARGET_TYPE_COMPLETION_PERCENT = TARGET_COMPLETION_PERCENT
    STATUS_CANCELLED = "cancelled"

    objects = GoalQuerySet.as_manager()

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_goals",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    course = models.ForeignKey(
        Course,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="learning_goals",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    period_type = models.CharField(
        max_length=16,
        choices=PERIOD_CHOICES,
        default=PERIOD_WEEKLY,
    )
    target_type = models.CharField(
        max_length=24,
        choices=TARGET_TYPE_CHOICES,
        default=TARGET_MINUTES,
    )
    target_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=ZERO_DECIMAL,
        validators=[MinValueValidator(Decimal("0"))],
    )
    current_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=ZERO_DECIMAL,
        validators=[MinValueValidator(Decimal("0"))],
    )
    start_date = models.DateField()
    due_date = models.DateField()
    priority = models.CharField(
        max_length=12,
        choices=PRIORITY_CHOICES,
        default=PRIORITY_MEDIUM,
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_NOT_STARTED,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "-created"]
        indexes = [
            models.Index(
                fields=["user", "period_type", "status"],
                name="li_goal_user_period_status_idx",
            ),
            models.Index(
                fields=["user", "start_date", "due_date"],
                name="li_goal_user_dates_idx",
            ),
            models.Index(fields=["user", "course"], name="li_goal_user_course_idx"),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def progress_percent(self) -> float:
        target = self.target_value or ZERO_DECIMAL
        current = self.current_value or ZERO_DECIMAL
        if target <= 0:
            return 0.0
        percent = (current / target) * Decimal("100")
        percent = max(Decimal("0"), min(Decimal("100"), percent))
        return float(percent.quantize(Decimal("0.01")))

    @property
    def remaining_value(self):
        target = self.target_value or ZERO_DECIMAL
        current = self.current_value or ZERO_DECIMAL
        remaining = target - current
        if remaining < ZERO_DECIMAL:
            remaining = ZERO_DECIMAL
        return remaining.quantize(Decimal("0.01"))

    @property
    def created_at(self):
        return self.created

    @property
    def updated_at(self):
        return self.updated

    def clean(self):
        super().clean()
        if self.due_date and self.start_date and self.due_date < self.start_date:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                {"due_date": "Due date cannot be earlier than start date."}
            )

        parent = getattr(self, "parent", None)
        if parent is not None and self.pk and getattr(parent, "pk", None) == self.pk:
            from django.core.exceptions import ValidationError

            raise ValidationError({"parent": "A goal cannot be its own parent."})

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            normalized_fields = []
            for field_name in update_fields:
                mapped_name = {
                    "created_at": "created",
                    "updated_at": "updated",
                }.get(field_name, field_name)
                if mapped_name not in normalized_fields:
                    normalized_fields.append(mapped_name)
            kwargs["update_fields"] = normalized_fields

        self.target_value = self.target_value or ZERO_DECIMAL
        self.current_value = self.current_value or ZERO_DECIMAL

        if self.target_value < 0:
            self.target_value = ZERO_DECIMAL
        if self.current_value < 0:
            self.current_value = ZERO_DECIMAL

        if self.target_value > 0 and self.current_value >= self.target_value:
            if self.status != self.STATUS_COMPLETED:
                self.status = self.STATUS_COMPLETED
            if self.completed_at is None:
                self.completed_at = timezone.now()
        elif (
            self.status == self.STATUS_COMPLETED
            and self.target_value > 0
            and self.current_value < self.target_value
        ):
            self.completed_at = None

        super().save(*args, **kwargs)


class NotificationPreference(models.Model):
    WEEKDAY_MONDAY = 0
    WEEKDAY_TUESDAY = 1
    WEEKDAY_WEDNESDAY = 2
    WEEKDAY_THURSDAY = 3
    WEEKDAY_FRIDAY = 4
    WEEKDAY_SATURDAY = 5
    WEEKDAY_SUNDAY = 6

    WEEKDAY_CHOICES = (
        (WEEKDAY_MONDAY, "Monday"),
        (WEEKDAY_TUESDAY, "Tuesday"),
        (WEEKDAY_WEDNESDAY, "Wednesday"),
        (WEEKDAY_THURSDAY, "Thursday"),
        (WEEKDAY_FRIDAY, "Friday"),
        (WEEKDAY_SATURDAY, "Saturday"),
        (WEEKDAY_SUNDAY, "Sunday"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_insights_preference",
    )
    timezone = models.CharField(max_length=64, default="UTC")
    week_start_day = models.PositiveSmallIntegerField(
        choices=WEEKDAY_CHOICES,
        default=WEEKDAY_MONDAY,
    )
    daily_enabled = models.BooleanField(default=True)
    weekly_enabled = models.BooleanField(default=True)
    daily_achievement_enabled = models.BooleanField(default=True)
    weekly_achievement_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    telegram_enabled = models.BooleanField(default=False)
    telegram_evening_summary_start = models.TimeField(default=time(hour=22, minute=0))
    telegram_evening_summary_end = models.TimeField(default=time(hour=0, minute=0))
    telegram_morning_summary_start = models.TimeField(default=time(hour=7, minute=0))
    telegram_morning_summary_end = models.TimeField(default=time(hour=9, minute=0))
    daily_time = models.TimeField(default=time(hour=8, minute=0))
    weekly_time = models.TimeField(default=time(hour=8, minute=0))

    class Meta:
        verbose_name = "Notification preference"
        verbose_name_plural = "Notification preferences"

    def __str__(self) -> str:
        return f"{self.user} preferences"


class InsightNotification(models.Model):
    CHANNEL_IN_APP = "in_app"
    CHANNEL_CHOICES = ((CHANNEL_IN_APP, "In-app"),)

    CATEGORY_DAILY_START = "daily_start"
    CATEGORY_WEEKLY_START = "weekly_start"
    CATEGORY_DAILY_ACHIEVEMENT = "daily_achievement"
    CATEGORY_WEEKLY_ACHIEVEMENT = "weekly_achievement"
    CATEGORY_GOAL_DUE = "goal_due"
    CATEGORY_GOAL_CREATED = "goal_created"
    CATEGORY_GOAL_COMPLETED = "goal_completed"
    CATEGORY_COURSE_COMPLETED = "course_completed"
    CATEGORY_INACTIVITY_WARNING = "inactivity_warning"
    CATEGORY_CHOICES = (
        (CATEGORY_DAILY_START, "Daily start"),
        (CATEGORY_WEEKLY_START, "Weekly start"),
        (CATEGORY_DAILY_ACHIEVEMENT, "Daily summary"),
        (CATEGORY_WEEKLY_ACHIEVEMENT, "Weekly achievement"),
        (CATEGORY_GOAL_DUE, "Goal due"),
        (CATEGORY_GOAL_CREATED, "Goal created"),
        (CATEGORY_GOAL_COMPLETED, "Goal completed"),
        (CATEGORY_COURSE_COMPLETED, "Course completed"),
        (CATEGORY_INACTIVITY_WARNING, "Inactivity warning"),
    )

    objects = InsightNotificationQuerySet.as_manager()

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="insight_notifications",
    )
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES)
    channel = models.CharField(
        max_length=16,
        choices=CHANNEL_CHOICES,
        default=CHANNEL_IN_APP,
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    payload = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=120, blank=True)
    scheduled_for = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    telegram_sent_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scheduled_for", "-id"]
        indexes = [
            models.Index(
                fields=["user", "channel", "scheduled_for"],
                name="li_notif_user_chan_sched_idx",
            ),
            models.Index(fields=["user", "read_at"], name="li_notif_user_read_idx"),
            models.Index(
                fields=["user", "category"], name="li_notif_user_category_idx"
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "channel", "dedupe_key"],
                condition=~Q(dedupe_key=""),
                name="li_notif_unique_dedupe_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.category}"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            normalized_fields = []
            for field_name in update_fields:
                if field_name == "created_at":
                    field_name = "created"
                elif field_name == "updated_at":
                    continue
                if field_name not in normalized_fields:
                    normalized_fields.append(field_name)
            kwargs["update_fields"] = normalized_fields
        super().save(*args, **kwargs)

    @property
    def created_at(self):
        return self.created

    @property
    def updated_at(self):
        return self.created

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    @property
    def is_dismissed(self) -> bool:
        return self.dismissed_at is not None

    def _reverse_first(self, candidates, **kwargs) -> str:
        for name in candidates:
            try:
                return reverse(name, kwargs=kwargs)
            except NoReverseMatch:
                continue
        return ""

    def get_target_url(self) -> str:
        course_id = self.payload.get("course_id")
        goal_id = self.payload.get("goal_id")

        if self.category == self.CATEGORY_GOAL_DUE and goal_id:
            return self._reverse_first(["learning_insights:goal_update"], pk=goal_id)

        if self.category == self.CATEGORY_GOAL_CREATED:
            if goal_id:
                return self._reverse_first(["learning_insights:goal_update"], pk=goal_id)
            return self._reverse_first(
                [
                    "learning_insights:goal_list",
                    "learning_insights:overview",
                ]
            )

        if self.category == self.CATEGORY_GOAL_COMPLETED:
            if goal_id:
                return self._reverse_first(["learning_insights:goal_update"], pk=goal_id)
            return self._reverse_first(
                [
                    "learning_insights:goal_list",
                    "learning_insights:overview",
                ]
            )

        if self.category == self.CATEGORY_COURSE_COMPLETED:
            if course_id:
                course_url = self._reverse_first(
                    [
                        "student_course_detail",
                    ],
                    pk=course_id,
                )
                if course_url:
                    return course_url
            return self._reverse_first(
                [
                    "student_course_list",
                    "learning_insights:overview",
                ]
            )

        if self.category in {
            self.CATEGORY_DAILY_START,
            self.CATEGORY_DAILY_ACHIEVEMENT,
            self.CATEGORY_WEEKLY_START,
            self.CATEGORY_WEEKLY_ACHIEVEMENT,
        }:
            if course_id:
                course_url = self._reverse_first(
                    [
                        "student_course_detail",
                    ],
                    pk=course_id,
                )
                if course_url:
                    return course_url

            if self.category in {
                self.CATEGORY_WEEKLY_START,
                self.CATEGORY_WEEKLY_ACHIEVEMENT,
            }:
                url = self._reverse_first(
                    [
                        "learning_insights:weekly_summary",
                        "learning_insights:overview",
                    ]
                )
                if url:
                    return url

            return self._reverse_first(
                [
                    "learning_insights:overview",
                    "learning_insights:notification_center",
                ]
            )

        if self.category == self.CATEGORY_INACTIVITY_WARNING:
            if course_id:
                course_url = self._reverse_first(
                    [
                        "student_course_detail",
                    ],
                    pk=course_id,
                )
                if course_url:
                    return course_url
            return self._reverse_first(
                [
                    "learning_insights:overview",
                    "student_course_list",
                ]
            )

        return self._reverse_first(
            [
                "learning_insights:notification_center",
                "learning_insights:overview",
            ]
        )


class TelegramSubscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_subscription",
    )
    chat_id = models.BigIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Telegram subscription"
        verbose_name_plural = "Telegram subscriptions"

    def __str__(self) -> str:
        return f"{self.user} - {self.chat_id}"


class TelegramConnectToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_connect_tokens",
    )
    token = models.CharField(max_length=64, unique=True)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_used"], name="li_tct_user_used_idx"),
        ]

    def __str__(self) -> str:
        suffix = "used" if self.is_used else "active"
        return f"{self.user} - {suffix}"


class AIPlanRun(models.Model):
    KIND_PROMPT_PLAN = "prompt_plan"
    KIND_WEEKLY_PLAN = "weekly_plan"
    KIND_DAILY_PLAN = "daily_plan"
    KIND_DAILY_REVIEW = "daily_review"
    KIND_WEEKLY_REVIEW = "weekly_review"
    KIND_IMPROVEMENT = "improvement"
    KIND_RECOVERY = "recovery"

    KIND_CHOICES = (
        (KIND_PROMPT_PLAN, "Prompt plan"),
        (KIND_WEEKLY_PLAN, "Weekly plan"),
        (KIND_DAILY_PLAN, "Daily plan"),
        (KIND_DAILY_REVIEW, "Daily review"),
        (KIND_WEEKLY_REVIEW, "Weekly review"),
        (KIND_IMPROVEMENT, "Improvement suggestions"),
        (KIND_RECOVERY, "Recovery suggestions"),
    )

    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_plan_runs",
    )
    kind = models.CharField(
        max_length=24,
        choices=KIND_CHOICES,
        default=KIND_PROMPT_PLAN,
    )
    period_type = models.CharField(
        max_length=16,
        choices=Goal.PERIOD_CHOICES,
        default=Goal.PERIOD_WEEKLY,
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    input_payload = models.JSONField(default=dict, blank=True)
    output_payload = models.JSONField(default=dict, blank=True)
    edited_payload = models.JSONField(default=dict, blank=True)
    summary_text = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    error_message = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "kind", "created_at"], name="li_air_user_kind_idx"),
            models.Index(fields=["status", "created_at"], name="li_air_status_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.kind} - {self.status}"

    @property
    def effective_payload(self) -> dict:
        if isinstance(self.edited_payload, dict) and self.edited_payload:
            return self.edited_payload
        if isinstance(self.output_payload, dict):
            return self.output_payload
        return {}
