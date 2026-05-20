from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import path

from .models import ContentProgress, CourseProgress, ModuleProgress
from .services import recompute_course_progress, recompute_module_progress


@admin.register(CourseProgress)
class CourseProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "progress_percent", "completed", "completed_at", "last_accessed")
    list_filter = ("completed", "course")
    search_fields = ("user__username", "course__title")


@admin.register(ModuleProgress)
class ModuleProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "module", "progress_percent", "completed", "time_spent", "last_accessed")
    list_filter = ("completed", "course")
    search_fields = ("user__username", "module__title", "course__title")


@admin.register(ContentProgress)
class ContentProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "course", "module", "content", "content_type", "progress_percent", "completed", "updated")
    list_filter = ("content_type", "completed", "course")
    search_fields = ("user__username", "course__title", "module__title", "content__id")
    change_form_template = "admin/students/contentprogress/change_form.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/reset-progress/",
                self.admin_site.admin_view(self.reset_progress_view),
                name="students_contentprogress_reset",
            ),
        ]
        return custom_urls + urls

    def reset_progress_view(self, request, object_id):
        progress = get_object_or_404(ContentProgress, pk=object_id)
        if not self.has_change_permission(request, progress):
            raise PermissionDenied

        progress.progress_percent = 0.0
        progress.completed = False
        progress.seconds_spent = 0
        progress.last_position = {}
        progress.save(
            update_fields=[
                "progress_percent",
                "completed",
                "seconds_spent",
                "last_position",
                "updated",
            ]
        )

        # Keep module/course progress in sync after reset.
        try:
            recompute_module_progress(progress.user, progress.module)
            recompute_course_progress(progress.user, progress.course)
        except Exception:
            # Avoid admin crashes if recompute fails.
            pass

        messages.success(request, "Progress reset to the beginning.")
        return redirect("admin:students_contentprogress_change", object_id)
