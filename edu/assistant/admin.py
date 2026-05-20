# from django.contrib import admin

# from .models import AssistantChat, AssistantTurn


# @admin.register(AssistantChat)
# class AssistantChatAdmin(admin.ModelAdmin):
#     list_display = ("id", "user", "title", "is_pinned", "pinned_at", "updated_at")
#     list_filter = ("is_pinned",)
#     search_fields = ("title", "user__username", "user__email")
#     ordering = ("-updated_at",)


# @admin.register(AssistantTurn)
# class AssistantTurnAdmin(admin.ModelAdmin):
#     list_display = ("id", "chat", "created_at")
#     search_fields = ("prompt", "response")
#     ordering = ("-created_at",)
