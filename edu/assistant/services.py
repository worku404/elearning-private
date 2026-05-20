from __future__ import annotations

import random
from collections.abc import Iterator
from typing import Any

import requests
from django.conf import settings
import time

MAX_RETRIES = 3
DELAY = 2
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_TEMPERATURE = 0.8

class GeminiError(RuntimeError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


def _get_gemini_api_keys() -> list[str]:
    api_keys = [
        getattr(settings, "API1_KEY", None),
        getattr(settings, "API2_KEY", None),
        getattr(settings, "API3_KEY", None),
        getattr(settings, "API4_KEY", None),
    ]
    return [
        key.strip()
        for key in api_keys
        if isinstance(key, str) and key.strip()
    ]


def _iter_gemini_api_keys(api_keys: list[str]) -> Iterator[tuple[int, str]]:
    if not api_keys:
        return

    start_index = random.randrange(len(api_keys)) if len(api_keys) > 1 else 0
    for offset in range(len(api_keys)):
        index = (start_index + offset) % len(api_keys)
        yield index + 1, api_keys[index]


def _build_contents(input_context: dict[str, Any]) -> list[dict[str, Any]]:
    if "contents" in input_context and isinstance(input_context["contents"], list):
        return input_context["contents"]

    messages = input_context.get("messages")
    if isinstance(messages, list):
        contents: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                continue
            role = (message.get("role") or "user").strip() or "user"
            text = (message.get("text") or "").strip()
            if not text:
                continue
            contents.append({"role": role, "parts": [{"text": text}]})
        if contents:
            return contents

    prompt = (input_context.get("prompt") or "").strip()
    if prompt:
        return [{"role": "user", "parts": [{"text": prompt}]}]

    raise ValueError(
        "input_context must include 'contents', 'messages', or 'prompt'."
    )


def _inject_system_prompt(
    contents: list[dict[str, Any]],
    system_prompt: str,
) -> list[dict[str, Any]]:
    system_prompt = (system_prompt or "").strip()
    if not system_prompt:
        return list(contents)

    # The public Generative Language `v1` API used by this project does not accept
    # a `systemInstruction` field, so we prepend the instruction as the first
    # message to keep compatibility across environments.
    system_text = (
        "System instruction:\n"
        f"{system_prompt}\n\n"
        "Follow the system instruction above."
    )
    return [{"role": "user", "parts": [{"text": system_text}]}] + list(contents)


def _extract_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        return ""
    first = candidates[0] if isinstance(candidates[0], dict) else {}
    content = first.get("content") if isinstance(first, dict) else {}
    parts = (content or {}).get("parts") if isinstance(content, dict) else []
    if not isinstance(parts, list) or not parts:
        return ""
    text_parts: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        part_text = part.get("text")
        if part_text:
            text_parts.append(str(part_text))
    return "".join(text_parts)


def _extract_error_message(response: requests.Response) -> str | None:
    error_payload: Any = {}
    try:
        error_payload = response.json()
    except ValueError:
        error_payload = {"message": response.text[:300]}

    api_error = (
        error_payload.get("error", {}) if isinstance(error_payload, dict) else {}
    )
    if isinstance(api_error, dict):
        return api_error.get("message") or error_payload.get("message")
    return error_payload.get("message") if isinstance(error_payload, dict) else None


def _build_failure_message(last_error: dict[str, Any] | None) -> str:
    if not last_error:
        return "All API keys failed."

    if last_error.get("error") and not last_error.get("status"):
        return f"Network error while contacting Gemini: {last_error['error']}"

    status = last_error.get("status")
    message = str(last_error.get("message") or "").strip()
    lowered_message = message.lower()

    if status == 429 and any(
        fragment in lowered_message
        for fragment in (
            "high demand",
            "temporarily unavailable",
            "overloaded",
            "spikes in demand",
        )
    ):
        return "Gemini is temporarily overloaded. Please try again in a moment."

    if status == 429:
        return "All API keys are over quota right now."

    if status in (401, 403):
        return (
            "All API keys were rejected (invalid key, API disabled, or key restriction mismatch)."
        )

    if status == 400 and any(
        fragment in lowered_message
        for fragment in (
            "token",
            "context",
            "too large",
            "prompt too long",
            "request size",
        )
    ):
        return (
            "The prompt is too long for the current model. Split it into smaller parts and try again."
        )

    if status in (503, 504) or any(
        fragment in lowered_message
        for fragment in (
            "high demand",
            "temporarily unavailable",
            "overloaded",
        )
    ):
        return "Gemini is temporarily overloaded. Please try again in a moment."

    return "All API keys failed."


def generate_ai_response(input_context: dict[str, Any], system_prompt: str) -> str:
    """
    Shared Gemini client used across apps.

    Args:
        input_context: dict containing either:
            - "contents": Gemini REST contents list, OR
            - "messages": [{"role": "user"|"model", "text": "..."}], OR
            - "prompt": "...".
        system_prompt: system instruction string.
    """

    api_keys = _get_gemini_api_keys()
    if not api_keys:
        raise GeminiError(
            "No Gemini API keys are configured. Add API1_KEY..API4_KEY in your .env file."
        )

    model_name = (input_context.get("model") or DEFAULT_GEMINI_MODEL).strip()
    timeout = int(input_context.get("timeout") or DEFAULT_TIMEOUT_SECONDS)

    url = (
        "https://generativelanguage.googleapis.com/v1/models/"
        f"{model_name}:generateContent"
    )

    contents = _build_contents(input_context)
    contents = _inject_system_prompt(contents, system_prompt)

    payload: dict[str, Any] = {"contents": contents}

    generation_config: dict[str, Any] = {}
    for key in ("temperature", "topP", "topK", "maxOutputTokens"):
        if key in input_context and input_context[key] is not None:
            generation_config[key] = input_context[key]
    if generation_config:
        payload["generationConfig"] = generation_config

    last_error: dict[str, Any] | None = None

    for key_index, api_key in _iter_gemini_api_keys(api_keys):
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            last_error = {
                "key_index": key_index,
                "error": str(exc),
                "type": exc.__class__.__name__,
            }
            continue

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                data = {}
            return _extract_text(data)

        message = _extract_error_message(response)

        last_error = {
            "key_index": key_index,
            "status": response.status_code,
            "message": message,
        }

        if response.status_code == 400:
            break
        continue

    raise GeminiError(_build_failure_message(last_error), details=last_error)


def generate_ai_response_simple(
    input_context: dict,
    system_prompt: str,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    input_context = dict(input_context)
    input_context["temperature"] = temperature
    return generate_ai_response(input_context, system_prompt)