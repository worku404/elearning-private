from django.contrib.auth import get_user_model

from .models import CourseReadState, Message

User = get_user_model()


def set_last_read(user: User, course, message_id: int) -> None:
    if not message_id:
        return

    state, _ = CourseReadState.objects.get_or_create(
        user=user,
        course=course,
        defaults={"last_read_message_id": 0},
    )
    if message_id > state.last_read_message_id:
        state.last_read_message_id = message_id
        state.save(update_fields=["last_read_message_id", "updated_at"])


def get_unread_preview(user: User, limit: int = 3, scan_limit: int = 100):
    pointers = {
        item.course_id: item.last_read_message_id
        for item in CourseReadState.objects.filter(user=user).only(
            "course_id",
            "last_read_message_id",
        )
    }

    candidates = (
        Message.objects.filter(course__students=user)
        .exclude(user=user)
        .select_related("user", "course")
        .order_by("-id")[:scan_limit]
    )

    unread = []
    for msg in candidates:
        if msg.id > pointers.get(msg.course_id, 0):
            unread.append(msg)
            if len(unread) >= limit:
                break
    return unread


def prune_course_messages(course_id: int, keep: int = 1000) -> int:
    keep = int(keep or 1000)
    ids_to_delete = list(
        Message.objects.filter(course_id=course_id)
        .order_by("-id")
        .values_list("id", flat=True)[keep:]
    )
    if not ids_to_delete:
        return 0

    deleted, _ = Message.objects.filter(id__in=ids_to_delete).delete()
    return deleted
