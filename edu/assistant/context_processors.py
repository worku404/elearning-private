from .forms import LLMForm
from .utils import build_chat_state, get_active_chat, serialize_history


def llm_widget(request):
    if not request.user.is_authenticated:
        return {"llm_form": None, "llm_history": [], "llm_chat_state": {}}

    active_chat = get_active_chat(request)
    history_ui = serialize_history(active_chat)
    chat_state = build_chat_state(request.user, active_chat)
    return {
        "llm_form": LLMForm(),
        "llm_history": history_ui,
        "llm_chat_state": chat_state,
    }
