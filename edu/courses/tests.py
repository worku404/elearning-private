import unittest

from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from courses.models import Content, Course, CourseSearchIndex, File, Module, Subject
from courses.search import rebuild_course_search_index, search_courses


@unittest.skipUnless(
    connection.vendor == "postgresql",
    "PostgreSQL-specific search tests.",
)
class PostgresCourseSearchTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="pass123",
            email="owner@example.com",
        )
        self.db_subject = Subject.objects.create(title="Databases", slug="databases")
        self.web_subject = Subject.objects.create(title="Web", slug="web")

        self.title_match_course = Course.objects.create(
            owner=self.owner,
            subject=self.db_subject,
            title="Advanced Databases",
            slug="advanced-databases",
            overview="PostgreSQL indexing and performance tuning.",
        )
        self.overview_match_course = Course.objects.create(
            owner=self.owner,
            subject=self.db_subject,
            title="Storage Fundamentals",
            slug="storage-fundamentals",
            overview="This module covers advanced databases search tactics.",
        )
        self.module_match_course = Course.objects.create(
            owner=self.owner,
            subject=self.web_subject,
            title="Web Foundations",
            slug="web-foundations",
            overview="Core web architecture and HTTP.",
        )

        Module.objects.create(
            course=self.title_match_course,
            title="PostgreSQL Search",
            description="Full-text search and ranking.",
        )
        self.refresh_target_module = Module.objects.create(
            course=self.module_match_course,
            title="Routing",
            description="Request lifecycle details.",
        )

        pdf_item = File.objects.create(
            owner=self.owner,
            title="DB PDF",
            file=SimpleUploadedFile(
                "db-notes.pdf",
                b"%PDF-1.4 fake test pdf",
                content_type="application/pdf",
            ),
        )
        File.objects.filter(id=pdf_item.id).update(
            pdf_index_status="indexed",
            pdf_text_index="vectorized write ahead logging index",
            pdf_page_count=4,
        )
        Content.objects.create(
            module=self.title_match_course.modules.first(),
            content_type=ContentType.objects.get_for_model(File),
            object_id=pdf_item.id,
        )

        rebuild_course_search_index()

    def test_catalog_exact_match_prioritizes_title_match(self):
        qs = search_courses(Course.objects.all(), "advanced databases")
        results = list(qs.values_list("id", flat=True))
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0], self.title_match_course.id)

    def test_fuzzy_typo_query_returns_expected_course(self):
        qs = search_courses(Course.objects.all(), "advnced databse")
        self.assertIn(
            self.title_match_course.id,
            list(qs.values_list("id", flat=True)),
        )

    def test_subject_and_query_filter_in_catalog_view(self):
        url = f"{reverse('course_list_subject', args=[self.db_subject.slug])}?q=advanced"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        course_ids = [course.id for course in response.context["courses"]]
        self.assertIn(self.title_match_course.id, course_ids)
        self.assertIn(self.overview_match_course.id, course_ids)
        self.assertNotIn(self.module_match_course.id, course_ids)

    def test_api_search_returns_paginated_ranked_results(self):
        url = f"{reverse('api:course-list')}?q=advanced databases"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("results", payload)
        self.assertGreaterEqual(payload.get("count", 0), 1)
        self.assertEqual(payload["results"][0]["id"], self.title_match_course.id)

    def test_no_query_paths_preserve_existing_behavior(self):
        web_response = self.client.get(reverse("course_list"))
        self.assertEqual(web_response.status_code, 200)
        self.assertEqual(web_response.context.get("query"), "")
        self.assertEqual(len(list(web_response.context["courses"])), Course.objects.count())

        api_response = self.client.get(reverse("api:course-list"))
        self.assertEqual(api_response.status_code, 200)
        self.assertIn("results", api_response.json())

    def test_module_change_refreshes_index(self):
        self.refresh_target_module.title = "Distributed Search Systems"
        self.refresh_target_module.save()

        qs = search_courses(Course.objects.all(), "distributed search")
        self.assertIn(
            self.module_match_course.id,
            list(qs.values_list("id", flat=True)),
        )

    def test_rebuild_command_backfills_missing_rows(self):
        CourseSearchIndex.objects.all().delete()
        self.assertEqual(CourseSearchIndex.objects.count(), 0)

        call_command("rebuild_course_search_index")

        self.assertEqual(CourseSearchIndex.objects.count(), Course.objects.count())
        qs = search_courses(Course.objects.all(), "advanced databases")
        self.assertIn(
            self.title_match_course.id,
            list(qs.values_list("id", flat=True)),
        )

    def test_pdf_body_terms_are_searchable(self):
        qs = search_courses(Course.objects.all(), "write ahead logging")
        self.assertIn(
            self.title_match_course.id,
            list(qs.values_list("id", flat=True)),
        )
