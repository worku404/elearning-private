from . import views
from django.urls import path
app_name = 'assistant'

urlpatterns = [
    path(
        '',
        views.llm_page,
        name='llm_page'
    ),
    path('llm/generate/',
         views.llm_generate,
         name='llm_generate'
         ),
    path(
        "llm/chats/new/",
        views.llm_new_chat,
        name="llm_new_chat",
    ),
    path(
        "llm/chats/<int:chat_id>/",
        views.llm_open_chat,
        name="llm_open_chat",
    ),
    path(
        "llm/chats/<int:chat_id>/pin/",
        views.llm_toggle_pin,
        name="llm_toggle_pin",
    ),
]
