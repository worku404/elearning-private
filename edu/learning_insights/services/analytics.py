from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from django.db.models import Count, Min, Sum

from ..models import DailyCourseStat, DailySiteStat, Goal, StudyTimeEvent
from .common import (
    PeriodRange,
    daterange,
    get_local_date,
    get_month_range,
    get_or_create_notification_preference,
    get_week_range,
)
from .goals import (
    calculate_planned_vs_actual_percent,
    calculate_weighted_achievement,
    get_goal_summary_for_period,
    get_goals_for_period,
    sync_goals,
)

ZERO_DECIMAL = Decimal("0")
ACTIVE_COURSE_SECONDS_THRESHOLD = 15 * 60
ACTIVE_SITE_SECONDS_THRESHOLD = 20 * 60


@dataclass(frozen=True)
class ComparisonSummary:
    previous_seconds: int
    current_seconds: int
    delta_seconds: int
    delta_percent: float | None


def _to_float(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _to_int(value) -> int:
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return int(value)
    return int(value)


def _period_days(period: PeriodRange) -> int:
    return max(0, (period.end - period.start).days + 1)


def _previous_period(period: PeriodRange) -> PeriodRange:
    days = _period_days(period)
    previous_end = period.start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=max(days - 1, 0))
    return PeriodRange(start=previous_start, end=previous_end)


def _get_preference(user, preference=None):
    return preference or get_or_create_notification_preference(user)


def _get_week_period(
    user, week_start: date | None = None, preference=None
) -> PeriodRange:
    pref = _get_preference(user, preference)
    anchor = week_start or get_local_date(user=user, preference=pref)
    return get_week_range(anchor, week_start_day=pref.week_start_day)


def _get_month_period(
    user, month_anchor: date | None = None, preference=None
) -> PeriodRange:
    pref = _get_preference(user, preference)
    anchor = month_anchor or get_local_date(user=user, preference=pref)
    return get_month_range(anchor)


def _get_course_rows(user, period: PeriodRange) -> list[dict]:
    rows = (
        DailyCourseStat.objects.filter(
            user=user,
            date__range=(period.start, period.end),
        )
        .values("course_id", "course__title")
        .annotate(
            total_seconds=Sum("module_seconds"),
            completed_content_count=Sum("completed_content_count"),
            session_count=Sum("session_count"),
            content_active_seconds=Sum("content_active_seconds"),
        )
        .order_by("-total_seconds", "-completed_content_count", "course__title")
    )

    results: list[dict] = []
    total_seconds = sum(_to_int(row["total_seconds"]) for row in rows)
    for row in rows:
        seconds = _to_int(row["total_seconds"])
        percent = (
            round((seconds / total_seconds) * 100.0, 2) if total_seconds > 0 else 0
        )
        results.append(
            {
                "course_id": row["course_id"],
                "course_title": row["course__title"],
                "total_seconds": seconds,
                "completed_content_count": _to_int(row["completed_content_count"]),
                "session_count": _to_int(row["session_count"]),
                "content_active_seconds": _to_int(row["content_active_seconds"]),
                "percent": percent,
            }
        )
    return results


def _get_site_seconds(user, period: PeriodRange) -> int:
    return _to_int(
        DailySiteStat.objects.filter(
            user=user,
            date__range=(period.start, period.end),
        ).aggregate(total=Sum("active_seconds"))["total"]
    )


def _get_course_seconds(user, period: PeriodRange) -> int:
    return _to_int(
        DailyCourseStat.objects.filter(
            user=user,
            date__range=(period.start, period.end),
        ).aggregate(total=Sum("module_seconds"))["total"]
    )


def _get_daily_breakdown(user, period: PeriodRange) -> list[dict]:
    use_weekday_labels = _period_days(period) <= 10
    site_rows = DailySiteStat.objects.filter(
        user=user,
        date__range=(period.start, period.end),
    ).values("date", "active_seconds", "ping_count")

    site_map = {
        row["date"]: {
            "site_active_seconds": _to_int(row["active_seconds"]),
            "ping_count": _to_int(row["ping_count"]),
        }
        for row in site_rows
    }

    course_rows = (
        DailyCourseStat.objects.filter(
            user=user,
            date__range=(period.start, period.end),
        )
        .values("date")
        .annotate(
            study_seconds=Sum("module_seconds"),
            completed_contents=Sum("completed_content_count"),
            content_active_seconds=Sum("content_active_seconds"),
            session_count=Sum("session_count"),
        )
    )
    course_map = {
        row["date"]: {
            "study_seconds": _to_int(row["study_seconds"]),
            "completed_contents": _to_int(row["completed_contents"]),
            "content_active_seconds": _to_int(row["content_active_seconds"]),
            "session_count": _to_int(row["session_count"]),
        }
        for row in course_rows
    }

    goal_completions = (
        Goal.objects.filter(
            user=user,
            completed_at__date__range=(period.start, period.end),
        )
        .values("completed_at__date")
        .annotate(total=Count("id"))
    )
    goal_map = {
        row["completed_at__date"]: _to_int(row["total"])
        for row in goal_completions
        if row["completed_at__date"] is not None
    }

    results: list[dict] = []
    for current_date in daterange(period.start, period.end):
        site_data = site_map.get(current_date, {})
        course_data = course_map.get(current_date, {})
        study_seconds = course_data.get("study_seconds", 0)
        site_seconds = site_data.get("site_active_seconds", 0)
        completed_goals = goal_map.get(current_date, 0)
        completed_contents = course_data.get("completed_contents", 0)

        productivity_score = round(
            (site_seconds / 60.0) + (completed_goals * 30) + (completed_contents * 10),
            2,
        )

        is_active = (
            study_seconds >= ACTIVE_COURSE_SECONDS_THRESHOLD
            or site_seconds >= ACTIVE_SITE_SECONDS_THRESHOLD
        )

        results.append(
            {
                "date": current_date,
                "label": current_date.strftime("%a")
                if use_weekday_labels
                else str(current_date.day),
                "study_seconds": study_seconds,
                "study_minutes": round(study_seconds / 60.0, 2),
                "course_seconds": study_seconds,
                "course_minutes": round(study_seconds / 60.0, 2),
                "site_active_seconds": site_seconds,
                "site_active_minutes": round(site_seconds / 60.0, 2),
                "site_minutes": round(site_seconds / 60.0, 2),
                "completed_goals": completed_goals,
                "completed_contents": completed_contents,
                "content_active_seconds": course_data.get("content_active_seconds", 0),
                "session_count": course_data.get("session_count", 0),
                "ping_count": site_data.get("ping_count", 0),
                "productivity_score": productivity_score,
                "is_active": is_active,
            }
        )
    return results


def _get_productive_day(daily_breakdown: list[dict]) -> dict | None:
    if not daily_breakdown:
        return None

    best = max(daily_breakdown, key=lambda item: item["productivity_score"])
    if best["productivity_score"] <= 0:
        return None

    return {
        "date": best["date"],
        "label": best["date"].strftime("%A"),
        "score": best["productivity_score"],
        "study_seconds": best["study_seconds"],
        "site_active_seconds": best["site_active_seconds"],
        "completed_goals": best["completed_goals"],
        "completed_contents": best["completed_contents"],
    }


def _get_consistency_percent(daily_breakdown: list[dict]) -> float:
    if not daily_breakdown:
        return 0.0
    active_days = sum(1 for item in daily_breakdown if item["is_active"])
    return round((active_days / len(daily_breakdown)) * 100.0, 2)


def _get_time_trend_ratio(current_seconds: int, previous_seconds: int) -> float:
    if current_seconds <= 0:
        return 0.0
    if previous_seconds <= 0:
        return 100.0
    return round(min((current_seconds / previous_seconds) * 100.0, 100.0), 2)


def _get_status_label(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "On Track"
    if score >= 50:
        return "Needs Attention"
    return "Behind Schedule"


def _build_status(
    *,
    goals: Iterable[Goal],
    daily_breakdown: list[dict],
    current_site_seconds: int,
    previous_site_seconds: int,
) -> dict:
    goals = list(goals)
    achievement_percent = round(calculate_weighted_achievement(goals), 2)
    planned_vs_actual_percent = round(calculate_planned_vs_actual_percent(goals), 2)
    consistency_percent = _get_consistency_percent(daily_breakdown)

    if goals:
        score = round(
            (achievement_percent * 0.50)
            + (consistency_percent * 0.30)
            + (planned_vs_actual_percent * 0.20),
            2,
        )
        note = ""
    else:
        time_trend_percent = _get_time_trend_ratio(
            current_site_seconds, previous_site_seconds
        )
        score = round((consistency_percent * 0.60) + (time_trend_percent * 0.40), 2)
        note = "No goals set for this period"

    return {
        "score": score,
        "label": _get_status_label(score),
        "achievement": achievement_percent,
        "consistency": consistency_percent,
        "planned_vs_actual": planned_vs_actual_percent,
        "has_goals": bool(goals),
        "note": note,
    }


def _build_comparison(current_seconds: int, previous_seconds: int) -> ComparisonSummary:
    delta_seconds = current_seconds - previous_seconds
    delta_percent: float | None
    if previous_seconds > 0:
        delta_percent = round((delta_seconds / previous_seconds) * 100.0, 2)
    elif current_seconds > 0:
        delta_percent = 100.0
    else:
        delta_percent = None

    return ComparisonSummary(
        previous_seconds=previous_seconds,
        current_seconds=current_seconds,
        delta_seconds=delta_seconds,
        delta_percent=delta_percent,
    )


def _build_improvement_items(
    *,
    goals: Iterable[Goal],
    daily_breakdown: list[dict],
    course_rows: list[dict],
) -> list[str]:
    goals = list(goals)
    items: list[str] = []

    weak_goals = [
        goal
        for goal in goals
        if goal.status in {Goal.STATUS_MISSED, Goal.STATUS_OVERDUE}
        or goal.progress_percent < 50
        and goal.status != Goal.STATUS_COMPLETED
    ]
    if weak_goals:
        items.append(
            f"{len(weak_goals)} goal(s) need attention because they are overdue, missed, or under 50 percent."
        )

    low_days = [
        item["date"].strftime("%A")
        for item in daily_breakdown
        if item["study_seconds"] < ACTIVE_COURSE_SECONDS_THRESHOLD
        and item["site_active_seconds"] < ACTIVE_SITE_SECONDS_THRESHOLD
    ]
    if low_days:
        items.append("Low activity days: " + ", ".join(low_days[:3]) + ".")

    if len(course_rows) > 1 and course_rows[-1]["total_seconds"] > 0:
        items.append(
            f"Your least-focused course this period was {course_rows[-1]['course_title']}."
        )

    if not goals:
        items.append(
            "Set at least one goal for this period to unlock richer achievement tracking."
        )

    return items[:4]


def _get_insights_started_on(user):
    candidates: list[date] = []

    event_date = StudyTimeEvent.objects.filter(user=user).aggregate(
        value=Min("local_date")
    )["value"]
    if event_date:
        candidates.append(event_date)

    course_stat_date = DailyCourseStat.objects.filter(user=user).aggregate(
        value=Min("date")
    )["value"]
    if course_stat_date:
        candidates.append(course_stat_date)

    site_stat_date = DailySiteStat.objects.filter(user=user).aggregate(
        value=Min("date")
    )["value"]
    if site_stat_date:
        candidates.append(site_stat_date)

    if not candidates:
        return None
    return min(candidates)


def _serialize_chart_data(
    daily_breakdown: list[dict], course_rows: list[dict]
) -> tuple[dict, dict]:
    daily_chart = {
        "labels": [item["label"] for item in daily_breakdown],
        "study_minutes": [item["study_minutes"] for item in daily_breakdown],
        "site_minutes": [item["site_minutes"] for item in daily_breakdown],
    }
    course_chart = {
        "labels": [row["course_title"] for row in course_rows[:5]],
        "minutes": [round(row["total_seconds"] / 60.0, 2) for row in course_rows[:5]],
    }
    return daily_chart, course_chart


def _build_period_summary(user, period: PeriodRange) -> dict:
    previous_period = _previous_period(period)

    goals = list(get_goals_for_period(user, period.start, period.end))
    sync_goals(goals, save=True)

    goal_summary = get_goal_summary_for_period(user, period.start, period.end)
    daily_breakdown = _get_daily_breakdown(user, period)
    course_rows = _get_course_rows(user, period)
    top_courses = course_rows[:3]

    site_seconds = _get_site_seconds(user, period)
    previous_site_seconds = _get_site_seconds(user, previous_period)
    course_seconds = _get_course_seconds(user, period)
    previous_course_seconds = _get_course_seconds(user, previous_period)

    status = _build_status(
        goals=goals,
        daily_breakdown=daily_breakdown,
        current_site_seconds=site_seconds,
        previous_site_seconds=previous_site_seconds,
    )
    productive_day = _get_productive_day(daily_breakdown)
    daily_chart, course_chart = _serialize_chart_data(daily_breakdown, course_rows)

    return {
        "period": period,
        "previous_period": previous_period,
        "site_seconds": site_seconds,
        "course_seconds": course_seconds,
        "top_courses": top_courses,
        "course_breakdown": course_rows,
        "productive_day": productive_day,
        "status": status,
        "achievement_percent": goal_summary["achievement_percent"],
        "consistency_percent": status["consistency"],
        "planned_vs_actual_percent": goal_summary["planned_vs_actual_percent"],
        "goal_summary": goal_summary,
        "goals": goals,
        "daily_breakdown": daily_breakdown,
        "daily_chart": daily_chart,
        "course_chart": course_chart,
        "improvements": _build_improvement_items(
            goals=goals,
            daily_breakdown=daily_breakdown,
            course_rows=course_rows,
        ),
        "site_comparison": _build_comparison(site_seconds, previous_site_seconds),
        "course_comparison": _build_comparison(course_seconds, previous_course_seconds),
        "insights_started_on": _get_insights_started_on(user),
        "has_data": site_seconds > 0 or course_seconds > 0 or bool(goals),
    }


def build_weekly_summary(user, preference=None, week_start: date | None = None) -> dict:
    pref = _get_preference(user, preference)
    period = _get_week_period(user, week_start=week_start, preference=pref)
    summary = _build_period_summary(user, period)

    return {
        "page_title": "Weekly Summary",
        "week": period,
        "summary": summary,
        "weekly_status": summary["status"],
        "totals": {
            "site_seconds": summary["site_seconds"],
            "course_seconds": summary["course_seconds"],
        },
        "top_courses": summary["top_courses"],
        "course_breakdown": summary["course_breakdown"],
        "productive_day": summary["productive_day"],
        "goals": summary["goals"],
        "goal_summary": summary["goal_summary"],
        "achievement_percent": summary["achievement_percent"],
        "consistency_percent": summary["consistency_percent"],
        "planned_vs_actual_percent": summary["planned_vs_actual_percent"],
        "improvements": summary["improvements"],
        "daily_breakdown": summary["daily_breakdown"],
        "daily_chart": summary["daily_chart"],
        "course_chart": summary["course_chart"],
        "comparison": summary["site_comparison"],
        "insights_started_on": summary["insights_started_on"],
        "has_data": summary["has_data"],
        "selected_week": period.start,
    }


def build_daily_summary(user, preference=None, day: date | None = None) -> dict:
    pref = _get_preference(user, preference)
    target_date = day or get_local_date(user=user, preference=pref)
    period = PeriodRange(start=target_date, end=target_date)
    summary = _build_period_summary(user, period)

    return {
        "page_title": "Daily Summary",
        "day": period,
        "summary": summary,
        "daily_status": summary["status"],
        "totals": {
            "site_seconds": summary["site_seconds"],
            "course_seconds": summary["course_seconds"],
        },
        "top_courses": summary["top_courses"],
        "course_breakdown": summary["course_breakdown"],
        "productive_day": summary["productive_day"],
        "goals": summary["goals"],
        "goal_summary": summary["goal_summary"],
        "achievement_percent": summary["achievement_percent"],
        "consistency_percent": summary["consistency_percent"],
        "planned_vs_actual_percent": summary["planned_vs_actual_percent"],
        "improvements": summary["improvements"],
        "daily_breakdown": summary["daily_breakdown"],
        "daily_chart": summary["daily_chart"],
        "course_chart": summary["course_chart"],
        "comparison": summary["site_comparison"],
        "insights_started_on": summary["insights_started_on"],
        "has_data": summary["has_data"],
        "selected_day": period.start,
    }


def build_monthly_summary(
    user, preference=None, month_anchor: date | None = None
) -> dict:
    pref = _get_preference(user, preference)
    period = _get_month_period(user, month_anchor=month_anchor, preference=pref)
    summary = _build_period_summary(user, period)

    month_value = period.start.strftime("%Y-%m")
    previous_label = summary["previous_period"].start.strftime("%B %Y")

    return {
        "page_title": "Monthly Summary",
        "month": period,
        "month_value": month_value,
        "summary": summary,
        "top_courses": summary["course_breakdown"][:5],
        "comparison": summary["site_comparison"],
        "previous_label": previous_label,
        "insights_started_on": summary["insights_started_on"],
        "has_data": summary["has_data"],
        "selected_month": month_value,
    }


def build_overview_context(user, preference=None) -> dict:
    pref = _get_preference(user, preference)
    current_week_period = _get_week_period(user, preference=pref)
    current_month_period = _get_month_period(user, preference=pref)

    weekly = _build_period_summary(user, current_week_period)
    monthly = _build_period_summary(user, current_month_period)

    return {
        "weekly": weekly,
        "monthly": monthly,
        "current_week": current_week_period,
        "current_month": current_month_period,
        "insights_started_on": _get_insights_started_on(user),
    }


def get_weekly_summary(
    user, reference_date: date | None = None, preference=None
) -> dict:
    pref = _get_preference(user, preference)
    period = _get_week_period(user, week_start=reference_date, preference=pref)
    summary = _build_period_summary(user, period)

    return {
        "period": {
            "start": period.start,
            "end": period.end,
        },
        "top_courses": [
            {
                "course_id": row["course_id"],
                "course_title": row["course_title"],
                "title": row["course_title"],
                "total_seconds": row["total_seconds"],
            }
            for row in summary["top_courses"]
        ],
        "daily_breakdown": summary["daily_breakdown"],
        "total_site_seconds": summary["site_seconds"],
        "total_course_seconds": summary["course_seconds"],
        "achievement_percent": summary["achievement_percent"],
        "consistency_percent": summary["consistency_percent"],
        "planned_vs_actual_percent": summary["planned_vs_actual_percent"],
        "weekly_status": summary["status"],
        "status": summary["status"],
    }
