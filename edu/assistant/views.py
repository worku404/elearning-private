from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .markdown_utils import render_llm_markdown
from .models import AssistantChat, AssistantTurn
from .services import GeminiError, generate_ai_response
from .utils import (
    PIN_LIMIT,
    build_chat_state,
    delete_unpinned_chat,
    get_active_chat,
    serialize_history,
    set_active_chat,
    title_from_prompt,
    toggle_pin,
)
DEFAULT_MAX_OUTPUT_TOKENS = getattr(settings, "ASSISTANT_MAX_OUTPUT_TOKENS", 65536)


def _gemini_error_status(details: dict[str, object] | None) -> int:
    if isinstance(details, dict):
        status = details.get("status")
        try:
            status_code = int(str(status or "").strip())
        except (TypeError, ValueError):
            status_code = 0
        if 400 <= status_code <= 599:
            return status_code
    return 502


@require_POST
@login_required
def llm_generate(request):
    prompt = (request.POST.get("prompt") or "").strip()

    if not prompt:
        return JsonResponse({"error": "Prompt is required."}, status=400)

    system_prompt = (
    "You are a warm, intelligent AI study assistant inside an e-learning platform. "
    "Behave like a knowledgeable tutor — direct, practical, and thorough. "
    "Never stop early; if the user asks for detail, give a complete answer. "
    "Keep the token count under 60000. "
    
    "**Tone:** Be kind and respectful. Push back or clarify when needed, but always with empathy. "
    "Never be condescending or assume the user lacks ability. "
    "Stay honest — admit when you don't know something rather than guessing. "
    
    "**Formatting:** Always use Markdown for every response. "
    "Use headers (##, ###) to organize content, bullet points for lists, "
    "bold for key terms, code blocks for any code, and tables where comparisons help. "
    "Never respond in plain prose without Markdown structure. "
    
    "**Questions:** Never ask more than one clarifying question at a time. "
    "Always attempt to answer first, then ask for clarification if needed. "
    
    "**Length:** Match length to complexity. Short questions get concise answers. "
    "Complex topics get thorough, well-structured breakdowns. "
    "Never pad or repeat content unnecessarily. "
    
    "**Never use these words:** 'genuinely', 'honestly', 'straightforward', "
    "'certainly', 'absolutely', 'of course', 'great question', 'I\'d be happy to'. "
    
    "When relevant, include short actionable steps or summaries at the end of responses."
)

    active_chat = get_active_chat(request)
    if not active_chat:
        active_chat = AssistantChat.objects.create(user=request.user)
        set_active_chat(request, active_chat)

    max_turns = 3
    contents = []
    if active_chat:
        recent_turns = list(
            AssistantTurn.objects.filter(chat=active_chat)
            .order_by("-created_at")[:max_turns]
        )
        for turn in reversed(recent_turns):
            if turn.prompt:
                contents.append(
                    {"role": "user", "parts": [{"text": turn.prompt}]}
                )
            if turn.response:
                contents.append(
                    {"role": "model", "parts": [{"text": turn.response}]}
                )
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    generation_context = {
        "contents": contents,
        "temperature": 0.2,
        "maxOutputTokens": DEFAULT_MAX_OUTPUT_TOKENS,
    }

    try:
        generated = generate_ai_response(generation_context, system_prompt).strip()
        if not generated:
            raise GeminiError("Gemini returned an empty response.", details={"status": 502})

        AssistantTurn.objects.create(
            chat=active_chat,
            prompt=prompt,
            response=generated,
        )

        if not (active_chat.title or "").strip():
            active_chat.title = title_from_prompt(prompt)
            active_chat.save(update_fields=["title", "updated_at"])
        else:
            active_chat.save(update_fields=["updated_at"])

        chat_state = build_chat_state(request.user, active_chat)
        return JsonResponse(
            {
                "generated": render_llm_markdown(generated),
                "chat_state": chat_state,
            }
        )
    except GeminiError as exc:
        details = exc.details if isinstance(exc.details, dict) else None
        return JsonResponse(
            {
                "error": exc.message,
                "details": details,
                "chat_state": build_chat_state(request.user, active_chat),
            },
            status=_gemini_error_status(details),
        )
    except Exception as exc:
        return JsonResponse(
            {
                "error": str(exc),
                "chat_state": build_chat_state(request.user, active_chat),
            },
            status=500,
        )


@require_POST
@login_required
def llm_new_chat(request):
    active_chat = get_active_chat(request)
    if active_chat:
        delete_unpinned_chat(active_chat)

    new_chat = AssistantChat.objects.create(user=request.user)
    set_active_chat(request, new_chat)

    return JsonResponse(
        {
            "history": [],
            "chat_state": build_chat_state(request.user, new_chat),
        }
    )


@require_GET
@login_required
def llm_open_chat(request, chat_id):
    active_chat = get_active_chat(request)
    target_chat = get_object_or_404(
        AssistantChat, id=chat_id, user=request.user
    )
    active_chat_id = getattr(active_chat, "id", None)
    target_chat_id = getattr(target_chat, "id", None)
    if active_chat_id and active_chat_id != target_chat_id:
        delete_unpinned_chat(active_chat)
    set_active_chat(request, target_chat)

    return JsonResponse(
        {
            "history": serialize_history(target_chat),
            "chat_state": build_chat_state(request.user, target_chat),
        }
    )


@require_POST
@login_required
def llm_toggle_pin(request, chat_id):
    chat = get_object_or_404(AssistantChat, id=chat_id, user=request.user)
    active_chat = get_active_chat(request)
    active_chat_id = getattr(active_chat, "id", None)
    chat_id_value = getattr(chat, "id", None)

    if not chat.is_pinned:
        pinned_count = AssistantChat.objects.filter(
            user=request.user, is_pinned=True
        ).count()
        if pinned_count >= PIN_LIMIT:
            return JsonResponse(
                {
                    "error": "You can only pin up to 6 chats. Unpin one to add another.",
                },
                status=400,
            )
        toggle_pin(chat, True)
    else:
        toggle_pin(chat, False)
        if not active_chat_id or active_chat_id != chat_id_value:
            chat.delete()

    active_chat = get_active_chat(request)
    return JsonResponse(
        {
            "chat_state": build_chat_state(request.user, active_chat),
        }
    )


@login_required
def llm_page(request):
    return render(request, "assistant/page.html")
