from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from assistant.services import GeminiError, generate_ai_response_simple
from courses.models import ContentSearchEntry, Course
from courses.search import search_content_entries, search_courses
from django.db import transaction
from django.utils import timezone
from notes.models import Note
from students.models import CourseProgress, ModuleProgress

from learning_insights.models import AIPlanRun, Goal, NotificationPreference
from learning_insights.services.analytics import build_monthly_summary, build_weekly_summary
from learning_insights.services.common import get_local_date, get_period_end, get_period_start


TEMPERATURE_PRECISE = 0.2
TEMPERATURE_BALANCED = 0.5
TEMPERATURE_REPAIR = 0.0
DEFAULT_MAX_OUTPUT_TOKENS = 4096


def _json_default(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return int(value.total_seconds())
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        loaded = json.loads(cleaned)
        if isinstance(loaded, dict):
            return loaded
        return {"value": loaded}
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = cleaned[start : end + 1]
            return json.loads(snippet)
        raise


def _build_json_repair_prompt(*, raw_text: str, parse_error: str) -> str:
    return (
        "The previous AI response was invalid JSON.\n"
        "Fix the JSON below so it is syntactically valid and preserves the original meaning.\n"
        "Return only valid JSON. Do not add markdown, comments, or explanation.\n\n"
        f"Parser error: {parse_error}\n\n"
        "Invalid JSON:\n"
        f"{raw_text}"
    )


def _repair_invalid_json_output(*, raw_text: str, system_prompt: str, parse_error: str) -> str:
    repair_prompt = _build_json_repair_prompt(raw_text=raw_text, parse_error=parse_error)
    try:
        return generate_ai_response_simple(
            {"prompt": repair_prompt, "maxOutputTokens": DEFAULT_MAX_OUTPUT_TOKENS},
            system_prompt,
            temperature=TEMPERATURE_REPAIR,
        )
    except GeminiError as repair_error:
        raise GeminiError(
            "AI output could not be parsed and the JSON repair retry failed.",
            details={
                "parse_error": parse_error,
                "raw_text": raw_text[:1200].strip(),
                "repair_error": repair_error.message,
                "repair_details": repair_error.details,
            },
        ) from repair_error


def _extract_json_with_repair(*, raw_text: str, system_prompt: str) -> dict[str, Any]:
    try:
        return _extract_json(raw_text)
    except json.JSONDecodeError as exc:
        repaired_text = _repair_invalid_json_output(
            raw_text=raw_text,
            system_prompt=system_prompt,
            parse_error=str(exc),
        )
        try:
            return _extract_json(repaired_text)
        except json.JSONDecodeError as repair_exc:
            raise GeminiError(
                "AI output could not be parsed after a repair retry.",
                details={
                    "parse_error": str(exc),
                    "raw_text": raw_text[:1200].strip(),
                    "repaired_text": repaired_text[:1200].strip(),
                    "repair_error": str(repair_exc),
                },
            ) from repair_exc


def _strip_html(html: str, limit: int = 1200) -> str:
    html = (html or "").strip()
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _normalize_whitespace(value: str) -> str:
    return " ".join((value or "").split())


def _truncate_text(value: str, limit: int) -> str:
    normalized = _normalize_whitespace(str(value or ""))
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)] + "..."


def _format_json_failure_summary(message: str, details: dict[str, Any] | None) -> str:
    summary = message
    if not isinstance(details, dict):
        return summary

    raw_text = str(details.get("raw_text") or "").strip()
    if raw_text:
        summary += f"\n\nInvalid JSON:\n{raw_text}"

    repaired_text = str(details.get("repaired_text") or "").strip()
    if repaired_text:
        summary += f"\n\nRepair attempt:\n{repaired_text}"

    return summary[:4000]


def _serialize_goals(goals) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for goal in goals:
        rows.append(
            {
                "id": goal.id,
                "title": goal.title,
                "description": goal.description,
                "period_type": goal.period_type,
                "target_type": goal.target_type,
                "target_value": float(goal.target_value or 0),
                "current_value": float(goal.current_value or 0),
                "start_date": goal.start_date.isoformat() if goal.start_date else "",
                "due_date": goal.due_date.isoformat() if goal.due_date else "",
                "priority": goal.priority,
                "status": goal.status,
                "course_id": goal.course_id,
                "course_title": goal.course.title if goal.course_id and goal.course else "",
            }
        )
    return rows



def _serialize_preferences(preference: NotificationPreference) -> dict[str, Any]:
    return {
        "timezone": preference.timezone,
        "week_start_day": int(preference.week_start_day),
        "daily_enabled": bool(preference.daily_enabled),
        "weekly_enabled": bool(preference.weekly_enabled),
        "daily_achievement_enabled": bool(preference.daily_achievement_enabled),
        "weekly_achievement_enabled": bool(preference.weekly_achievement_enabled),
        "in_app_enabled": bool(preference.in_app_enabled),
        "telegram_enabled": bool(getattr(preference, "telegram_enabled", False)),
        "telegram_daily_summary_enabled": bool(
            getattr(preference, "telegram_daily_summary_enabled", False)
        ),
        "telegram_weekly_review_enabled": bool(
            getattr(preference, "telegram_weekly_review_enabled", True)
        ),
        "telegram_critical_alerts_enabled": bool(
            getattr(preference, "telegram_critical_alerts_enabled", True)
        ),
        "daily_time": preference.daily_time.isoformat() if preference.daily_time else "",
        "weekly_time": preference.weekly_time.isoformat() if preference.weekly_time else "",
    }


def _serialize_courses(user) -> list[dict[str, Any]]:
    courses = (
        user.courses_joined.select_related("subject")
        .prefetch_related("modules")
        .order_by("title")
    )

    progress_by_course_id = {
        row.course_id: row
        for row in CourseProgress.objects.filter(user=user, course__in=courses)
    }

    module_progress = (
        ModuleProgress.objects.filter(user=user, course__in=courses)
        .select_related("module")
        .order_by("module__order")
    )
    progress_by_course_module: dict[int, list[ModuleProgress]] = {}
    for row in module_progress:
        progress_by_course_module.setdefault(row.course_id, []).append(row)

    serialized: list[dict[str, Any]] = []
    for course in courses:
        course_progress = progress_by_course_id.get(course.id)
        module_rows = progress_by_course_module.get(course.id, [])

        completed_count = sum(1 for row in module_rows if row.completed)
        modules = list(course.modules.all())
        total_modules = len(modules)

        next_module = None
        completed_module_ids = {row.module_id for row in module_rows if row.completed}
        for module in modules:
            if module.id not in completed_module_ids:
                next_module = module
                break

        serialized.append(
            {
                "course_id": course.id,
                "title": course.title,
                "subject": course.subject.title if course.subject_id else "",
                "progress_percent": float(getattr(course_progress, "progress_percent", 0) or 0),
                "completed": bool(getattr(course_progress, "completed", False)),
                "total_modules": total_modules,
                "completed_modules": completed_count,
                "next_module": {
                    "module_id": next_module.id,
                    "order": next_module.order,
                    "title": next_module.title,
                }
                if next_module
                else None,
            }
        )
    return serialized


def _serialize_notes(user, limit: int = 5) -> list[dict[str, Any]]:
    # Tags are optional; we match on slug prefixes that align with constants.py.
    qs = (
        Note.objects.filter(user=user, tags__slug__in=["daily-reflection", "weekly-review"])
        .distinct()
        .order_by("-updated_at")[:limit]
    )

    rows: list[dict[str, Any]] = []
    for note in qs:
        rows.append(
            {
                "id": note.id,
                "title": note.title,
                "updated_at": note.updated_at.isoformat() if note.updated_at else "",
                "content": _strip_html(note.content_html),
            }
        )
    return rows


def build_ai_input_payload(
    *,
    user,
    preference: NotificationPreference,
    week_start: date | None = None,
    month_anchor: date | None = None,
) -> dict[str, Any]:
    week_ctx = build_weekly_summary(user, preference=preference, week_start=week_start)
    month_ctx = build_monthly_summary(user, preference=preference, month_anchor=month_anchor)

    goals = Goal.objects.filter(user=user).select_related("course").order_by("-due_date", "-created")[:50]
    goal_rows = _serialize_goals(goals)

    weekly_top = week_ctx.get("top_courses") or []
    weekly_breakdown = week_ctx.get("course_breakdown") or []
    active_course_ids = {
        int(row.get("course_id"))
        for row in weekly_breakdown
        if row.get("course_id") and int(row.get("total_seconds") or 0) > 0
    }

    courses = _serialize_courses(user)
    neglected = [row for row in courses if row.get("course_id") not in active_course_ids]

    return {
        "goals": goal_rows,
        "weekly_analytics": json.loads(json.dumps(week_ctx, default=_json_default)),
        "monthly_analytics": json.loads(json.dumps(month_ctx, default=_json_default)),
        "courses": courses,
        "neglected_courses": neglected[:5],
        "top_courses": weekly_top[:5],
        "preferences": _serialize_preferences(preference),
        "notes": _serialize_notes(user),
    }


def _compact_prompt_plan_rows(rows: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []

    compacted: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        compacted.append(row)
        if len(compacted) >= limit:
            break
    return compacted


def _compact_prompt_plan_analytics(analytics: Any) -> dict[str, Any]:
    if not isinstance(analytics, dict):
        return {}

    compacted: dict[str, Any] = {}
    for key in (
        "weekly_status",
        "daily_status",
        "status",
        "month_value",
        "previous_label",
        "selected_week",
        "selected_day",
        "selected_month",
        "has_data",
    ):
        value = analytics.get(key)
        if value not in (None, ""):
            compacted[key] = value

    for key in (
        "totals",
        "goal_summary",
        "comparison",
        "productive_day",
        "achievement_percent",
        "consistency_percent",
        "planned_vs_actual_percent",
    ):
        value = analytics.get(key)
        if value not in (None, {}, []):
            compacted[key] = value

    if isinstance(analytics.get("top_courses"), list):
        compacted["top_courses"] = _compact_prompt_plan_rows(analytics["top_courses"], 4)
    if isinstance(analytics.get("course_breakdown"), list):
        compacted["course_breakdown"] = _compact_prompt_plan_rows(
            analytics["course_breakdown"],
            5,
        )
    if isinstance(analytics.get("improvements"), list):
        compacted["improvements"] = _compact_prompt_plan_rows(analytics["improvements"], 4)
    if isinstance(analytics.get("daily_breakdown"), list):
        compacted["daily_breakdown"] = _compact_prompt_plan_rows(
            analytics["daily_breakdown"],
            7,
        )

    return compacted


def _compact_prompt_plan_matches(matches: Any) -> dict[str, Any]:
    if not isinstance(matches, dict):
        return {}

    return {
        "enrolled_courses": _compact_prompt_plan_rows(matches.get("enrolled_courses"), 4),
        "enrolled_content": _compact_prompt_plan_rows(matches.get("enrolled_content"), 6),
        "catalog_courses": _compact_prompt_plan_rows(matches.get("catalog_courses"), 4),
    }


def _compact_prompt_plan_payload(input_payload: dict[str, Any]) -> dict[str, Any]:
    compacted = dict(input_payload)

    for key, limit in (
        ("goals", 12),
        ("courses", 10),
        ("neglected_courses", 3),
        ("top_courses", 5),
        ("notes", 3),
    ):
        compacted[key] = _compact_prompt_plan_rows(compacted.get(key), limit)

    compacted["weekly_analytics"] = _compact_prompt_plan_analytics(compacted.get("weekly_analytics"))
    compacted["monthly_analytics"] = _compact_prompt_plan_analytics(compacted.get("monthly_analytics"))
    compacted["matches"] = _compact_prompt_plan_matches(compacted.get("matches"))

    return compacted


def _build_ai_run_prompt(input_payload: dict[str, Any]) -> str:
    return (
        "Input context JSON:\n"
        + json.dumps(
            input_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        )
    )


PROMPT_PLAN_SYSTEM_PROMPT = """
You are an AI learning coach and planner.

Your job is to turn the user's prompt into a realistic study plan using ONLY the
resources available on this site.

You will receive "Input context JSON" that includes:
- today (YYYY-MM-DD) in the user's timezone
- user_prompt (free-form user text)
- clarification (optional): previous_questions + previous_answers
- allowed_course_ids: course ids the user is enrolled in (allowed for plan items)
- matches: search results from enrolled content + catalog recommendations
- courses: enrolled courses with progress and next module
- goals, analytics, notes, and preferences

Hard rules:
- Return ONLY valid JSON (no markdown, no commentary).
- If required details are missing/ambiguous, return type="clarification" with 1-5 questions.
- Prefer asking the minimum questions needed to produce a high-quality plan.
- Default plan start is today unless the user explicitly says otherwise.
- If the user provides a clear deadline (tomorrow / in N days / on a date), plan from today through the deadline.
- If the deadline is ambiguous (e.g. "in 2 or 3 days"), ask for the exact target date.
- Plan items MUST use course_id from allowed_course_ids. If no enrolled course matches, set course_id=0 and course_title="".
- Recommendations MUST come from matches.catalog_courses only.

Return JSON in one of these shapes:
Do NOT include any explanation before or after the JSON.
Do NOT wrap in markdown.

CLARIFICATION:
{
  "type": "clarification",
  "reasoning_summary": "",
  "questions": [
    {
      "id": "snake_case_id",
      "label": "",
      "type": "text",
      "required": true,
      "placeholder": ""
    }
  ]
}

PLAN:
{
  "type": "plan",
  "reasoning_summary": "",
  "inputs_used": {
    "goals": "",
    "analytics": "",
    "roadmap": "",
    "constraints": ""
  },
  "period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
  "focus_courses": [
    {"course_id": 0, "course_title": "", "why": ""}
  ],
  "plan": [
    {
      "date": "YYYY-MM-DD",
      "is_buffer_day": false,
      "items": [
        {
          "course_id": 0,
          "course_title": "",
          "minutes": 30,
          "task": "",
          "notes": ""
        }
      ]
    }
  ],
  "recommendations": [
    {"course_id": 0, "course_title": "", "slug": "", "why": ""}
  ],
  "risk_level": "low"
}

Where risk_level is one of: "low", "medium", "high".
""".strip()

REVIEW_SYSTEM_PROMPT = """
You are an AI learning coach. Produce a performance review summary and actionable next steps.

Requirements:
- Include performance gap analysis (planned vs actual) when possible.
- Detect behavior patterns (timing trends, procrastination signals, consistency changes).
- Provide course-level insights (ignored vs improving courses).
- Suggestions must be actionable (behavioral + study strategy), not just descriptive.

Return ONLY valid JSON (no markdown, no commentary).

Required JSON shape:
{
  "summary": "",
  "achievements": [],
  "missed_targets": [],
  "insights": [],
  "suggestions": [],
  "risk_level": "low"
}

Where risk_level is one of: "low", "medium", "high".
""".strip()


IMPROVEMENT_SYSTEM_PROMPT = """
You are an AI learning coach. Generate improvement suggestions focused on behavior and study strategy.

Requirements:
- Focus on 3-7 concrete changes the user can implement this week.
- Tie each suggestion to evidence from goals + analytics + course roadmap.
- Suggest small experiments (timeboxing, focus blocks, review cadence, distraction control).

Return ONLY valid JSON (no markdown, no commentary).
Do NOT include any explanation before or after the JSON.

Required JSON shape:
{
  "summary": "",
  "achievements": [],
  "missed_targets": [],
  "insights": [],
  "suggestions": [],
  "risk_level": "low"
}
""".strip()


RECOVERY_SYSTEM_PROMPT = """
You are an AI learning coach. Generate recovery suggestions for a stalled or missed plan.

Requirements:
- Identify the biggest bottlenecks (time, consistency, overload, unclear next steps).
- Propose a recovery plan for the next 3-5 days with realistic workloads.
- Include a buffer day if risk is medium/high.
- Provide actionable steps (not vague motivation).

Return ONLY valid JSON (no markdown, no commentary).
Do NOT include any explanation before or after the JSON.

Required JSON shape:
{
  "summary": "",
  "achievements": [],
  "missed_targets": [],
  "insights": [],
  "suggestions": [],
  "risk_level": "high"
}
""".strip()


SYSTEM_PROMPT_EXTRACT_SEARCH_KEYWORDS = """
You are a keyword extraction engine for an educational platform.

Task:
- Given a user learning request and enrolled course titles, return concise search terms
  that improve retrieval for courses/modules/content.

Hard rules:
1) Return ONLY valid JSON. No markdown or extra commentary.
2) Use exactly this JSON shape:
{
  "keywords": ["...", "..."],
  "course_hints": ["..."],
  "normalized_intent": "..."
}
3) "keywords" MUST contain at least 3 items.
   If uncertain, infer from common curriculum structure.
   NEVER return an empty array.
4) Infer canonical technical terms from colloquial user language.
5) "course_hints" may include enrolled course title fragments only; do not invent new course names.
6) Keep "normalized_intent" short, clear, and faithful to the user request.
7)Do NOT include any explanation before or after the JSON.
8)Do NOT wrap in markdown.
Before returning the final JSON:
- Verify all required keys exist
- Verify "keywords" length is between 3 and 8
- If validation fails, regenerate internally until valid
""".strip()


def _extract_search_keywords(*, user, user_prompt: str) -> dict[str, Any]:
    """
    Extract normalized intent + search terms from a free-form prompt.

    Returns a safe dict containing:
    - keywords: list[str]
    - course_hints: list[str]
    - normalized_intent: str
    - query_text: str   # merged final search query
    """
    prompt_value = _normalize_whitespace(user_prompt or "")
    if not prompt_value:
        return {
            "keywords": [],
            "course_hints": [],
            "normalized_intent": "",
            "query_text": "",
        }

    enrolled_titles = list(
        Course.objects.filter(students=user).order_by("title").values_list("title", flat=True)
    )

    llm_input = {
        "user_prompt": prompt_value,
        "enrolled_course_titles": enrolled_titles[:80],
        "instructions": "Return JSON only using the required schema.",
    }

    fallback = {
        "keywords": [],
        "course_hints": [],
        "normalized_intent": prompt_value,
    }

    try:
        raw = generate_ai_response_simple(
            {
                "prompt": json.dumps(llm_input, ensure_ascii=False, separators=(",", ":")),
                "maxOutputTokens": 256,
            },
            SYSTEM_PROMPT_EXTRACT_SEARCH_KEYWORDS,
            temperature=TEMPERATURE_PRECISE,
        )
        parsed = _extract_json(raw) if raw else {}
    except Exception:
        parsed = fallback

    keywords_raw = parsed.get("keywords") if isinstance(parsed, dict) else []
    hints_raw = parsed.get("course_hints") if isinstance(parsed, dict) else []
    normalized_intent = (
        str(parsed.get("normalized_intent") or "").strip()
        if isinstance(parsed, dict)
        else ""
    )
    if not normalized_intent:
        normalized_intent = prompt_value

    def _clean_terms(values: Any, limit: int) -> list[str]:
        if not isinstance(values, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for value in values:
            term = _truncate_text(str(value or ""), 80).strip(" ,.;")
            if not term:
                continue
            key = term.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(term)
            if len(cleaned) >= limit:
                break
        return cleaned

    keywords = _clean_terms(keywords_raw, 8)
    course_hints = _clean_terms(hints_raw, 6)

    enrolled_lower = [title.lower() for title in enrolled_titles]
    filtered_hints: list[str] = []
    for hint in course_hints:
        hint_lower = hint.lower()
        if any(
            hint_lower in enrolled_title or enrolled_title in hint_lower
            for enrolled_title in enrolled_lower
        ):
            filtered_hints.append(hint)

    query_parts = [prompt_value, normalized_intent]
    if keywords:
        query_parts.append(", ".join(keywords))
    if filtered_hints:
        query_parts.append(", ".join(filtered_hints))
    query_text = _truncate_text(" | ".join(part for part in query_parts if part), 700)

    return {
        "keywords": keywords,
        "course_hints": filtered_hints,
        "normalized_intent": normalized_intent,
        "query_text": query_text,
    }


def _build_prompt_plan_matches(*, user, query_text: str) -> dict[str, Any]:
    query_text = _truncate_text(query_text, 700)
    matches: dict[str, Any] = {
        "enrolled_courses": [],
        "enrolled_content": [],
        "catalog_courses": [],
    }
    if not query_text:
        return matches

    try:
        enrolled_course_qs = Course.objects.select_related("subject").filter(students=user)
        enrolled = list(search_courses(enrolled_course_qs, query_text)[:6])
        for course in enrolled:
            matches["enrolled_courses"].append(
                {
                    "course_id": course.id,
                    "course_title": course.title,
                    "subject": getattr(getattr(course, "subject", None), "title", "") or "",
                    "slug": getattr(course, "slug", "") or "",
                    "overview": _truncate_text(getattr(course, "overview", "") or "", 240),
                    "score": float(getattr(course, "combined_score", 0.0) or 0.0),
                }
            )
    except Exception:
        pass

    try:
        content_qs = ContentSearchEntry.objects.select_related("course", "module", "content").filter(
            course__students=user
        )
        entries = list(search_content_entries(content_qs, query_text)[:10])
        for entry in entries:
            matches["enrolled_content"].append(
                {
                    "course_id": entry.course_id,
                    "course_title": getattr(getattr(entry, "course", None), "title", "") or "",
                    "module_id": entry.module_id,
                    "module_title": getattr(getattr(entry, "module", None), "title", "") or "",
                    "content_id": entry.content_id,
                    "kind": getattr(entry, "kind", "") or "",
                    "item_title": getattr(entry, "item_title", "") or "",
                    "page_number": int(getattr(entry, "page_number", 0) or 0) or None,
                    "snippet": _truncate_text(str(getattr(entry, "snippet", "") or ""), 340),
                    "score": float(getattr(entry, "combined_score", 0.0) or 0.0),
                }
            )
    except Exception:
        pass

    try:
        catalog_qs = Course.objects.select_related("subject").exclude(students=user)
        catalog = list(search_courses(catalog_qs, query_text)[:6])
        for course in catalog:
            matches["catalog_courses"].append(
                {
                    "course_id": course.id,
                    "course_title": course.title,
                    "subject": getattr(getattr(course, "subject", None), "title", "") or "",
                    "slug": getattr(course, "slug", "") or "",
                    "overview": _truncate_text(getattr(course, "overview", "") or "", 240),
                    "score": float(getattr(course, "combined_score", 0.0) or 0.0),
                }
            )
    except Exception:
        pass

    return matches


def _safe_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_prompt_plan_output(
    *,
    output: dict[str, Any],
    today: date,
    allowed_course_ids: set[int],
    enrolled_titles: dict[int, str],
    recommended_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {}

    kind = str(output.get("type") or "").strip().lower()
    if not kind:
        if isinstance(output.get("questions"), list):
            kind = "clarification"
        elif isinstance(output.get("plan"), list) or isinstance(output.get("items"), list):
            kind = "plan"

    if kind == "clarification":
        questions = output.get("questions")
        if not isinstance(questions, list):
            questions = []
        cleaned_questions: list[dict[str, Any]] = []
        for idx, raw in enumerate(questions[:5], start=1):
            if not isinstance(raw, dict):
                continue
            qid = str(raw.get("id") or "").strip()
            if not re.match(r"^[a-z][a-z0-9_]{0,50}$", qid):
                qid = f"question_{idx}"
            label = str(raw.get("label") or raw.get("question") or "").strip()
            if not label:
                continue
            qtype = str(raw.get("type") or "text").strip().lower()
            if qtype not in {"text", "date", "number"}:
                qtype = "text"
            placeholder = str(raw.get("placeholder") or "").strip()
            cleaned_questions.append(
                {
                    "id": qid,
                    "label": label[:240],
                    "type": qtype,
                    "required": bool(raw.get("required", True)),
                    "placeholder": placeholder[:140],
                }
            )
        return {
            "type": "clarification",
            "reasoning_summary": str(output.get("reasoning_summary") or "").strip()[:2000],
            "questions": cleaned_questions,
        }

    # Normalize into a multi-day plan shape (even for 1 day).
    plan_days = output.get("plan")
    if not isinstance(plan_days, list):
        items = output.get("items")
        if isinstance(items, list):
            single_date = str(output.get("date") or output.get("day") or "").strip()
            plan_days = [{"date": single_date or today.isoformat(), "is_buffer_day": False, "items": items}]
        else:
            plan_days = []

    normalized_days: list[dict[str, Any]] = []
    for day in plan_days[:31]:
        if not isinstance(day, dict):
            continue
        day_value = str(day.get("date") or "").strip()
        parsed_day = _safe_date(day_value) or today
        items = day.get("items")
        if not isinstance(items, list):
            items = []
        normalized_items: list[dict[str, Any]] = []
        for item in items[:10]:
            if not isinstance(item, dict):
                continue
            course_id = item.get("course_id")
            try:
                course_id_value = int(course_id or 0)
            except (TypeError, ValueError):
                course_id_value = 0
            if course_id_value not in allowed_course_ids:
                course_id_value = 0

            minutes = item.get("minutes")
            try:
                minutes_value = max(0, int(minutes or 0))
            except (TypeError, ValueError):
                minutes_value = 0

            task = str(item.get("task") or "").strip()
            if not task:
                continue

            course_title = str(item.get("course_title") or "").strip()
            if not course_title and course_id_value in enrolled_titles:
                course_title = enrolled_titles[course_id_value]

            normalized_items.append(
                {
                    "course_id": course_id_value,
                    "course_title": course_title[:200] if course_title else "",
                    "minutes": minutes_value,
                    "task": task[:240],
                    "notes": str(item.get("notes") or "").strip()[:600],
                }
            )
        normalized_days.append(
            {
                "date": parsed_day.isoformat(),
                "is_buffer_day": bool(day.get("is_buffer_day", False)),
                "items": normalized_items,
            }
        )

    # Period: prefer provided period, else derive from plan days.
    start_date = None
    end_date = None
    period = output.get("period") if isinstance(output.get("period"), dict) else {}
    start_date = _safe_date(period.get("start")) or None
    end_date = _safe_date(period.get("end")) or None
    if normalized_days and (start_date is None or end_date is None):
        dates = [_safe_date(row.get("date")) for row in normalized_days]
        dates = [d for d in dates if d is not None]
        if dates:
            start_date = start_date or min(dates)
            end_date = end_date or max(dates)
    start_date = start_date or today
    end_date = end_date or start_date

    focus = output.get("focus_courses")
    if not isinstance(focus, list):
        focus = output.get("weekly_focus") if isinstance(output.get("weekly_focus"), list) else []
    normalized_focus: list[dict[str, Any]] = []
    for row in focus[:6]:
        if not isinstance(row, dict):
            continue
        cid = row.get("course_id")
        try:
            cid_value = int(cid or 0)
        except (TypeError, ValueError):
            cid_value = 0
        if cid_value not in allowed_course_ids:
            cid_value = 0
        title = str(row.get("course_title") or "").strip()
        if not title and cid_value in enrolled_titles:
            title = enrolled_titles[cid_value]
        why = str(row.get("why") or "").strip()
        if not title and not why:
            continue
        normalized_focus.append(
            {
                "course_id": cid_value,
                "course_title": title[:200] if title else "",
                "why": why[:300],
            }
        )

    recommendations = output.get("recommendations")
    if not isinstance(recommendations, list):
        recommendations = []
    normalized_recs: list[dict[str, Any]] = []
    for row in recommendations[:6]:
        if not isinstance(row, dict):
            continue
        cid = row.get("course_id")
        try:
            cid_value = int(cid or 0)
        except (TypeError, ValueError):
            cid_value = 0
        canonical = recommended_by_id.get(cid_value)
        if not canonical:
            continue
        normalized_recs.append(
            {
                "course_id": cid_value,
                "course_title": canonical.get("course_title") or "",
                "slug": canonical.get("slug") or "",
                "why": str(row.get("why") or "").strip()[:320],
            }
        )

    risk_level = str(output.get("risk_level") or "").strip().lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = "low"

    inputs_used = output.get("inputs_used") if isinstance(output.get("inputs_used"), dict) else {}
    return {
        "type": "plan",
        "reasoning_summary": str(output.get("reasoning_summary") or "").strip()[:2000],
        "inputs_used": {
            "goals": str(inputs_used.get("goals") or "").strip()[:500],
            "analytics": str(inputs_used.get("analytics") or "").strip()[:500],
            "roadmap": str(inputs_used.get("roadmap") or "").strip()[:500],
            "constraints": str(inputs_used.get("constraints") or "").strip()[:500],
        },
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "focus_courses": normalized_focus,
        "plan": normalized_days,
        "recommendations": normalized_recs,
        "risk_level": risk_level,
    }


def _create_ai_run(
    *,
    user,
    kind: str,
    period_type: str,
    period_start: date | None,
    period_end: date | None,
    input_payload: dict[str, Any],
    system_prompt: str,
) -> AIPlanRun:
    run = AIPlanRun.objects.create(
        user=user,
        kind=kind,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        input_payload=input_payload,
        status=AIPlanRun.STATUS_PENDING,
    )

    prompt = _build_ai_run_prompt(input_payload)

    try:
        raw_text = generate_ai_response_simple(
            {"prompt": prompt, "maxOutputTokens": DEFAULT_MAX_OUTPUT_TOKENS},
            system_prompt,
            temperature=TEMPERATURE_BALANCED,
        )
        output_payload = _extract_json_with_repair(raw_text=raw_text, system_prompt=system_prompt)
    except GeminiError as exc:
        run.status = AIPlanRun.STATUS_FAILED
        run.error_message = exc.message
        run.summary_text = _format_json_failure_summary(exc.message, exc.details)
        run.save(update_fields=["status", "error_message", "summary_text", "updated_at"])
        return run
    except Exception as exc:
        run.status = AIPlanRun.STATUS_FAILED
        run.error_message = str(exc)
        run.summary_text = "AI output could not be parsed."
        run.save(update_fields=["status", "error_message", "summary_text", "updated_at"])
        return run

    summary_text = ""
    if isinstance(output_payload, dict):
        summary_text = str(
            output_payload.get("reasoning_summary")
            or output_payload.get("summary")
            or ""
        ).strip()

    run.status = AIPlanRun.STATUS_SUCCESS
    run.output_payload = output_payload
    run.summary_text = summary_text[:2000]
    run.error_message = ""
    run.save(update_fields=["status", "output_payload", "summary_text", "error_message", "updated_at"])
    return run


def generate_prompt_plan_run(
    *,
    user,
    preference: NotificationPreference,
    user_prompt: str,
    previous_questions: list[dict[str, Any]] | None = None,
    previous_answers: dict[str, Any] | None = None,
) -> AIPlanRun:
    prompt_value = (user_prompt or "").strip()
    today = get_local_date(preference=preference)
    recent_start = today - timedelta(days=6)

    base_payload = build_ai_input_payload(
        user=user,
        preference=preference,
        week_start=recent_start,
        month_anchor=today,
    )

    clarification = {
        "previous_questions": previous_questions or [],
        "previous_answers": previous_answers or {},
    }
    extracted_search = _extract_search_keywords(user=user, user_prompt=prompt_value)
    query_text = str(extracted_search.get("query_text") or prompt_value).strip()
    if previous_answers:
        answers_blob = json.dumps(previous_answers, ensure_ascii=False)
        query_text = _truncate_text(f"{query_text}\n\nAnswers:\n{answers_blob}", 700)

    matches = _build_prompt_plan_matches(user=user, query_text=query_text)
    allowed_course_ids = list(user.courses_joined.values_list("id", flat=True))

    input_payload = dict(base_payload)
    input_payload.update(
        {
            "today": today.isoformat(),
            "user_prompt": prompt_value,
            "clarification": clarification,
            "search_intent": {
                "keywords": extracted_search.get("keywords") or [],
                "course_hints": extracted_search.get("course_hints") or [],
                "normalized_intent": extracted_search.get("normalized_intent") or "",
                "query_text": query_text,
            },
            "allowed_course_ids": allowed_course_ids,
            "matches": matches,
        }
    )
    input_payload = _compact_prompt_plan_payload(input_payload)

    run = _create_ai_run(
        user=user,
        kind=AIPlanRun.KIND_PROMPT_PLAN,
        period_type=Goal.PERIOD_DAILY,
        period_start=today,
        period_end=today,
        input_payload=input_payload,
        system_prompt=PROMPT_PLAN_SYSTEM_PROMPT,
    )

    if run.status != AIPlanRun.STATUS_SUCCESS or not isinstance(run.output_payload, dict):
        return run

    enrolled_titles = {
        int(course_id): str(title)
        for course_id, title in user.courses_joined.values_list("id", "title")
    }
    recommended_by_id = {
        int(row.get("course_id")): row
        for row in (matches.get("catalog_courses") or [])
        if isinstance(row, dict) and row.get("course_id")
    }

    normalized = _normalize_prompt_plan_output(
        output=run.output_payload,
        today=today,
        allowed_course_ids=set(int(x) for x in allowed_course_ids),
        enrolled_titles=enrolled_titles,
        recommended_by_id=recommended_by_id,
    )
    if normalized:
        run.output_payload = normalized
        run.summary_text = str(normalized.get("reasoning_summary") or "").strip()[:2000]
        if isinstance(normalized.get("period"), dict):
            start_date = _safe_date(normalized["period"].get("start"))
            end_date = _safe_date(normalized["period"].get("end"))
            if start_date:
                run.period_start = start_date
            if end_date:
                run.period_end = end_date
        run.save(update_fields=["output_payload", "summary_text", "period_start", "period_end", "updated_at"])

    return run

def generate_weekly_review_run(
    *,
    user,
    preference: NotificationPreference,
    reference_date: date | None = None,
) -> AIPlanRun:
    today = get_local_date(preference=preference)
    anchor = reference_date or today
    week_start = get_period_start(
        anchor,
        Goal.PERIOD_WEEKLY,
        week_start_day=preference.week_start_day,
    )
    payload = build_ai_input_payload(
        user=user,
        preference=preference,
        week_start=week_start,
        month_anchor=anchor,
    )
    payload["review_period"] = "weekly"

    return _create_ai_run(
        user=user,
        kind=AIPlanRun.KIND_WEEKLY_REVIEW,
        period_type=Goal.PERIOD_WEEKLY,
        period_start=week_start,
        period_end=week_start + timedelta(days=6),
        input_payload=payload,
        system_prompt=REVIEW_SYSTEM_PROMPT,
    )


def generate_daily_review_run(
    *,
    user,
    preference: NotificationPreference,
    reference_date: date | None = None,
) -> AIPlanRun:
    anchor = reference_date or get_local_date(preference=preference)
    weekly_analytics_start = anchor - timedelta(days=6)
    payload = build_ai_input_payload(
        user=user,
        preference=preference,
        week_start=weekly_analytics_start,
        month_anchor=anchor,
    )
    payload["review_period"] = "daily"
    payload["day"] = anchor.isoformat()

    return _create_ai_run(
        user=user,
        kind=AIPlanRun.KIND_DAILY_REVIEW,
        period_type=Goal.PERIOD_DAILY,
        period_start=anchor,
        period_end=anchor,
        input_payload=payload,
        system_prompt=REVIEW_SYSTEM_PROMPT,
    )


def generate_improvement_run(
    *,
    user,
    preference: NotificationPreference,
    reference_date: date | None = None,
) -> AIPlanRun:
    today = get_local_date(preference=preference)
    anchor = reference_date or today
    week_start = get_period_start(
        anchor,
        Goal.PERIOD_WEEKLY,
        week_start_day=preference.week_start_day,
    )
    payload = build_ai_input_payload(
        user=user,
        preference=preference,
        week_start=week_start,
        month_anchor=anchor,
    )
    payload["intent"] = "improvement_suggestions"

    return _create_ai_run(
        user=user,
        kind=AIPlanRun.KIND_IMPROVEMENT,
        period_type=Goal.PERIOD_WEEKLY,
        period_start=week_start,
        period_end=week_start + timedelta(days=6),
        input_payload=payload,
        system_prompt=IMPROVEMENT_SYSTEM_PROMPT,
    )


def generate_recovery_run(
    *,
    user,
    preference: NotificationPreference,
    reference_date: date | None = None,
) -> AIPlanRun:
    today = get_local_date(preference=preference)
    anchor = reference_date or today
    week_start = get_period_start(
        anchor,
        Goal.PERIOD_WEEKLY,
        week_start_day=preference.week_start_day,
    )
    payload = build_ai_input_payload(
        user=user,
        preference=preference,
        week_start=week_start,
        month_anchor=anchor,
    )
    payload["intent"] = "recovery_suggestions"

    return _create_ai_run(
        user=user,
        kind=AIPlanRun.KIND_RECOVERY,
        period_type=Goal.PERIOD_WEEKLY,
        period_start=week_start,
        period_end=week_start + timedelta(days=6),
        input_payload=payload,
        system_prompt=RECOVERY_SYSTEM_PROMPT,
    )


def apply_prompt_plan_run(*, run: AIPlanRun) -> int:
    """
    Create daily Goal rows from a prompt-based plan run.

    Returns: number of goals created.
    """

    if run.kind != AIPlanRun.KIND_PROMPT_PLAN:
        return 0
    if run.status != AIPlanRun.STATUS_SUCCESS:
        return 0

    payload = run.effective_payload
    if not isinstance(payload, dict):
        return 0
    if payload.get("type") not in (None, "", "plan") and "plan" not in payload:
        return 0

    plan_days = payload.get("plan")
    if not isinstance(plan_days, list):
        return 0

    created_count = 0

    with transaction.atomic():
        for day in plan_days:
            if not isinstance(day, dict):
                continue
            day_value = (day.get("date") or "").strip()
            try:
                day_date = datetime.strptime(day_value, "%Y-%m-%d").date()
            except ValueError:
                continue

            items = day.get("items")
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                course_id = item.get("course_id")
                course = None
                try:
                    course_id_value = int(course_id or 0)
                except (TypeError, ValueError):
                    course_id_value = 0
                if course_id_value > 0:
                    course = Course.objects.filter(pk=course_id_value).first()

                minutes = item.get("minutes")
                try:
                    minutes_value = max(0, int(minutes or 0))
                except (TypeError, ValueError):
                    minutes_value = 0

                task = (item.get("task") or "").strip()
                if not task:
                    continue

                title = f"[AI Plan] {task}"[:200]
                exists = Goal.objects.filter(
                    user=run.user,
                    title=title,
                    start_date=day_date,
                    due_date=day_date,
                    period_type=Goal.PERIOD_DAILY,
                ).exists()
                if exists:
                    continue

                target_type = Goal.TARGET_MINUTES if minutes_value > 0 else Goal.TARGET_TASKS
                target_value = Decimal(str(minutes_value)) if minutes_value > 0 else Decimal("1")

                Goal.objects.create(
                    user=run.user,
                    course=course,
                    title=title,
                    description=(item.get("notes") or "").strip(),
                    period_type=Goal.PERIOD_DAILY,
                    target_type=target_type,
                    target_value=target_value,
                    current_value=Decimal("0"),
                    start_date=day_date,
                    due_date=day_date,
                    priority=Goal.PRIORITY_MEDIUM,
                    status=Goal.STATUS_NOT_STARTED,
                )
                created_count += 1

        run.approved_at = run.approved_at or timezone.now()
        run.applied_at = timezone.now()
        run.save(update_fields=["approved_at", "applied_at", "updated_at"])

    return created_count
