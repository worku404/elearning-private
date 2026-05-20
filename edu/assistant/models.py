from django.conf import settings
from django.db import models


class AssistantChat(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assistant_chats",
    )
    title = models.CharField(max_length=200, blank=True)
    is_pinned = models.BooleanField(default=False)
    pinned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_pinned", "pinned_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        label = self.title.strip() if self.title else "New chat"
        return f"{self.user_id}:{label}"


class AssistantTurn(models.Model):
    chat = models.ForeignKey(
        AssistantChat,
        on_delete=models.CASCADE,
        related_name="turns",
    )
    prompt = models.TextField()
    response = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["chat", "created_at"]),
        ]

    def __str__(self) -> str:
        preview = (self.prompt or "").strip()[:40]
        return f"{self.chat_id}:{preview}"
