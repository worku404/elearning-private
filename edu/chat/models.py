from django.db import models
from django.conf import settings

class Message(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='chat_messages'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.PROTECT,
        related_name='chat_messages'
    )
    content = models.TextField()
    sent_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["course", "id"]),
            models.Index(fields=["course", "sent_on"]),
        ]
    
    def __str__(self) -> str:
        return f'{self.user} on {self.course} at {self.sent_on}'


class CourseReadState(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_read_states",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="chat_read_states",
    )
    # Keep numeric pointer so message pruning does not invalidate this relation.
    last_read_message_id = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "course"],
                name="uniq_chat_read_state_user_course",
            )
        ]
        indexes = [
            models.Index(fields=["user", "course"]),
            models.Index(fields=["course", "user"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.course_id} -> {self.last_read_message_id}"
