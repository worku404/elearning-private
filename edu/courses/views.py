"""

Main view layer for:
1) Public course browsing (catalog + course detail)
2) Instructor management (course/module/content CRUD)
3) AJAX ordering for modules and content
"""

# Redirect URL builder used by class-based views after successful actions.
from django.urls import reverse_lazy

# Core class-based views.
from django.views.generic.base import TemplateResponseMixin, View
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.views.generic.edit import CreateView, UpdateView, DeleteView

# Request/response helpers.
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404, JsonResponse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_http_methods
from django.db.models.functions import Lower

# Auth and permission guards.
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

# ORM and dynamic-form helpers.
from django.db.models import Count
from django.apps import apps
from django.forms.models import modelform_factory

# Django cache API (Redis/Memcache/local depending on settings).
from django.core.cache import cache

# Third-party helpers for JSON endpoints.
from braces.views import CsrfExemptMixin, JsonRequestResponseMixin

# Local models/forms.
from .models import Course, Subject, Module, Content, ContentSearchEntry
from .forms import ModuleFormSet
from .search import search_courses, search_content_entries
from .motto import get_daily_motto
from notes.models import NoteSearchIndex
from notes.search import search_notes
from students.forms import CourseEnrollForm


# Shared cache duration for public course list data.
COURSE_LIST_CACHE_TTL = 60 * 60 * 24 * 7 # 7 days
SEARCH_CONTENT_LIMIT = 40
SEARCH_COURSE_LIMIT = 20
SEARCH_NOTE_LIMIT = 40


# -------------------------------------------------------------------
# Public views (student/visitor facing)
# -------------------------------------------------------------------


def front_door(request, *args, **kwargs):
    """
    Public entry point for the site.

    Anonymous visitors see the marketing landing page.
    Authenticated users continue straight into the course home page.
    """
    if request.user.is_authenticated:
        return redirect("course_list")

    return render(request, "courses/landing.html")

class CourseListview(TemplateResponseMixin, View):
    """
    Public catalog page.
    Data flow:
    - Try cache for subjects + courses
    - If cache miss, query DB and store in cache
    - Render list template with filtering by optional subject slug
    """
    model = Course
    template_name = "courses/course/list.html"

    def get(self, request, subject=None):
        current_subject = None
        query = (request.GET.get("q") or "").strip()
        enrolled_course_ids = []
        if request.user.is_authenticated:
            enrolled_course_ids = list(
                request.user.courses_joined.values_list("id", flat=True)
            )

        # 1) Subjects sidebar (with number of courses per subject).
        if settings.DEBUG:
            subjects = Subject.objects.annotate(total_courses=Count("courses"))
        else:
            subjects = cache.get("all_subjects")
            if subjects is None:
                subjects = Subject.objects.annotate(total_courses=Count("courses"))
                cache.set("all_subjects", subjects, COURSE_LIST_CACHE_TTL)

        # 2) Base queryset for courses (with number of modules per course).
        all_courses = Course.objects.select_related("subject", "owner").annotate(
            total_modules=Count("modules")
        )

        # 3) Optional filtering by subject slug from URL.
        if subject:
            current_subject = get_object_or_404(Subject, slug=subject)

        # 4) Search path bypasses cached querysets so ranking runs in PostgreSQL.
        if query:
            courses = all_courses
            if current_subject:
                courses = courses.filter(subject=current_subject)
            courses = search_courses(courses, query)
        elif current_subject:
            if settings.DEBUG:
                courses = all_courses.filter(subject=current_subject)
            else:
                cache_key = f"subject_{current_subject.id}_courses"
                courses = cache.get(cache_key)
                if courses is None:
                    courses = all_courses.filter(subject=current_subject)
                    cache.set(cache_key, courses, COURSE_LIST_CACHE_TTL)
        else:
            if settings.DEBUG:
                courses = all_courses
            else:
                courses = cache.get("all_courses")
                if courses is None:
                    courses = all_courses
                    cache.set("all_courses", courses, COURSE_LIST_CACHE_TTL)

        # 5) Render page context used by courses/course/list.html.
        return self.render_to_response(
            {
                "subjects": subjects,
                "subject": current_subject,
                "courses": courses,
                "query": query,
                "enrolled_course_ids": enrolled_course_ids,
            }
        )


class SearchResultsView(TemplateResponseMixin, View):
    """
    Global search page for courses, course contents, and notes.
    """
    template_name = "courses/search/results.html"

    def get(self, request):
        query = (request.GET.get("q") or "").strip()

        course_results = []
        content_results = []
        note_results = []
        enrolled_course_ids = []
        if request.user.is_authenticated:
            enrolled_course_ids = list(
                request.user.courses_joined.values_list("id", flat=True)
            )

        if query:
            course_qs = Course.objects.select_related("subject", "owner").annotate(
                total_modules=Count("modules")
            )
            course_results = list(search_courses(course_qs, query)[:SEARCH_COURSE_LIMIT])

            if request.user.is_authenticated:
                content_qs = (
                    ContentSearchEntry.objects.select_related("course", "module", "content")
                    .filter(course__students=request.user)
                )
                content_results = list(
                    search_content_entries(content_qs, query)[:SEARCH_CONTENT_LIMIT]
                )

                note_qs = (
                    NoteSearchIndex.objects.select_related("note")
                    .prefetch_related("note__tags")
                    .filter(note__user=request.user)
                )
                note_results = list(
                    search_notes(note_qs, query)[:SEARCH_NOTE_LIMIT]
                )

        return self.render_to_response(
            {
                "query": query,
                "content_results": content_results,
                "course_results": course_results,
                "note_results": note_results,
                "enrolled_course_ids": enrolled_course_ids,
            }
        )


class CourseDetailView(DetailView):
    """
    Public single-course page.
    Adds hidden enrollment form into template context.
    """
    model = Course
    template_name = "courses/course/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Pre-fill hidden course field so POST enroll endpoint knows selected course.
        context["enroll_form"] = CourseEnrollForm(initial={"course": self.object})
        return context


# -------------------------------------------------------------------
# Shared owner mixins (used by instructor management views)
# -------------------------------------------------------------------

class OwnerMixin:
    """
    Restricts queryset to objects owned by logged-in user.
    Used for list/update/delete safety.
    """
    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)


class OwnerEditMixin:
    """
    Forces object.owner to current user during create/update.
    Prevents client-side owner spoofing.
    """
    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class OwnerCourseMixin(OwnerMixin, LoginRequiredMixin, PermissionRequiredMixin):
    """
    Base config for Course CRUD views.
    """
    model = Course
    fields = ["subject", "title", "slug", "overview"]
    success_url = reverse_lazy("manage_course_list")


class OwnerCourseEditMixin(OwnerCourseMixin, OwnerEditMixin):
    """
    Shared template for create/update course forms.
    """
    template_name = "courses/manage/course/form.html"


# -------------------------------------------------------------------
# Instructor course CRUD
# -------------------------------------------------------------------

class ManageCourseListView(OwnerCourseMixin, ListView):
    """
    Instructor dashboard listing only their own courses.
    """
    template_name = "courses/manage/course/list.html"
    permission_required = "courses.view_course"
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.annotate(
            title_lower=Lower('title')
            ).order_by('title_lower') 


class CourseCreateView(OwnerCourseEditMixin, CreateView):
    """
    Create course; owner set automatically in OwnerEditMixin.
    """
    permission_required = "courses.add_course"


class CourseUpdateView(OwnerCourseEditMixin, UpdateView):
    """
    Update course; queryset already restricted to current owner.
    """
    permission_required = "courses.change_course"


class CourseDeleteView(OwnerCourseMixin, DeleteView):
    """
    Delete course; only owner can reach object via restricted queryset.
    """
    template_name = "courses/manage/course/delete.html"
    permission_required = "courses.delete_course"


# -------------------------------------------------------------------
# Instructor module management
# -------------------------------------------------------------------

class CourseModuleUpdateView(TemplateResponseMixin, View):
    """
    Edit module formset for one course.
    Data flow:
    - dispatch(): load owned course once
    - GET: show module formset
    - POST: validate/save module formset
    """
    template_name = "courses/manage/module/formset.html"
    course = None

    def dispatch(self, request, *args, **kwargs):
        self.course = get_object_or_404(
            Course,
            id=kwargs["pk"],
            owner=request.user,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_formset(self, data=None):
        return ModuleFormSet(instance=self.course, data=data)

    def get(self, request, *args, **kwargs):
        formset = self.get_formset()
        return self.render_to_response({"course": self.course, "formset": formset})

    def post(self, request, *args, **kwargs):
        formset = self.get_formset(data=request.POST)
        if formset.is_valid():
            formset.save()
            return redirect("manage_course_list")
        return self.render_to_response({"course": self.course, "formset": formset})


class ModuleContentListView(TemplateResponseMixin, View):
    """
    Shows all content blocks inside one module.
    """
    template_name = "courses/manage/module/content_list.html"

    def get(self, request, module_id):
        module = get_object_or_404(
            Module,
            id=module_id,
            course__owner=request.user,
        )
        return self.render_to_response({"module": module})


# -------------------------------------------------------------------
# Instructor content CRUD (Text / Video / Image / File)
# -------------------------------------------------------------------

class ContentCreateUpdateView(TemplateResponseMixin, View):
    """
    Handles create and update for content item models dynamically.
    model_name in URL decides which model is used: text/video/image/file.
    """
    template_name = "courses/manage/content/form.html"
    module = None
    model = None
    obj = None

    def get_model(self, model_name):
        # Whitelist to block arbitrary model access from URL.
        allowed = {"text", "video", "image", "file"}
        if model_name not in allowed:
            return None
        return apps.get_model(app_label="courses", model_name=model_name)

    def get_form(self, model, *args, **kwargs):
        # Build ModelForm on the fly for the resolved model class.
        FormClass = modelform_factory(
            model,
            exclude=["owner", "order", "created", "updated"],
        )
        return FormClass(*args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        """
        Shared preload before GET/POST:
        - module lookup with ownership check
        - content model resolution from URL
        - existing object fetch for update mode
        """
        module_id = kwargs.get("module_id")
        model_name = kwargs.get("model_name")
        object_id = kwargs.get("id")

        self.module = get_object_or_404(
            Module,
            id=module_id,
            course__owner=request.user,
        )

        self.model = self.get_model(model_name)
        if self.model is None:
            raise Http404("Unsupported content type")

        if object_id is not None:
            self.obj = get_object_or_404(
                self.model,
                id=object_id,
                owner=request.user,
            )

        return super().dispatch(request, *args, **kwargs)

    def get(self, request, module_id, model_name, id=None):
        # Empty form for create mode, prefilled form for update mode.
        form = self.get_form(self.model, instance=self.obj)
        return self.render_to_response({"form": form, "object": self.obj})

    def post(self, request, module_id, model_name, id=None):
        form = self.get_form(
            self.model,
            instance=self.obj,
            data=request.POST,
            files=request.FILES,
        )

        if form.is_valid():
            # Force owner server-side.
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.save()

            # Create Content relation only on create.
            if id is None:
                Content.objects.create(module=self.module, item=obj)

            return redirect("module_content_list", self.module.id)

        return self.render_to_response({"form": form, "object": self.obj})


class ContentDeleteView(View):
    """
    Deletes content relation + underlying item (Text/Video/Image/File).
    """
    def post(self, request, id):
        content = get_object_or_404(
            Content,
            id=id,
            module__course__owner=request.user,
        )
        module = content.module
        content.item.delete()
        content.delete()
        return redirect("module_content_list", module.id)


# -------------------------------------------------------------------
# AJAX ordering endpoints
# -------------------------------------------------------------------

class ModuleOrderView(CsrfExemptMixin, JsonRequestResponseMixin, View):
    """
    Receives JSON like {"module_id": new_order, ...} and updates module order.
    """
    def post(self, request):
        for id, order in self.request_json.items():
            Module.objects.filter(
                id=id,
                course__owner=request.user,
            ).update(order=order)
        return self.render_json_response({"saved": "OK"})


class ContentOrderview(CsrfExemptMixin, JsonRequestResponseMixin, View):
    """
    Receives JSON like {"content_id": new_order, ...} and updates content order.
    (Name kept as-is to avoid breaking existing URL references.)
    """
    def post(self, request):
        for id, order in self.request_json.items():
            Content.objects.filter(
                id=id,
                module__course__owner=request.user,
            ).update(order=order)
        return self.render_json_response({"saved": "OK"})


@require_http_methods(["GET", "POST"])
@login_required
def refresh_daily_motto(request):
    motto_data = get_daily_motto(force_refresh=True)
    response = JsonResponse({"motto": motto_data})
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response
