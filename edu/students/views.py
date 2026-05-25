"""
Student-facing views:
- account registration
- course enrollment
- enrolled course list/detail
"""


# URL builder used for redirects after successful actions.
import json
import os
import mimetypes
import subprocess
import re
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from django.http import FileResponse, Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.contrib.contenttypes.models import ContentType
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from django.utils.cache import patch_cache_control, patch_response_headers
from django.utils import timezone
from django.core.cache import cache

# Auth helpers and login-protection mixin.
from django.contrib.auth import authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin

# Generic class-based views for create/form/list/detail pages.
from django.views.generic.edit import FormView
from django.views.generic.list import ListView
from django.views.generic import TemplateView, DetailView, View


# Local enrollment form and Course model.
from .forms import CourseEnrollForm
from courses.models import Content, Course, File, Image, Module, ContentSearchEntry, Video
from courses.search import search_content_entries
from .models import ContentProgress, CourseProgress, ModuleProgress
from .services import (add_time_spent, mark_module_completed, 
                       get_overall_progress, get_course_time_spent,
                        touch_user_presence, update_content_progress,
                        recompute_course_progress
                    )


import redis


r = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
)

VIDEO_CACHE_SECONDS = 60 * 60 * 24 * 7  # 7 days
PDF_CACHE_SECONDS = 60 * 60 * 24 * 7  # 7 days
PDF_SEARCH_CACHE_SECONDS = 60 * 60  # 1 hour


def _pdf_cache_key(prefix, user_id, file_id, suffix=""):
    return f"pdf:{prefix}:u{user_id}:f{file_id}:{suffix}"

def _course_progress_table_ready() -> bool:
    """
    Guard against runtime crashes when code is deployed before migrations run.

    Why this exists:
    - New code reads from CourseProgress.
    - If migration 0003 is not applied yet, querying that model raises:
      `ProgrammingError: relation "students_courseprogress" does not exist`.
    - This check lets pages render with a safe fallback until migrations are applied.
    """
    try:
        return CourseProgress._meta.db_table in connection.introspection.table_names()
    except (ProgrammingError, OperationalError):
        return False


class StudentEnrollCourseView(LoginRequiredMixin, FormView):
    # This form sends a selected Course object (hidden input).
    form_class = CourseEnrollForm

    # Temporary storage: filled in form_valid(), used by get_success_url().
    course = None

    def form_valid(self, form):
        # 1) Pull validated Course object from form.
        self.course = form.cleaned_data["course"]

        # 2) Add current user to course.students (ManyToMany relation).
        self.course.students.add(self.request.user)

        # 3) Continue FormView success flow.
        return super().form_valid(form)

    def get_success_url(self):
        # Redirect to detail page of the enrolled course.
        return reverse_lazy("student_course_detail", args=[self.course.id])


class StudentCourseListView(LoginRequiredMixin, ListView):
    # Base model for list.
    model = Course
    template_name = "students/course/list.html"
    context_object_name = "courses"

    def get_queryset(self):
        # Return only courses where current user is enrolled.
        qs = super().get_queryset()
        return qs.filter(students__in=[self.request.user])

    def get_context_data(self, **kwargs):
        """
        Attach persisted course progress fields to each course card.
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user
        courses = list(context["courses"])

        # Defensive fallback for environments where DB migration 0003 is pending.
        if not _course_progress_table_ready():
            for course in courses:
                course.student_progress_percent = 0.0
                course.student_completed = False
                course.student_last_module_id = None
            context["courses"] = courses
            return context

        try:
            progress_rows = {
                row.course_id: row
                for row in CourseProgress.objects.filter(user=user, course__in=courses)
            }
        except (ProgrammingError, OperationalError):
            # If schema and code become temporarily out of sync, keep page usable.
            progress_rows = {}

        for course in courses:
            row = progress_rows.get(course.id)
            if row is None:
                try:
                    row = recompute_course_progress(user, course)
                except (ProgrammingError, OperationalError):
                    row = None
            if row is None:
                course.student_progress_percent = 0.0
                course.student_completed = False
                course.student_last_accessed = None
                course.student_last_module_id = None 
                continue
            course.student_progress_percent = round(row.progress_percent, 2)
            course.student_completed = row.completed
            course.student_last_accessed = row.last_accessed
            course.student_last_module_id = row.last_module_id 

        # Order by most recently accessed (newest first).
        # Secondary sort keeps ordering stable/readable when last_accessed matches.
        courses.sort(
            key=lambda course: (
                -float(getattr(course.student_last_accessed, "timestamp", lambda: 0)() or 0),
                (course.title or "").lower(),
            )
        )

        context["courses"] = courses
        return context


class StudentCourseDetailView(LoginRequiredMixin, DetailView):
    model = Course
    template_name = "students/course/detail.html"

    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(students__in=[self.request.user])
    
    def get(self, request, *args, **kwargs):
        """
        Override to redirect unenrolled users to course enrollment page if course exists.
        
        Logic:
        - If user is enrolled: render course detail page (normal flow)
        - If course exists but user is NOT enrolled: redirect to public course page for enrollment
        - If course doesn't exist: show 404
        """
        pk = self.kwargs.get('pk')
        try:
            # Try to get course from enrolled courses (normal path)
            queryset = self.get_queryset()
            course = queryset.get(pk=pk)
            # User is enrolled, proceed normally
            return super().get(request, *args, **kwargs)
        except Course.DoesNotExist:
            # Course not found in enrolled list, check if it exists at all
            try:
                course = Course.objects.get(pk=pk)
                # Course exists but user is not enrolled
                # Redirect to the public course page where user can enroll
                public_course_url = reverse('course_detail', args=[course.slug])
                return redirect(public_course_url)
            except Course.DoesNotExist:
                # Course doesn't exist at all, raise 404
                raise Http404(f"No course found with id {pk}")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.object
        modules = list(course.modules.all())
        user = self.request.user

        if "module_id" in self.kwargs:
            module = get_object_or_404(Module, id=self.kwargs["module_id"], course=course)
        else:
             module = modules[0] if modules else None 

        # Load and attach per-module progress rows so the template can render module percentages.
        module_progress_rows = {
            row.module_id: row
            for row in ModuleProgress.objects.filter(user=user, course=course)
        }
        for module_item in modules:
            module_row = module_progress_rows.get(module_item.id)
            module_item.student_progress_percent = round(
                module_row.progress_percent if module_row else 0.0,
                2,
            )
            module_item.student_completed = bool(module_row.completed) if module_row else False

        # Persisted course completion/percentage row (created on demand if missing).
        course_progress = None
        if _course_progress_table_ready():
            try:
                course_progress = CourseProgress.objects.filter(user=user, course=course).first()
                if course_progress is None:
                    course_progress = recompute_course_progress(user, course)
            except (ProgrammingError, OperationalError):
                course_progress = None

        if course_progress is None:
            # Fallback when CourseProgress table is unavailable:
            # derive a temporary course percentage from existing module rows.
            total_modules = len(modules)
            accumulated_percent = 0.0
            completed_modules = 0
            for module_item in modules:
                module_row = module_progress_rows.get(module_item.id)
                if not module_row:
                    continue
                accumulated_percent += float(module_row.progress_percent or 0.0)
                if module_row.completed:
                    completed_modules += 1

            fallback_percent = 0.0
            fallback_completed = False
            if total_modules > 0:
                fallback_percent = max(0.0, min(100.0, accumulated_percent / total_modules))
                fallback_completed = completed_modules >= total_modules

            course_progress = SimpleNamespace(
                progress_percent=round(fallback_percent, 2),
                completed=fallback_completed,
            )
        elif _course_progress_table_ready():
            try:
                CourseProgress.objects.filter(id=course_progress.id).update(
                    last_accessed=timezone.now(),
                    last_module_id=module.id if module else None, 
                )
            except (ProgrammingError, OperationalError):
                pass

        # Build a concrete list of module contents, and attach content progress state.
        module_contents = list(module.contents.select_related("content_type")) if module else []
        content_progress_rows = {
            row.content_id: row
            for row in ContentProgress.objects.filter(
                user=user,
                content__in=module_contents,
            )
        }
        for content_item in module_contents:
            progress_row = content_progress_rows.get(content_item.id)
            content_item.student_progress_percent = round(
                progress_row.progress_percent if progress_row else 0.0,
                2,
            )
            content_item.student_completed = bool(progress_row.completed) if progress_row else False
            # For PDF resume support we expose the stored JSON position to the template.
            # Ensure expected keys exist to avoid template lookup errors.
            default_position = {
                "page": 1,
                "current_page": 1,
                "page_offset_ratio": 0,
                "doc_y_ratio": 0,
                "zoom": 0,
                "max_page_seen": 1,
            }
            if progress_row and isinstance(progress_row.last_position, dict):
                content_item.student_last_position = {
                    **default_position,
                    **progress_row.last_position,
                }
            else:
                content_item.student_last_position = default_position

        context["module"] = module
        context["modules"] = modules
        context["module_contents"] = module_contents
        context["course_time"] = get_course_time_spent(self.request.user, course)
        context["course_progress"] = course_progress
        context["course_progress_percent"] = round(course_progress.progress_percent, 2)
        context["course_completed"] = course_progress.completed
        context["current_course_id"] = course.id
        return context

class MarkModuleCompleteView(LoginRequiredMixin, View):
    def post(self, request, module_id):
        module = get_object_or_404(
            Module, 
            id=module_id,
            course__students=request.user,
            )

        module_progress, course_progress = mark_module_completed(request.user, module)

        return JsonResponse(
            {
                "status": "completed",
                "module_progress": {
                    "module_id": module.id,
                    "progress_percent": round(module_progress.progress_percent, 2),
                    "completed": module_progress.completed,
                },
                "course_progress": {
                    "course_id": module.course_id,
                    "progress_percent": round(course_progress.progress_percent, 2),
                    "completed": course_progress.completed,
                    "completed_at": (
                        course_progress.completed_at.isoformat()
                        if course_progress.completed_at
                        else None
                    ),
                },
            }
        )

class TrackTimeView(LoginRequiredMixin, View):
    def post(self, request, module_id):
        module = get_object_or_404(
            Module,
            id=module_id,
            course__students=request.user,
            
            )
        
        try:
            # Handle both standard POST and JSON/Beacon payloads
            seconds = int(request.POST.get('seconds', 0))
            
            if seconds > 0:
                add_time_spent(request.user, module, seconds)
                return JsonResponse({'status': 'tracked', 'seconds': seconds})
            
            return JsonResponse({'status': 'ignored', 'reason': '0 seconds'})
            
        except ValueError:
            return JsonResponse({'status': 'error', 'reason': 'Invalid seconds value'}, status=400)


class TrackContentProgressView(LoginRequiredMixin, View):
    def post(self, request, content_id):
        content = get_object_or_404(
            Content,
            id=content_id,
            module__course__students=request.user,
        )

        payload = {}
        if request.content_type and request.content_type.startswith("application/json"):
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                return JsonResponse(
                    {"status": "error", "reason": "Invalid JSON payload"},
                    status=400,
                )
        else:
            payload = request.POST.dict()

        kind = (payload.get("kind") or "").strip().lower()
        if not kind:
            model_name = content.content_type.model
            if model_name == "text":
                kind = "text"
            elif model_name == "file":
                file_obj = content.item
                filename = str(getattr(file_obj, "file", "") or "")
                if filename.lower().endswith(".pdf"):
                    kind = "pdf"
            elif model_name == "video":
                kind = "video"

        try:
            seconds_delta = int(payload.get("seconds_delta", 0))
        except (TypeError, ValueError):
            seconds_delta = 0

        try:
            result = update_content_progress(
                user=request.user,
                content=content,
                kind=kind,
                payload=payload,
                seconds_delta=seconds_delta,
            )
        except ValueError as exc:
            return JsonResponse({"status": "error", "reason": str(exc)}, status=400)

        content_progress = result["content_progress"]
        module_progress = result["module_progress"]
        course = content.module.course
        course_progress = result["course_progress"]

        return JsonResponse(
            {
                "status": "tracked",
                "content_progress": {
                    "id": content_progress.id,
                    "content_id": content.id,
                    "kind": content_progress.content_type,
                    "progress_percent": round(content_progress.progress_percent, 2),
                    "completed": content_progress.completed,
                    "seconds_spent": content_progress.seconds_spent,
                    "last_position": content_progress.last_position,
                },
                "module_progress": {
                    "module_id": module_progress.module_id,
                    "progress_percent": round(module_progress.progress_percent, 2),
                    "completed": module_progress.completed,
                },
                "course_progress": {
                    "course_id": course.id,
                    "progress_percent": result["course_progress_percent"],
                    "completed": course_progress.completed,
                    "completed_at": (
                        course_progress.completed_at.isoformat()
                        if course_progress.completed_at
                        else None
                    ),
                },
                "overall_progress": result["overall_progress_percent"],
                "completed_flags": {
                    "content": content_progress.completed,
                    "module": module_progress.completed,
                    "course": course_progress.completed,
                },
            }
        )


class StudentDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'students/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context['overall_progress'] = get_overall_progress(user)
        context['courses'] = user.courses_joined.all()

        return context


class DownloadModuleFileView(LoginRequiredMixin, View):
    """
    Serves a module file as an attachment for enrolled users.
    This avoids relying on direct /media URLs in production.
    """
    def get(self, request, file_id):
        file_type = ContentType.objects.get_for_model(File)
        content = get_object_or_404(
            Content,
            content_type=file_type,
            object_id=file_id,
            module__course__students=request.user,
        )
        file_obj = content.item

        if not file_obj or not file_obj.file:
            raise Http404("File not found.")

        filename = os.path.basename(file_obj.file.name)

        try:
            return FileResponse(
                file_obj.file.open("rb"),
                as_attachment=True,
                filename=filename,
            )
        except FileNotFoundError as exc:
            raise Http404("File not found.") from exc




class ModuleImageView(LoginRequiredMixin, View):
    """
    Serves module images only to enrolled users.
    This avoids relying on direct /media URLs in production.
    """
    def get(self, request, image_id):
        image_type = ContentType.objects.get_for_model(Image)
        content = get_object_or_404(
            Content,
            content_type=image_type,
            object_id=image_id,
            module__course__students=request.user,
        )
        image_obj = content.item

        if not image_obj or not image_obj.file:
            raise Http404("Image not found.")

        filename = os.path.basename(image_obj.file.name)

        try:
            return FileResponse(
                image_obj.file.open("rb"),
                filename=filename,
            )
        except FileNotFoundError as exc:
            raise Http404("Image not found.") from exc


def _parse_byte_range(range_header: str | None, file_size: int):
    if not range_header:
        return None
    if not range_header.startswith("bytes="):
        return None

    range_spec = range_header.replace("bytes=", "", 1).split(",")[0].strip()
    if "-" not in range_spec:
        return None

    start_str, end_str = range_spec.split("-", 1)
    try:
        if start_str == "":
            # Suffix range: "-500" means last 500 bytes
            suffix_len = int(end_str)
            if suffix_len <= 0:
                return None
            start = max(file_size - suffix_len, 0)
            end = file_size - 1
        else:
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
            if start < 0:
                return None
            end = min(end, file_size - 1)
        if start > end or start >= file_size:
            return None
        return start, end
    except (TypeError, ValueError):
        return None


def _stream_file_range(file_obj, start: int, length: int, chunk_size: int = 1024 * 512):
    file_obj.seek(start)
    remaining = length
    try:
        while remaining > 0:
            chunk = file_obj.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        try:
            file_obj.close()
        except Exception:
            pass


class ModuleVideoStreamView(LoginRequiredMixin, View):
    """
    Stream module videos with HTTP Range support to allow seeking.
    """
    def get(self, request, video_id):
        video_type = ContentType.objects.get_for_model(Video)
        content = get_object_or_404(
            Content,
            content_type=video_type,
            object_id=video_id,
            module__course__students=request.user,
        )
        video_obj = content.item

        if not video_obj or not video_obj.file:
            raise Http404("Video not found.")

        try:
            video_obj.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404("Video not found.") from exc

        file_obj = video_obj.file.file
        file_size = getattr(video_obj.file, "size", None) or 0
        content_type, _ = mimetypes.guess_type(video_obj.file.name)
        if not content_type:
            content_type = "application/octet-stream"

        range_header = request.headers.get("Range") or request.META.get("HTTP_RANGE")
        byte_range = _parse_byte_range(range_header, file_size)

        if byte_range:
            start, end = byte_range
            length = end - start + 1
            response = StreamingHttpResponse(
                _stream_file_range(file_obj, start, length),
                status=206,
                content_type=content_type,
            )
            response["Content-Length"] = str(length)
            response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        else:
            response = FileResponse(file_obj, content_type=content_type)
            response["Content-Length"] = str(file_size)

        response["Accept-Ranges"] = "bytes"
        patch_response_headers(response, cache_timeout=VIDEO_CACHE_SECONDS)
        return response

# pdf previw page

@method_decorator(xframe_options_exempt, name="dispatch")
class ModuleFilePreviewView(LoginRequiredMixin, View):
    """
    Serve module file inline (for PDF browser preview) to enrolled users.
    """
    def get(self, request, file_id):
        file_type = ContentType.objects.get_for_model(File)
        content = get_object_or_404(
            Content,
            content_type=file_type,
            object_id=file_id,
            module__course__students=request.user,
        )
        file_obj = content.item

        if not file_obj or not file_obj.file:
            raise Http404("File not found.")

        filename = os.path.basename(file_obj.file.name)
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "application/octet-stream"

        try:
            response = FileResponse(
                file_obj.file.open("rb"),
                as_attachment=False,
                filename=filename,
                content_type=content_type,
            )
        except FileNotFoundError as exc:
            raise Http404("File not found.") from exc

        # Force inline rendering in browser viewers (PDF/image support).
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        patch_cache_control(response, private=True, max_age=PDF_CACHE_SECONDS)
        return response


class ModuleFileSearchView(LoginRequiredMixin, View):
    """
    Search within an enrolled PDF using the server-side ContentSearchEntry index.
    """
    def get(self, request, file_id):
        query = (request.GET.get("q") or "").strip()
        if not query:
            return JsonResponse({"query": "", "total_matches": 0, "matches": []})

        file_type = ContentType.objects.get_for_model(File)
        content = get_object_or_404(
            Content,
            content_type=file_type,
            object_id=file_id,
            module__course__students=request.user,
        )
        file_obj = content.item

        indexed_at = getattr(file_obj, "pdf_indexed_at", None) if file_obj else None
        cache_suffix = f"{query.lower()}:{indexed_at.isoformat() if indexed_at else 'none'}"
        cache_key = _pdf_cache_key("search", request.user.id, file_id, cache_suffix)
        cached = cache.get(cache_key)
        if cached is not None:
            return JsonResponse(cached)

        qs = ContentSearchEntry.objects.filter(content=content, page_number__isnull=False)
        results = list(search_content_entries(qs, query)[:500])

        page_map = {}
        for row in results:
            page = int(row.page_number or 1)
            document = row.document or ""
            match_count = len(re.findall(re.escape(query), document, flags=re.IGNORECASE))
            if page not in page_map:
                page_map[page] = {
                    "page": page,
                    "count": 0,
                    "snippet": "",
                }
            page_map[page]["count"] += max(1, match_count) if document else 1
            if not page_map[page]["snippet"] and document:
                snippet = document[:160]
                if len(document) > 160:
                    snippet = f"{snippet}…"
                page_map[page]["snippet"] = snippet

        matches = [page_map[key] for key in sorted(page_map.keys())]
        total_matches = sum(item["count"] for item in matches)
        payload = {
            "query": query,
            "total_matches": total_matches,
            "matches": matches,
        }
        cache.set(cache_key, payload, PDF_SEARCH_CACHE_SECONDS)
        return JsonResponse(payload)


class ModuleFilePageTextView(LoginRequiredMixin, View):
    """
    Return indexed PDF page text for on-demand highlighting.
    """
    def get(self, request, file_id):
        pages_param = (request.GET.get("pages") or "").strip()
        if not pages_param:
            return JsonResponse({"pages": {}}, status=400)

        pages = []
        for token in pages_param.split(","):
            token = token.strip()
            if token.isdigit():
                pages.append(int(token))
        if not pages:
            return JsonResponse({"pages": {}}, status=400)

        file_type = ContentType.objects.get_for_model(File)
        content = get_object_or_404(
            Content,
            content_type=file_type,
            object_id=file_id,
            module__course__students=request.user,
        )
        file_obj = content.item

        indexed_at = getattr(file_obj, "pdf_indexed_at", None) if file_obj else None
        cache_suffix = f"{','.join(str(page) for page in pages)}:{indexed_at.isoformat() if indexed_at else 'none'}"
        cache_key = _pdf_cache_key("page-text", request.user.id, file_id, cache_suffix)
        cached = cache.get(cache_key)
        if cached is not None:
            return JsonResponse(cached)

        rows = (
            ContentSearchEntry.objects.filter(content=content, page_number__in=pages)
            .values_list("page_number", "document")
        )
        page_map = {int(page): (doc or "") for page, doc in rows}
        payload = {"pages": page_map}
        cache.set(cache_key, payload, PDF_SEARCH_CACHE_SECONDS)
        return JsonResponse(payload)


# Online count
class PresencePingView(LoginRequiredMixin, View):
    def post(self, request):
        online_count = touch_user_presence(request.user.id)
        return JsonResponse({"online_count": online_count})
    
