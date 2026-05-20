from django.conf import settings  # Django setting access for AUTH_USER_MODEL.
from django.db import models  # Django ORM base classes and field types.
from django.db.models import F, Func
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.utils.text import slugify  # Utility to normalize tag names into slugs.


# Tag model to group notes by optional labels.
class Tag(models.Model):
    # Associate tags to the owning user (global per user notes).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Link to the configured user model.
        on_delete=models.CASCADE,  # Delete tags when the user is deleted.
        related_name="note_tags",  # Reverse accessor for a user's tags.
    )
    # Store the human-readable tag label.
    name = models.CharField(max_length=60)
    # Store the URL-friendly slug used for filtering.
    slug = models.SlugField(max_length=70)
    # Track when the tag was created.
    created_at = models.DateTimeField(auto_now_add=True)
    # Track when the tag was last updated.
    updated_at = models.DateTimeField(auto_now=True)

    # Django model metadata configuration.
    class Meta:
        # Prevent duplicate tags per user by slug.
        unique_together = ("user", "slug")
        # Keep tags ordered alphabetically in queries.
        ordering = ["name"]

    # Override save to ensure slug is always populated.
    def save(self, *args, **kwargs):
        # Auto-generate slug if missing to keep filters consistent.
        # Only generate a slug when missing to preserve edits.
        if not self.slug:
            # Limit slug length to field max length.
            self.slug = slugify(self.name)[:70]
        # Continue with the normal save flow.
        # Call the base save implementation.
        return super().save(*args, **kwargs)

    # Return a readable string representation.
    def __str__(self):
        # Return the human-readable tag label.
        # Provide the tag name for display.
        return self.name


# Note model storing title, HTML content, and optional tags.
class Note(models.Model):
    # Associate each note with its owning user.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Link to the configured user model.
        on_delete=models.CASCADE,  # Delete notes when the user is deleted.
        related_name="notes",  # Reverse accessor for a user's notes.
    )
    # Store the note title requested at save time.
    title = models.CharField(max_length=200)
    # Store the note content as HTML (Quill output).
    content_html = models.TextField(blank=True, default="")
    # Store the first "@" timestamp inserted into the note (immutable once set).
    date_time_now = models.DateTimeField(null=True, blank=True)
    # Store optional tags for filtering (limit enforced in views/UI).
    tags = models.ManyToManyField(
        Tag,  # Link to the Tag model for optional categorization.
        blank=True,  # Allow notes to have no tags.
        related_name="notes",  # Reverse accessor for tag -> notes.
    )
    # Track when the note was created.
    created_at = models.DateTimeField(auto_now_add=True)
    # Track when the note was last updated.
    updated_at = models.DateTimeField(auto_now=True)

    # Django model metadata configuration.
    class Meta:
        # Sort notes newest first for the sidebar list.
        ordering = ["-created_at"]

    # Return a readable string representation.
    def __str__(self):
        # Return the note title for admin/debugging.
        # Provide the note title for display.
        return self.title


class NoteSearchIndex(models.Model):
    # One searchable document per note.
    note = models.OneToOneField(
        Note,
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
                name="note_idx_doc_tsv_gin",
            ),
            GinIndex(
                fields=["document"],
                opclasses=["gin_trgm_ops"],
                name="note_idx_doc_trgm_gin",
            ),
        ]

    def __str__(self):
        return f"NoteSearchIndex(note={self.note_id})"
