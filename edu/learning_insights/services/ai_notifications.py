from __future__ import annotations

from datetime import date, time, timedelta
from typing import Any

from django.core.cache import cache

from django.db.models import Sum

from learning_insights.models import (
    AIPlanRun,
    DailyCourseStat,
    DailySiteStat,
    Goal,
    NotificationPreference,
)
from learning_insights.services.ai_coach import (
    generate_recovery_run,
    generate_weekly_review_run,
)
from learning_insights.services.common import get_local_now, get_period_start
from learning_insights.services.telegram import send_notification

# Scheduled windows (user-local time).
DAILY_SUMMARY_WINDOW_START = time(hour=20, minute=0)
DAILY_SUMMARY_WINDOW_END = time(hour=23, minute=59, second=59)
WEEKLY_REVIEW_WINDOW_START = time(hour=20, minute=0)
WEEKLY_REVIEW_WINDOW_END = time(hour=23, minute=59, second=59)

# Weekly review minimum data requirement.
WEEKLY_REVIEW_MIN_ACTIVE_DAYS = 3
WEEKLY_REVIEW_MIN_TOTAL_ACTIVITY_SECONDS = 60 * 60  # 60 minutes

# Active day definition (for "enough data exists" checks).
ACTIVE_DAY_MIN_MODULE_SECONDS = 5 * 60
ACTIVE_DAY_MIN_SITE_SECONDS = 10 * 60

# Critical drop detection.
CONSISTENCY_BASELINE_DAYS = 7
CONSISTENCY_DROP_RATIO = 0.5  # >50% drop from baseline average
CONSISTENCY_BASELINE_MIN_AVG_SECONDS = 15 * 60


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _format_bullets(items: list[str], *, limit: int = 5) -> str:
    cleaned = [str(item).strip() for item in (items or []) if str(item).strip()]
    if not cleaned:
        return ""
    lines = [f"- {item}" for item in cleaned[:limit]]
    return "\n".join(lines)


def format_weekly_plan_message(payload: dict[str, Any]) -> str:
    reasoning = str(payload.get("reasoning_summary") or "").strip()
    inputs = payload.get("inputs_used") if isinstance(payload.get("inputs_used"), dict) else {}
    focus = payload.get("focus_courses") if isinstance(payload.get("focus_courses"), list) else []
    if not focus:
        focus = payload.get("weekly_focus") if isinstance(payload.get("weekly_focus"), list) else []
    plan = payload.get("plan") if isinstance(payload.get("plan"), list) else []
    period = payload.get("period") if isinstance(payload.get("period"), dict) else {}

    lines: list[str] = []
    lines.append("AI Study Plan")

    start = str(period.get("start") or "").strip()
    end = str(period.get("end") or "").strip()
    if start and end:
        lines.append("")
        lines.append(f"Period: {start} -> {end}")
    if reasoning:
        lines.append("")
        lines.append(_truncate(reasoning, 900))

    if inputs:
        lines.append("")
        lines.append("Decision factors:")
        for key in ("goals", "analytics", "roadmap", "constraints"):
            value = str(inputs.get(key) or "").strip()
            if value:
                label = key.capitalize()
                lines.append(f"- {label}: {_truncate(value, 280)}")

    if focus:
        lines.append("")
        lines.append("Focus:")
        focus_lines = []
        for row in focus[:4]:
            if not isinstance(row, dict):
                continue
            title = row.get("course_title") or row.get("title") or ""
            why = row.get("why") or ""
            title = str(title).strip()
            if not title:
                continue
            label = f"{title}: {why}" if why else title
            focus_lines.append(_truncate(label, 200))
        bullets = _format_bullets(focus_lines, limit=4)
        if bullets:
            lines.append(bullets)

    if plan:
        lines.append("")
        lines.append("Plan highlights:")
        highlights: list[str] = []
        for day in plan[:3]:
            if not isinstance(day, dict):
                continue
            day_value = str(day.get("date") or "").strip()
            if day.get("is_buffer_day"):
                highlights.append(f"{day_value}: Buffer / rest")
                continue
            items = day.get("items") if isinstance(day.get("items"), list) else []
            if not items:
                continue
            first = items[0] if isinstance(items[0], dict) else {}
            course_title = str(first.get("course_title") or "").strip()
            minutes = first.get("minutes")
            try:
                minutes_value = int(minutes or 0)
            except (TypeError, ValueError):
                minutes_value = 0
            task = str(first.get("task") or "").strip()
            label = f"{day_value}: "
            if minutes_value:
                label += f"{minutes_value}m "
            if course_title:
                label += f"{course_title} — "
            label += task or "Study"
            highlights.append(_truncate(label, 220))
        bullets = _format_bullets(highlights, limit=3)
        if bullets:
            lines.append(bullets)

    risk = str(payload.get("risk_level") or "").strip()
    if risk:
        lines.append("")
        lines.append(f"Risk level: {risk}")

    return "\n".join(lines).strip()


def format_daily_plan_message(payload: dict[str, Any]) -> str:
    reasoning = str(payload.get("reasoning_summary") or "").strip()
    inputs = payload.get("inputs_used") if isinstance(payload.get("inputs_used"), dict) else {}
    day_value = str(payload.get("date") or payload.get("day") or "").strip()
    items = payload.get("items") if isinstance(payload.get("items"), list) else []

    lines: list[str] = []
    lines.append("AI Daily Plan")
    if day_value:
        lines.append("")
        lines.append(f"Date: {day_value}")

    if reasoning:
        lines.append("")
        lines.append(_truncate(reasoning, 900))

    if inputs:
        lines.append("")
        lines.append("Decision factors:")
        for key in ("goals", "analytics", "roadmap", "constraints"):
            value = str(inputs.get(key) or "").strip()
            if value:
                label = key.capitalize()
                lines.append(f"- {label}: {_truncate(value, 280)}")

    if items:
        lines.append("")
        lines.append("Plan:")
        bullets: list[str] = []
        for item in items[:6]:
            if not isinstance(item, dict):
                continue
            course_title = str(item.get("course_title") or "").strip()
            task = str(item.get("task") or "").strip()
            minutes = item.get("minutes")
            try:
                minutes_value = int(minutes or 0)
            except (TypeError, ValueError):
                minutes_value = 0

            label = ""
            if minutes_value:
                label += f"{minutes_value}m "
            if course_title:
                label += f"{course_title} — "
            label += task or "Study"
            bullets.append(_truncate(label, 220))

        formatted = _format_bullets(bullets, limit=6)
        if formatted:
            lines.append(formatted)

    risk = str(payload.get("risk_level") or "").strip()
    if risk:
        lines.append("")
        lines.append(f"Risk level: {risk}")

    return "\n".join(lines).strip()


def format_review_message(payload: dict[str, Any], *, title: str = "AI Review") -> str:
    summary = str(payload.get("summary") or "").strip()
    risk = str(payload.get("risk_level") or "").strip()
    achievements = payload.get("achievements") if isinstance(payload.get("achievements"), list) else []
    missed = payload.get("missed_targets") if isinstance(payload.get("missed_targets"), list) else []
    insights = payload.get("insights") if isinstance(payload.get("insights"), list) else []
    suggestions = payload.get("suggestions") if isinstance(payload.get("suggestions"), list) else []

    lines: list[str] = [title]
    if summary:
        lines.append("")
        lines.append(_truncate(summary, 900))

    if achievements:
        lines.append("")
        lines.append("Achievements:")
        lines.append(_format_bullets([str(x) for x in achievements], limit=4))

    if missed:
        lines.append("")
        lines.append("Missed targets:")
        lines.append(_format_bullets([str(x) for x in missed], limit=4))

    if insights:
        lines.append("")
        lines.append("Insights:")
        lines.append(_format_bullets([str(x) for x in insights], limit=4))

    if suggestions:
        lines.append("")
        lines.append("Suggestions:")
        lines.append(_format_bullets([str(x) for x in suggestions], limit=6))

    if risk:
        lines.append("")
        lines.append(f"Risk level: {risk}")

    return "\n".join([line for line in lines if line is not None]).strip()

def _cache_key(prefix: str, user_id: int, suffix: str) -> str:
    return f"li_tg:{prefix}:{user_id}:{suffix}"


def _within_window(current: time, start: time, end: time) -> bool:
    return start <= current <= end


def _day_totals(*, user, target_date: date) -> tuple[int, int]:
    course_seconds = (
        DailyCourseStat.objects.filter(user=user, date=target_date)
        .aggregate(total=Sum("module_seconds"))
        .get("total")
        or 0
    )
    site_seconds = (
        DailySiteStat.objects.filter(user=user, date=target_date)
        .aggregate(total=Sum("active_seconds"))
        .get("total")
        or 0
    )
    try:
        return int(course_seconds or 0), int(site_seconds or 0)
    except (TypeError, ValueError):
        return 0, 0


def _studied_on_day(*, user, target_date: date) -> bool:
    course_seconds, _ = _day_totals(user=user, target_date=target_date)
    return course_seconds > 0


def _week_end_weekday(week_start_day: int) -> int:
    try:
        start = int(week_start_day)
    except (TypeError, ValueError):
        start = 0
    return (start - 1) % 7


def _week_activity(*, user, week_start: date, week_end: date) -> tuple[int, int]:
    module_rows = (
        DailyCourseStat.objects.filter(user=user, date__gte=week_start, date__lte=week_end)
        .values("date")
        .annotate(total=Sum("module_seconds"))
    )
    module_by_date = {row["date"]: int(row["total"] or 0) for row in module_rows}

    site_rows = (
        DailySiteStat.objects.filter(user=user, date__gte=week_start, date__lte=week_end)
        .values("date")
        .annotate(total=Sum("active_seconds"))
    )
    site_by_date = {row["date"]: int(row["total"] or 0) for row in site_rows}

    active_days = 0
    total_activity = 0
    cursor = week_start
    while cursor <= week_end:
        module_seconds = int(module_by_date.get(cursor, 0) or 0)
        site_seconds = int(site_by_date.get(cursor, 0) or 0)
        total_activity += module_seconds + site_seconds

        if module_seconds >= ACTIVE_DAY_MIN_MODULE_SECONDS or site_seconds >= ACTIVE_DAY_MIN_SITE_SECONDS:
            active_days += 1
        cursor += timedelta(days=1)

    return active_days, total_activity


def _minutes(seconds: int) -> int:
    seconds = int(seconds or 0)
    return max(0, seconds // 60)


def format_daily_summary_message(
    *,
    user,
    preference: NotificationPreference,
    target_date: date,
    course_seconds: int,
    site_seconds: int,
) -> str:
    course_minutes = _minutes(course_seconds)
    site_minutes = _minutes(site_seconds)

    top = (
        DailyCourseStat.objects.filter(user=user, date=target_date)
        .values("course__title")
        .annotate(total=Sum("module_seconds"))
        .order_by("-total")
        .first()
    )
    top_course = (top or {}).get("course__title") or ""
    top_minutes = _minutes(int((top or {}).get("total") or 0))

    planned_minutes = 0
    try:
        planned_minutes = int(
            Goal.objects.filter(
                user=user,
                period_type=Goal.PERIOD_DAILY,
                target_type=Goal.TARGET_MINUTES,
                start_date__lte=target_date,
                due_date__gte=target_date,
            )
            .aggregate(total=Sum("target_value"))
            .get("total")
            or 0
        )
    except (TypeError, ValueError):
        planned_minutes = 0

    lines: list[str] = []
    lines.append(f"Daily summary ({target_date.isoformat()})")
    lines.append("")
    lines.append(f"Course study: {course_minutes} min")
    lines.append(f"Site active: {site_minutes} min")

    if planned_minutes > 0:
        pct = int(min(100, (course_minutes / planned_minutes) * 100)) if planned_minutes else 0
        lines.append(f"Planned vs actual: {course_minutes}/{planned_minutes} min ({pct}%)")

    if top_course and top_minutes:
        lines.append(f"Top course: {top_course} ({top_minutes} min)")

    # Minimal insight + next-step nudge.
    if course_minutes == 0:
        lines.append("")
        lines.append("You didn’t log course study time today.")
        lines.append("Reset suggestion: do a 20-minute light session tomorrow and stop after one module.")
    elif planned_minutes > 0 and course_minutes < int(planned_minutes * 0.5):
        lines.append("")
        lines.append("You’re behind today’s plan. Keep tomorrow simple: 1 focused block (25–30 min).")

    return "\n".join(lines).strip()


def format_missed_streak_alert_message(
    *,
    user,
    preference: NotificationPreference,
    today: date,
    missed_dates: list[date],
) -> str:
    start = missed_dates[-1]
    end = missed_dates[0]

    run = generate_recovery_run(user=user, preference=preference, reference_date=today)
    suggestions = []
    if run.status == AIPlanRun.STATUS_SUCCESS:
        payload = run.effective_payload if isinstance(run.effective_payload, dict) else {}
        raw = payload.get("suggestions")
        if isinstance(raw, list):
            suggestions = [str(item).strip() for item in raw if str(item).strip()]

    lines: list[str] = []
    lines.append("Critical alert: missed 3 days")
    lines.append("")
    lines.append(f"No course study time logged for {start.isoformat()} → {end.isoformat()}.")
    lines.append("Recommended reset: restart with a 20-minute light session today.")
    if suggestions:
        lines.append("")
        lines.append("Recovery suggestion:")
        lines.append(_format_bullets(suggestions, limit=3))
    return _truncate("\n".join(lines).strip(), 3800)


def format_consistency_drop_alert_message(
    *,
    today: date,
    today_seconds: int,
    baseline_avg_seconds: float,
) -> str:
    today_minutes = _minutes(today_seconds)
    baseline_minutes = _minutes(int(round(baseline_avg_seconds)))
    drop_pct = 0
    if baseline_avg_seconds > 0:
        drop_pct = int(max(0, min(100, (1 - (today_seconds / baseline_avg_seconds)) * 100)))

    lines: list[str] = []
    lines.append("Critical alert: sharp consistency drop")
    lines.append("")
    lines.append(
        f"Today ({today.isoformat()}): {today_minutes} min vs 7-day avg {baseline_minutes} min ({drop_pct}% drop)."
    )
    lines.append("Suggested adjustment: reduce tomorrow to 1 focus block (20–30 min) and rebuild from there.")
    return "\n".join(lines).strip()


def maybe_send_daily_summary(*, user, preference: NotificationPreference) -> bool:
    if not getattr(preference, "telegram_enabled", False):
        return False

    local_now = get_local_now(preference=preference)
    if not _within_window(local_now.time(), DAILY_SUMMARY_WINDOW_START, DAILY_SUMMARY_WINDOW_END):
        return False

    target_date = local_now.date()
    dedupe = _cache_key("daily_summary", user.id, target_date.isoformat())
    if cache.get(dedupe) == "1":
        return False

    course_seconds, site_seconds = _day_totals(user=user, target_date=target_date)
    has_activity = (course_seconds + site_seconds) > 0
    if not has_activity and not getattr(preference, "telegram_daily_summary_enabled", False):
        return False

    message_text = format_daily_summary_message(
        user=user,
        preference=preference,
        target_date=target_date,
        course_seconds=course_seconds,
        site_seconds=site_seconds,
    )
    ok = send_notification(user=user, message=message_text)
    if ok:
        cache.set(dedupe, "1", timeout=60 * 60 * 30)
    return ok


def maybe_send_weekly_review(*, user, preference: NotificationPreference) -> bool:
    if not getattr(preference, "telegram_enabled", False):
        return False
    if not getattr(preference, "telegram_weekly_review_enabled", False):
        return False

    local_now = get_local_now(preference=preference)
    week_end_day = _week_end_weekday(getattr(preference, "week_start_day", 0))
    if local_now.weekday() != week_end_day:
        return False
    if not _within_window(local_now.time(), WEEKLY_REVIEW_WINDOW_START, WEEKLY_REVIEW_WINDOW_END):
        return False

    week_start = get_period_start(
        local_now.date(),
        Goal.PERIOD_WEEKLY,
        week_start_day=preference.week_start_day,
    )
    week_end = week_start + timedelta(days=6)
    active_days, total_activity = _week_activity(user=user, week_start=week_start, week_end=week_end)
    if not (
        active_days >= WEEKLY_REVIEW_MIN_ACTIVE_DAYS
        or total_activity >= WEEKLY_REVIEW_MIN_TOTAL_ACTIVITY_SECONDS
    ):
        return False

    dedupe = _cache_key("weekly_review", user.id, week_start.isoformat())
    if cache.get(dedupe) == "1":
        return False

    review_run = generate_weekly_review_run(user=user, preference=preference, reference_date=local_now.date())
    if review_run.status != AIPlanRun.STATUS_SUCCESS:
        return False

    message_text = format_review_message(review_run.effective_payload or {}, title="Weekly Review")
    message_text = _truncate(
        message_text
        + "\n\n"
        + "Tip: Create a study plan from a prompt in Learning Insights → Create goal → AI planner.",
        3800,
    )

    ok = send_notification(user=user, message=message_text)
    if ok:
        cache.set(dedupe, "1", timeout=60 * 60 * 24 * 10)
    return ok


def maybe_send_critical_alerts(*, user, preference: NotificationPreference) -> bool:
    if not getattr(preference, "telegram_enabled", False):
        return False
    if not getattr(preference, "telegram_critical_alerts_enabled", False):
        return False

    local_now = get_local_now(preference=preference)
    today = local_now.date()

    # 1) Missed streak: send when the previous 3 days had no course study time.
    missed_dates = [today - timedelta(days=1), today - timedelta(days=2), today - timedelta(days=3)]
    if all(not _studied_on_day(user=user, target_date=day) for day in missed_dates):
        suffix = f"missed:{missed_dates[-1].isoformat()}:{missed_dates[0].isoformat()}"
        dedupe = _cache_key("critical", user.id, suffix)
        if cache.get(dedupe) == "1":
            return False

        ok = send_notification(
            user=user,
            message=format_missed_streak_alert_message(
                user=user,
                preference=preference,
                today=today,
                missed_dates=missed_dates,
            ),
        )
        if ok:
            cache.set(dedupe, "1", timeout=60 * 60 * 24 * 7)
        return ok

    # 2) Sharp consistency drop: evaluate near end-of-day.
    if not _within_window(local_now.time(), DAILY_SUMMARY_WINDOW_START, DAILY_SUMMARY_WINDOW_END):
        return False

    baseline_end = today - timedelta(days=1)
    baseline_start = today - timedelta(days=CONSISTENCY_BASELINE_DAYS)

    baseline_rows = (
        DailyCourseStat.objects.filter(user=user, date__gte=baseline_start, date__lte=baseline_end)
        .values("date")
        .annotate(total=Sum("module_seconds"))
    )
    baseline_by_date = {row["date"]: int(row["total"] or 0) for row in baseline_rows}
    baseline_total = 0
    cursor = baseline_start
    while cursor <= baseline_end:
        baseline_total += int(baseline_by_date.get(cursor, 0) or 0)
        cursor += timedelta(days=1)

    baseline_avg = baseline_total / float(CONSISTENCY_BASELINE_DAYS)
    if baseline_avg < CONSISTENCY_BASELINE_MIN_AVG_SECONDS:
        return False

    today_seconds, _ = _day_totals(user=user, target_date=today)
    if today_seconds >= (baseline_avg * CONSISTENCY_DROP_RATIO):
        return False

    dedupe = _cache_key("critical", user.id, f"drop:{today.isoformat()}")
    if cache.get(dedupe) == "1":
        return False

    ok = send_notification(
        user=user,
        message=format_consistency_drop_alert_message(
            today=today,
            today_seconds=today_seconds,
            baseline_avg_seconds=baseline_avg,
        ),
    )
    if ok:
        cache.set(dedupe, "1", timeout=60 * 60 * 24 * 3)
    return ok
