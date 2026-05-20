from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)

from .forms import (
    AIPlanRunEditForm,
    GoalForm,
    NotificationPreferenceForm,
    PromptPlanItemFormSet,
)
from .models import AIPlanRun, Goal, InsightNotification, NotificationPreference
from .services.analytics import (
    build_daily_summary,
    build_monthly_summary,
    build_overview_context,
    build_weekly_summary,
)
from .services.common import get_local_date, get_period_start
from .services.goals import sync_goal_progress_for_user
from .services.notifications import (
    create_goal_batch_notification,
    create_goal_created_notification,
    dismiss_notification,
    ensure_due_notifications,
    get_notification_payload,
    mark_notification_read,
    mark_notifications_read,
)
from .services.telegram import (
    generate_connect_token,
    get_active_connect_token,
    get_bot_username,
    get_subscription_for_user,
    send_notification,
)
from .services.ai_coach import (
    apply_prompt_plan_run,
    generate_daily_review_run,
    generate_improvement_run,
    generate_prompt_plan_run,
    generate_recovery_run,
    generate_weekly_review_run,
)


def _with_query_param(url: str, **params: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in params.items():
        query[key] = value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class InsightsBaseMixin(LoginRequiredMixin):
    """
    Shared setup for insights pages.

    Release 1 keeps the pages server-rendered and lightweight.
    On each request we refresh goal progress and generate any due in-app
    reminders so the dashboard reflects recent study activity.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        sync_goal_progress_for_user(request.user)
        ensure_due_notifications(request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_notification_preference(self) -> NotificationPreference:
        preference, _ = NotificationPreference.objects.get_or_create(
            user=self.request.user,
            defaults={
                "timezone": timezone.get_current_timezone_name(),
                "week_start_day": NotificationPreference.WEEKDAY_MONDAY,
            },
        )
        return preference


class InsightsOverviewView(InsightsBaseMixin, TemplateView):
    template_name = "learning_insights/overview.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        preference = self.get_notification_preference()
        context.update(build_overview_context(self.request.user, preference=preference))
        context["preference"] = preference
        context["page_title"] = "Learning Insights"
        return context


class DailySummaryView(InsightsBaseMixin, TemplateView):
    template_name = "learning_insights/daily_summary.html"

    def _parse_day(self) -> date | None:
        raw = (self.request.GET.get("day") or "").strip()
        if not raw:
            return None
        parsed = parse_date(raw)
        if parsed is None:
            return None
        return parsed

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        preference = self.get_notification_preference()
        day = self._parse_day()
        context.update(build_daily_summary(self.request.user, preference=preference, day=day))
        context["preference"] = preference
        return context


class WeeklySummaryView(InsightsBaseMixin, TemplateView):
    template_name = "learning_insights/weekly_summary.html"

    def _parse_week_start(self) -> date | None:
        raw = (self.request.GET.get("week") or "").strip()
        if not raw:
            return None
        parsed = parse_date(raw)
        if parsed is None:
            return None
        return parsed

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        preference = self.get_notification_preference()
        week_start = self._parse_week_start()
        context.update(
            build_weekly_summary(
                self.request.user,
                preference=preference,
                week_start=week_start,
            )
        )
        context["preference"] = preference
        context["selected_week"] = week_start
        context["page_title"] = "Weekly Summary"
        return context


class MonthlySummaryView(InsightsBaseMixin, TemplateView):
    template_name = "learning_insights/monthly_summary.html"

    def _parse_month(self) -> date | None:
        raw = (self.request.GET.get("month") or "").strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m").date().replace(day=1)
        except ValueError:
            return None

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        preference = self.get_notification_preference()
        month_anchor = self._parse_month()
        context.update(
            build_monthly_summary(
                self.request.user,
                preference=preference,
                month_anchor=month_anchor,
            )
        )
        context["preference"] = preference
        context["page_title"] = "Monthly Summary"
        return context


class GoalQuerysetMixin(InsightsBaseMixin):
    model = Goal

    def get_queryset(self) -> QuerySet[Goal]:
        queryset = (
            Goal.objects.filter(user=self.request.user)
            .select_related("course", "parent")
            .order_by("-due_date", "-created")
        )

        status_value = (self.request.GET.get("status") or "").strip()
        period_value = (self.request.GET.get("period") or "").strip()
        course_value = (self.request.GET.get("course") or "").strip()
        priority_value = (self.request.GET.get("priority") or "").strip()

        if status_value:
            queryset = queryset.filter(status=status_value)
        if period_value:
            queryset = queryset.filter(period_type=period_value)
        if course_value.isdigit():
            queryset = queryset.filter(course_id=int(course_value))
        if priority_value:
            queryset = queryset.filter(priority=priority_value)

        return queryset


class GoalListView(GoalQuerysetMixin, ListView):
    template_name = "learning_insights/goals/list.html"
    context_object_name = "goals"
    paginate_by = 20

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        context["page_title"] = "Goals"
        context["status_choices"] = Goal.STATUS_CHOICES
        context["period_choices"] = Goal.PERIOD_CHOICES
        context["priority_choices"] = Goal.PRIORITY_CHOICES
        context["enrolled_courses"] = self.request.user.courses_joined.order_by("title")
        context["filters"] = {
            "status": (self.request.GET.get("status") or "").strip(),
            "period": (self.request.GET.get("period") or "").strip(),
            "course": (self.request.GET.get("course") or "").strip(),
            "priority": (self.request.GET.get("priority") or "").strip(),
        }
        context["summary"] = {
            "total": queryset.count(),
            "completed": queryset.filter(status=Goal.STATUS_COMPLETED).count(),
            "in_progress": queryset.filter(status=Goal.STATUS_IN_PROGRESS).count(),
            "overdue": queryset.filter(status=Goal.STATUS_OVERDUE).count(),
            "missed": queryset.filter(status=Goal.STATUS_MISSED).count(),
            "not_started": queryset.filter(status=Goal.STATUS_NOT_STARTED).count(),
        }
        return context


class GoalFormMixin(GoalQuerysetMixin):
    form_class = GoalForm
    success_url = reverse_lazy("learning_insights:goal_list")
    force_notifications_bootstrap = True

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        url = super().get_success_url()
        if getattr(self, "force_notifications_bootstrap", False):
            return _with_query_param(url, li_bootstrap="1")
        return url

    def form_valid(self, form):
        response = super().form_valid(form)
        sync_goal_progress_for_user(self.request.user)
        messages.success(self.request, "Goal saved successfully.")
        return response


class GoalCreateView(GoalFormMixin, CreateView):
    template_name = "learning_insights/goals/form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        create_goal_created_notification(goal=self.object)
        return response

    def get_initial(self):
        initial = super().get_initial()
        today = timezone.localdate()
        period = (self.request.GET.get("period") or "").strip()

        if period in dict(Goal.PERIOD_CHOICES):
            initial["period_type"] = period

        selected_period = initial.get("period_type") or Goal.PERIOD_WEEKLY
        initial["start_date"] = today

        if selected_period == Goal.PERIOD_DAILY:
            initial["due_date"] = today
        elif selected_period == Goal.PERIOD_WEEKLY:
            week_start = get_period_start(today, "weekly")
            initial["start_date"] = week_start
            initial["due_date"] = week_start + timedelta(days=6)
        elif selected_period == Goal.PERIOD_MONTHLY:
            initial["start_date"] = today.replace(day=1)
            if today.month == 12:
                next_month = today.replace(year=today.year + 1, month=1, day=1)
            else:
                next_month = today.replace(month=today.month + 1, day=1)
            initial["due_date"] = next_month - timedelta(days=1)
        else:
            initial["due_date"] = today + timedelta(days=30)

        return initial

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Create Goal"
        context["form_mode"] = "create"

        ai_run = None
        raw_ai_run = (self.request.GET.get("ai_run") or "").strip()
        if raw_ai_run.isdigit():
            ai_run = (
                AIPlanRun.objects.filter(
                    user=self.request.user,
                    kind=AIPlanRun.KIND_PROMPT_PLAN,
                    pk=int(raw_ai_run),
                )
                .order_by("-created_at", "-id")
                .first()
            )

        ai_output = ai_run.effective_payload if ai_run else None
        context["ai_run"] = ai_run
        context["ai_output"] = ai_output if isinstance(ai_output, dict) else None
        context["ai_prompt"] = (
            str(ai_run.input_payload.get("user_prompt") or "").strip()
            if ai_run and isinstance(ai_run.input_payload, dict)
            else ""
        )
        return context


class GoalUpdateView(GoalFormMixin, UpdateView):
    template_name = "learning_insights/goals/form.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Edit Goal"
        context["form_mode"] = "edit"
        return context


class GoalAIPlannerView(InsightsBaseMixin, View):
    """
    Prompt-based planning flow embedded on the goal create page.

    This view handles both:
    - starting a new AI prompt plan run
    - continuing a run by answering clarification questions
    """

    def post(self, request, *args, **kwargs):
        preference = self.get_notification_preference()
        action = (request.POST.get("action") or "start").strip().lower()

        if action == "clear":
            run_id = (request.POST.get("run_id") or "").strip()
            if run_id.isdigit():
                run = (
                    AIPlanRun.objects.filter(
                        user=request.user,
                        kind=AIPlanRun.KIND_PROMPT_PLAN,
                        pk=int(run_id),
                    )
                    .order_by("-created_at", "-id")
                    .first()
                )
                if run is not None:
                    if run.applied_at is not None:
                        messages.info(request, "This plan was already applied and cannot be cleared from the planner.")
                        return HttpResponseRedirect(
                            _with_query_param(reverse("learning_insights:goal_create"), ai_run=str(run.id))
                        )
                    run.delete()
                    messages.success(request, "AI draft cleared.")
            return HttpResponseRedirect(reverse("learning_insights:goal_create"))

        if action == "continue":
            run_id = (request.POST.get("run_id") or "").strip()
            run = get_object_or_404(
                AIPlanRun.objects.filter(user=request.user),
                pk=run_id,
                kind=AIPlanRun.KIND_PROMPT_PLAN,
            )

            output = run.effective_payload if isinstance(run.effective_payload, dict) else {}
            current_questions = output.get("questions") if isinstance(output.get("questions"), list) else []

            previous = run.input_payload if isinstance(run.input_payload, dict) else {}
            previous_clarification = (
                previous.get("clarification") if isinstance(previous.get("clarification"), dict) else {}
            )
            previous_questions = (
                previous_clarification.get("previous_questions")
                if isinstance(previous_clarification.get("previous_questions"), list)
                else []
            )
            previous_answers = (
                previous_clarification.get("previous_answers")
                if isinstance(previous_clarification.get("previous_answers"), dict)
                else {}
            )

            answers: dict[str, Any] = {}
            for key, value in request.POST.items():
                if not key.startswith("answer_"):
                    continue
                qid = key.removeprefix("answer_").strip()
                if not qid:
                    continue
                answers[qid] = (value or "").strip()

            merged_questions = list(previous_questions) + list(current_questions)
            merged_answers = dict(previous_answers)
            merged_answers.update(answers)

            user_prompt = str(previous.get("user_prompt") or "").strip()
            if not user_prompt:
                user_prompt = (request.POST.get("prompt") or "").strip()

            new_run = generate_prompt_plan_run(
                user=request.user,
                preference=preference,
                user_prompt=user_prompt,
                previous_questions=merged_questions,
                previous_answers=merged_answers,
            )
        else:
            prompt_value = (request.POST.get("prompt") or "").strip()
            if not prompt_value:
                messages.error(request, "Describe what you want to plan first.")
                return HttpResponseRedirect(reverse("learning_insights:goal_create"))

            new_run = generate_prompt_plan_run(
                user=request.user,
                preference=preference,
                user_prompt=prompt_value,
            )

        if new_run.status == AIPlanRun.STATUS_SUCCESS:
            messages.success(request, "AI response generated. Review and apply if it looks good.")
        else:
            messages.error(request, f"AI planning failed: {new_run.summary_text or new_run.error_message}")

        return HttpResponseRedirect(
            _with_query_param(reverse("learning_insights:goal_create"), ai_run=str(new_run.id))
        )


class GoalAIApplyView(InsightsBaseMixin, View):
    def post(self, request, *args, **kwargs):
        run = get_object_or_404(
            AIPlanRun.objects.filter(user=request.user),
            pk=kwargs.get("pk"),
            kind=AIPlanRun.KIND_PROMPT_PLAN,
        )

        created = apply_prompt_plan_run(run=run)
        if created:
            messages.success(request, f"Applied AI plan: created {created} daily goal(s).")
            create_goal_batch_notification(
                user=request.user,
                created_count=created,
                source="ai_plan",
                reference_id=run.id,
            )
        else:
            messages.info(request, "Nothing applied. Ensure the AI output is a plan you can apply.")

        return HttpResponseRedirect(_with_query_param(reverse("learning_insights:goal_list"), li_bootstrap="1"))


class GoalDeleteView(GoalQuerysetMixin, DeleteView):
    template_name = "learning_insights/goals/confirm_delete.html"
    success_url = reverse_lazy("learning_insights:goal_list")

    def get_success_url(self):
        url = super().get_success_url()
        return _with_query_param(url, li_bootstrap="1")

    def form_valid(self, form):
        messages.success(self.request, "Goal deleted.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Delete Goal"
        return context


class GoalQuickActionView(GoalQuerysetMixin, View):
    """
    Minimal POST endpoint for common goal actions.

    Supported actions:
    - complete
    - carry_forward
    """

    def post(self, request, *args, **kwargs):
        goal = get_object_or_404(self.get_queryset(), pk=kwargs.get("pk"))
        action = (request.POST.get("action") or "").strip()
        today = timezone.localdate()

        if action == "complete":
            goal.current_value = goal.target_value
            goal.status = Goal.STATUS_COMPLETED
            goal.completed_at = timezone.now()
            goal.save(update_fields=["current_value", "status", "completed_at"])
            messages.success(request, "Goal marked as completed.")
        elif action == "carry_forward":
            if goal.period_type == Goal.PERIOD_DAILY:
                new_start = today + timedelta(days=1)
                new_due = new_start
            elif goal.period_type == Goal.PERIOD_WEEKLY:
                new_start = get_period_start(today + timedelta(days=7), "weekly")
                new_due = new_start + timedelta(days=6)
            elif goal.period_type == Goal.PERIOD_MONTHLY:
                current_month_start = today.replace(day=1)
                if current_month_start.month == 12:
                    new_start = current_month_start.replace(
                        year=current_month_start.year + 1,
                        month=1,
                    )
                else:
                    new_start = current_month_start.replace(
                        month=current_month_start.month + 1
                    )
                if new_start.month == 12:
                    next_month = new_start.replace(
                        year=new_start.year + 1, month=1, day=1
                    )
                elif new_start.month == 1 and new_start.year > today.year:
                    next_month = new_start.replace(month=2, day=1)
                else:
                    if new_start.month == 12:
                        next_month = new_start.replace(
                            year=new_start.year + 1, month=1, day=1
                        )
                    else:
                        next_month = new_start.replace(month=new_start.month + 1, day=1)
                new_due = next_month - timedelta(days=1)
            else:
                new_start = today
                new_due = max(goal.due_date, today + timedelta(days=7))

            goal.start_date = new_start
            goal.due_date = new_due
            goal.status = Goal.STATUS_NOT_STARTED
            if goal.target_type != Goal.TARGET_TASKS:
                goal.current_value = 0
            goal.completed_at = None
            goal.save(
                update_fields=[
                    "start_date",
                    "due_date",
                    "status",
                    "current_value",
                    "completed_at",
                ]
            )
            messages.success(request, "Goal carried forward.")
        else:
            messages.error(request, "Unknown goal action.")

        sync_goal_progress_for_user(request.user)
        return HttpResponseRedirect(
            _with_query_param(reverse("learning_insights:goal_list"), li_bootstrap="1")
        )


class NotificationPreferenceView(InsightsBaseMixin, UpdateView):
    model = NotificationPreference
    form_class = NotificationPreferenceForm
    template_name = "learning_insights/preferences/form.html"
    success_url = reverse_lazy("learning_insights:preferences")

    def get_object(self, queryset=None):
        return self.get_notification_preference()

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Notification preferences updated.")
        return response

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Preferences"
        context["subscription"] = get_subscription_for_user(user=self.request.user)
        return context


class NotificationCenterView(InsightsBaseMixin, ListView):
    model = InsightNotification
    template_name = "learning_insights/notifications/center.html"
    context_object_name = "notifications"
    paginate_by = 25

    def get_queryset(self) -> QuerySet[InsightNotification]:
        queryset = InsightNotification.objects.filter(user=self.request.user).order_by(
            "-scheduled_for", "-created"
        )

        category = (self.request.GET.get("category") or "").strip()
        unread_only = (self.request.GET.get("unread") or "").strip()

        if category:
            queryset = queryset.filter(category=category)
        if unread_only == "1":
            queryset = queryset.filter(read_at__isnull=True)

        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        context["page_title"] = "Notifications"
        context["selected_category"] = (self.request.GET.get("category") or "").strip()
        context["unread_only"] = (self.request.GET.get("unread") or "").strip()
        context["category_choices"] = InsightNotification.CATEGORY_CHOICES
        context["unread_count"] = InsightNotification.objects.filter(
            user=self.request.user,
            read_at__isnull=True,
            dismissed_at__isnull=True,
        ).count()
        context["category_count"] = (
            queryset.values_list("category", flat=True).distinct().count()
        )
        return context


class NotificationBootstrapView(LoginRequiredMixin, View):
    """
    Return lightweight notification payload for page-load toast display.
    """

    def get(self, request, *args, **kwargs):
        ensure_due_notifications(request.user)
        items = get_notification_payload(request.user, limit=4, mark_read=True)
        return JsonResponse({"items": items})


class NotificationMarkReadView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        notification = get_object_or_404(
            InsightNotification,
            user=request.user,
            pk=kwargs.get("pk"),
        )
        mark_notification_read(notification)

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "notification_id": notification.id})

        messages.success(request, "Notification marked as read.")
        return HttpResponseRedirect(
            request.META.get("HTTP_REFERER")
            or reverse("learning_insights:notification_center")
        )


class NotificationDismissView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        notification = get_object_or_404(
            InsightNotification,
            user=request.user,
            pk=kwargs.get("pk"),
        )
        dismiss_notification(notification)

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "notification_id": notification.id})

        messages.success(request, "Notification dismissed.")
        return HttpResponseRedirect(
            request.META.get("HTTP_REFERER")
            or reverse("learning_insights:notification_center")
        )


class NotificationMarkAllReadView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        notifications = InsightNotification.objects.filter(
            user=request.user,
            read_at__isnull=True,
            dismissed_at__isnull=True,
        )
        updated = mark_notifications_read(notifications)
        if updated:
            messages.success(request, "All notifications marked as read.")
        else:
            messages.info(request, "No unread notifications to update.")
        return HttpResponseRedirect(
            request.META.get("HTTP_REFERER")
            or reverse("learning_insights:notification_center")
        )


class TelegramConnectView(InsightsBaseMixin, TemplateView):
    template_name = "learning_insights/telegram/connect.html"

    def _ensure_connect_token(self):
        token = get_active_connect_token(user=self.request.user)
        if token is None:
            token = generate_connect_token(user=self.request.user)
        return token

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Telegram"
        context["bot_username"] = get_bot_username()
        context["connect_token"] = self._ensure_connect_token()
        context["subscription"] = get_subscription_for_user(user=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        action = (request.POST.get("action") or "").strip()

        if action == "regen_token":
            generate_connect_token(user=request.user)
            messages.success(request, "A new Telegram connect token was generated.")
        elif action == "queue_test":
            subscription = get_subscription_for_user(user=request.user)
            if subscription is None:
                messages.error(
                    request, "Connect Telegram first to receive a test message."
                )
            else:
                ok = send_notification(
                    user=request.user,
                    message="Test notification. Learning Insights is connected.",
                )
                if ok:
                    messages.success(request, "Test notification sent to Telegram.")
                else:
                    messages.error(
                        request,
                        "Unable to send Telegram message. Check TELEGRAM_BOT_TOKEN and your network connection.",
                    )
        elif action == "disconnect":
            subscription = get_subscription_for_user(user=request.user)
            if subscription is None:
                messages.info(request, "Telegram is not connected.")
            else:
                subscription.delete()
                messages.success(request, "Telegram disconnected.")
        else:
            messages.error(request, "Unknown action.")

        return HttpResponseRedirect(reverse("learning_insights:telegram_connect"))


class AIRunQuerysetMixin(InsightsBaseMixin):
    model = AIPlanRun

    def get_queryset(self) -> QuerySet[AIPlanRun]:
        return AIPlanRun.objects.filter(user=self.request.user).order_by("-created_at", "-id")


class AIReviewHubView(AIRunQuerysetMixin, TemplateView):
    template_name = "learning_insights/ai/review.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        runs = list(
            self.get_queryset()
            .filter(
                kind__in=[
                    AIPlanRun.KIND_WEEKLY_REVIEW,
                    AIPlanRun.KIND_DAILY_REVIEW,
                    AIPlanRun.KIND_IMPROVEMENT,
                    AIPlanRun.KIND_RECOVERY,
                ]
            )
            [:20]
        )
        context["page_title"] = "AI Review"
        context["runs"] = runs
        context["latest_run"] = runs[0] if runs else None
        context["subscription"] = get_subscription_for_user(user=self.request.user)
        return context


class AIReviewGenerateView(InsightsBaseMixin, View):
    def post(self, request, *args, **kwargs):
        preference = self.get_notification_preference()
        period = (request.POST.get("period") or "weekly").strip().lower()

        if period == "daily":
            run = generate_daily_review_run(user=request.user, preference=preference)
            label = "daily"
        elif period == "improvement":
            run = generate_improvement_run(user=request.user, preference=preference)
            label = "improvement"
        elif period == "recovery":
            run = generate_recovery_run(user=request.user, preference=preference)
            label = "recovery"
        else:
            run = generate_weekly_review_run(user=request.user, preference=preference)
            label = "weekly"

        if run.status == AIPlanRun.STATUS_SUCCESS:
            messages.success(
                request,
                f"AI {label} review generated and saved automatically.",
            )
        else:
            messages.error(request, f"AI review generation failed: {run.summary_text or run.error_message}")
        return HttpResponseRedirect(reverse("learning_insights:ai_run_detail", kwargs={"pk": run.id}))


class AIRunDetailView(AIRunQuerysetMixin, TemplateView):
    template_name = "learning_insights/ai/run_detail.html"
    SUMMARY_RUN_KINDS = {
        AIPlanRun.KIND_DAILY_REVIEW,
        AIPlanRun.KIND_WEEKLY_REVIEW,
        AIPlanRun.KIND_IMPROVEMENT,
        AIPlanRun.KIND_RECOVERY,
    }

    def dispatch(self, request, *args, **kwargs):
        self.run = get_object_or_404(self.get_queryset(), pk=kwargs.get("pk"))
        return super().dispatch(request, *args, **kwargs)

    def _is_prompt_plan(self) -> bool:
        return self.run.kind == AIPlanRun.KIND_PROMPT_PLAN

    def _is_summary_run(self) -> bool:
        return self.run.kind in self.SUMMARY_RUN_KINDS

    def _normalize_summary_items(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []

        items: list[str] = []
        for row in value[:8]:
            text = ""
            if isinstance(row, str):
                text = row.strip()
            elif isinstance(row, dict):
                preferred_keys = (
                    "title",
                    "summary",
                    "description",
                    "reason",
                    "why",
                    "action",
                    "value",
                )
                parts = [str(row.get(key) or "").strip() for key in preferred_keys]
                parts = [part for part in parts if part]
                if not parts:
                    parts = [str(raw or "").strip() for raw in row.values()]
                    parts = [part for part in parts if part]
                text = " - ".join(parts[:2]).strip()
            elif row is not None:
                text = str(row).strip()

            if text:
                items.append(text[:400])

        return items

    def _build_summary_view(self) -> dict[str, Any]:
        payload = self.run.effective_payload if isinstance(self.run.effective_payload, dict) else {}
        risk_level = str(payload.get("risk_level") or "").strip().lower()
        if risk_level not in {"low", "medium", "high"}:
            risk_level = ""

        return {
            "summary": str(payload.get("summary") or self.run.summary_text or "").strip(),
            "achievements": self._normalize_summary_items(payload.get("achievements")),
            "missed_targets": self._normalize_summary_items(payload.get("missed_targets")),
            "insights": self._normalize_summary_items(payload.get("insights")),
            "suggestions": self._normalize_summary_items(payload.get("suggestions")),
            "risk_level": risk_level,
        }

    def _build_prompt_plan_formset(self, *, data=None):
        courses = self.request.user.courses_joined.order_by("title")

        initial_rows: list[dict[str, Any]] = []
        payload = self.run.effective_payload
        if isinstance(payload, dict):
            plan = payload.get("plan")
            if isinstance(plan, list):
                for day in plan:
                    if not isinstance(day, dict):
                        continue
                    day_value = str(day.get("date") or "").strip()
                    try:
                        day_date = date.fromisoformat(day_value)
                    except ValueError:
                        continue

                    items = day.get("items")
                    if not isinstance(items, list):
                        continue
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        initial_rows.append(
                            {
                                "day": day_date,
                                "course": item.get("course_id") or None,
                                "minutes": item.get("minutes") or None,
                                "task": item.get("task") or "",
                                "notes": item.get("notes") or "",
                            }
                        )

        return PromptPlanItemFormSet(
            data=data,
            initial=initial_rows,
            prefix="items",
            courses=courses,
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["page_title"] = "AI Run"
        context["run"] = self.run

        is_prompt_plan = self._is_prompt_plan()
        is_summary_run = self._is_summary_run()
        context["is_prompt_plan"] = is_prompt_plan
        context["is_summary_run"] = is_summary_run
        context["is_payload_editable"] = not is_prompt_plan and not is_summary_run
        if is_prompt_plan:
            context["plan_formset"] = self._build_prompt_plan_formset()
        elif context["is_payload_editable"]:
            context["form"] = AIPlanRunEditForm(
                initial={
                    "edited_payload": self.run.effective_payload,
                }
            )
        if is_summary_run:
            context["summary_view"] = self._build_summary_view()

        if not is_summary_run:
            try:
                import json

                context["payload_pretty"] = json.dumps(
                    self.run.effective_payload,
                    indent=2,
                    ensure_ascii=False,
                )
            except Exception:
                context["payload_pretty"] = str(self.run.effective_payload)

        context["subscription"] = get_subscription_for_user(user=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        if self._is_summary_run():
            messages.info(
                request,
                "This AI summary is saved automatically and cannot be edited here.",
            )
            return HttpResponseRedirect(
                reverse("learning_insights:ai_run_detail", kwargs={"pk": self.run.id})
            )

        if self._is_prompt_plan():
            formset = self._build_prompt_plan_formset(data=request.POST)
            if not formset.is_valid():
                try:
                    import json

                    payload_pretty = json.dumps(
                        self.run.effective_payload, indent=2, ensure_ascii=False
                    )
                except Exception:
                    payload_pretty = str(self.run.effective_payload)
                return self.render_to_response(
                    {
                        "page_title": "AI Run",
                        "run": self.run,
                        "is_prompt_plan": True,
                        "is_summary_run": False,
                        "is_payload_editable": False,
                        "plan_formset": formset,
                        "payload_pretty": payload_pretty,
                        "subscription": get_subscription_for_user(user=request.user),
                    }
                )

            plan_by_day: dict[date, list[dict[str, Any]]] = {}
            for form in formset:
                cleaned = getattr(form, "cleaned_data", None) or {}
                if cleaned.get("DELETE"):
                    continue

                day_date = cleaned.get("day")
                task = str(cleaned.get("task") or "").strip()
                if not isinstance(day_date, date) or not task:
                    continue

                minutes = cleaned.get("minutes")
                try:
                    minutes_value = max(0, int(minutes or 0))
                except (TypeError, ValueError):
                    minutes_value = 0

                course = cleaned.get("course")
                course_id = getattr(course, "id", None) if course else None
                course_title = getattr(course, "title", "") if course else ""

                item_payload: dict[str, Any] = {
                    "task": task,
                    "minutes": minutes_value,
                    "notes": str(cleaned.get("notes") or "").strip(),
                }
                if course_id:
                    item_payload["course_id"] = int(course_id)
                    item_payload["course_title"] = str(course_title or "").strip()

                plan_by_day.setdefault(day_date, []).append(item_payload)

            plan_days: list[dict[str, Any]] = []
            for day_date in sorted(plan_by_day.keys()):
                plan_days.append(
                    {
                        "date": day_date.isoformat(),
                        "items": plan_by_day[day_date],
                    }
                )

            base_payload = self.run.effective_payload if isinstance(self.run.effective_payload, dict) else {}
            edited_payload = dict(base_payload)
            edited_payload["type"] = "plan"
            edited_payload["plan"] = plan_days
            if plan_days:
                period = edited_payload.get("period")
                if not isinstance(period, dict):
                    period = {}
                period["start"] = plan_days[0]["date"]
                period["end"] = plan_days[-1]["date"]
                edited_payload["period"] = period

            self.run.edited_payload = edited_payload
            self.run.save(update_fields=["edited_payload", "updated_at"])
            messages.success(request, "Plan updated.")
            return HttpResponseRedirect(
                reverse("learning_insights:ai_run_detail", kwargs={"pk": self.run.id}) + "#edit"
            )

        form = AIPlanRunEditForm(data=request.POST)
        if not form.is_valid():
            try:
                import json

                payload_pretty = json.dumps(self.run.effective_payload, indent=2, ensure_ascii=False)
            except Exception:
                payload_pretty = str(self.run.effective_payload)
            return self.render_to_response(
                {
                    "page_title": "AI Run",
                    "run": self.run,
                    "is_prompt_plan": False,
                    "is_summary_run": False,
                    "is_payload_editable": True,
                    "form": form,
                    "payload_pretty": payload_pretty,
                    "subscription": get_subscription_for_user(user=request.user),
                }
            )

        self.run.edited_payload = form.cleaned_data["edited_payload"] or {}
        self.run.save(update_fields=["edited_payload", "updated_at"])
        messages.success(request, "AI output updated.")
        return HttpResponseRedirect(reverse("learning_insights:ai_run_detail", kwargs={"pk": self.run.id}) + "#edit")


class AIRunApplyView(AIRunQuerysetMixin, View):
    def post(self, request, *args, **kwargs):
        run = get_object_or_404(self.get_queryset(), pk=kwargs.get("pk"))
        created = apply_prompt_plan_run(run=run)
        if created:
            messages.success(request, f"Applied plan: created {created} daily goal(s).")
            create_goal_batch_notification(
                user=request.user,
                created_count=created,
                source="ai_plan",
                reference_id=run.id,
            )
        else:
            messages.info(
                request,
                "Nothing applied. Ensure this is a successful AI plan run.",
            )
        return HttpResponseRedirect(reverse("learning_insights:ai_run_detail", kwargs={"pk": run.id}))
