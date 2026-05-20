from django.utils import timezone

from .markdown_utils import render_llm_markdown
from .models import AssistantChat, AssistantTurn


PIN_LIMIT = 6
SESSION_CHAT_KEY = "assistant_chat_id"


def get_active_chat(request):
    chat_id = request.session.get(SESSION_CHAT_KEY)
    if not chat_id:
        return None
    try:
        return AssistantChat.objects.get(id=chat_id, user=request.user)
    except AssistantChat.DoesNotExist:
        request.session.pop(SESSION_CHAT_KEY, None)
        request.session.modified = True
        return None


def set_active_chat(request, chat):
    if chat:
        request.session[SESSION_CHAT_KEY] = chat.id
    else:
        request.session.pop(SESSION_CHAT_KEY, None)
    request.session.modified = True


def delete_unpinned_chat(chat):
    if chat and not chat.is_pinned:
        chat.delete()


def title_from_prompt(prompt, limit=60):
    cleaned = " ".join((prompt or "").split())
    if not cleaned:
        return "New chat"
    return cleaned[:limit]


def serialize_chat(chat):
    if not chat:
        return None
    title = (chat.title or "").strip() or "New chat"
    return {
        "id": chat.id,
        "title": title,
        "is_pinned": chat.is_pinned,
        "pinned_at": chat.pinned_at.isoformat() if chat.pinned_at else "",
        "updated_at": chat.updated_at.isoformat() if chat.updated_at else "",
        "created_at": chat.created_at.isoformat() if chat.created_at else "",
    }


def serialize_history(chat):
    if not chat:
        return []
    turns = AssistantTurn.objects.filter(chat=chat).order_by("created_at")
    return [
        {
            "prompt": turn.prompt,
            "response": render_llm_markdown(turn.response),
        }
        for turn in turns
    ]


def build_chat_state(user, active_chat):
    purge_unpinned_chats(user, active_chat.id if active_chat else None)
    pinned_qs = (
        AssistantChat.objects.filter(user=user, is_pinned=True)
        .order_by("-pinned_at", "-created_at")[:PIN_LIMIT]
    )
    pinned = [serialize_chat(chat) for chat in pinned_qs]
    temp_chat = None
    if active_chat and not active_chat.is_pinned:
        temp_chat = serialize_chat(active_chat)
    return {
        "active_chat_id": active_chat.id if active_chat else None,
        "pinned_chats": pinned,
        "temp_chat": temp_chat,
        "max_pins": PIN_LIMIT,
    }


def purge_unpinned_chats(user, keep_chat_id=None):
    qs = AssistantChat.objects.filter(user=user, is_pinned=False)
    if keep_chat_id:
        qs = qs.exclude(id=keep_chat_id)
    qs.delete()


def toggle_pin(chat, pinned):
    if pinned:
        chat.is_pinned = True
        chat.pinned_at = timezone.now()
    else:
        chat.is_pinned = False
        chat.pinned_at = None
    chat.save(update_fields=["is_pinned", "pinned_at", "updated_at"])
    return chat
