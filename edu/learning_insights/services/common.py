from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone

from ..models import NotificationPreference

DEFAULT_WEEK_START = 0  # Monday


@dataclass(frozen=True)
class PeriodRange:
    start: date
    end: date

    @property
    def days(self) -> int:
        return max(0, (self.end - self.start).days + 1)


def get_or_create_notification_preference(user) -> NotificationPreference:
    preference, _ = NotificationPreference.objects.get_or_create(
        user=user,
        defaults={
            "timezone": settings.TIME_ZONE,
            "week_start_day": DEFAULT_WEEK_START,
        },
    )
    return preference


def normalize_week_start(week_start_day: int | None) -> int:
    if week_start_day is None:
        return DEFAULT_WEEK_START
    try:
        value = int(week_start_day)
    except (TypeError, ValueError):
        return DEFAULT_WEEK_START

    if 0 <= value <= 6:
        return value
    return DEFAULT_WEEK_START


def _coerce_timezone_name(
    value=None,
    *,
    user=None,
    preference: NotificationPreference | None = None,
) -> str:
    if isinstance(value, NotificationPreference):
        preference = value
        value = None

    if isinstance(value, str) and value.strip():
        return value.strip()

    if preference is not None:
        tz_name = (getattr(preference, "timezone", "") or "").strip()
        if tz_name:
            return tz_name

    if user is not None:
        related_pref = getattr(user, "learning_insights_preference", None)
        tz_name = (getattr(related_pref, "timezone", "") or "").strip()
        if tz_name:
            return tz_name

    return settings.TIME_ZONE


def get_user_timezone(
    user=None,
    preference: NotificationPreference | None = None,
    timezone_name: str | None = None,
):
    tz_name = _coerce_timezone_name(
        timezone_name,
        user=user,
        preference=preference,
    )
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(settings.TIME_ZONE)


def get_local_now(
    value=None,
    *,
    user=None,
    preference: NotificationPreference | None = None,
) -> datetime:
    """
    Flexible helper for local "now".

    Supported call styles:
    - get_local_now()
    - get_local_now(user=request.user)
    - get_local_now(preference=preference)
    - get_local_now("Africa/Addis_Ababa")
    """
    if value is not None and user is None and preference is None:
        if isinstance(value, NotificationPreference):
            preference = value
        elif isinstance(value, str):
            return timezone.localtime(
                timezone.now(), get_user_timezone(timezone_name=value)
            )
        else:
            user = value

    return timezone.localtime(
        timezone.now(),
        get_user_timezone(user=user, preference=preference),
    )


def get_local_date(
    value=None,
    *,
    user=None,
    preference: NotificationPreference | None = None,
) -> date:
    return get_local_now(value, user=user, preference=preference).date()


def get_local_hour(
    value=None,
    *,
    user=None,
    preference: NotificationPreference | None = None,
) -> int:
    return get_local_now(value, user=user, preference=preference).hour


def combine_local_date_time(
    target_date: date,
    target_time: time,
    value=None,
    *,
    user=None,
    preference: NotificationPreference | None = None,
) -> datetime:
    if value is not None and user is None and preference is None:
        if isinstance(value, NotificationPreference):
            preference = value
        elif not isinstance(value, str):
            user = value

    tz = (
        get_user_timezone(timezone_name=value)
        if isinstance(value, str)
        else get_user_timezone(user=user, preference=preference)
    )
    naive = datetime.combine(target_date, target_time)
    return timezone.make_aware(naive, tz)


def get_week_range(
    target_date: date,
    week_start_day: int | None = DEFAULT_WEEK_START,
) -> PeriodRange:
    week_start_day = normalize_week_start(week_start_day)
    offset = (target_date.weekday() - week_start_day) % 7
    start = target_date - timedelta(days=offset)
    end = start + timedelta(days=6)
    return PeriodRange(start=start, end=end)


def get_month_range(target_date: date) -> PeriodRange:
    _, last_day = calendar.monthrange(target_date.year, target_date.month)
    start = target_date.replace(day=1)
    end = target_date.replace(day=last_day)
    return PeriodRange(start=start, end=end)


def parse_week_start(value: str | None, fallback: date | None = None) -> date:
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return fallback or timezone.localdate()


def parse_month_start(value: str | None, fallback: date | None = None) -> date:
    if value:
        try:
            return datetime.strptime(value, "%Y-%m").date().replace(day=1)
        except ValueError:
            pass

    base = fallback or timezone.localdate()
    return base.replace(day=1)


def coerce_week_start_date(
    target_date: date,
    week_start_day: int | None = DEFAULT_WEEK_START,
) -> date:
    return get_week_range(target_date, week_start_day=week_start_day).start


def previous_week_range(
    week_start: date,
    week_start_day: int | None = DEFAULT_WEEK_START,
) -> PeriodRange:
    normalized_start = coerce_week_start_date(
        week_start,
        week_start_day=week_start_day,
    )
    previous_start = normalized_start - timedelta(days=7)
    return get_week_range(previous_start, week_start_day=week_start_day)


def previous_month_range(month_start: date) -> PeriodRange:
    normalized_start = month_start.replace(day=1)
    previous_day = normalized_start - timedelta(days=1)
    return get_month_range(previous_day)


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def format_month_key(target_date: date) -> str:
    return target_date.strftime("%Y-%m")


def weekday_name(weekday: int) -> str:
    names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    return names[normalize_week_start(weekday)]


def get_week_label(period: PeriodRange) -> str:
    return f"{period.start.isoformat()} to {period.end.isoformat()}"


def get_month_label(period: PeriodRange) -> str:
    return period.start.strftime("%B %Y")


# Compatibility helpers used by existing app code.
def get_period_start(
    target_date: date,
    period_type: str,
    week_start_day: int | None = DEFAULT_WEEK_START,
) -> date:
    if period_type == "weekly":
        return get_week_range(target_date, week_start_day=week_start_day).start
    if period_type == "monthly":
        return get_month_range(target_date).start
    return target_date


def get_period_end(
    target_date: date,
    period_type: str,
    week_start_day: int | None = DEFAULT_WEEK_START,
) -> date:
    if period_type == "weekly":
        return get_week_range(target_date, week_start_day=week_start_day).end
    if period_type == "monthly":
        return get_month_range(target_date).end
    return target_date
