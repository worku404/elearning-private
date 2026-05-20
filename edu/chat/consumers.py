import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

from courses.models import Course
from chat.models import Message
from chat.services import prune_course_messages

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        self.course_id = int(self.scope["url_route"]["kwargs"]["course_id"])
        self.room_group_name = f"chat_{self.course_id}"

        if not self.user.is_authenticated:
            await self.close(code=4401)
            return

        if not await self._is_enrolled():
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = (text_data_json.get("message") or "").strip()
        if not message:
            return

        message_data = await self._persist_message(message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message_id": message_data["id"],
                "message": message_data["content"],
                "user": message_data["username"],
                "datetime": message_data["sent_on"],
            }
        )

        course_title, recipient_ids = await self._get_notification_targets()
        for recipient_id in recipient_ids:
            await self.channel_layer.group_send(
                f"notify_user_{recipient_id}",
                {
                    "type": "notify_message",
                    "course_id": self.course_id,
                    "course_title": course_title,
                    "message_id": message_data["id"],
                    "from_user": message_data["username"],
                    "message_preview": message_data["content"][:120],
                    "datetime": message_data["sent_on"],
                },
            )

        if message_data["id"] % 20 == 0:
            await self._prune_messages()

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def _is_enrolled(self):
        return Course.objects.filter(id=self.course_id, students=self.user).exists()

    @database_sync_to_async
    def _persist_message(self, content):
        obj = Message.objects.create(
            user=self.user,
            course_id=self.course_id,
            content=content,
        )
        return {
            "id": obj.id,
            "content": obj.content,
            "username": self.user.username,
            "sent_on": obj.sent_on.isoformat(),
        }

    @database_sync_to_async
    def _get_notification_targets(self):
        course = Course.objects.get(id=self.course_id)
        recipient_ids = list(
            course.students.exclude(id=self.user.id).values_list("id", flat=True)
        )
        return course.title, recipient_ids

    @database_sync_to_async
    def _prune_messages(self):
        keep = getattr(settings, "CHAT_MAX_MESSAGES_PER_COURSE", 1000)
        prune_course_messages(self.course_id, keep=keep)


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.group_name = f"notify_user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def notify_message(self, event):
        await self.send(text_data=json.dumps(event))
