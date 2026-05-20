# from django.contrib import admin

# from .models import (
#     AIPlanRun,
#     DailyCourseStat,
#     DailySiteStat,
#     Goal,
#     InsightNotification,
#     NotificationPreference,
#     StudyTimeEvent,
#     TelegramConnectToken,
#     TelegramSubscription,
# )


# @admin.register(StudyTimeEvent)
# class StudyTimeEventAdmin(admin.ModelAdmin):
#     list_display = (
#         "id",
#         "user",
#         "course",
#         "module",
#         "seconds_delta",
#         "source",
#         "session_end_at",
#         "local_date",
#         "local_hour",
#         "created",
#     )
#     list_filter = (
#         "source",
#         "local_date",
#         "local_hour",
#         "course",
#     )
#     search_fields = (
#         "user__username",
#         "course__title",
#         "module__title",
#     )
#     autocomplete_fields = ("user", "course", "module")
#     date_hierarchy = "session_end_at"
#     ordering = ("-session_end_at", "-id")
#     readonly_fields = ("created",)


# @admin.register(DailyCourseStat)
# class DailyCourseStatAdmin(admin.ModelAdmin):
#     list_display = (
#         "user",
#         "course",
#         "date",
#         "module_seconds",
#         "content_active_seconds",
#         "completed_content_count",
#         "session_count",
#         "created",
#         "updated",
#     )
#     list_filter = ("date", "course")
#     search_fields = (
#         "user__username",
#         "course__title",
#     )
#     autocomplete_fields = ("user", "course")
#     date_hierarchy = "date"
#     ordering = ("-date", "-id")
#     readonly_fields = ("created", "updated")


# @admin.register(DailySiteStat)
# class DailySiteStatAdmin(admin.ModelAdmin):
#     list_display = (
#         "user",
#         "date",
#         "active_seconds",
#         "ping_count",
#         "created",
#         "updated",
#     )
#     list_filter = ("date",)
#     search_fields = ("user__username",)
#     autocomplete_fields = ("user",)
#     date_hierarchy = "date"
#     ordering = ("-date", "-id")
#     readonly_fields = ("created", "updated")


# @admin.register(Goal)
# class GoalAdmin(admin.ModelAdmin):
#     list_display = (
#         "title",
#         "user",
#         "course",
#         "period_type",
#         "target_type",
#         "priority",
#         "status",
#         "current_value",
#         "target_value",
#         "start_date",
#         "due_date",
#         "completed_at",
#         "created",
#         "updated",
#     )
#     list_filter = (
#         "period_type",
#         "target_type",
#         "priority",
#         "status",
#         "start_date",
#         "due_date",
#         "course",
#     )
#     search_fields = (
#         "title",
#         "description",
#         "user__username",
#         "course__title",
#     )
#     autocomplete_fields = ("user", "course", "parent")
#     date_hierarchy = "due_date"
#     ordering = ("due_date", "-created")
#     readonly_fields = ("completed_at", "created", "updated")

#     fieldsets = (
#         (
#             "Ownership",
#             {
#                 "fields": ("user", "parent", "course"),
#             },
#         ),
#         (
#             "Goal details",
#             {
#                 "fields": (
#                     "title",
#                     "description",
#                     "period_type",
#                     "target_type",
#                     "priority",
#                     "status",
#                 ),
#             },
#         ),
#         (
#             "Progress",
#             {
#                 "fields": (
#                     "target_value",
#                     "current_value",
#                     "start_date",
#                     "due_date",
#                     "completed_at",
#                 ),
#             },
#         ),
#         (
#             "Metadata",
#             {
#                 "fields": ("created", "updated"),
#             },
#         ),
#     )


# @admin.register(NotificationPreference)
# class NotificationPreferenceAdmin(admin.ModelAdmin):
#     list_display = (
#         "user",
#         "timezone",
#         "week_start_day",
#         "daily_enabled",
#         "weekly_enabled",
#         "daily_achievement_enabled",
#         "weekly_achievement_enabled",
#         "in_app_enabled",
#         "telegram_enabled",
#         "telegram_evening_summary_start",
#         "telegram_evening_summary_end",
#         "telegram_morning_summary_start",
#         "telegram_morning_summary_end",
#         "daily_time",
#         "weekly_time",
#     )
#     list_filter = (
#         "week_start_day",
#         "daily_enabled",
#         "weekly_enabled",
#         "daily_achievement_enabled",
#         "weekly_achievement_enabled",
#         "in_app_enabled",
#         "telegram_enabled",
#     )
#     search_fields = ("user__username", "timezone")
#     autocomplete_fields = ("user",)


# @admin.register(InsightNotification)
# class InsightNotificationAdmin(admin.ModelAdmin):
#     list_display = (
#         "id",
#         "user",
#         "category",
#         "channel",
#         "title",
#         "scheduled_for",
#         "read_at",
#         "dismissed_at",
#         "telegram_sent_at",
#         "created",
#     )
#     list_filter = (
#         "category",
#         "channel",
#         "scheduled_for",
#         "read_at",
#         "dismissed_at",
#     )
#     search_fields = (
#         "user__username",
#         "title",
#         "body",
#         "dedupe_key",
#     )
#     autocomplete_fields = ("user",)
#     date_hierarchy = "scheduled_for"
#     ordering = ("-scheduled_for", "-id")
#     readonly_fields = ("created",)

#     fieldsets = (
#         (
#             "Recipient",
#             {
#                 "fields": ("user", "category", "channel"),
#             },
#         ),
#         (
#             "Content",
#             {
#                 "fields": ("title", "body", "payload"),
#             },
#         ),
#         (
#             "Scheduling and state",
#             {
#                 "fields": (
#                     "dedupe_key",
#                     "scheduled_for",
#                     "read_at",
#                     "dismissed_at",
#                     "created",
#                 ),
#             },
#         ),
#     )


# @admin.register(TelegramSubscription)
# class TelegramSubscriptionAdmin(admin.ModelAdmin):
#     list_display = ("user", "chat_id", "created_at")
#     search_fields = ("user__username", "chat_id")
#     autocomplete_fields = ("user",)
#     ordering = ("-created_at", "-id")
#     readonly_fields = ("created_at",)


# @admin.register(TelegramConnectToken)
# class TelegramConnectTokenAdmin(admin.ModelAdmin):
#     list_display = ("user", "token", "is_used", "created_at")
#     list_filter = ("is_used", "created_at")
#     search_fields = ("user__username", "token")
#     autocomplete_fields = ("user",)
#     ordering = ("-created_at", "-id")
#     readonly_fields = ("created_at",)


# @admin.register(AIPlanRun)
# class AIPlanRunAdmin(admin.ModelAdmin):
#     list_display = (
#         "id",
#         "user",
#         "kind",
#         "period_type",
#         "status",
#         "approved_at",
#         "applied_at",
#         "created_at",
#     )
#     list_filter = ("kind", "period_type", "status", "created_at")
#     search_fields = ("user__username", "summary_text", "error_message")
#     autocomplete_fields = ("user",)
#     ordering = ("-created_at", "-id")
#     readonly_fields = ("created_at", "updated_at")
