from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import EmailOTP
from courses.models import Course


admin.site.site_header = "NextGen Academy Administration"
admin.site.site_title = "NextGen Academy Admin"
admin.site.index_title = "Welcome to NextGen Academy"

# @admin.register(EmailOTP)
# class EmailOTPAdmin(admin.ModelAdmin):
#     list_display = ("user", "attempts", "expires_at", "last_sent_at")
#     list_filter = ("attempts", "expires_at")
#     search_fields = ("user__email", "user__username")
#     readonly_fields = ("expires_at", "last_sent_at")

#     fieldsets = (
#         ("User", {"fields": ("user",)}),
#         ("OTP Details", {"fields": ("expires_at", "attempts", "last_sent_at")}),
#     )

#     def has_add_permission(self, request):
#         return False


# Unregister Django's default User admin so we can add our custom button/action
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """
    Custom User admin with:
    1. A button on the user change page to enroll that user in all courses.
    2. A list action to enroll multiple selected users in all courses.
    """

    change_form_template = "admin/auth/user/change_form.html"

    actions = ["enroll_selected_users_to_all_courses"]

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            path(
                "<int:user_id>/enroll-all-courses/",
                self.admin_site.admin_view(self.enroll_user_to_all_courses),
                name="auth_user_enroll_all_courses",
            ),
        ]

        return custom_urls + urls

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        """
        Pass custom button URL to the template.
        """
        extra_context = extra_context or {}

        if object_id:
            enroll_url = reverse(
                "admin:auth_user_enroll_all_courses",
                args=[object_id],
            )
            extra_context["enroll_all_courses_url"] = enroll_url
            extra_context["show_enroll_all_courses_button"] = True
        else:
            extra_context["show_enroll_all_courses_button"] = False

        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context,
        )

    def enroll_user_to_all_courses(self, request, user_id):
        """
        Enroll one user in all available courses.
        This is called when the admin button is clicked.
        """
        if request.method != "POST":
            messages.error(request, "Invalid request method.")
            return redirect("admin:auth_user_change", user_id)

        user = get_object_or_404(User, pk=user_id)

        all_courses = Course.objects.all()
        total_courses = all_courses.count()

        if total_courses == 0:
            messages.warning(request, "There are no courses available.")
            return redirect("admin:auth_user_change", user_id)

        already_enrolled_count = user.courses_joined.count()

        # Add the user to all courses.
        # ManyToMany add() is safe; it will not duplicate existing enrollments.
        user.courses_joined.add(*all_courses)

        new_enrolled_count = user.courses_joined.count()
        added_count = new_enrolled_count - already_enrolled_count

        if added_count > 0:
            messages.success(
                request,
                f"{user.username} was successfully enrolled in {added_count} new course(s). "
                f"Total enrolled courses: {new_enrolled_count}."
            )
        else:
            messages.info(
                request,
                f"{user.username} is already enrolled in all {total_courses} course(s)."
            )

        return redirect("admin:auth_user_change", user_id)

    @admin.action(description="Enroll selected users in all courses")
    def enroll_selected_users_to_all_courses(self, request, queryset):
        """
        Optional bulk admin action from the Users list page.
        Select many users, choose this action, and enroll them all.
        """
        all_courses = Course.objects.all()
        total_courses = all_courses.count()

        if total_courses == 0:
            self.message_user(
                request,
                "There are no courses available.",
                level=messages.WARNING,
            )
            return

        affected_users = 0

        for user in queryset:
            before_count = user.courses_joined.count()
            user.courses_joined.add(*all_courses)
            after_count = user.courses_joined.count()

            if after_count > before_count:
                affected_users += 1

        self.message_user(
            request,
            f"Selected users processed successfully. "
            f"{affected_users} user(s) received new course enrollment(s). "
            f"Each user can be enrolled in up to {total_courses} course(s).",
            level=messages.SUCCESS,
        )