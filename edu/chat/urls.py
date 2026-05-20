from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('room/<int:course_id>/', views.course_chat_room, name='course_chat_room'),
    path('history/<int:course_id>/', views.chat_history, name='chat_history'),
    path(
        "notifications/bootstrap/",
        views.notifications_bootstrap,
        name="notifications_bootstrap",
    ),
    path(
        "room/<int:course_id>/mark-read/",
        views.mark_room_read,
        name="mark_room_read",
    ),
]
