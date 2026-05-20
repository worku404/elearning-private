from django.urls import path

from . import views

app_name = "learning_insights"

urlpatterns = [
    path("", views.InsightsOverviewView.as_view(), name="overview"),
    path("daily/", views.DailySummaryView.as_view(), name="daily_summary"),
    path("weekly/", views.WeeklySummaryView.as_view(), name="weekly_summary"),
    path("monthly/", views.MonthlySummaryView.as_view(), name="monthly_summary"),
    path("goals/", views.GoalListView.as_view(), name="goal_list"),
    path("goals/new/", views.GoalCreateView.as_view(), name="goal_create"),
    path("goals/ai/", views.GoalAIPlannerView.as_view(), name="goal_ai_planner"),
    path("goals/ai/<int:pk>/apply/", views.GoalAIApplyView.as_view(), name="goal_ai_apply"),
    path("goals/<int:pk>/edit/", views.GoalUpdateView.as_view(), name="goal_update"),
    path("goals/<int:pk>/delete/", views.GoalDeleteView.as_view(), name="goal_delete"),
    path(
        "goals/<int:pk>/action/",
        views.GoalQuickActionView.as_view(),
        name="goal_action",
    ),
    path(
        "notifications/",
        views.NotificationCenterView.as_view(),
        name="notification_center",
    ),
    path(
        "notifications/bootstrap/",
        views.NotificationBootstrapView.as_view(),
        name="notifications_bootstrap",
    ),
    path(
        "notifications/read-all/",
        views.NotificationMarkAllReadView.as_view(),
        name="notifications_mark_all_read",
    ),
    path(
        "notifications/<int:pk>/read/",
        views.NotificationMarkReadView.as_view(),
        name="notification_mark_read",
    ),
    path(
        "notifications/<int:pk>/dismiss/",
        views.NotificationDismissView.as_view(),
        name="notification_dismiss",
    ),
    path(
        "preferences/",
        views.NotificationPreferenceView.as_view(),
        name="preferences",
    ),
    path(
        "telegram/",
        views.TelegramConnectView.as_view(),
        name="telegram_connect",
    ),
    path("ai/review/", views.AIReviewHubView.as_view(), name="ai_review"),
    path("ai/review/generate/", views.AIReviewGenerateView.as_view(), name="ai_review_generate"),
    path("ai/runs/<int:pk>/", views.AIRunDetailView.as_view(), name="ai_run_detail"),
    path("ai/runs/<int:pk>/edit/", views.AIRunDetailView.as_view(), name="ai_run_edit"),
    path("ai/runs/<int:pk>/apply/", views.AIRunApplyView.as_view(), name="ai_run_apply"),
]
