"""SQLite foundation and conversation API model tests."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.core.database import connect_database, initialize_database
from app import main
from app.main import ConversationImportInput, ConversationInput, ConversationMessageInput
from app.services import conversation_store as store


class ConversationStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "nested" / "tia.sqlite3"
        self.database_override = patch("app.core.database.DATABASE_PATH", self.database_path)
        self.database_override.start()
        initialize_database()

    def tearDown(self):
        self.database_override.stop()
        self.temp_dir.cleanup()

    @staticmethod
    def message(role="user", content="hello", created_at=100):
        return {
            "id": str(uuid4()),
            "role": role,
            "content": content,
            "createdAt": created_at,
        }

    @staticmethod
    def conversation(conversation_id=None, messages=None):
        return {
            "id": conversation_id or str(uuid4()),
            "title": "Imported chat",
            "createdAt": 50,
            "updatedAt": 50,
            "messages": messages or [],
        }

    def test_initialization_is_idempotent_and_enables_database_pragmas(self):
        initialize_database()
        with connect_database() as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
            names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertTrue({"conversations", "messages", "memory_records", "memory_sources"} <= names)

    def test_create_retrieve_order_update_and_delete_with_foreign_key_actions(self):
        first, second = self.message("user", "first"), self.message("assistant", "second", 110)
        conversation = self.conversation(messages=[first, second])
        result = store.import_conversations([conversation])
        self.assertEqual(result, {"conversationsImported": 1, "messagesImported": 2})
        retrieved = store.get_conversation(conversation["id"])
        self.assertEqual(retrieved["id"], conversation["id"])
        self.assertEqual([message["id"] for message in retrieved["messages"]], [first["id"], second["id"]])
        self.assertEqual([message["sequence"] for message in retrieved["messages"]], [1, 2])
        self.assertEqual(retrieved["createdAt"], 50)

        updated = store.update_title(conversation["id"], "Renamed", 120)
        self.assertEqual(updated["title"], "Renamed")
        self.assertEqual(updated["updatedAt"], 120)

        memory_id, source_id = str(uuid4()), str(uuid4())
        with connect_database() as connection:
            connection.execute(
                """INSERT INTO memory_records(id,kind,content,status,source_conversation_id,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (memory_id, "fact", "local test", "proposed", conversation["id"], 1, 1),
            )
            connection.execute(
                "INSERT INTO memory_sources(id,memory_id,message_id,created_at) VALUES(?,?,?,?)",
                (source_id, memory_id, first["id"], 1),
            )
        store.delete_conversation(conversation["id"])
        with connect_database() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)
            self.assertIsNone(connection.execute("SELECT source_conversation_id FROM memory_records").fetchone()[0])
            self.assertIsNone(connection.execute("SELECT message_id FROM memory_sources").fetchone()[0])

    def test_import_preserves_ids_and_is_idempotent(self):
        message = self.message("assistant", "saved response", 2345678901234)
        conversation = self.conversation(messages=[message])
        self.assertEqual(
            store.import_conversations([conversation]),
            {"conversationsImported": 1, "messagesImported": 1},
        )
        self.assertEqual(
            store.import_conversations([conversation]),
            {"conversationsImported": 0, "messagesImported": 0},
        )
        saved = store.get_conversation(conversation["id"])
        self.assertEqual(saved["id"], conversation["id"])
        self.assertEqual(saved["messages"][0]["id"], message["id"])
        self.assertEqual(saved["messages"][0]["createdAt"], message["createdAt"])
        self.assertEqual(saved["updatedAt"], message["createdAt"])

    def test_upsert_and_append_are_idempotent_and_conflicting_ids_rejected(self):
        conversation = self.conversation()
        self.assertEqual(store.upsert_conversation(conversation)["id"], conversation["id"])
        message = self.message()
        store.append_message(conversation["id"], message)
        store.append_message(conversation["id"], message)
        self.assertEqual(len(store.get_conversation(conversation["id"])["messages"]), 1)
        conflicting = {**message, "content": "changed"}
        with self.assertRaises(store.ConflictError):
            store.append_message(conversation["id"], conflicting)

    def test_reopen_persists_records(self):
        conversation = self.conversation(messages=[self.message()])
        store.import_conversations([conversation])
        initialize_database(self.database_path)
        with patch("app.core.database.DATABASE_PATH", self.database_path):
            self.assertEqual(store.get_conversation(conversation["id"])["id"], conversation["id"])

    def test_invalid_uuid_and_payload_roles_are_rejected(self):
        with self.assertRaises(store.InvalidDataError):
            store.get_conversation("not-a-uuid")
        with self.assertRaises(ValidationError):
            ConversationMessageInput(id=str(uuid4()), role="system", content="x", createdAt=1)
        with self.assertRaises(ValidationError):
            ConversationInput(id="not-a-uuid", title="bad", createdAt=1)
        with self.assertRaises(ValidationError):
            ConversationInput.model_validate(
                {"id": str(uuid4()), "title": " ", "createdAt": 1, "messages": []}
            )
        with self.assertRaises(ValidationError):
            ConversationInput.model_validate(
                {"id": str(uuid4()), "title": "valid", "createdAt": 1, "messages": [{"id": str(uuid4()), "role": "system", "content": "x", "createdAt": 1}]}
            )

    def test_database_enforces_foreign_keys(self):
        with connect_database() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO messages(id,conversation_id,role,content,created_at,sequence) VALUES(?,?,?,?,?,?)",
                    (str(uuid4()), str(uuid4()), "user", "orphan", 1, 1),
                )

    def test_import_endpoint_accepts_frontend_shape_and_is_repeatable(self):
        message = self.message("assistant", "preserved answer", 987654321000)
        conversation = self.conversation(messages=[message])
        request = ConversationImportInput.model_validate({"conversations": [conversation]})
        self.assertEqual(
            main.import_local_conversations(request),
            {"conversationsImported": 1, "messagesImported": 1},
        )
        self.assertEqual(
            main.import_local_conversations(request),
            {"conversationsImported": 0, "messagesImported": 0},
        )
        self.assertEqual(main.get_conversation_endpoint(conversation["id"])["messages"][0]["id"], message["id"])

    def test_conversation_api_functions_create_list_update_append_and_delete(self):
        message = self.message("user", "original", 60)
        record = self.conversation(messages=[message])
        payload = ConversationInput.model_validate(record)
        created = main.put_conversation(record["id"], payload)
        self.assertEqual(created["id"], record["id"])
        self.assertEqual(created["updatedAt"], message["createdAt"])
        self.assertEqual(main.get_conversations(limit=200)[0]["id"], record["id"])

        title = main.ConversationTitleInput.model_validate({"title": "Updated", "updatedAt": 70})
        self.assertEqual(main.patch_conversation_title(record["id"], title)["title"], "Updated")
        added = self.message("assistant", "reply", 80)
        result = main.post_conversation_message(
            record["id"], ConversationMessageInput.model_validate(added)
        )
        self.assertEqual([item["id"] for item in result["messages"]], [message["id"], added["id"]])
        self.assertEqual(main.remove_conversation(record["id"]).status_code, 204)
        with self.assertRaises(HTTPException) as error:
            main.get_conversation_endpoint(record["id"])
        self.assertEqual(error.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
