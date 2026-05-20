"""

Route groups:
1) Instructor management routes
2) Module/content management routes
3) Public catalog routes
"""

from django.urls import path
from . import views


urlpatterns = [
    # -------------------------------
    # Instructor course management
    # -------------------------------
    path(
        "mine/",
        views.ManageCourseListView.as_view(),
        name="manage_course_list",
    ),
    path(
        "create/",
        views.CourseCreateView.as_view(),
        name="course_create",
    ),
    path(
        "<pk>/edit/",
        views.CourseUpdateView.as_view(),
        name="course_edit",
    ),
    path(
        "<pk>/delete/",
        views.CourseDeleteView.as_view(),
        name="course_delete",
    ),

    # -------------------------------
    # Module management for a course
    # -------------------------------
    path(
        "<pk>/module/",
        views.CourseModuleUpdateView.as_view(),
        name="course_module_update",
    ),
    path(
        "module/<int:module_id>/",
        views.ModuleContentListView.as_view(),
        name="module_content_list",
    ),

    # -------------------------------
    # Content CRUD inside a module
    # model_name is one of: text, video, image, file
    # -------------------------------
    path(
        "module/<int:module_id>/content/<str:model_name>/create/",
        views.ContentCreateUpdateView.as_view(),
        name="module_content_create",
    ),
    path(
        "module/<int:module_id>/content/<str:model_name>/<int:id>/",
        views.ContentCreateUpdateView.as_view(),
        name="module_content_update",
    ),
    path(
        "content/<int:id>/delete/",
        views.ContentDeleteView.as_view(),
        name="module_content_delete",
    ),

    # -------------------------------
    # AJAX ordering endpoints
    # -------------------------------
    path(
        "module/order/",
        views.ModuleOrderView.as_view(),
        name="module_order",
    ),
    path(
        "content/order/",
        views.ContentOrderview.as_view(),
        name="content_order",
    ),
    path(
        "motto/refresh/",
        views.refresh_daily_motto,
        name="motto_refresh",
    ),

    # -------------------------------
    # Public catalog routes
    # -------------------------------
    path(
        "home/",
        views.CourseListview.as_view(),
        name="course_list",
    ),
    path(
        "subject/<slug:subject>/",
        views.CourseListview.as_view(),
        name="course_list_subject",
    ),
    path(
        "<slug:slug>/",
        views.CourseDetailView.as_view(),
        name="course_detail",
    ),
]
