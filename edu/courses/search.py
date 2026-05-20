from __future__ import annotations

import unicodedata
import html
from functools import lru_cache

from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
)
from django.db.models import F, FloatField, Q, TextField, Value
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest, Substr
from django.db.models import Func
from django.db import transaction
from django.utils.html import strip_tags
from django.db import IntegrityError

try:
    from django.contrib.postgres.search import SearchHeadline
except Exception:  # pragma: no cover - optional depending on Django version
    SearchHeadline = None

from .models import (
    Content,
    ContentSearchEntry,
    Course,
    CourseSearchIndex,
    File,
    Text,
)
from .pdf_indexing import extract_pdf_index_data

RANK_THRESHOLD = 0.02
SIMILARITY_THRESHOLD = 0.08
COURSE_DOC_MAX_PDF_CHARS = 220000
CONTENT_RANK_THRESHOLD = 0.02
CONTENT_SIMILARITY_THRESHOLD = 0.08


def _normalize_whitespace(value: str) -> str:
    return " ".join((value or "").split())


def _unaccent_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text or value or ""


@lru_cache(maxsize=1)
def _file_content_type_id() -> int:
    return ContentType.objects.get_for_model(File).id


def _course_pdf_text_chunks(course_id: int):
    file_ct = _file_content_type_id()
    file_ids = Content.objects.filter(
        module__course_id=course_id,
        content_type_id=file_ct,
    ).values_list("object_id", flat=True)
    return File.objects.filter(
        id__in=file_ids,
        pdf_index_status="indexed",
    ).exclude(pdf_text_index="").values_list("pdf_text_index", flat=True)


def build_course_search_document(course: Course) -> str:
    parts = [
        course.title,
        course.overview,
        course.subject.title if course.subject_id else "",
    ]
    for module in course.modules.all():
        parts.append(module.title)
        parts.append(module.description)

    char_budget = COURSE_DOC_MAX_PDF_CHARS
    for chunk in _course_pdf_text_chunks(course.id):
        if char_budget <= 0:
            break
        clean = _normalize_whitespace(chunk)
        if not clean:
            continue
        if len(clean) > char_budget:
            clean = clean[:char_budget]
        parts.append(clean)
        char_budget -= len(clean)

    return "\n".join(_normalize_whitespace(p) for p in parts if p)


def refresh_course_search_index(course_id: int) -> bool:
    course = (
        Course.objects.select_related("subject")
        .prefetch_related("modules")
        .filter(id=course_id)
        .first()
    )
    if not course:
        return False

    document = build_course_search_document(course)
    try:
        CourseSearchIndex.objects.update_or_create(
            course_id=course_id,
            defaults={"document": document},
        )
    except IntegrityError:
        # Course vanished during delete cascade
        return False
    return True


def refresh_subject_course_indexes(subject_id: int) -> int:
    updated = 0
    for course_id in Course.objects.filter(subject_id=subject_id).values_list("id", flat=True):
        if refresh_course_search_index(course_id):
            updated += 1
    return updated


def refresh_file_related_course_indexes(file_id: int) -> int:
    file_ct = _file_content_type_id()
    course_ids = (
        Course.objects.filter(
            modules__contents__content_type_id=file_ct,
            modules__contents__object_id=file_id,
        )
        .values_list("id", flat=True)
        .distinct()
    )
    updated = 0
    for course_id in course_ids:
        if refresh_course_search_index(course_id):
            updated += 1
    return updated


def rebuild_course_search_index(course_ids: list[int] | None = None) -> dict[str, int]:
    queryset = Course.objects.select_related("subject").prefetch_related("modules")
    if course_ids:
        queryset = queryset.filter(id__in=course_ids)

    created = 0
    updated = 0
    processed = 0

    for course in queryset:
        processed += 1
        _, row_created = CourseSearchIndex.objects.update_or_create(
            course_id=course.id,
            defaults={
                "document": build_course_search_document(course),
            },
        )
        if row_created:
            created += 1
        else:
            updated += 1

    return {"processed": processed, "created": created, "updated": updated}


def search_courses(queryset, query: str):
    normalized_query = _normalize_whitespace(query)
    if not normalized_query:
        return queryset

    query_text = _unaccent_text(normalized_query)
    document = Coalesce(F("search_index__document"), Value(""), output_field=TextField())
    unaccented_document = Func(
        document,
        function="immutable_unaccent",
        output_field=TextField(),
    )

    unaccented_title = Func(
        F("title"),
        function="immutable_unaccent",
        output_field=TextField(),
    )
    unaccented_subject = Func(
        F("subject__title"),
        function="immutable_unaccent",
        output_field=TextField(),
    )

    search_query = SearchQuery(query_text, config="simple", search_type="websearch")
    search_vector = SearchVector(unaccented_document, config="simple")
    search_rank = SearchRank(search_vector, search_query)

    trigram_document = TrigramSimilarity(unaccented_document, Value(query_text))
    trigram_title = TrigramSimilarity(unaccented_title, Value(query_text))
    trigram_subject = TrigramSimilarity(unaccented_subject, Value(query_text))

    trigram_score = Greatest(trigram_title, trigram_subject, trigram_document)
    combined_score = ExpressionWrapper(
        (search_rank * Value(2.2))
        + (trigram_title * Value(1.2))
        + (trigram_subject * Value(0.7))
        + (trigram_document * Value(1.0)),
        output_field=FloatField(),
    )

    return (
        queryset.select_related("subject")
        .annotate(
            search_rank=search_rank,
            trigram_document=trigram_document,
            trigram_title=trigram_title,
            trigram_subject=trigram_subject,
            trigram_score=trigram_score,
            combined_score=combined_score,
        )
        .filter(
            Q(search_rank__gte=RANK_THRESHOLD)
            | Q(trigram_score__gte=SIMILARITY_THRESHOLD)
        )
        .order_by("-combined_score", "-created")
    )


def _is_pdf_file(file_obj: File) -> bool:
    return str(getattr(file_obj.file, "name", "") or "").lower().endswith(".pdf")


def _build_content_document(title: str, body: str) -> str:
    plain_body = html.unescape(strip_tags(body or ""))
    parts = [title or "", plain_body]
    return _normalize_whitespace(" ".join(p for p in parts if p))


def _content_item_title(item) -> str:
    return getattr(item, "title", "") or ""


def refresh_content_search_entries_for_content(
    content: Content,
    item=None,
    page_texts: list[str] | None = None,
) -> int:
    if item is None:
        item = content.item

    # If the item no longer exists, drop entries.
    if not item:
        return ContentSearchEntry.objects.filter(content_id=content.id).delete()[0]

    kind = content.content_type.model
    module = content.module
    course = module.course
    item_title = _content_item_title(item)

    # Remove existing entries first to avoid stale rows.
    ContentSearchEntry.objects.filter(content_id=content.id).delete()

    rows: list[ContentSearchEntry] = []

    if isinstance(item, Text):
        document = _build_content_document(item_title, item.content)
        rows.append(
            ContentSearchEntry(
                content=content,
                course=course,
                module=module,
                kind=kind,
                item_title=item_title,
                document=document,
            )
        )
    elif isinstance(item, File) and _is_pdf_file(item):
        if page_texts is None:
            result = extract_pdf_index_data(item)
            page_texts = result.page_texts
        if page_texts is None:
            page_texts = []
        for idx, page_text in enumerate(page_texts, start=1):
            # Skip empty pages except for the first page so title-only searches still resolve.
            if not page_text and idx != 1:
                continue
            if idx == 1 and item_title:
                document = _build_content_document(item_title, page_text)
            else:
                document = _normalize_whitespace(page_text)
            if not document:
                continue
            rows.append(
                ContentSearchEntry(
                    content=content,
                    course=course,
                    module=module,
                    kind=kind,
                    item_title=item_title,
                    document=document,
                    page_number=idx,
                )
            )
        if not rows and item_title:
            rows.append(
                ContentSearchEntry(
                    content=content,
                    course=course,
                    module=module,
                    kind=kind,
                    item_title=item_title,
                    document=_normalize_whitespace(item_title),
                    page_number=1,
                )
            )
    else:
        document = _build_content_document(item_title, "")
        if document:
            rows.append(
                ContentSearchEntry(
                    content=content,
                    course=course,
                    module=module,
                    kind=kind,
                    item_title=item_title,
                    document=document,
                )
            )

    if not rows:
        return 0

    ContentSearchEntry.objects.bulk_create(rows, batch_size=200)
    return len(rows)


def refresh_content_search_entries_for_item(item, page_texts: list[str] | None = None) -> int:
    ct = ContentType.objects.get_for_model(item)
    contents = (
        Content.objects.filter(content_type=ct, object_id=item.id)
        .select_related("module", "module__course", "content_type")
    )
    total = 0
    for content in contents:
        total += refresh_content_search_entries_for_content(
            content,
            item=item,
            page_texts=page_texts,
        )
    return total


def refresh_content_search_entries_for_file(file_id: int, page_texts: list[str] | None = None) -> int:
    try:
        file_obj = File.objects.get(id=file_id)
    except File.DoesNotExist:
        return 0
    return refresh_content_search_entries_for_item(file_obj, page_texts=page_texts)


def rebuild_content_search_index(content_ids: list[int] | None = None) -> dict[str, int]:
    queryset = Content.objects.select_related("module", "module__course", "content_type")
    if content_ids:
        queryset = queryset.filter(id__in=content_ids)

    created = 0
    processed = 0

    with transaction.atomic():
        for content in queryset.iterator():
            processed += 1
            created += refresh_content_search_entries_for_content(content)

    return {"processed": processed, "created": created}


def search_content_entries(queryset, query: str):
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
            Q(search_rank__gte=CONTENT_RANK_THRESHOLD)
            | Q(trigram_score__gte=CONTENT_SIMILARITY_THRESHOLD)
        )
        .order_by("-combined_score", "-updated")
    )
