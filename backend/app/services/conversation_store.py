"""Persistence operations for backend-owned conversation records."""

import logging
import sqlite3
import uuid
from collections.abc import Sequence
from typing import Any

from app.core.database import connect_database

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """A database operation failed without exposing database details to clients."""


class NotFoundError(Exception):
    """A requested conversation does not exist."""


class ConflictError(Exception):
    """A stable ID already refers to different stored content."""


class InvalidDataError(Exception):
    """Incoming identifiers or records are inconsistent."""


def validate_uuid(value: str) -> str:
    """Validate UUID syntax while retaining the caller's exact ID spelling."""
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise InvalidDataError("IDs must be valid UUID strings.") from None
    return value


def _run(operation: str, callback):
    try:
        with connect_database() as connection:
            return callback(connection)
    except (NotFoundError, ConflictError, InvalidDataError):
        raise
    except sqlite3.Error as exc:
        logger.warning("SQLite operation %s failed (%s).", operation, type(exc).__name__)
        raise StorageError("Conversation storage is unavailable.") from None
    except OSError as exc:
        logger.warning("SQLite operation %s failed (%s).", operation, type(exc).__name__)
        raise StorageError("Conversation storage is unavailable.") from None


def upsert_conversation(record: dict[str, Any]) -> dict[str, Any]:
    conversation_id = validate_uuid(record["id"])

    def write(connection: sqlite3.Connection):
        connection.execute(
            """INSERT INTO conversations(id, title, created_at, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at""",
            (conversation_id, record["title"], record["createdAt"], record["updatedAt"]),
        )
        return get_conversation(conversation_id, connection=connection)

    return _run("upsert conversation", write)


def ensure_conversation(conversation_id: str, title: str, created_at: int) -> None:
    """Create a conversation if absent without overwriting an existing record."""
    validate_uuid(conversation_id)

    def write(connection: sqlite3.Connection):
        connection.execute(
            "INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?) ON CONFLICT(id) DO NOTHING",
            (conversation_id, title, created_at, created_at),
        )

    _run("ensure conversation", write)


def save_conversation(record: dict[str, Any]) -> dict[str, Any]:
    """Atomically upsert a conversation and its ordered, stable-ID messages."""
    conversation_id = validate_uuid(record["id"])
    for message in record["messages"]:
        validate_uuid(message["id"])

    def write(connection: sqlite3.Connection):
        connection.execute(
            """INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET title=excluded.title, updated_at=excluded.updated_at""",
            (conversation_id, record["title"], record["createdAt"], record["updatedAt"]),
        )
        for sequence, message in enumerate(record["messages"], start=1):
            message_id = message["id"]
            expected = (conversation_id, message["role"], message["content"], message["createdAt"], sequence)
            existing = connection.execute(
                "SELECT conversation_id,role,content,created_at,sequence FROM messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != expected:
                    raise ConflictError("Message ID already exists with different data.")
                continue
            occupied = connection.execute(
                "SELECT 1 FROM messages WHERE conversation_id = ? AND sequence = ?",
                (conversation_id, sequence),
            ).fetchone()
            if occupied is not None:
                raise ConflictError("Conversation message order conflicts with stored data.")
            connection.execute(
                """INSERT INTO messages(id,conversation_id,role,content,created_at,sequence)
                   VALUES(?,?,?,?,?,?)""",
                (message_id, conversation_id, message["role"], message["content"], message["createdAt"], sequence),
            )
        return get_conversation(conversation_id, connection=connection)

    return _run("save conversation", write)


def list_conversations(*, include_archived: bool = False, limit: int = 200) -> list[dict[str, Any]]:
    def read(connection: sqlite3.Connection):
        rows = connection.execute(
            """SELECT id, title, created_at, updated_at, archived FROM conversations
               WHERE (? = 1 OR archived = 0) ORDER BY updated_at DESC, id LIMIT ?""",
            (int(include_archived), limit),
        ).fetchall()
        return [_conversation_dict(row) for row in rows]

    return _run("list conversations", read)


def _conversation_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "archived": bool(row["archived"]),
    }


def _message_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "role": row["role"],
        "content": row["content"],
        "createdAt": row["created_at"],
        "sequence": row["sequence"],
    }


def get_conversation(
    conversation_id: str,
    *,
    connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    validate_uuid(conversation_id)
    if connection is None:
        return _run("get conversation", lambda db: get_conversation(conversation_id, connection=db))
    row = connection.execute(
        "SELECT id, title, created_at, updated_at, archived FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    if row is None:
        raise NotFoundError("Conversation not found.")
    result = _conversation_dict(row)
    messages = connection.execute(
        """SELECT id, role, content, created_at, sequence FROM messages
           WHERE conversation_id = ? ORDER BY sequence""",
        (conversation_id,),
    ).fetchall()
    result["messages"] = [_message_dict(message) for message in messages]
    return result


def get_recent_messages(conversation_id: str, limit: int) -> list[dict[str, Any]]:
    """Fetch the most recent messages while returning them chronologically."""
    validate_uuid(conversation_id)

    def read(connection: sqlite3.Connection):
        if connection.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone() is None:
            raise NotFoundError("Conversation not found.")
        rows = connection.execute(
            """SELECT id, role, content, created_at, sequence FROM messages
               WHERE conversation_id = ? ORDER BY sequence DESC LIMIT ?""",
            (conversation_id, limit),
        ).fetchall()
        return [_message_dict(row) for row in reversed(rows)]

    return _run("get recent conversation messages", read)


def _append_message(connection: sqlite3.Connection, conversation_id: str, message: dict[str, Any]) -> dict[str, Any]:
    message_id = validate_uuid(message["id"])
    if connection.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone() is None:
        raise NotFoundError("Conversation not found.")
    existing = connection.execute(
        "SELECT conversation_id, role, content, created_at FROM messages WHERE id = ?", (message_id,)
    ).fetchone()
    expected = (conversation_id, message["role"], message["content"], message["createdAt"])
    if existing is not None:
        if tuple(existing) != expected:
            raise ConflictError("Message ID already exists with different data.")
        return get_conversation(conversation_id, connection=connection)
    sequence = connection.execute(
        "SELECT COALESCE(MAX(sequence), 0) + 1 FROM messages WHERE conversation_id = ?", (conversation_id,)
    ).fetchone()[0]
    connection.execute(
        "INSERT INTO messages(id, conversation_id, role, content, created_at, sequence) VALUES (?, ?, ?, ?, ?, ?)",
        (message_id, conversation_id, message["role"], message["content"], message["createdAt"], sequence),
    )
    connection.execute("UPDATE conversations SET updated_at = MAX(updated_at, ?) WHERE id = ?", (message["createdAt"], conversation_id))
    return get_conversation(conversation_id, connection=connection)


def begin_turn(
    conversation_id: str,
    user_message: dict[str, Any],
    assistant_message_id: str,
    *,
    history_limit: int = 13,
) -> list[dict[str, Any]]:
    """Persist the user message and an incomplete turn atomically, idempotently."""
    validate_uuid(conversation_id)
    user_message_id = validate_uuid(user_message["id"])
    assistant_message_id = validate_uuid(assistant_message_id)
    if user_message.get("role") != "user":
        raise InvalidDataError("A conversation turn must start with a user message.")

    def write(connection: sqlite3.Connection):
        _append_message(connection, conversation_id, user_message)
        existing = connection.execute(
            "SELECT conversation_id, assistant_message_id FROM conversation_turns WHERE id = ?", (user_message_id,)
        ).fetchone()
        if existing is None:
            connection.execute(
                """INSERT INTO conversation_turns(id, conversation_id, user_message_id, assistant_message_id, created_at)
                   VALUES(?,?,?,?,?)""",
                (user_message_id, conversation_id, user_message_id, assistant_message_id, user_message["createdAt"]),
            )
        elif (existing["conversation_id"], existing["assistant_message_id"]) != (conversation_id, assistant_message_id):
            raise ConflictError("Turn ID already exists with different data.")
        rows = connection.execute(
            """SELECT id, role, content, created_at, sequence FROM messages
               WHERE conversation_id = ? ORDER BY sequence DESC LIMIT ?""",
            (conversation_id, history_limit),
        ).fetchall()
        return [_message_dict(row) for row in reversed(rows)]

    return _run("begin conversation turn", write)


def mark_turn_search_used(turn_id: str) -> None:
    validate_uuid(turn_id)

    def write(connection: sqlite3.Connection):
        cursor = connection.execute("UPDATE conversation_turns SET used_web_search = 1 WHERE id = ?", (turn_id,))
        if cursor.rowcount == 0:
            raise NotFoundError("Conversation turn not found.")

    _run("mark turn search provenance", write)


def complete_turn(turn_id: str, conversation_id: str, assistant_message: dict[str, Any], completed_at: int) -> None:
    """Atomically persist a complete assistant message and mark its turn complete."""
    validate_uuid(turn_id)
    validate_uuid(conversation_id)
    validate_uuid(assistant_message["id"])
    if assistant_message.get("role") != "assistant":
        raise InvalidDataError("A completed conversation turn requires an assistant message.")

    def write(connection: sqlite3.Connection):
        turn = connection.execute(
            "SELECT conversation_id, assistant_message_id, completed FROM conversation_turns WHERE id = ?",
            (turn_id,),
        ).fetchone()
        if turn is None:
            raise NotFoundError("Conversation turn not found.")
        if turn["conversation_id"] != conversation_id or turn["assistant_message_id"] != assistant_message["id"]:
            raise ConflictError("Assistant response does not match its conversation turn.")
        _append_message(connection, conversation_id, assistant_message)
        if not turn["completed"]:
            connection.execute(
                "UPDATE conversation_turns SET completed = 1, completed_at = ? WHERE id = ?",
                (completed_at, turn_id),
            )

    _run("complete conversation turn", write)


def update_title(conversation_id: str, title: str, updated_at: int) -> dict[str, Any]:
    validate_uuid(conversation_id)

    def write(connection: sqlite3.Connection):
        cursor = connection.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title, updated_at, conversation_id),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("Conversation not found.")
        return get_conversation(conversation_id, connection=connection)

    return _run("update conversation title", write)


def delete_conversation(conversation_id: str) -> None:
    validate_uuid(conversation_id)

    def write(connection: sqlite3.Connection):
        cursor = connection.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        if cursor.rowcount == 0:
            raise NotFoundError("Conversation not found.")

    _run("delete conversation", write)


def append_message(conversation_id: str, message: dict[str, Any]) -> dict[str, Any]:
    validate_uuid(conversation_id)
    validate_uuid(message["id"])

    def write(connection: sqlite3.Connection):
        return _append_message(connection, conversation_id, message)

    return _run("append conversation message", write)


def import_conversations(records: Sequence[dict[str, Any]]) -> dict[str, int]:
    """Import browser records atomically; repeated identical imports are no-ops."""
    for conversation in records:
        validate_uuid(conversation["id"])
        seen_ids: set[str] = set()
        for message in conversation["messages"]:
            validate_uuid(message["id"])
            if message["id"] in seen_ids:
                raise InvalidDataError("A conversation contains duplicate message IDs.")
            seen_ids.add(message["id"])

    def write(connection: sqlite3.Connection):
        imported_conversations = 0
        imported_messages = 0
        for conversation in records:
            conversation_id = conversation["id"]
            current = connection.execute(
                "SELECT title, created_at, updated_at FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if current is None:
                derived_updated = max(
                    [conversation["createdAt"], *(message["createdAt"] for message in conversation["messages"])],
                )
                connection.execute(
                    "INSERT INTO conversations(id,title,created_at,updated_at) VALUES(?,?,?,?)",
                    (conversation_id, conversation["title"], conversation["createdAt"], max(conversation.get("updatedAt", derived_updated), derived_updated)),
                )
                imported_conversations += 1
            elif current["title"] != conversation["title"] or current["created_at"] != conversation["createdAt"]:
                raise ConflictError("Conversation ID already exists with different data.")

            for sequence, message in enumerate(conversation["messages"], start=1):
                by_id = connection.execute(
                    "SELECT conversation_id, role, content, created_at, sequence FROM messages WHERE id = ?",
                    (message["id"],),
                ).fetchone()
                expected = (conversation_id, message["role"], message["content"], message["createdAt"], sequence)
                if by_id is not None:
                    if tuple(by_id) != expected:
                        raise ConflictError("Message ID already exists with different data.")
                    continue
                by_sequence = connection.execute(
                    "SELECT id FROM messages WHERE conversation_id = ? AND sequence = ?",
                    (conversation_id, sequence),
                ).fetchone()
                if by_sequence is not None:
                    raise ConflictError("Imported message order conflicts with stored data.")
                connection.execute(
                    "INSERT INTO messages(id,conversation_id,role,content,created_at,sequence) VALUES(?,?,?,?,?,?)",
                    (message["id"], conversation_id, message["role"], message["content"], message["createdAt"], sequence),
                )
                imported_messages += 1
        return {"conversationsImported": imported_conversations, "messagesImported": imported_messages}

    return _run("import conversations", write)
