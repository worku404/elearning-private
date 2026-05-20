from __future__ import annotations

import html

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
)
from django.db.models import F, FloatField, Q, TextField, Value
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce, Substr
from django.db.models import Func
from django.utils.html import strip_tags

try:
    from django.contrib.postgres.search import SearchHeadline
except Exception:  # pragma: no cover - optional depending on Django version
    SearchHeadline = None

from .models import Note, NoteSearchIndex

NOTE_RANK_THRESHOLD = 0.02
NOTE_SIMILARITY_THRESHOLD = 0.08


def _normalize_whitespace(value: str) -> str:
    return " ".join((value or "").split())


def _unaccent_text(value: str) -> str:
    normalized = (value or "").strip()
    return normalized or ""


def _plain_text_from_html(value: str) -> str:
    raw = strip_tags(value or "")
    return html.unescape(raw or "")


def build_note_search_document(note: Note) -> str:
    tag_names = " ".join(tag.name for tag in note.tags.all())
    parts = [
        note.title,
        tag_names,
        _plain_text_from_html(note.content_html),
    ]
    return _normalize_whitespace(" ".join(p for p in parts if p))


def refresh_note_search_index(note_id: int) -> bool:
    try:
        note = Note.objects.prefetch_related("tags").get(id=note_id)
    except Note.DoesNotExist:
        return False
    document = build_note_search_document(note)
    NoteSearchIndex.objects.update_or_create(
        note_id=note_id,
        defaults={"document": document},
    )
    return True


def delete_note_search_index(note_id: int) -> None:
    NoteSearchIndex.objects.filter(note_id=note_id).delete()


def rebuild_note_search_index(note_ids: list[int] | None = None) -> dict[str, int]:
    queryset = Note.objects.prefetch_related("tags")
    if note_ids:
        queryset = queryset.filter(id__in=note_ids)

    created = 0
    updated = 0
    processed = 0

    for note in queryset:
        processed += 1
        _, row_created = NoteSearchIndex.objects.update_or_create(
            note_id=note.id,
            defaults={"document": build_note_search_document(note)},
        )
        if row_created:
            created += 1
        else:
            updated += 1

    return {"processed": processed, "created": created, "updated": updated}


def search_notes(queryset, query: str):
    normalized_query = _normalize_whitespace(query)
    if not normalized_query:
        return queryset.none()

    query_text = _unaccent_text(normalized_query)
    document = Coalesce(F("document"), Value(""), output_field=TextField())
    unaccented_document = Func(
        document,
        function="immutable_unaccent",
        output_field=TextField(),
    )

    search_query = SearchQuery(query_text, config="simple", search_type="websearch")
    search_vector = SearchVector(unaccented_document, config="simple")
    search_rank = SearchRank(search_vector, search_query)

    trigram_document = TrigramSimilarity(unaccented_document, Value(query_text))
    trigram_score = trigram_document

    combined_score = ExpressionWrapper(
        (search_rank * Value(2.2)) + (trigram_document * Value(1.0)),
        output_field=FloatField(),
    )

    if SearchHeadline:
        headline = SearchHeadline(
            document,
            search_query,
            config="simple",
            start_sel="<mark class=\"search-highlight\">",
            stop_sel="</mark>",
            max_words=35,
            min_words=12,
            short_word=2,
            highlight_all=True,
        )
    else:
        headline = Substr(document, 1, 180)

    return (
        queryset.annotate(
            search_rank=search_rank,
            trigram_document=trigram_document,
            trigram_score=trigram_score,
            combined_score=combined_score,
            snippet=headline,
        )
        .filter(
            Q(search_rank__gte=NOTE_RANK_THRESHOLD)
            | Q(trigram_score__gte=NOTE_SIMILARITY_THRESHOLD)
        )
        .order_by("-combined_score", "-updated")
    )
