from __future__ import annotations

from datetime import datetime
from datetime import timezone as dt_timezone

from courses.models import Content, Module
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import F
from django.utils import timezone

from ..models import DailyCourseStat, DailySiteStat, StudyTimeEvent
from .common import get_user_timezone

PRESENCE_CACHE_KEY = "learning_insights:last_presence_ping:{user_id}"
LAST_ACTIVITY_CACHE_KEY = "learning_insights:last_activity_at:{user_id}"
PRESENCE_MAX_GAP_SECONDS = 120
LAST_ACTIVITY_TTL_SECONDS = 60 * 60 * 24 * 7
DEFAULT_EVENT_SOURCE = StudyTimeEvent.SOURCE_MODULE


def _coerce_positive_seconds(value) -> int:
    try:
        seconds = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, seconds)


def _presence_cache_key(user_id: int) -> str:
    return PRESENCE_CACHE_KEY.format(user_id=user_id)


def _last_activity_cache_key(user_id: int) -> str:
    return LAST_ACTIVITY_CACHE_KEY.format(user_id=user_id)


def _touch_last_activity(user_id: int, recorded_at: datetime):
    try:
        cache.set(
            _last_activity_cache_key(int(user_id)),
            recorded_at.timestamp(),
            timeout=LAST_ACTIVITY_TTL_SECONDS,
        )
    except Exception:
        # Cache failures should never break tracking.
        return


def _get_local_parts(
    user, recorded_at: datetime | None = None
) -> tuple[datetime, object, int]:
    recorded_at = recorded_at or timezone.now()
    local_dt = timezone.localtime(recorded_at, get_user_timezone(user=user))
    return recorded_at, local_dt.date(), local_dt.hour


def record_module_time_event(
    user,
    module: Module,
    seconds_delta: int,
    recorded_at: datetime | None = None,
):
    """
    Record canonical module study time and roll it into daily course stats.

    Module time is the Release 1 source of truth for course-level study time.
    """
    seconds_delta = _coerce_positive_seconds(seconds_delta)
    if seconds_delta <= 0 or module is None:
        return None

    recorded_at, local_date, local_hour = _get_local_parts(user, recorded_at)
    _touch_last_activity(getattr(user, "id", 0) or 0, recorded_at)

    event = StudyTimeEvent.objects.create(
        user=user,
        course=module.course,
        module=module,
        seconds_delta=seconds_delta,
        source=DEFAULT_EVENT_SOURCE,
        session_end_at=recorded_at,
        local_date=local_date,
        local_hour=local_hour,
    )

    stat, created = DailyCourseStat.objects.get_or_create(
        user=user,
        course=module.course,
        date=local_date,
        defaults={
            "module_seconds": seconds_delta,
            "content_active_seconds": 0,
            "completed_content_count": 0,
            "session_count": 1,
        },
    )

    if not created:
        stat.module_seconds = F("module_seconds") + seconds_delta
        stat.session_count = F("session_count") + 1
        stat.save(update_fields=["module_seconds", "session_count"])

    return event


def record_content_progress_event(
    user,
    content: Content,
    *,
    seconds_delta: int = 0,
    completed_now: bool = False,
    recorded_at: datetime | None = None,
):
    """
    Record content engagement signals without creating a StudyTimeEvent.

    Release 1 treats module time as canonical time. Content progress only
    enriches engagement/completion stats.
    """
    if content is None:
        return None

    seconds_delta = _coerce_positive_seconds(seconds_delta)
    recorded_at, local_date, _local_hour = _get_local_parts(user, recorded_at)
    _touch_last_activity(getattr(user, "id", 0) or 0, recorded_at)
    course = content.module.course

    stat, created = DailyCourseStat.objects.get_or_create(
        user=user,
        course=course,
        date=local_date,
        defaults={
            "module_seconds": 0,
            "content_active_seconds": seconds_delta,
            "completed_content_count": 1 if completed_now else 0,
            "session_count": 0,
        },
    )

    if not created:
        update_fields: list[str] = []

        if seconds_delta > 0:
            stat.content_active_seconds = F("content_active_seconds") + seconds_delta
            update_fields.append("content_active_seconds")

        if completed_now:
            stat.completed_content_count = F("completed_content_count") + 1
            update_fields.append("completed_content_count")

        if update_fields:
            stat.save(update_fields=update_fields)

    return stat


def record_presence_ping(user_id: int, recorded_at: datetime | None = None):
    """
    Convert site presence heartbeats into daily active site time.

    The first ping contributes 0 seconds. Later pings add the elapsed gap,
    capped to avoid counting long idle periods as active study time.
    """
    recorded_at = recorded_at or timezone.now()

    User = get_user_model()
    user = User.objects.get(pk=user_id)
    _touch_last_activity(int(user_id), recorded_at)

    _, local_date, _ = _get_local_parts(user, recorded_at)
    cache_key = _presence_cache_key(user_id)
    previous_timestamp = cache.get(cache_key)

    delta_seconds = 0
    if previous_timestamp is not None:
        try:
            previous_dt = datetime.fromtimestamp(
                float(previous_timestamp),
                tz=dt_timezone.utc,
            )
            raw_gap = int((recorded_at - previous_dt).total_seconds())
            delta_seconds = max(0, min(raw_gap, PRESENCE_MAX_GAP_SECONDS))
        except (TypeError, ValueError, OSError, OverflowError):
            delta_seconds = 0

    cache.set(
        cache_key,
        recorded_at.timestamp(),
        timeout=PRESENCE_MAX_GAP_SECONDS * 2,
    )

    stat, created = DailySiteStat.objects.get_or_create(
        user=user,
        date=local_date,
        defaults={
            "active_seconds": delta_seconds,
            "ping_count": 1,
        },
    )

    if not created:
        stat.ping_count = F("ping_count") + 1
        if delta_seconds > 0:
            stat.active_seconds = F("active_seconds") + delta_seconds
            stat.save(update_fields=["active_seconds", "ping_count"])
        else:
            stat.save(update_fields=["ping_count"])

    return stat


def get_last_activity_at(*, user):
    """
    Best-effort "last activity" timestamp for inactivity warnings.

    Sources (in priority order):
    - cache updated by presence + study events
    - latest DailySiteStat.updated
    - latest StudyTimeEvent.session_end_at
    """
    user_id = getattr(user, "id", None)
    if not user_id:
        return None

    cached = cache.get(_last_activity_cache_key(int(user_id)))
    if cached is not None:
        try:
            return datetime.fromtimestamp(float(cached), tz=dt_timezone.utc)
        except (TypeError, ValueError, OSError, OverflowError):
            pass

    last_site = (
        DailySiteStat.objects.filter(user_id=int(user_id))
        .order_by("-date", "-updated", "-id")
        .values_list("updated", flat=True)
        .first()
    )
    last_study = (
        StudyTimeEvent.objects.filter(user_id=int(user_id))
        .order_by("-session_end_at", "-id")
        .values_list("session_end_at", flat=True)
        .first()
    )

    candidates = [dt for dt in (last_site, last_study) if dt is not None]
    if not candidates:
        return None

    latest = max(candidates)
    try:
        _touch_last_activity(int(user_id), latest)
    except Exception:
        pass
    return latest


def safe_record_module_time_event(
    user,
    module: Module,
    seconds_delta: int,
    recorded_at: datetime | None = None,
):
    """
    Best-effort wrapper so insight tracking never breaks the caller.
    """
    try:
        return record_module_time_event(
            user,
            module,
            seconds_delta,
            recorded_at=recorded_at,
        )
    except Exception:
        return None


def safe_record_content_progress_event(
    user,
    content: Content,
    *,
    seconds_delta: int = 0,
    completed_now: bool = False,
    recorded_at: datetime | None = None,
):
    """
    Best-effort wrapper for content engagement tracking.
    """
    try:
        return record_content_progress_event(
            user,
            content,
            seconds_delta=seconds_delta,
            completed_now=completed_now,
            recorded_at=recorded_at,
        )
    except Exception:
        return None


def safe_record_presence_ping(
    user_id: int,
    recorded_at: datetime | None = None,
):
    """
    Best-effort wrapper for site presence tracking.
    """
    try:
        return record_presence_ping(user_id, recorded_at=recorded_at)
    except Exception:
        return None
