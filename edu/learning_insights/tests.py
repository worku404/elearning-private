import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Subject
from learning_insights.models import DailyCourseStat, Goal
from learning_insights.services.goals import sync_goal_progress_for_user

from learning_insights.services.ai_coach import (
    GeminiError,
    _build_ai_run_prompt,
    _compact_prompt_plan_payload,
    _create_ai_run,
    _extract_json_with_repair,
)

class GoalAIPlannerPersistenceTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        from learning_insights.models import AIPlanRun, Goal

        self.AIPlanRun = AIPlanRun
        self.Goal = Goal
        self.user = get_user_model().objects.create_user(username="learner", password="test-pass")
        self.client.force_login(self.user)

    def _build_prompt_plan_run(self):
        today = timezone.localdate()
        return self.AIPlanRun.objects.create(
            user=self.user,
            kind=self.AIPlanRun.KIND_PROMPT_PLAN,
            period_type=self.Goal.PERIOD_DAILY,
            period_start=today,
            period_end=today,
            input_payload={"user_prompt": "plan for exam prep"},
            output_payload={
                "type": "plan",
                "period": {"start": today.isoformat(), "end": today.isoformat()},
                "plan": [
                    {
                        "date": today.isoformat(),
                        "items": [
                            {
                                "task": "Review chapter 1",
                                "minutes": 20,
                                "notes": "Focus on key definitions",
                            }
                        ],
                    }
                ],
            },
            status=self.AIPlanRun.STATUS_SUCCESS,
            summary_text="Generated plan",
        )

    @patch("learning_insights.views.generate_prompt_plan_run")
    def test_generate_does_not_create_goal_rows(self, mock_generate_prompt_plan_run):
        run = self._build_prompt_plan_run()
        mock_generate_prompt_plan_run.return_value = run

        response = self.client.post(
            reverse("learning_insights:goal_ai_planner"),
            {"action": "start", "prompt": "Plan 20 minutes of study"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"ai_run={run.id}", response.url)
        self.assertEqual(self.Goal.objects.filter(user=self.user).count(), 0)

    def test_apply_creates_goal_rows(self):
        run = self._build_prompt_plan_run()

        response = self.client.post(reverse("learning_insights:goal_ai_apply", kwargs={"pk": run.id}))

        self.assertEqual(response.status_code, 302)
        self.assertGreater(self.Goal.objects.filter(user=self.user).count(), 0)

    def test_clear_deletes_unapplied_prompt_plan_run(self):
        run = self._build_prompt_plan_run()

        response = self.client.post(
            reverse("learning_insights:goal_ai_planner"),
            {"action": "clear", "run_id": str(run.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("learning_insights:goal_create"))
        self.assertFalse(self.AIPlanRun.objects.filter(pk=run.id).exists())

    def test_clear_keeps_applied_prompt_plan_run(self):
        run = self._build_prompt_plan_run()
        run.applied_at = timezone.now() - timedelta(minutes=1)
        run.save(update_fields=["applied_at", "updated_at"])

        response = self.client.post(
            reverse("learning_insights:goal_ai_planner"),
            {"action": "clear", "run_id": str(run.id)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(f"ai_run={run.id}", response.url)
        self.assertTrue(self.AIPlanRun.objects.filter(pk=run.id).exists())


class MinuteGoalFIFOAllocationTests(TestCase):
    def setUp(self):
        self.user = self._create_user()
        self.subject = Subject.objects.create(title="Computer Science", slug="computer-science")
        self.course = Course.objects.create(
            owner=self.user,
            subject=self.subject,
            title="Learning SQL",
            slug="learning-sql",
            overview="SQL course for FIFO timing tests.",
        )
        self.today = timezone.localdate()

        self.first_goal = Goal.objects.create(
            user=self.user,
            course=self.course,
            title="First 45-minute goal",
            period_type=Goal.PERIOD_DAILY,
            target_type=Goal.TARGET_MINUTES,
            target_value=Decimal("45.00"),
            current_value=Decimal("0.00"),
            start_date=self.today,
            due_date=self.today,
            priority=Goal.PRIORITY_MEDIUM,
            status=Goal.STATUS_NOT_STARTED,
        )
        self.second_goal = Goal.objects.create(
            user=self.user,
            course=self.course,
            title="Second 45-minute goal",
            period_type=Goal.PERIOD_DAILY,
            target_type=Goal.TARGET_MINUTES,
            target_value=Decimal("45.00"),
            current_value=Decimal("0.00"),
            start_date=self.today,
            due_date=self.today,
            priority=Goal.PRIORITY_MEDIUM,
            status=Goal.STATUS_NOT_STARTED,
        )

    @staticmethod
    def _create_user():
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(
            username="fifo-learner",
            password="test-pass",
        )

    def test_fifo_allocation_keeps_same_duration_goals_sequential(self):
        stat = DailyCourseStat.objects.create(
            user=self.user,
            course=self.course,
            date=self.today,
            module_seconds=2700,
        )

        sync_goal_progress_for_user(self.user)

        self.first_goal.refresh_from_db()
        self.second_goal.refresh_from_db()

        self.assertEqual(Decimal("45.00"), self.first_goal.current_value)
        self.assertEqual(Goal.STATUS_COMPLETED, self.first_goal.status)
        self.assertEqual(Decimal("0.00"), self.second_goal.current_value)
        self.assertEqual(Goal.STATUS_NOT_STARTED, self.second_goal.status)
        self.assertEqual(Decimal("45.00"), self.second_goal.remaining_value)

        stat.module_seconds = 5400
        stat.save()

        sync_goal_progress_for_user(self.user)

        self.first_goal.refresh_from_db()
        self.second_goal.refresh_from_db()

        self.assertEqual(Decimal("45.00"), self.first_goal.current_value)
        self.assertEqual(Goal.STATUS_COMPLETED, self.first_goal.status)
        self.assertEqual(Decimal("45.00"), self.second_goal.current_value)
        self.assertEqual(Goal.STATUS_COMPLETED, self.second_goal.status)


class PromptPlanPayloadTests(SimpleTestCase):
    def test_compact_prompt_plan_payload_trims_large_context(self):
        base_payload = {
            "goals": [{"id": index} for index in range(20)],
            "weekly_analytics": {
                "weekly_status": "On Track",
                "totals": {"site_seconds": 1200, "course_seconds": 900},
                "top_courses": [{"course_id": index} for index in range(10)],
                "course_breakdown": [{"course_id": index} for index in range(10)],
                "improvements": [{"id": index} for index in range(10)],
                "daily_breakdown": [{"date": f"2026-04-{index + 1:02d}"} for index in range(10)],
                "daily_chart": list(range(10)),
                "course_chart": list(range(10)),
            },
            "monthly_analytics": {
                "month_value": "2026-04",
                "top_courses": [{"course_id": index} for index in range(10)],
                "comparison": {"delta": 1},
                "daily_breakdown": list(range(10)),
            },
            "courses": [{"course_id": index} for index in range(15)],
            "neglected_courses": [{"course_id": index} for index in range(6)],
            "top_courses": [{"course_id": index} for index in range(6)],
            "notes": [{"id": index} for index in range(6)],
            "matches": {
                "enrolled_courses": [{"course_id": index} for index in range(10)],
                "enrolled_content": [{"content_id": index} for index in range(10)],
                "catalog_courses": [{"course_id": index} for index in range(10)],
            },
            "preferences": {"timezone": "UTC"},
        }

        compact = _compact_prompt_plan_payload(base_payload)

        self.assertEqual(12, len(compact["goals"]))
        self.assertEqual(10, len(compact["courses"]))
        self.assertEqual(3, len(compact["notes"]))
        self.assertEqual(4, len(compact["matches"]["enrolled_courses"]))
        self.assertEqual(4, len(compact["matches"]["catalog_courses"]))
        self.assertNotIn("daily_chart", compact["weekly_analytics"])
        self.assertNotIn("course_chart", compact["weekly_analytics"])
        self.assertEqual(4, len(compact["weekly_analytics"]["top_courses"]))

    def test_build_ai_run_prompt_uses_compact_json(self):
        prompt = _build_ai_run_prompt({"alpha": 1, "nested": {"beta": [1, 2]}})

        self.assertTrue(prompt.startswith("Input context JSON:\n"))
        payload_text = prompt.removeprefix("Input context JSON:\n")
        self.assertEqual({"alpha": 1, "nested": {"beta": [1, 2]}}, json.loads(payload_text))
        self.assertNotIn("\n  ", payload_text)


class JsonRepairTests(SimpleTestCase):
    @patch("learning_insights.services.ai_coach.generate_ai_response_simple")
    def test_extract_json_with_repair_repairs_invalid_json(self, mock_generate):
        invalid_raw = (
            '{"type":"plan","reasoning_summary":"fixed",'
            '"period":{"start":"2026-04-27" "end":"2026-04-27"},'
            '"plan":[],"focus_courses":[],"recommendations":[],"risk_level":"low"}'
        )
        repaired_raw = (
            '{"type":"plan","reasoning_summary":"fixed",'
            '"period":{"start":"2026-04-27","end":"2026-04-27"},'
            '"plan":[],"focus_courses":[],"recommendations":[],"risk_level":"low"}'
        )
        mock_generate.return_value = repaired_raw

        result = _extract_json_with_repair(
            raw_text=invalid_raw,
            system_prompt="Return JSON only.",
        )

        self.assertEqual("plan", result["type"])
        self.assertEqual("fixed", result["reasoning_summary"])
        self.assertEqual(1, mock_generate.call_count)

        repair_input = mock_generate.call_args.args[0]
        self.assertIn("Parser error:", repair_input["prompt"])
        self.assertIn("Invalid JSON:", repair_input["prompt"])
        self.assertIn(invalid_raw[:40], repair_input["prompt"])
        self.assertEqual(0.0, mock_generate.call_args.kwargs["temperature"])

    @patch("learning_insights.services.ai_coach.generate_ai_response_simple")
    def test_extract_json_with_repair_raises_gemini_error_when_repair_still_invalid(self, mock_generate):
        invalid_raw = (
            '{"type":"plan","reasoning_summary":"fixed",'
            '"period":{"start":"2026-04-27" "end":"2026-04-27"},'
            '"plan":[],"focus_courses":[],"recommendations":[],"risk_level":"low"}'
        )
        mock_generate.return_value = invalid_raw

        with self.assertRaises(GeminiError) as context:
            _extract_json_with_repair(
                raw_text=invalid_raw,
                system_prompt="Return JSON only.",
            )

        self.assertIn("repair retry", str(context.exception))
        details = getattr(context.exception, "details", {}) or {}
        self.assertIn("raw_text", details)
        self.assertIn("repaired_text", details)


class CreateAIRunRepairTests(SimpleTestCase):
    @patch("learning_insights.services.ai_coach.AIPlanRun.objects.create")
    @patch("learning_insights.services.ai_coach.generate_ai_response_simple")
    def test_create_ai_run_repairs_invalid_json_and_succeeds(self, mock_generate, mock_create):
        fake_run = Mock()
        fake_run.save = Mock()
        mock_create.return_value = fake_run

        invalid_raw = (
            '{"reasoning_summary":"fixed",'
            '"period":{"start":"2026-04-27" "end":"2026-04-27"},'
            '"plan":[],"focus_courses":[],"recommendations":[],"risk_level":"low"}'
        )
        repaired_raw = (
            '{"reasoning_summary":"fixed",'
            '"period":{"start":"2026-04-27","end":"2026-04-27"},'
            '"plan":[],"focus_courses":[],"recommendations":[],"risk_level":"low"}'
        )
        mock_generate.side_effect = [invalid_raw, repaired_raw]

        run = _create_ai_run(
            user=Mock(id=1),
            kind="prompt_plan",
            period_type="daily",
            period_start=date(2026, 4, 27),
            period_end=date(2026, 4, 27),
            input_payload={"today": "2026-04-27"},
            system_prompt="Return JSON only.",
        )

        self.assertIs(run, fake_run)
        self.assertEqual("success", fake_run.status)
        self.assertEqual("fixed", fake_run.summary_text)
        self.assertEqual("", fake_run.error_message)
        self.assertEqual("fixed", fake_run.output_payload["reasoning_summary"])
        self.assertEqual(2, mock_generate.call_count)
        fake_run.save.assert_called_once_with(
            update_fields=["status", "output_payload", "summary_text", "error_message", "updated_at"]
        )

    @patch("learning_insights.services.ai_coach.AIPlanRun.objects.create")
    @patch("learning_insights.services.ai_coach.generate_ai_response_simple")
    def test_create_ai_run_reports_invalid_json_when_repair_fails(self, mock_generate, mock_create):
        fake_run = Mock()
        fake_run.save = Mock()
        mock_create.return_value = fake_run

        invalid_raw = (
            '{"reasoning_summary":"fixed",'
            '"period":{"start":"2026-04-27" "end":"2026-04-27"},'
            '"plan":[],"focus_courses":[],"recommendations":[],"risk_level":"low"}'
        )
        mock_generate.side_effect = [invalid_raw, invalid_raw]

        run = _create_ai_run(
            user=Mock(id=1),
            kind="prompt_plan",
            period_type="daily",
            period_start=date(2026, 4, 27),
            period_end=date(2026, 4, 27),
            input_payload={"today": "2026-04-27"},
            system_prompt="Return JSON only.",
        )

        self.assertIs(run, fake_run)
        self.assertEqual("failed", fake_run.status)
        self.assertIn("repair retry", fake_run.error_message)
        self.assertIn("Invalid JSON:", fake_run.summary_text)
        self.assertIn('"period"', fake_run.summary_text)
        self.assertEqual(2, mock_generate.call_count)
        fake_run.save.assert_called_once()
