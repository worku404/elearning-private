from django.contrib import admin
from .models import Course, Module, Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    # Columns shown on the Subject list page
    list_display = ("title", "slug")

    # Auto-fill slug from title in the admin form
    prepopulated_fields = {"slug": ("title",)}


class ModuleInline(admin.StackedInline):
    # Show Module forms inside the Course admin page
    model = Module
    extra = 1  # Number of empty module forms to show by default


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order")
    list_filter = ("course",)
    search_fields = ("title", "course__title")
    ordering = ("course", "order", "id")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    # Columns shown on the Course list page
    list_display = ("title", "subject", "created")

    # Sidebar filters for quick narrowing
    list_filter = ("created", "subject")

    # Search box fields
    search_fields = ("title", "overview")

    # Auto-fill slug from title in the admin form
    prepopulated_fields = {"slug": ("title",)}

    # Allow editing related modules within Course admin
    inlines = [ModuleInline]
