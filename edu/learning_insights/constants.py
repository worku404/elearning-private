from __future__ import annotations

from datetime import time

# Periods
PERIOD_DAILY = "daily"
PERIOD_WEEKLY = "weekly"
PERIOD_MONTHLY = "monthly"
PERIOD_LONG_TERM = "long_term"

PERIOD_TYPE_CHOICES = (
    (PERIOD_DAILY, "Daily"),
    (PERIOD_WEEKLY, "Weekly"),
    (PERIOD_MONTHLY, "Monthly"),
    (PERIOD_LONG_TERM, "Long term"),
)

# Goal target types
TARGET_MINUTES = "minutes"
TARGET_TASKS = "tasks"
TARGET_COMPLETION_PERCENT = "completion_percent"

TARGET_TYPE_CHOICES = (
    (TARGET_MINUTES, "Minutes"),
    (TARGET_TASKS, "Tasks"),
    (TARGET_COMPLETION_PERCENT, "Completion percent"),
)

# Goal statuses
GOAL_STATUS_NOT_STARTED = "not_started"
GOAL_STATUS_IN_PROGRESS = "in_progress"
GOAL_STATUS_COMPLETED = "completed"
GOAL_STATUS_MISSED = "missed"
GOAL_STATUS_OVERDUE = "overdue"

GOAL_STATUS_CHOICES = (
    (GOAL_STATUS_NOT_STARTED, "Not started"),
    (GOAL_STATUS_IN_PROGRESS, "In progress"),
    (GOAL_STATUS_COMPLETED, "Completed"),
    (GOAL_STATUS_MISSED, "Missed"),
    (GOAL_STATUS_OVERDUE, "Overdue"),
)

# Goal priorities
PRIORITY_LOW = "low"
PRIORITY_MEDIUM = "medium"
PRIORITY_HIGH = "high"

GOAL_PRIORITY_CHOICES = (
    (PRIORITY_LOW, "Low"),
    (PRIORITY_MEDIUM, "Medium"),
    (PRIORITY_HIGH, "High"),
)

PRIORITY_WEIGHTS = {
    PRIORITY_LOW: 1,
    PRIORITY_MEDIUM: 2,
    PRIORITY_HIGH: 3,
}

# Time/event sources
TIME_SOURCE_MODULE = "module"
TIME_SOURCE_CONTENT = "content"
TIME_SOURCE_PRESENCE = "presence"

TIME_SOURCE_CHOICES = (
    (TIME_SOURCE_MODULE, "Module"),
    (TIME_SOURCE_CONTENT, "Content"),
    (TIME_SOURCE_PRESENCE, "Presence"),
)

# Notification categories
NOTIF_DAILY_START = "daily_start"
NOTIF_WEEKLY_START = "weekly_start"
NOTIF_DAILY_ACHIEVEMENT = "daily_achievement"
NOTIF_WEEKLY_ACHIEVEMENT = "weekly_achievement"
NOTIF_GOAL_DUE = "goal_due"
NOTIF_GOAL_COMPLETED = "goal_completed"

NOTIFICATION_CATEGORY_CHOICES = (
    (NOTIF_DAILY_START, "Daily start"),
    (NOTIF_WEEKLY_START, "Weekly start"),
    (NOTIF_DAILY_ACHIEVEMENT, "Daily achievement"),
    (NOTIF_WEEKLY_ACHIEVEMENT, "Weekly achievement"),
    (NOTIF_GOAL_DUE, "Goal due"),
    (NOTIF_GOAL_COMPLETED, "Goal completed"),
)

# Notification channels
CHANNEL_IN_APP = "in_app"
CHANNEL_TELEGRAM = "telegram"

NOTIFICATION_CHANNEL_CHOICES = (
    (CHANNEL_IN_APP, "In-app"),
    (CHANNEL_TELEGRAM, "Telegram"),
)

# AI plan run statuses
AI_RUN_PENDING = "pending"
AI_RUN_SUCCESS = "success"
AI_RUN_FAILED = "failed"

AI_PLAN_RUN_STATUS_CHOICES = (
    (AI_RUN_PENDING, "Pending"),
    (AI_RUN_SUCCESS, "Success"),
    (AI_RUN_FAILED, "Failed"),
)

# Week start days
WEEKDAY_MONDAY = 0
WEEKDAY_TUESDAY = 1
WEEKDAY_WEDNESDAY = 2
WEEKDAY_THURSDAY = 3
WEEKDAY_FRIDAY = 4
WEEKDAY_SATURDAY = 5
WEEKDAY_SUNDAY = 6

WEEK_START_DAY_CHOICES = (
    (WEEKDAY_MONDAY, "Monday"),
    (WEEKDAY_TUESDAY, "Tuesday"),
    (WEEKDAY_WEDNESDAY, "Wednesday"),
    (WEEKDAY_THURSDAY, "Thursday"),
    (WEEKDAY_FRIDAY, "Friday"),
    (WEEKDAY_SATURDAY, "Saturday"),
    (WEEKDAY_SUNDAY, "Sunday"),
)

# Scoring defaults
ACTIVE_DAY_MINIMUM_COURSE_SECONDS = 15 * 60
ACTIVE_DAY_MINIMUM_SITE_SECONDS = 20 * 60

PRODUCTIVITY_GOAL_COMPLETION_POINTS = 30
PRODUCTIVITY_CONTENT_COMPLETION_POINTS = 10

STATUS_SCORE_EXCELLENT_MIN = 85
STATUS_SCORE_ON_TRACK_MIN = 70
STATUS_SCORE_NEEDS_ATTENTION_MIN = 50

STATUS_LABEL_EXCELLENT = "Excellent"
STATUS_LABEL_ON_TRACK = "On Track"
STATUS_LABEL_NEEDS_ATTENTION = "Needs Attention"
STATUS_LABEL_BEHIND = "Behind Schedule"

WEEKLY_STATUS_WEIGHTS = {
    "achievement": 0.50,
    "consistency": 0.30,
    "planned_vs_actual": 0.20,
}

# Notification defaults
DEFAULT_DAILY_REMINDER_TIME = time(hour=8, minute=0)
DEFAULT_WEEKLY_REMINDER_TIME = time(hour=8, minute=0)
DEFAULT_WEEK_START_DAY = WEEKDAY_MONDAY
DEFAULT_NOTIFICATION_FETCH_LIMIT = 5

# Presence tracking
PRESENCE_HEARTBEAT_MAX_GAP_SECONDS = 75

# Reflection note tags
DAILY_REFLECTION_TAG = "daily-reflection"
WEEKLY_REFLECTION_TAG = "weekly-review"
REFLECTION_TAGS = (
    DAILY_REFLECTION_TAG,
    WEEKLY_REFLECTION_TAG,
)
