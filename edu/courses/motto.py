import json
import re
import random
from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

MOTTO_CACHE_PREFIX = "daily_motto"
FAILURE_TTL_SECONDS = 60 * 15
DAILY_QUOTE_MODEL = "gemini-2.5-flash"
DAILY_QUOTE_TEMPERATURE = 0.35
DAILY_QUOTE_TIMEOUT_SECONDS = 60
SOURCE_FETCH_TIMEOUT_SECONDS = 20
SOURCE_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SOURCE_SITES = [
    {
        "name": "ThoughtWorks Radar",
        "url": "https://www.thoughtworks.com/radar",
        "include": ("/radar/", "/insights/blog/"),
        "exclude": ("/radar/archive", "/radar/faq", "/content/dam/"),
    },
    {
        "name": "DZone Refcards",
        "url": "https://dzone.com/refcardz",
        "include": ("/refcardz/",),
        "exclude": (
            "/refcardz#",
            "/users/",
            "/pages/",
            "/download",
            "/login",
            "/registration",
        ),
    },
    {
        "name": "InfoQ",
        "url": "https://www.infoq.com/",
        "include": ("/articles/", "/news/", "/podcasts/", "/minibooks/"),
        "exclude": (
            "/vendorcontent/",
            "/profile/",
            "/events/",
            "/reginit.action",
            "/social/",
            "/write-for-infoq",
        ),
    },
]

GENERIC_LINK_TEXTS = {
    "download",
    "learn more",
    "read more",
    "save",
    "more news",
    "more articles",
    "more podcasts",
    "more guides",
    "more presentations",
    "more",
    "news",
    "articles",
    "podcasts",
    "guides",
    "presentations",
}


class _AnchorCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text_parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._text_parts = []

    def handle_data(self, data):
        if self._href is not None:
            self._text_parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or self._href is None:
            return
        text = " ".join("".join(self._text_parts).split())
        self.links.append({"href": self._href, "text": text})
        self._href = None
        self._text_parts = []


def _seconds_until_midnight():
    now = timezone.localtime()
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return max(60, int((tomorrow - now).total_seconds()))


def _extract_json(text):
    cleaned = (text or "").strip()
    if not cleaned:
        return {"text": ""}
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = cleaned[start : end + 1]
            try:
                parsed = json.loads(snippet)
            except json.JSONDecodeError:
                return {"text": cleaned}
        else:
            return {"text": cleaned}

    if isinstance(parsed, dict):
        return parsed
    if isinstance(parsed, str):
        return {"text": parsed}
    return {"text": cleaned}


def _extract_candidate_text(payload):
    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return ""
    first = candidates[0] if isinstance(candidates[0], dict) else {}
    content = first.get("content") if isinstance(first, dict) else {}
    parts = (content or {}).get("parts") if isinstance(content, dict) else []
    if not isinstance(parts, list) or not parts:
        return ""
    text_parts = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_text = part.get("text")
        if part_text:
            text_parts.append(str(part_text))
    return "".join(text_parts)


def _extract_error_message(response):
    try:
        error_payload = response.json()
    except ValueError:
        error_payload = {"message": response.text[:300]}

    api_error = error_payload.get("error", {}) if isinstance(error_payload, dict) else {}
    if isinstance(api_error, dict):
        return api_error.get("message") or error_payload.get("message")
    return error_payload.get("message") if isinstance(error_payload, dict) else None


def _normalized_text(value):
    return " ".join(str(value or "").split())


def _clip_text(value, limit):
    text = _normalized_text(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _clean_motto_text(value):
    text = _normalized_text(value)
    if not text:
        return ""

    for pattern in (
        r"\(ai generated text\)",
        r"Open the article for the full context\."
    ):
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    return _normalized_text(text)


def _collect_source_candidates(site):
    response = requests.get(
        site["url"],
        headers={"User-Agent": SOURCE_USER_AGENT},
        timeout=SOURCE_FETCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    collector = _AnchorCollector()
    collector.feed(response.text)

    base_host = urlparse(site["url"]).netloc.lower()
    seen = set()
    candidates = []

    for link in collector.links:
        href = _normalized_text(link.get("href"))
        title = _normalized_text(link.get("text"))
        if not href or not title:
            continue

        title_lower = title.lower()
        if title_lower in GENERIC_LINK_TEXTS or title_lower.startswith("more "):
            continue

        absolute_url = urljoin(site["url"], href).split("#", 1)[0].rstrip("/")
        parsed = urlparse(absolute_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if parsed.netloc and not parsed.netloc.lower().endswith(base_host):
            continue
        if any(fragment in absolute_url for fragment in site["exclude"]):
            continue
        if not any(fragment in absolute_url for fragment in site["include"]):
            continue
        if absolute_url in seen:
            continue

        seen.add(absolute_url)
        candidates.append(
            {
                "site_name": site["name"],
                "site_url": site["url"],
                "title": title,
                "url": absolute_url,
            }
        )

    return candidates


def _select_source_article(refresh=False):
    today = timezone.localdate()
    if not SOURCE_SITES:
        return {
            "site_name": "Knowledge",
            "site_url": "",
            "title": "general technology insight",
            "url": "",
        }

    if refresh:
        ordered_sites = SOURCE_SITES[:]
        random.SystemRandom().shuffle(ordered_sites)
    else:
        start_index = today.toordinal() % len(SOURCE_SITES)
        ordered_sites = SOURCE_SITES[start_index:] + SOURCE_SITES[:start_index]
    ordinal = today.toordinal()

    for site in ordered_sites:
        try:
            candidates = _collect_source_candidates(site)
        except Exception:
            continue
        if not candidates:
            continue
        if refresh:
            return random.SystemRandom().choice(candidates)
        return candidates[ordinal % len(candidates)]

    fallback_site = ordered_sites[0]
    return {
        "site_name": fallback_site["name"],
        "site_url": fallback_site["url"],
        "title": fallback_site["name"],
        "url": fallback_site["url"],
    }


def _normalize_motto(payload, source_context=None):
    if isinstance(payload, str):
        text = _clean_motto_text(payload)
        author = ""
        source = ""
        link = ""
    else:
        text = _clean_motto_text(payload.get("text", ""))
        author = str(payload.get("author", "")).strip()
        source = str(payload.get("source", "")).strip()
        link = str(payload.get("url") or payload.get("link") or "").strip()

    if source_context:
        source = source or str(source_context.get("site_name", "")).strip()
        link = link or str(source_context.get("url", "")).strip()

    author = author or "Knowledge"
    source = source or "General knowledge"
    if not text:
        text = "Daily insight unavailable."
        author = "Knowledge"
        source = "General knowledge"
    return {
        "text": text,
        "author": author,
        "source": source,
        "link": link,
    }


def _fallback_motto(source_context):
    site_name = _normalized_text(source_context.get("site_name") or "Knowledge") or "Knowledge"
    title = _clip_text(source_context.get("title") or site_name, 110)
    link = _normalized_text(source_context.get("url") or source_context.get("site_url") or "")

    return {
        "text": title,
        "author": "Knowledge",
        "source": site_name,
        "link": link,
    }


def _is_placeholder_motto(motto):
    if not isinstance(motto, dict):
        return False
    return (
        motto.get("text") == "Daily insight unavailable."
        and motto.get("author") == "Knowledge"
        and motto.get("source") == "General knowledge"
    )


def _build_prompt(source_context):
    title = _normalized_text(source_context.get("title") or "technology article")
    site_name = _normalized_text(source_context.get("site_name") or "technology source")
    source_url = _normalized_text(source_context.get("url") or source_context.get("site_url") or "")
    return (
        f"Teach one practical idea inspired by '{title}' from {site_name}. "
        f"Use the direct read-more URL exactly as {source_url}. "
        "Reply only with valid JSON: {\"text\":\"...\",\"author\":\"Knowledge\",\"source\":\"...\",\"url\":\"...\"}. "
        "Keep the text under 250 characters. Avoid jokes, markdown, bullets, and extra commentary. "
        "Do not add AI labels or article-link callouts; the UI renders the link and source separately."
    )


def _call_daily_quote_api(source_context=None):
    api_key = (getattr(settings, "DAILY_QUOTE_API_KEY", "") or "").strip()
    if not api_key:
        raise RuntimeError("DAILY_QUOTE_API_KEY is not configured.")

    source_context = source_context or _select_source_article()

    url = (
        "https://generativelanguage.googleapis.com/v1/models/"
        f"{DAILY_QUOTE_MODEL}:generateContent"
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": _build_prompt(source_context)}],
            }
        ],
        "generationConfig": {
            "temperature": DAILY_QUOTE_TEMPERATURE,
        },
    }

    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        json=payload,
        timeout=DAILY_QUOTE_TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        raise RuntimeError(
            _extract_error_message(response)
            or f"Daily quote API returned HTTP {response.status_code}."
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Daily quote API returned invalid JSON.") from exc

    response_text = _extract_candidate_text(data)
    if not response_text.strip():
        raise RuntimeError("Daily quote API returned an empty response.")

    return response_text, source_context


def get_daily_motto(force_refresh=False):
    today = timezone.localdate().isoformat()
    cache_key = f"{MOTTO_CACHE_PREFIX}:{today}"
    cached = cache.get(cache_key)
    if cached and not force_refresh and not _is_placeholder_motto(cached):
        return cached

    source_context = _select_source_article(refresh=force_refresh)

    try:
        response_text, source_context = _call_daily_quote_api(source_context)
        raw_payload = _extract_json(response_text)
        motto = _normalize_motto(raw_payload, source_context)
        cache.set(cache_key, motto, _seconds_until_midnight())
        return motto
    except Exception:
        if cached and not force_refresh:
            return cached
        fallback = _fallback_motto(source_context)
        cache.set(cache_key, fallback, FAILURE_TTL_SECONDS)
        return fallback
