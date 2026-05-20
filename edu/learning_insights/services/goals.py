from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from django.db.models import Avg, Sum
from django.utils import timezone
from students.models import CourseProgress

from ..models import DailyCourseStat, Goal
from .common import get_local_date

ZERO_DECIMAL = Decimal("0.00")
ONE_HUNDRED = Decimal("100.00")
MINUTE_DIVISOR = Decimal("60")
PERCENT_QUANTIZER = Decimal("0.01")

PRIORITY_WEIGHTS = {
    Goal.PRIORITY_LOW: 1,
    Goal.PRIORITY_MEDIUM: 2,
    Goal.PRIORITY_HIGH: 3,
}


@dataclass(frozen=True)
class GoalAchievement:
    goal: Goal
    current_value: Decimal
    achievement_percent: float
    weight: int


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return ZERO_DECIMAL
    return Decimal(str(value))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(PERCENT_QUANTIZER, rounding=ROUND_HALF_UP)


def _clamp_percent(value) -> float:
    decimal_value = _to_decimal(value)
    if decimal_value < ZERO_DECIMAL:
        decimal_value = ZERO_DECIMAL
    if decimal_value > ONE_HUNDRED:
        decimal_value = ONE_HUNDRED
    return float(_quantize(decimal_value))


def _reference_date_for_user(user, reference_date: date | None = None) -> date:
    if reference_date is not None:
        return reference_date
    try:
        return get_local_date(user=user)
    except Exception:
        return timezone.localdate()


def _goal_date_bounds(
    goal: Goal,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> tuple[date, date]:
    effective_start = start_date or goal.start_date
    effective_end = end_date or goal.due_date
    if effective_end < effective_start:
        effective_end = effective_start
    return effective_start, effective_end


def _goal_fifo_order_key(goal: Goal) -> tuple:
    return (
        goal.due_date or date.max,
        goal.created or timezone.now(),
        goal.pk or 0,
    )


def _minute_goal_scope_key(goal: Goal):
    return goal.course_id


def _daily_course_minutes_by_date(
    user,
    goals: Iterable[Goal],
    *,
    reference_date: date | None = None,
) -> tuple[dict[int | None, dict[date, Decimal]], dict[date, Decimal]]:
    goals = list(goals)
    if not goals:
        return {}, {}

    start_date = min(goal.start_date for goal in goals)
    end_date = reference_date or timezone.localdate()
    if end_date < start_date:
        return {}, {}

    rows = (
        DailyCourseStat.objects.filter(
            user=user,
            date__range=(start_date, end_date),
        )
        .values("date", "course_id")
        .annotate(total_seconds=Sum("module_seconds"))
        .order_by("date", "course_id")
    )

    course_minutes_by_date: dict[int | None, dict[date, Decimal]] = defaultdict(dict)
    total_minutes_by_date: dict[date, Decimal] = defaultdict(lambda: ZERO_DECIMAL)

    for row in rows:
        current_date = row["date"]
        course_id = row["course_id"]
        total_seconds = Decimal(row["total_seconds"] or 0)
        total_minutes = total_seconds / MINUTE_DIVISOR

        course_minutes_by_date[course_id][current_date] = total_minutes
        total_minutes_by_date[current_date] += total_minutes

    return dict(course_minutes_by_date), dict(total_minutes_by_date)


def _allocate_fifo_minute_goal_values(
    user,
    goals: Iterable[Goal],
    *,
    reference_date: date | None = None,
) -> dict[int, Decimal]:
    minute_goals = [goal for goal in goals if goal.target_type == Goal.TARGET_MINUTES]
    if not minute_goals:
        return {}

    course_minutes_by_date, total_minutes_by_date = _daily_course_minutes_by_date(
        user,
        minute_goals,
        reference_date=reference_date,
    )

    allocations: dict[int, Decimal] = {
        goal.pk: ZERO_DECIMAL for goal in minute_goals if goal.pk is not None
    }
    goals_by_scope: dict[int | None, list[Goal]] = defaultdict(list)
    for goal in minute_goals:
        goals_by_scope[_minute_goal_scope_key(goal)].append(goal)

    for scope_key, scope_goals in goals_by_scope.items():
        ordered_goals = sorted(scope_goals, key=_goal_fifo_order_key)
        daily_minutes_by_date = (
            total_minutes_by_date
            if scope_key is None
            else course_minutes_by_date.get(scope_key, {})
        )

        for current_date in sorted(daily_minutes_by_date):
            minutes_available = Decimal(daily_minutes_by_date[current_date])
            if minutes_available <= ZERO_DECIMAL:
                continue

            active_goals = [
                goal
                for goal in ordered_goals
                if goal.start_date <= current_date <= goal.due_date
            ]

            for goal in active_goals:
                if minutes_available <= ZERO_DECIMAL:
                    break

                target_minutes = _to_decimal(goal.target_value)
                allocated_minutes = allocations.get(goal.pk, ZERO_DECIMAL)
                remaining_minutes = target_minutes - allocated_minutes
                if remaining_minutes <= ZERO_DECIMAL:
                    continue

                applied_minutes = min(minutes_available, remaining_minutes)
                allocations[goal.pk] = allocated_minutes + applied_minutes
                minutes_available -= applied_minutes

    return {goal_id: _quantize(value) for goal_id, value in allocations.items()}


def _daily_course_stats_queryset(
    goal: Goal,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
):
    effective_start, effective_end = _goal_date_bounds(
        goal,
        start_date=start_date,
        end_date=end_date,
    )
    queryset = DailyCourseStat.objects.filter(
        user=goal.user,
        date__range=(effective_start, effective_end),
    )
    course_id = getattr(goal, "course_id", None)
    if course_id:
        queryset = queryset.filter(course_id=course_id)
    return queryset


def _get_priority_weight(goal: Goal) -> int:
    return PRIORITY_WEIGHTS.get(goal.priority, 1)


def _calculate_minutes_value(
    goal: Goal,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Decimal:
    total_seconds = (
        _daily_course_stats_queryset(
            goal,
            start_date=start_date,
            end_date=end_date,
        )
        .aggregate(total=Sum("module_seconds"))
        .get("total")
        or 0
    )
    minutes = Decimal(total_seconds) / MINUTE_DIVISOR
    return _quantize(minutes)


def _calculate_tasks_value(
    goal: Goal,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Decimal:
    completed_count = (
        _daily_course_stats_queryset(
            goal,
            start_date=start_date,
            end_date=end_date,
        )
        .aggregate(total=Sum("completed_content_count"))
        .get("total")
        or 0
    )
    return _quantize(Decimal(completed_count))


def _calculate_completion_percent_value(goal: Goal) -> Decimal:
    course_id = getattr(goal, "course_id", None)
    if course_id:
        progress = (
            CourseProgress.objects.filter(
                user=goal.user,
                course_id=course_id,
            )
            .values_list("progress_percent", flat=True)
            .first()
        )
        return _quantize(_to_decimal(progress or 0))

    course_ids = list(goal.user.courses_joined.values_list("id", flat=True))
    if not course_ids:
        return ZERO_DECIMAL

    progress_rows = CourseProgress.objects.filter(
        user=goal.user,
        course_id__in=course_ids,
    )
    progress_by_course = {
        row["course_id"]: float(row["avg_progress"] or 0.0)
        for row in progress_rows.values("course_id").annotate(
            avg_progress=Avg("progress_percent")
        )
    }

    total = Decimal("0")
    for course_id in course_ids:
        total += _to_decimal(progress_by_course.get(course_id, 0.0))

    average = total / Decimal(len(course_ids))
    return _quantize(average)


def get_goals_for_period(user, start_date: date, end_date: date):
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    return (
        Goal.objects.filter(
            user=user,
            start_date__lte=end_date,
            due_date__gte=start_date,
        )
        .select_related("course", "parent")
        .order_by("due_date", "-created")
    )


def get_active_goals(user, reference_date: date | None = None):
    today = _reference_date_for_user(user, reference_date)
    return (
        Goal.objects.filter(
            user=user,
            start_date__lte=today,
            due_date__gte=today,
        )
        .exclude(
            status__in=[
                Goal.STATUS_COMPLETED,
                Goal.STATUS_MISSED,
                Goal.STATUS_OVERDUE,
            ]
        )
        .select_related("course", "parent")
        .order_by("due_date", "-created")
    )


def calculate_goal_current_value(
    goal: Goal,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Decimal:
    if goal.target_type == Goal.TARGET_MINUTES:
        return _quantize(_to_decimal(goal.current_value))

    if goal.target_type == Goal.TARGET_TASKS:
        return _calculate_tasks_value(goal, start_date=start_date, end_date=end_date)

    if goal.target_type == Goal.TARGET_COMPLETION_PERCENT:
        return _calculate_completion_percent_value(goal)

    return _quantize(_to_decimal(goal.current_value))


def calculate_goal_achievement_percent(
    goal: Goal,
    *,
    current_value: Decimal | None = None,
) -> float:
    current = (
        current_value
        if current_value is not None
        else calculate_goal_current_value(goal)
    )
    current = _to_decimal(current)
    target = _to_decimal(goal.target_value)

    if target <= ZERO_DECIMAL:
        return 100.0 if goal.status == Goal.STATUS_COMPLETED else 0.0

    return _clamp_percent((current / target) * ONE_HUNDRED)


def resolve_goal_status(
    goal: Goal,
    *,
    achievement_percent: float | None = None,
    current_value: Decimal | None = None,
    reference_date: date | None = None,
) -> str:
    current = (
        current_value
        if current_value is not None
        else calculate_goal_current_value(goal)
    )
    achievement = (
        achievement_percent
        if achievement_percent is not None
        else calculate_goal_achievement_percent(goal, current_value=current)
    )
    today = _reference_date_for_user(goal.user, reference_date)

    if achievement >= 100.0:
        return Goal.STATUS_COMPLETED

    if today < goal.start_date:
        return Goal.STATUS_NOT_STARTED

    if today > goal.due_date:
        if current > ZERO_DECIMAL:
            return Goal.STATUS_OVERDUE
        return Goal.STATUS_MISSED

    if current > ZERO_DECIMAL:
        return Goal.STATUS_IN_PROGRESS

    return Goal.STATUS_NOT_STARTED


def sync_goal(
    goal: Goal,
    *,
    save: bool = True,
    reference_date: date | None = None,
) -> Goal:
    synced_goals = _sync_goal_progress_for_user(
        goal.user,
        save=save,
        reference_date=reference_date,
    )
    for synced_goal in synced_goals:
        if synced_goal.pk == goal.pk:
            goal.current_value = synced_goal.current_value
            goal.status = synced_goal.status
            goal.completed_at = synced_goal.completed_at
            return goal
    return goal


def sync_goals(
    goals: Iterable[Goal],
    *,
    save: bool = True,
    reference_date: date | None = None,
) -> list[Goal]:
    goal_list = list(goals)
    if not goal_list:
        return []

    synced_by_user: dict[int, dict[int, Goal]] = {}
    for user_id in {goal.user_id for goal in goal_list}:
        user = next(goal.user for goal in goal_list if goal.user_id == user_id)
        synced_goals = _sync_goal_progress_for_user(
            user,
            save=save,
            reference_date=reference_date,
        )
        synced_by_user[user_id] = {goal.pk: goal for goal in synced_goals}

    updated_goals: list[Goal] = []
    for goal in goal_list:
        synced_goal = synced_by_user.get(goal.user_id, {}).get(goal.pk)
        if synced_goal is not None:
            goal.current_value = synced_goal.current_value
            goal.status = synced_goal.status
            goal.completed_at = synced_goal.completed_at
        updated_goals.append(goal)

    return updated_goals


def sync_goal_progress_for_user(user, reference_date: date | None = None) -> list[Goal]:
    return _sync_goal_progress_for_user(user, save=True, reference_date=reference_date)


def _sync_goal_progress_for_user(
    user,
    *,
    save: bool = True,
    reference_date: date | None = None,
) -> list[Goal]:
    goals = list(
        Goal.objects.filter(user=user)
        .select_related("course", "parent")
        .order_by("due_date", "created", "pk")
    )
    if not goals:
        return []

    minute_allocations = _allocate_fifo_minute_goal_values(
        user,
        goals,
        reference_date=reference_date,
    )

    updated_goals: list[Goal] = []
    for goal in goals:
        if goal.target_type == Goal.TARGET_MINUTES:
            current_value = minute_allocations.get(goal.pk, ZERO_DECIMAL)
        elif goal.target_type == Goal.TARGET_TASKS:
            current_value = _calculate_tasks_value(goal)
        elif goal.target_type == Goal.TARGET_COMPLETION_PERCENT:
            current_value = _calculate_completion_percent_value(goal)
        else:
            current_value = _quantize(_to_decimal(goal.current_value))

        achievement_percent = calculate_goal_achievement_percent(
            goal,
            current_value=current_value,
        )
        next_status = resolve_goal_status(
            goal,
            achievement_percent=achievement_percent,
            current_value=current_value,
            reference_date=reference_date,
        )

        changed_fields: list[str] = []

        if _to_decimal(goal.current_value) != current_value:
            goal.current_value = current_value
            changed_fields.append("current_value")

        if goal.status != next_status:
            goal.status = next_status
            changed_fields.append("status")

        if next_status == Goal.STATUS_COMPLETED:
            if goal.completed_at is None:
                goal.completed_at = timezone.now()
                changed_fields.append("completed_at")
        elif goal.completed_at is not None:
            goal.completed_at = None
            changed_fields.append("completed_at")

        if save and changed_fields:
            goal.save(update_fields=changed_fields)

        updated_goals.append(goal)

    return updated_goals


def sync_goal_progress(user, reference_date: date | None = None) -> list[Goal]:
    return sync_goal_progress_for_user(user, reference_date=reference_date)


def build_goal_achievement(goal: Goal) -> GoalAchievement:
    current_value = calculate_goal_current_value(goal)
    achievement_percent = calculate_goal_achievement_percent(
        goal,
        current_value=current_value,
    )
    return GoalAchievement(
        goal=goal,
        current_value=current_value,
        achievement_percent=achievement_percent,
        weight=_get_priority_weight(goal),
    )


def calculate_weighted_achievement(goals: Iterable[Goal]) -> float:
    achievements = [build_goal_achievement(goal) for goal in goals]
    if not achievements:
        return 0.0

    total_weight = sum(item.weight for item in achievements)
    if total_weight <= 0:
        return 0.0

    weighted_total = sum(
        Decimal(str(item.achievement_percent)) * item.weight for item in achievements
    )
    return _clamp_percent(weighted_total / Decimal(total_weight))


def calculate_planned_minutes(goals: Iterable[Goal]) -> Decimal:
    total = ZERO_DECIMAL
    for goal in goals:
        if goal.target_type == Goal.TARGET_MINUTES:
            total += _to_decimal(goal.target_value)
    return _quantize(total)


def calculate_actual_minutes(goals: Iterable[Goal]) -> Decimal:
    total = ZERO_DECIMAL
    for goal in goals:
        if goal.target_type == Goal.TARGET_MINUTES:
            total += calculate_goal_current_value(goal)
    return _quantize(total)


def calculate_planned_vs_actual_percent(goals: Iterable[Goal]) -> float:
    goals = list(goals)
    planned = calculate_planned_minutes(goals)
    if planned <= ZERO_DECIMAL:
        return calculate_weighted_achievement(goals)

    actual = calculate_actual_minutes(goals)
    return _clamp_percent((actual / planned) * ONE_HUNDRED)


def get_goal_summary_for_period(user, start_date: date, end_date: date) -> dict:
    goals = list(get_goals_for_period(user, start_date, end_date))
    sync_goals(goals, save=True)

    total = len(goals)
    completed = sum(1 for goal in goals if goal.status == Goal.STATUS_COMPLETED)
    missed = sum(1 for goal in goals if goal.status == Goal.STATUS_MISSED)
    overdue = sum(1 for goal in goals if goal.status == Goal.STATUS_OVERDUE)
    in_progress = sum(1 for goal in goals if goal.status == Goal.STATUS_IN_PROGRESS)
    not_started = sum(1 for goal in goals if goal.status == Goal.STATUS_NOT_STARTED)

    return {
        "goals": goals,
        "total": total,
        "completed": completed,
        "missed": missed,
        "overdue": overdue,
        "in_progress": in_progress,
        "not_started": not_started,
        "achievement_percent": calculate_weighted_achievement(goals),
        "planned_minutes": calculate_planned_minutes(goals),
        "actual_minutes": calculate_actual_minutes(goals),
        "planned_vs_actual_percent": calculate_planned_vs_actual_percent(goals),
        "needs_improvement": get_needs_improvement(goals),
    }


def get_needs_improvement(goals: Iterable[Goal]) -> list[Goal]:
    result: list[Goal] = []
    for goal in goals:
        achievement = calculate_goal_achievement_percent(goal)
        if goal.status in {Goal.STATUS_MISSED, Goal.STATUS_OVERDUE}:
            result.append(goal)
            continue
        if goal.status != Goal.STATUS_COMPLETED and achievement < 50.0:
            result.append(goal)
    return result
