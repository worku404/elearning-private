from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

from .models import Content, Course, File, Module, Subject, Text, Video, Image, ContentSearchEntry
from .pdf_indexing import update_pdf_index_for_file
from .search import (
    refresh_content_search_entries_for_content,
    refresh_content_search_entries_for_file,
    refresh_content_search_entries_for_item,
    refresh_course_search_index,
    refresh_file_related_course_indexes,
    refresh_subject_course_indexes,
)

def _safe_refresh_course_index(course_id):
    if not course_id:
        return

    def _refresh():
        if Course.objects.filter(id=course_id).exists():
            refresh_course_search_index(course_id)

    transaction.on_commit(_refresh)



@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance, created, **kwargs):
    if created:
        Token.objects.get_or_create(user=instance)


@receiver(post_save, sender=Course)
def update_course_search_index(sender, instance, **kwargs):
    refresh_course_search_index(instance.id)


@receiver(post_save, sender=Module)
@receiver(post_delete, sender=Module)
def update_module_course_search_index(sender, instance, **kwargs):
    _safe_refresh_course_index(instance.course_id)


@receiver(post_save, sender=Subject)
def update_subject_courses_search_indexes(sender, instance, **kwargs):
    refresh_subject_course_indexes(instance.id)


@receiver(post_save, sender=Content)
def refresh_course_index_for_content_save(sender, instance, **kwargs):
    if instance.module_id:
        course_id = Module.objects.filter(id=instance.module_id).values_list("course_id", flat=True).first()
        if course_id:
            refresh_course_search_index(course_id)
    refresh_content_search_entries_for_content(instance)


@receiver(post_delete, sender=Content)
def refresh_course_index_for_content_delete(sender, instance, **kwargs):
    course_id = Module.objects.filter(id=instance.module_id).values_list("course_id", flat=True).first()
    _safe_refresh_course_index(course_id)
    ContentSearchEntry.objects.filter(content_id=instance.id).delete()


@receiver(post_save, sender=File)
def update_pdf_index_and_refresh_search(sender, instance, **kwargs):
    result = update_pdf_index_for_file(instance.id)
    if result:
        refresh_content_search_entries_for_file(instance.id, page_texts=result.page_texts)
    refresh_file_related_course_indexes(instance.id)


@receiver(post_save, sender=Text)
@receiver(post_save, sender=Video)
@receiver(post_save, sender=Image)
def refresh_content_entries_for_items(sender, instance, **kwargs):
    refresh_content_search_entries_for_item(instance)
