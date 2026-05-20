import json
from contextlib import ExitStack
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, patch

import requests
from django.test import RequestFactory, SimpleTestCase, override_settings

from .services import GeminiError, generate_ai_response

# Create your tests here.


class GeminiServiceTests(SimpleTestCase):
	@override_settings(API1_KEY="test-key")
	@patch("assistant.services.requests.post")
	def test_generate_ai_response_surfaces_network_error(self, mock_post):
		mock_post.side_effect = requests.exceptions.ConnectionError("connection reset")

		with self.assertRaises(GeminiError) as context:
			generate_ai_response(
				{"prompt": "Hello"},
				"You are a helpful assistant.",
			)

		self.assertIn("Network error while contacting Gemini", context.exception.message)
		self.assertIn("connection reset", context.exception.message)

	@override_settings(API1_KEY="key-1", API2_KEY="key-2")
	@patch("assistant.services._get_gemini_api_keys", return_value=["key-1", "key-2"])
	@patch("assistant.services.random.randrange", return_value=0)
	@patch("assistant.services.requests.post")
	def test_generate_ai_response_falls_back_to_second_key(self, mock_post, mock_randrange, mock_get_keys):
		first_response = Mock()
		first_response.status_code = 503
		first_response.json.return_value = {
			"error": {"message": "This model is currently experiencing high demand."}
		}
		second_response = Mock()
		second_response.status_code = 200
		second_response.json.return_value = {
			"candidates": [
				{"content": {"parts": [{"text": "OK"}]}}
			]
		}
		mock_post.side_effect = [first_response, second_response]

		result = generate_ai_response(
			{"prompt": "Hello"},
			"You are a helpful assistant.",
		)

		self.assertEqual("OK", result)
		self.assertEqual(2, mock_post.call_count)
		self.assertEqual(
			"key-1",
			mock_post.call_args_list[0].kwargs["headers"]["x-goog-api-key"],
		)
		self.assertEqual(
			"key-2",
			mock_post.call_args_list[1].kwargs["headers"]["x-goog-api-key"],
		)
		mock_randrange.assert_called_once_with(2)
		mock_get_keys.assert_called_once()

	@override_settings(API1_KEY="test-key")
	@patch("assistant.services.requests.post")
	def test_generate_ai_response_surfaces_overload_error(self, mock_post):
		response = Mock()
		response.status_code = 503
		response.json.return_value = {
			"error": {
				"message": (
					"This model is currently experiencing high demand. "
					"Spikes in demand are usually temporary. Please try again later."
				)
			}
		}
		mock_post.return_value = response

		with self.assertRaises(GeminiError) as context:
			generate_ai_response(
				{"prompt": "Hello"},
				"You are a helpful assistant.",
			)

		self.assertEqual(
			"Gemini is temporarily overloaded. Please try again in a moment.",
			context.exception.message,
		)
		details = context.exception.details or {}
		self.assertEqual(503, details["status"])

	@override_settings(API1_KEY="test-key")
	@patch("assistant.services.requests.post")
	def test_generate_ai_response_surfaces_high_demand_429(self, mock_post):
		response = Mock()
		response.status_code = 429
		response.json.return_value = {
			"error": {
				"message": (
					"This model is currently experiencing high demand. "
					"Spikes in demand are usually temporary. Please try again later."
				)
			}
		}
		mock_post.return_value = response

		with self.assertRaises(GeminiError) as context:
			generate_ai_response(
				{"prompt": "Hello"},
				"You are a helpful assistant.",
			)

		self.assertEqual(
			"Gemini is temporarily overloaded. Please try again in a moment.",
			context.exception.message,
		)
		details = context.exception.details or {}
		self.assertEqual(429, details["status"])

	@override_settings(API1_KEY="test-key")
	@patch("assistant.services.requests.post")
	def test_generate_ai_response_surfaces_prompt_too_large(self, mock_post):
		response = Mock()
		response.status_code = 400
		response.json.return_value = {
			"error": {"message": "The prompt is too large for this model."}
		}
		mock_post.return_value = response

		with self.assertRaises(GeminiError) as context:
			generate_ai_response(
				{"prompt": "Hello"},
				"You are a helpful assistant.",
			)

		self.assertEqual(
			"The prompt is too long for the current model. Split it into smaller parts and try again.",
			context.exception.message,
		)
		details = context.exception.details or {}
		self.assertEqual(400, details["status"])


class AssistantGenerateViewTests(SimpleTestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.user = SimpleNamespace(is_authenticated=True)

	@override_settings(API1_KEY="test-key")
	def test_llm_generate_returns_json_response(self):
		from . import views as views_module

		with ExitStack() as stack:
			mock_generate = stack.enter_context(
				patch.object(
					views_module,
					"generate_ai_response",
					return_value="Hello",
				)
			)
			mock_turn_query = stack.enter_context(
				patch.object(
					views_module.AssistantTurn.objects,
					"filter",
				)
			)
			mock_build_state = stack.enter_context(
				patch.object(views_module, "build_chat_state")
			)
			mock_set_active_chat = stack.enter_context(
				patch.object(views_module, "set_active_chat")
			)
			mock_get_active_chat = stack.enter_context(
				patch.object(views_module, "get_active_chat")
			)
			mock_turn_create = stack.enter_context(
				patch.object(views_module.AssistantTurn.objects, "create")
			)
			mock_chat_create = stack.enter_context(
				patch.object(views_module.AssistantChat.objects, "create")
			)
			stack.enter_context(
				patch.object(views_module, "render_llm_markdown", side_effect=lambda value: value)
			)

			mock_chat = Mock(id=1, title="", is_pinned=False)
			mock_chat.save = Mock()
			mock_chat.pk = 1
			mock_chat_create.return_value = mock_chat
			mock_turns_queryset = Mock()
			mock_turns_queryset.order_by.return_value = []
			mock_turn_query.return_value = mock_turns_queryset
			mock_get_active_chat.return_value = None
			mock_set_active_chat.return_value = None
			mock_build_state.side_effect = lambda user, chat: {
				"active_chat_id": getattr(chat, "id", None),
				"pinned_chats": [],
				"temp_chat": {
					"id": getattr(chat, "id", None),
					"title": getattr(chat, "title", ""),
					"is_pinned": False,
				},
				"max_pins": 6,
			}

			request = self.factory.post("/assistant/llm/generate/", {"prompt": "Hello"})
			request_any = cast(Any, request)
			request_any.user = self.user
			request_any.session = {}

			response = views_module.llm_generate(request)

			self.assertEqual(200, response.status_code)
			self.assertFalse(getattr(response, "streaming", False))
			self.assertEqual("application/json", response.headers["Content-Type"].split(";")[0])
			data = json.loads(response.content.decode("utf-8"))
			self.assertEqual("Hello", data["generated"])
			self.assertEqual(1, data["chat_state"]["active_chat_id"])
			mock_chat_create.assert_called_once()
			mock_turn_create.assert_called_once()
			mock_generate.assert_called_once()
			generation_context, system_prompt = mock_generate.call_args.args
			self.assertEqual(views_module.DEFAULT_MAX_OUTPUT_TOKENS, generation_context["maxOutputTokens"])
			self.assertEqual(0.2, generation_context["temperature"])
			self.assertTrue(system_prompt.startswith("You are a helpful AI study assistant"))
