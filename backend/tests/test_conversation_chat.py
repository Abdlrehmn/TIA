"""Conversation-aware chat persistence, history, and streaming tests."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app import main
from app.core import database
from app.services import chat_context, conversation_store
from app.services.web_search import WebSearchResult


class ConversationChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(database, "DATABASE_PATH", Path(self.temp.name) / "chat.sqlite3")
        self.db_patch.start()
        database.initialize_database()
        self.conversation_id = str(uuid4())
        self.user_id = str(uuid4())
        self.assistant_id = str(uuid4())

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def payload(self, message="Explain software design."):
        return main.ConversationChatRequest(
            message=message,
            conversation_id=self.conversation_id,
            user_message_id=self.user_id,
            assistant_message_id=self.assistant_id,
            user_created_at=100,
            assistant_created_at=101,
            conversation_created_at=1,
            conversation_title="Chat",
        )

    @staticmethod
    def upstream(*lines):
        stream = MagicMock()
        stream.readline.side_effect = [*lines, b""]
        return stream

    @staticmethod
    def run_response(payload, upstream, opened=None, request=None):
        async def run():
            async def open_stream(ollama_request):
                if opened:
                    opened(ollama_request)
                return upstream

            with patch("app.main.open_ollama_stream", new=AsyncMock(side_effect=open_stream)):
                response = await main.stream_message(payload, request or MagicMock(is_disconnected=AsyncMock(return_value=False)))
                return b"".join([part async for part in response.body_iterator])

        return asyncio.run(run())

    def test_metadata_turn_persists_before_generation_and_saves_successful_answer(self):
        previous_user = {"id": str(uuid4()), "role": "user", "content": "earlier", "createdAt": 2}
        previous_assistant = {"id": str(uuid4()), "role": "assistant", "content": "earlier reply", "createdAt": 3}
        conversation_store.ensure_conversation(self.conversation_id, "Chat", 1)
        conversation_store.append_message(self.conversation_id, previous_user)
        conversation_store.append_message(self.conversation_id, previous_assistant)
        captured = []

        def inspect_request(request):
            record = conversation_store.get_conversation(self.conversation_id)
            self.assertEqual(record["messages"][-1]["id"], self.user_id)
            captured.extend(json.loads(request.data)["messages"])

        stream = self.upstream(
            b'{"message":{"content":"answer"},"done":false}\n',
            b'{"message":{"content":"!"},"done":true}\n',
        )
        body = self.run_response(self.payload(), stream, inspect_request)
        self.assertEqual([item["role"] for item in captured], ["system", "user", "assistant", "user"])
        self.assertEqual([item["content"] for item in captured[1:]], ["earlier", "earlier reply", "Explain software design."])
        self.assertEqual(sum(item["content"] == "Explain software design." for item in captured), 1)
        self.assertIn(b"event: start", body)
        self.assertIn(b"event: delta", body)
        self.assertIn(b"event: done", body)
        messages = conversation_store.get_conversation(self.conversation_id)["messages"]
        self.assertEqual([m["id"] for m in messages[-2:]], [self.user_id, self.assistant_id])
        self.assertEqual(messages[-1]["content"], "answer!")
        self.assertEqual(messages[-1]["createdAt"], 101)
        with database.connect_database() as connection:
            turn = connection.execute("SELECT user_message_id, assistant_message_id, used_web_search, completed FROM conversation_turns").fetchone()
        self.assertEqual(tuple(turn), (self.user_id, self.assistant_id, 0, 1))

    def test_duplicate_request_ids_do_not_duplicate_messages(self):
        stream = self.upstream(b'{"message":{"content":"answer"},"done":true}\n')
        self.run_response(self.payload(), stream)
        stream = self.upstream(b'{"message":{"content":"answer"},"done":true}\n')
        self.run_response(self.payload(), stream)
        messages = conversation_store.get_conversation(self.conversation_id)["messages"]
        self.assertEqual([message["id"] for message in messages], [self.user_id, self.assistant_id])

    def test_failed_or_cancelled_stream_does_not_save_assistant(self):
        failed = self.upstream(b'{"error":"private"}\n')
        failed_body = self.run_response(self.payload(), failed)
        self.assertIn(b"event: error", failed_body)
        self.assertNotIn(b"event: done", failed_body)
        self.assertEqual(len(conversation_store.get_conversation(self.conversation_id)["messages"]), 1)
        with database.connect_database() as connection:
            self.assertEqual(connection.execute("SELECT completed FROM conversation_turns").fetchone()[0], 0)

        def disconnected_after_delta(_ollama_request):
            return None

        request = MagicMock()
        request.is_disconnected = AsyncMock(side_effect=[False, False, True])
        partial = self.upstream(b'{"message":{"content":"partial"},"done":false}\n')
        body = self.run_response(self.payload(), partial, disconnected_after_delta, request)
        self.assertIn(b"event: delta", body)
        self.assertNotIn(b"event: done", body)
        self.assertEqual(len(conversation_store.get_conversation(self.conversation_id)["messages"]), 1)
        with database.connect_database() as connection:
            self.assertEqual(connection.execute("SELECT completed FROM conversation_turns").fetchone()[0], 0)

    def test_search_augmented_turn_is_recorded_for_future_extraction_exclusion(self):
        payload = self.payload("What is the latest version of Python?")
        upstream = self.upstream(b'{"message":{"content":"Current answer."},"done":true}\n')

        async def run():
            request = MagicMock(is_disconnected=AsyncMock(return_value=False))
            with (
                patch.object(main, "WEB_SEARCH_ENABLED", True),
                patch(
                    "app.main.search_web",
                    new=AsyncMock(return_value=[WebSearchResult("Python", "https://example.com", "version", None)]),
                ),
                patch(
                    "app.main.retrieve_search_content",
                    new=AsyncMock(side_effect=lambda results: results),
                ),
                patch("app.main.open_ollama_stream", new=AsyncMock(return_value=upstream)),
            ):
                response = await main.stream_message(payload, request)
                return b"".join([part async for part in response.body_iterator])

        body = asyncio.run(run())
        self.assertIn(b"event: done", body)
        with database.connect_database() as connection:
            turn = connection.execute("SELECT used_web_search, completed FROM conversation_turns").fetchone()
        self.assertEqual(tuple(turn), (1, 1))

    def test_history_context_budget_keeps_newest_order_and_current_is_appended_once(self):
        history = [
            {"id": str(uuid4()), "role": "user", "content": "old"},
            {"id": str(uuid4()), "role": "assistant", "content": "x" * 15},
            {"id": self.user_id, "role": "user", "content": "current question"},
            {"id": str(uuid4()), "role": "assistant", "content": "newest"},
        ]
        with (
            patch.object(chat_context, "CHAT_HISTORY_MAX_MESSAGES", 3),
            patch.object(chat_context, "CHAT_HISTORY_MAX_CHARS", 6),
        ):
            messages = chat_context.build_ollama_messages(
                "current question", history=history, current_message_id=self.user_id
            )
        self.assertEqual([item["content"] for item in messages[1:]], ["newest", "current question"])
        self.assertEqual(sum(item["content"] == "current question" for item in messages), 1)

    def test_chat_metadata_validation_and_legacy_request(self):
        with self.assertRaises(Exception):
            main.ConversationChatRequest(message="Hi", conversation_id="not-a-uuid")
        self.assertEqual(main.TestMessageRequest(message="Hello").message, "Hello")


if __name__ == "__main__":
    unittest.main()
