from __future__ import annotations

from django.db.models import Q
from django.dispatch import receiver
from django.utils import timezone
from students.signals import (
    content_progress_recorded,
    course_completed,
    module_time_tracked,
    presence_ping_recorded,
)

from learning_insights.models import Goal
from learning_insights.services.common import get_local_date, get_user_timezone
from learning_insights.services.goals import sync_goals
from learning_insights.services.tracking import (
    safe_record_content_progress_event,
    safe_record_module_time_event,
    safe_record_presence_ping,
)
from learning_insights.services.notifications import (
    create_course_completed_notification,
    create_goal_completed_notification,
)


def _local_date_for_event(*, user, recorded_at=None):
    if recorded_at is None:
        return get_local_date(user=user)
    try:
        local_dt = timezone.localtime(recorded_at, get_user_timezone(user=user))
        return local_dt.date()
    except Exception:
        return get_local_date(user=user)


def _sync_course_goals_and_notify_completed(*, user, reference_date, course_id=None) -> None:
    queryset = Goal.objects.filter(
        user=user,
        start_date__lte=reference_date,
    ).exclude(status=Goal.STATUS_COMPLETED)

    if course_id:
        queryset = queryset.filter(Q(course_id=course_id) | Q(course__isnull=True))

    goals = list(queryset.select_related("course"))
    if not goals:
        return

    synced = sync_goals(goals, save=True, reference_date=reference_date)
    for goal in synced:
        if goal.status == Goal.STATUS_COMPLETED:
            create_goal_completed_notification(goal=goal)


@receiver(module_time_tracked)
def handle_module_time_tracked(sender, **kwargs):
    user = kwargs.get("user")
    module = kwargs.get("module")
    seconds_delta = kwargs.get("seconds_delta", 0)
    recorded_at = kwargs.get("recorded_at")

    if user is None or module is None:
        return

    event = safe_record_module_time_event(
        user=user,
        module=module,
        seconds_delta=seconds_delta,
        recorded_at=recorded_at,
    )

    reference_date = getattr(event, "local_date", None) or _local_date_for_event(
        user=user, recorded_at=recorded_at
    )
    _sync_course_goals_and_notify_completed(
        user=user,
        reference_date=reference_date,
        course_id=getattr(module, "course_id", None),
    )


@receiver(content_progress_recorded)
def handle_content_progress_recorded(sender, **kwargs):
    user = kwargs.get("user")
    content = kwargs.get("content")
    seconds_delta = kwargs.get("seconds_delta", 0)
    completed_now = kwargs.get("completed_now", False)
    recorded_at = kwargs.get("recorded_at")

    if user is None or content is None:
        return

    safe_record_content_progress_event(
        user=user,
        content=content,
        seconds_delta=seconds_delta,
        completed_now=completed_now,
        recorded_at=recorded_at,
    )

    reference_date = _local_date_for_event(user=user, recorded_at=recorded_at)
    module = getattr(content, "module", None)
    course_id = getattr(module, "course_id", None) if module is not None else None
    _sync_course_goals_and_notify_completed(
        user=user,
        reference_date=reference_date,
        course_id=course_id,
    )


@receiver(presence_ping_recorded)
def handle_presence_ping_recorded(sender, **kwargs):
    user_id = kwargs.get("user_id")
    recorded_at = kwargs.get("recorded_at")

    if not user_id:
        return

    safe_record_presence_ping(
        user_id=user_id,
        recorded_at=recorded_at,
    )


@receiver(course_completed)
def handle_course_completed(sender, **kwargs):
    user = kwargs.get("user")
    course = kwargs.get("course")
    completed_at = kwargs.get("completed_at")

    if user is None or course is None:
        return

    create_course_completed_notification(
        user=user,
        course=course,
        completed_at=completed_at,
    )
