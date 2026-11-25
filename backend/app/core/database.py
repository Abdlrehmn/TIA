"""SQLite connection and schema migration helpers for TIA."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator

from app.core.config import DATABASE_PATH

DATABASE_VERSION = 2
BUSY_TIMEOUT_MS = 5_000


def _migration_1(connection: sqlite3.Connection) -> None:
    """Create the original conversations and memory foundation schema."""
    statements = (
        """CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1))
        )""",
        """CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            sequence INTEGER NOT NULL CHECK (sequence > 0),
            UNIQUE (conversation_id, sequence)
        )""",
        "CREATE INDEX messages_conversation_sequence ON messages(conversation_id, sequence)",
        "CREATE INDEX conversations_updated_at ON conversations(updated_at DESC)",
        """CREATE TABLE memory_records (
            id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('proposed', 'approved', 'rejected', 'superseded', 'deleted')),
            confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
            source_conversation_id TEXT REFERENCES conversations(id) ON DELETE SET NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            approved_at INTEGER,
            content_hash TEXT
        )""",
        """CREATE TABLE memory_sources (
            id TEXT PRIMARY KEY,
            memory_id TEXT NOT NULL REFERENCES memory_records(id) ON DELETE CASCADE,
            message_id TEXT REFERENCES messages(id) ON DELETE SET NULL,
            created_at INTEGER NOT NULL
        )""",
        "CREATE INDEX memory_records_status ON memory_records(status)",
        "CREATE INDEX memory_records_source_conversation ON memory_records(source_conversation_id)",
        "CREATE INDEX memory_sources_memory_id ON memory_sources(memory_id)",
        "CREATE INDEX memory_sources_message_id ON memory_sources(message_id)",
    )
    for statement in statements:
        connection.execute(statement)


def _migration_2(connection: sqlite3.Connection) -> None:
    """Record chat turn membership, search provenance, and completion state."""
    connection.execute(
        """CREATE TABLE conversation_turns (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            user_message_id TEXT NOT NULL UNIQUE REFERENCES messages(id) ON DELETE CASCADE,
            assistant_message_id TEXT UNIQUE,
            used_web_search INTEGER NOT NULL DEFAULT 0 CHECK (used_web_search IN (0, 1)),
            completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
            created_at INTEGER NOT NULL,
            completed_at INTEGER,
            CHECK ((completed = 0 AND completed_at IS NULL) OR
                   (completed = 1 AND completed_at IS NOT NULL AND assistant_message_id IS NOT NULL))
        )"""
    )
    connection.execute("CREATE INDEX conversation_turns_conversation ON conversation_turns(conversation_id, created_at)")
    connection.execute("CREATE INDEX conversation_turns_extraction ON conversation_turns(completed, used_web_search)")


MIGRATIONS = {1: _migration_1, 2: _migration_2}


@contextmanager
def connect_database(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Yield a configured connection and commit or roll back its transaction."""
    database_path = Path(path) if path is not None else DATABASE_PATH
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=BUSY_TIMEOUT_MS / 1_000)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(path: Path | str | None = None) -> None:
    """Apply each pending schema migration in its own transaction."""
    database_path = Path(path) if path is not None else DATABASE_PATH
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=BUSY_TIMEOUT_MS / 1_000)
    try:
        connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > DATABASE_VERSION:
            raise RuntimeError(f"Database version {version} is newer than supported version {DATABASE_VERSION}.")
        connection.execute("PRAGMA journal_mode = WAL")
        while True:
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > DATABASE_VERSION:
                connection.rollback()
                raise RuntimeError(f"Database version {version} is newer than supported version {DATABASE_VERSION}.")
            if version == DATABASE_VERSION:
                connection.commit()
                break
            migration_version = version + 1
            migration = MIGRATIONS.get(migration_version)
            if migration is None:
                connection.rollback()
                raise RuntimeError(f"No migration is available for database version {migration_version}.")
            try:
                migration(connection)
                connection.execute(f"PRAGMA user_version = {migration_version}")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
    finally:
        connection.close()
