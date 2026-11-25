"""Sequential SQLite migration tests, including an authentic version 1 database."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from app.core import database


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "tia.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_fresh_and_repeated_initialization_reach_latest_version(self):
        database.initialize_database(self.path)
        database.initialize_database(self.path)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("memory_records", names)
        self.assertIn("conversation_turns", names)

    def test_real_version_one_data_survives_upgrade(self):
        conversation_id, user_id, assistant_id = str(uuid4()), str(uuid4()), str(uuid4())
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            database._migration_1(connection)
            connection.execute(
                "INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                (conversation_id, "Existing chat", 10, 20),
            )
            connection.execute(
                "INSERT INTO messages(id,conversation_id,role,content,created_at,sequence) VALUES(?,?,?,?,?,?)",
                (user_id, conversation_id, "user", "old user message", 11, 1),
            )
            connection.execute(
                "INSERT INTO messages(id,conversation_id,role,content,created_at,sequence) VALUES(?,?,?,?,?,?)",
                (assistant_id, conversation_id, "assistant", "old reply", 12, 2),
            )
            connection.execute("PRAGMA user_version = 1")

        database.initialize_database(self.path)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 2)
            messages = connection.execute(
                "SELECT id, role, content, sequence FROM messages ORDER BY sequence"
            ).fetchall()
            turns = connection.execute("SELECT count(*) FROM conversation_turns").fetchone()[0]
        self.assertEqual(messages, [(user_id, "user", "old user message", 1), (assistant_id, "assistant", "old reply", 2)])
        self.assertEqual(turns, 0, "pre-existing messages must not be assigned guessed turn provenance")

    def test_failed_migration_rolls_back_its_partial_ddl(self):
        def broken_migration(connection):
            connection.execute("CREATE TABLE transient_migration_table(id INTEGER)")
            raise RuntimeError("migration fault")

        with patch.dict(database.MIGRATIONS, {2: broken_migration}):
            with self.assertRaisesRegex(RuntimeError, "migration fault"):
                database.initialize_database(self.path)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("transient_migration_table", names)
        self.assertNotIn("conversation_turns", names)

    def test_unknown_future_schema_is_rejected_without_schema_changes(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("PRAGMA user_version = 99")
        with self.assertRaisesRegex(RuntimeError, "newer than supported"):
            database.initialize_database(self.path)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 99)
            self.assertEqual(connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
