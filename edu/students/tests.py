import json

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from courses.models import Content, Course, File, Module, Subject, Text
from .models import ContentProgress, CourseProgress, ModuleProgress
from .services import get_overall_progress


class ContentProgressTrackingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="owner-pass")
        self.learner = User.objects.create_user("learner", password="learner-pass")

        subject = Subject.objects.create(title="Computer Science", slug="computer-science")
        self.course_main = Course.objects.create(
            owner=self.owner,
            subject=subject,
            title="Backend Engineering",
            slug="backend-engineering",
            overview="Advanced backend systems.",
        )
        self.course_other = Course.objects.create(
            owner=self.owner,
            subject=subject,
            title="Algorithms",
            slug="algorithms",
            overview="Foundational algorithms.",
        )
        self.course_main.students.add(self.learner)
        self.course_other.students.add(self.learner)

        self.module_main = Module.objects.create(
            course=self.course_main,
            title="Storage and Search",
            description="Progress-tracking module.",
        )
        self.module_other = Module.objects.create(
            course=self.course_other,
            title="Graphs",
            description="No activity yet.",
        )

        text_item = Text.objects.create(
            owner=self.owner,
            title="Intro Text",
            content="Study this content for progress tracking.",
        )
        pdf_item = File.objects.create(
            owner=self.owner,
            title="Module PDF",
            file=SimpleUploadedFile(
                "lesson.pdf",
                b"%PDF-1.4 fake content",
                content_type="application/pdf",
            ),
            pdf_index_status="indexed",
            pdf_text_index="searchable pdf body",
            pdf_page_count=3,
        )

        self.text_content = Content.objects.create(
            module=self.module_main,
            content_type=ContentType.objects.get_for_model(Text),
            object_id=text_item.id,
        )
        self.pdf_content = Content.objects.create(
            module=self.module_main,
            content_type=ContentType.objects.get_for_model(File),
            object_id=pdf_item.id,
        )

        self.client.force_login(self.learner)

    def test_text_progress_endpoint_updates_module_percentage(self):
        url = reverse("track_content_progress", args=[self.text_content.id])
        response = self.client.post(
            url,
            data=json.dumps({"kind": "text", "percent": 50}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "tracked")
        self.assertEqual(payload["content_progress"]["progress_percent"], 50.0)

        module_progress = ModuleProgress.objects.get(user=self.learner, module=self.module_main)
        self.assertAlmostEqual(module_progress.progress_percent, 25.0, places=1)
        self.assertFalse(module_progress.completed)

    def test_pdf_progress_page_tracking_marks_content_complete(self):
        url = reverse("track_content_progress", args=[self.pdf_content.id])
        response = self.client.post(
            url,
            data=json.dumps(
                {
                    "kind": "pdf",
                    "current_page": 3,
                    "total_pages": 3,
                    "max_page_seen": 3,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["content_progress"]["completed"])

        row = ContentProgress.objects.get(user=self.learner, content=self.pdf_content)
        self.assertEqual(row.last_position["max_page_seen"], 3)
        self.assertAlmostEqual(row.progress_percent, 100.0, places=1)

    def test_overall_progress_uses_enrolled_courses_scope(self):
        self.client.post(
            reverse("track_content_progress", args=[self.text_content.id]),
            data=json.dumps({"kind": "text", "percent": 100}),
            content_type="application/json",
        )
        self.client.post(
            reverse("track_content_progress", args=[self.pdf_content.id]),
            data=json.dumps({"kind": "pdf", "current_page": 3, "total_pages": 3, "max_page_seen": 3}),
            content_type="application/json",
        )

        # Two modules across enrolled courses: module_main=100, module_other=0 -> overall 50.
        self.assertAlmostEqual(get_overall_progress(self.learner), 50.0, places=1)

    def test_legacy_module_complete_sets_percentage_to_hundred(self):
        response = self.client.post(reverse("mark_module_complete", args=[self.module_other.id]))
        self.assertEqual(response.status_code, 200)

        module_progress = ModuleProgress.objects.get(user=self.learner, module=self.module_other)
        self.assertTrue(module_progress.completed)
        self.assertEqual(module_progress.progress_percent, 100.0)

    def test_course_is_marked_completed_and_persisted_when_all_modules_finish(self):
        # Complete all trackable content in the course's only module.
        self.client.post(
            reverse("track_content_progress", args=[self.text_content.id]),
            data=json.dumps({"kind": "text", "percent": 100}),
            content_type="application/json",
        )
        self.client.post(
            reverse("track_content_progress", args=[self.pdf_content.id]),
            data=json.dumps({"kind": "pdf", "current_page": 3, "total_pages": 3, "max_page_seen": 3}),
            content_type="application/json",
        )

        course_progress = CourseProgress.objects.get(user=self.learner, course=self.course_main)
        self.assertTrue(course_progress.completed)
        self.assertEqual(course_progress.progress_percent, 100.0)
        self.assertIsNotNone(course_progress.completed_at)

    def test_pdf_viewer_resumes_from_last_saved_page(self):
        # Save page state for a PDF content item.
        self.client.post(
            reverse("track_content_progress", args=[self.pdf_content.id]),
            data=json.dumps(
                {"kind": "pdf", "current_page": 2, "total_pages": 3, "max_page_seen": 2}
            ),
            content_type="application/json",
        )

        response = self.client.get(
            reverse("student_course_detail_module", args=[self.course_main.id, self.module_main.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-start-page="2"')
        self.assertContains(response, 'data-max-page-seen="2"')
