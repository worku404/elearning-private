from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Func
from django.template.loader import render_to_string

from .fields import OrderField


class Subject(models.Model):
    # Human-readable subject name (e.g., "Mathematics")
    title = models.CharField(max_length=200)

    # URL-safe unique identifier (e.g., "mathematics")
    slug = models.SlugField(max_length=200, unique=True)

    class Meta:
        # Default order: A-Z by title
        ordering = ["title"]

    def __str__(self) -> str:
        # Display subject title in admin/shell
        return self.title


class Course(models.Model):
    # Creator of the course; deleting user deletes their courses
    owner = models.ForeignKey(
        User,
        related_name="courses_created",
        on_delete=models.CASCADE,
    )

    # Subject this course belongs to; deleting subject deletes its courses
    subject = models.ForeignKey(
        Subject,
        related_name="courses",
        on_delete=models.CASCADE,
    )
    students = models.ManyToManyField(
        User,
        related_name="courses_joined",
        blank=True,
    )
    # Core course information
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    overview = models.TextField()

    # Timestamp set once when course is created
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Default order: newest course first
        ordering = ["-created"]

    def __str__(self) -> str:
        # Display course title in admin/shell
        return self.title


class CourseSearchIndex(models.Model):
    # One denormalized search document per course.
    course = models.OneToOneField(
        Course,
        related_name="search_index",
        on_delete=models.CASCADE,
    )
    document = models.TextField(blank=True, default="")
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            GinIndex(
                SearchVector(
                    Func(
                        F("document"),
                        function="immutable_unaccent",
                        output_field=models.TextField(),
                    ),
                    config="simple",
                ),
                name="course_idx_doc_tsv_gin",
            ),
            GinIndex(
                fields=["document"],
                opclasses=["gin_trgm_ops"],
                name="course_idx_doc_trgm_gin",
            ),
        ]

    def __str__(self) -> str:
        return f"SearchIndex(course={self.course_id})"


class ContentSearchEntry(models.Model):
    # Each row represents a searchable unit of content (or a PDF page).
    content = models.ForeignKey(
        "Content",
        related_name="search_entries",
        on_delete=models.CASCADE,
    )
    course = models.ForeignKey(
        "Course",
        related_name="content_search_entries",
        on_delete=models.CASCADE,
    )
    module = models.ForeignKey(
        "Module",
        related_name="content_search_entries",
        on_delete=models.CASCADE,
    )
    # Cache the content model name (text/video/image/file).
    kind = models.CharField(max_length=24)
    # Cache the content title for display.
    item_title = models.CharField(max_length=250, blank=True, default="")
    # Searchable document text (plain text).
    document = models.TextField(blank=True, default="")
    # Optional page number when the entry maps to a PDF page.
    page_number = models.PositiveIntegerField(null=True, blank=True)
    # Auto-updated timestamp for ranking/maintenance.
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            GinIndex(
                SearchVector(
                    Func(
                        F("document"),
                        function="immutable_unaccent",
                        output_field=models.TextField(),
                    ),
                    config="simple",
                ),
                name="content_idx_doc_tsv_gin",
            ),
            GinIndex(
                fields=["document"],
                opclasses=["gin_trgm_ops"],
                name="content_idx_doc_trgm_gin",
            ),
            models.Index(
                fields=["course", "module", "content"],
                name="content_idx_course_module",
            ),
            models.Index(
                fields=["kind", "page_number"],
                name="content_idx_kind_page",
            ),
        ]

    def __str__(self) -> str:
        label = f"content={self.content_id}"
        if self.page_number:
            label = f"{label}, page={self.page_number}"
        return f"ContentSearchEntry({label})"


class Module(models.Model):
    # Module belongs to a course; deleting course deletes its modules
    course = models.ForeignKey(
        Course,
        related_name="modules",
        on_delete=models.CASCADE,
    )

    # Module details
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)  # optional field
    order = OrderField(blank=True, for_fields=["course"])

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        # Display module title and order in admin/shell
        return f"{self.order}. {self.title}"


class Content(models.Model):
    # The module this content block belongs to.
    # related_name='contents' allows: module.contents.all()
    module = models.ForeignKey(
        "Module",
        related_name="contents",
        on_delete=models.CASCADE,
    )

    # Stores which model this content points to (e.g., Text, Video, Image, File).
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={
            "model__in": ("text", "video", "image", "file"),
        },
    )

    # Stores the primary key of the target object in the selected model table.
    object_id = models.PositiveIntegerField()

    # Virtual relation that combines content_type + object_id.
    # Example: if content_type=Video and object_id=7, item returns Video(id=7).
    item = GenericForeignKey("content_type", "object_id")

    order = OrderField(blank=True, for_fields=["module"])

    class Meta:
        ordering = ["order"]


class ItemBase(models.Model):
    # Owner of this learning item (Text/File/Image/Video)
    # %(class)s makes reverse names unique per subclass:
    # user.text_related, user.file_related, user.image_related, user.video_related
    owner = models.ForeignKey(
        User,
        related_name="%(class)s_related",
        on_delete=models.CASCADE,
    )

    # Common title shown in UI/admin
    title = models.CharField(max_length=250)

    # Auto-set only when object is first created
    created = models.DateTimeField(auto_now_add=True)

    # Auto-updated every time object is saved
    updated = models.DateTimeField(auto_now=True)

    def render(self):
        return render_to_string(
            f"courses/content/{self._meta.model_name}.html",
            {"item": self},
        )

    class Meta:
        # No database table for ItemBase itself; fields are inherited into child tables
        abstract = True


class Text(ItemBase):
    # Text lesson body/content
    content = models.TextField()


class File(ItemBase):
    # General file upload, stored under MEDIA_ROOT/files/
    file = models.FileField(upload_to="files", max_length=500)
    pdf_text_index = models.TextField(blank=True, default="")
    pdf_page_count = models.PositiveIntegerField(default=0)
    pdf_index_status = models.CharField(max_length=24, default="pending")
    pdf_index_error = models.TextField(blank=True, default="")
    pdf_indexed_at = models.DateTimeField(null=True, blank=True)


class Image(ItemBase):
    # Image upload, stored under MEDIA_ROOT/images/
    file = models.FileField(upload_to="images", max_length=500)


class Video(ItemBase):
    # External video link (URL validation included)
    url = models.URLField(
        blank=True,
        help_text="Optional video URL (YouTube/Vimeo). Leave blank if uploading a file.",
    )
    file = models.FileField(
        upload_to="videos",
        blank=True,
        max_length=500,
        help_text="Upload a video file for local playback (MP4/WebM/OGG).",
    )

    def clean(self):
        super().clean()
        if not self.file and not self.url:
            raise ValidationError("Provide either a video URL or upload a video file.")
