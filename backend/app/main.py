"""FastAPI entry point for the TIA backend."""

import asyncio
import ipaddress
import json
import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, urlopen

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.responses import JSONResponse, StreamingResponse

from app.core.config import (
    APP_NAME,
    APP_VERSION,
    CORS_ALLOWED_ORIGINS,
    API_ALLOWED_HOSTS,
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    WEB_SEARCH_ENABLED,
    WEB_SEARCH_MAX_RESULTS,
    CHAT_HISTORY_MAX_MESSAGES,
)
from app.core.logging_config import configure_logging
from app.core.database import initialize_database
from app.services.chat_context import (
    MAX_CHAT_SEARCH_RESULTS,
    bounded_search_results,
    build_ollama_messages,
    build_sources_markdown,
)
from app.services.search_intent import needs_web_search
from app.services.web_content import retrieve_search_content
from app.services.web_search import (
    WebSearchError,
    WebSearchResult,
    WebSearchTimeoutError,
    search_web,
    start_web_search,
    close_web_search,
)
from app.services.conversation_store import (
    ConflictError,
    InvalidDataError,
    NotFoundError,
    StorageError,
    append_message,
    delete_conversation,
    get_conversation,
    import_conversations,
    list_conversations,
    save_conversation,
    update_title,
    ensure_conversation,
    begin_turn,
    mark_turn_search_used,
    complete_turn,
)

configure_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize storage and shared search resources for this app process."""
    await asyncio.to_thread(initialize_database)
    await start_web_search()
    try:
        yield
    finally:
        await close_web_search()


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def require_local_api_auth(request: Request, call_next):
    """Require a per-session bearer token and reject non-loopback HTTP peers."""
    client_host = request.client.host if request.client else ""
    try:
        if not ipaddress.ip_address(client_host).is_loopback:
            return JSONResponse({"detail": "Local API access is restricted."}, status_code=403)
    except ValueError:
        return JSONResponse({"detail": "Local API access is restricted."}, status_code=403)

    if request.headers.get("host", "").lower() not in API_ALLOWED_HOSTS:
        return JSONResponse({"detail": "Invalid request host."}, status_code=403)
    origin = request.headers.get("origin")
    if origin is not None and origin not in CORS_ALLOWED_ORIGINS:
        return JSONResponse({"detail": "Request origin is not allowed."}, status_code=403)

    # The health endpoint reveals only process identity/version and is used by
    # startup checks before the UI has obtained its session credential.
    if request.url.path == "/health" or request.method == "OPTIONS":
        return await call_next(request)

    expected = os.environ.get("TIA_API_TOKEN")
    if not expected or len(expected) < 43:
        return JSONResponse({"detail": "Backend authentication is not configured."}, status_code=503)
    try:
        expected_bytes = expected.encode("ascii")
    except UnicodeEncodeError:
        return JSONResponse({"detail": "Backend authentication is not configured."}, status_code=503)
    scheme, separator, supplied = request.headers.get("authorization", "").partition(" ")
    try:
        matches = separator == " " and scheme.lower() == "bearer" and secrets.compare_digest(
            supplied.encode("ascii"), expected_bytes
        )
    except UnicodeEncodeError:
        matches = False
    if not matches:
        return JSONResponse(
            {"detail": "Authentication required."},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await call_next(request)

SEARCH_HEARTBEAT_INTERVAL_SECONDS = 10


class HealthResponse(BaseModel):
    """Public health response for the local backend process."""

    status: Literal["healthy"]
    app: str
    version: str


class TestMessageRequest(BaseModel):
    """Message payload used to verify frontend/backend communication."""

    message: str = Field(min_length=1, max_length=100_000)

    @field_validator("message")
    @classmethod
    def message_must_contain_non_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be empty or whitespace.")
        return value


class ConversationChatRequest(TestMessageRequest):
    """Optional stable frontend metadata for a persistent conversation turn."""
    conversation_id: str | None = Field(default=None, max_length=64)
    user_message_id: str | None = Field(default=None, max_length=64)
    assistant_message_id: str | None = Field(default=None, max_length=64)
    user_created_at: int | None = Field(default=None, ge=0)
    assistant_created_at: int | None = Field(default=None, ge=0)
    conversation_created_at: int | None = Field(default=None, ge=0)
    conversation_title: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def metadata_is_all_or_none(self):
        ids = (self.conversation_id, self.user_message_id, self.assistant_message_id)
        if any(ids) and not all(ids):
            raise ValueError("Conversation chat metadata must include all three IDs.")
        if any((self.user_created_at, self.assistant_created_at, self.conversation_created_at, self.conversation_title)) and not all(ids):
            raise ValueError("Message timestamps require complete conversation metadata.")
        return self

    @field_validator("conversation_id", "user_message_id", "assistant_message_id")
    @classmethod
    def optional_ids_must_be_uuids(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                uuid.UUID(value)
            except ValueError:
                raise ValueError("IDs must be UUID strings.") from None
        return value

    @field_validator("assistant_created_at")
    @classmethod
    def assistant_timestamp_requires_id(cls, value: int | None, info):
        if value is not None and not info.data.get("assistant_message_id"):
            raise ValueError("Assistant timestamp requires conversation metadata.")
        return value

    @field_validator("user_created_at")
    @classmethod
    def user_timestamp_requires_id(cls, value: int | None, info):
        if value is not None and not info.data.get("user_message_id"):
            raise ValueError("User timestamp requires conversation metadata.")
        return value

    @field_validator("assistant_message_id")
    @classmethod
    def metadata_must_be_complete(cls, value: str | None, info):
        if value is not None and not all(info.data.get(key) for key in ("conversation_id", "user_message_id")):
            raise ValueError("Conversation chat metadata must include all message IDs.")
        return value

    @field_validator("user_message_id")
    @classmethod
    def conversation_id_required_for_user_id(cls, value: str | None, info):
        if value is not None and not info.data.get("conversation_id"):
            raise ValueError("Conversation ID is required with message IDs.")
        return value


class TestMessageResponse(BaseModel):
    """Chat reply returned by the local model."""

    success: Literal[True]
    message: str
    reply: str


class WebSearchRequest(BaseModel):
    """Validated query and optional result count for the local search API."""

    query: str = Field(min_length=1, max_length=400)
    max_results: int = Field(
        default=WEB_SEARCH_MAX_RESULTS,
        ge=1,
        le=WEB_SEARCH_MAX_RESULTS,
    )

    @field_validator("query")
    @classmethod
    def query_must_contain_non_whitespace(cls, value: str) -> str:
        query = value.strip()
        if not query:
            raise ValueError("Query must not be empty or whitespace.")
        return query


class WebSearchResultResponse(BaseModel):
    """Public result shape; provider-specific fields are never returned."""

    title: str
    url: str
    snippet: str
    published: str | None


class WebSearchResponse(BaseModel):
    success: Literal[True]
    query: str
    results: list[WebSearchResultResponse]
    result_count: int


class ConversationMessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1_000_000)
    created_at: int = Field(alias="createdAt", ge=0)

    @field_validator("id")
    @classmethod
    def id_must_be_uuid(cls, value: str) -> str:
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValueError("ID must be a UUID string.") from None
        return value


class ConversationInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    created_at: int = Field(alias="createdAt", ge=0)
    updated_at: int | None = Field(default=None, alias="updatedAt", ge=0)
    messages: list[ConversationMessageInput] = Field(default_factory=list, max_length=5000)

    @field_validator("id")
    @classmethod
    def id_must_be_uuid(cls, value: str) -> str:
        try:
            uuid.UUID(value)
        except ValueError:
            raise ValueError("ID must be a UUID string.") from None
        return value

    @field_validator("title")
    @classmethod
    def title_must_contain_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be empty or whitespace.")
        return value


class ConversationTitleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    updated_at: int = Field(alias="updatedAt", ge=0)

    @field_validator("title")
    @classmethod
    def title_must_contain_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be empty or whitespace.")
        return value


class ConversationImportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversations: list[ConversationInput] = Field(max_length=500)


def _conversation_api_call(callback):
    try:
        return callback()
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except InvalidDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except StorageError:
        raise HTTPException(status_code=500, detail="Conversation storage is unavailable.") from None


def _validated_conversation(record: ConversationInput) -> dict[str, Any]:
    messages = [message.model_dump(by_alias=True) for message in record.messages]
    latest_message_timestamp = max(
        (message["createdAt"] for message in messages),
        default=record.created_at,
    )
    return {
        "id": record.id,
        "title": record.title,
        "createdAt": record.created_at,
        "updatedAt": max(
            record.updated_at if record.updated_at is not None else record.created_at,
            latest_message_timestamp,
        ),
        "messages": messages,
    }


def ollama_chat_request(
    payload: TestMessageRequest,
    *,
    stream: bool,
    search_results: list[WebSearchResult] | None = None,
    history: list[dict[str, Any]] | None = None,
    current_message_id: str | None = None,
) -> URLRequest:
    """Build the configured Ollama request for one current user message."""
    return URLRequest(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=json.dumps(
            {
                "model": OLLAMA_MODEL,
                "messages": build_ollama_messages(payload.message, search_results, history, current_message_id),
                "stream": stream,
                "keep_alive": OLLAMA_KEEP_ALIVE,
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )


def sse_event(name: str, data: dict[str, object]) -> bytes:
    """Encode one JSON Server-Sent Event frame."""
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health_check() -> HealthResponse:
    """Report that the backend process is responding."""
    return HealthResponse(status="healthy", app=APP_NAME, version=APP_VERSION)


@app.put("/api/v1/conversations/{conversation_id}", tags=["conversations"])
def put_conversation(conversation_id: str, payload: ConversationInput) -> dict[str, Any]:
    """Create or update a conversation while retaining its stable local IDs."""
    if conversation_id != payload.id:
        raise HTTPException(status_code=422, detail="Path and payload conversation IDs must match.")
    record = _validated_conversation(payload)

    def write():
        return save_conversation(record)

    return _conversation_api_call(write)


@app.get("/api/v1/conversations", tags=["conversations"])
def get_conversations(
    include_archived: bool = False,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    """List persisted conversations, newest activity first."""
    return _conversation_api_call(
        lambda: list_conversations(include_archived=include_archived, limit=limit)
    )


@app.get("/api/v1/conversations/{conversation_id}", tags=["conversations"])
def get_conversation_endpoint(conversation_id: str) -> dict[str, Any]:
    """Return one conversation and its messages in insertion order."""
    return _conversation_api_call(lambda: get_conversation(conversation_id))


@app.patch("/api/v1/conversations/{conversation_id}", tags=["conversations"])
def patch_conversation_title(
    conversation_id: str,
    payload: ConversationTitleInput,
) -> dict[str, Any]:
    """Update a conversation title and activity timestamp."""
    return _conversation_api_call(
        lambda: update_title(conversation_id, payload.title, payload.updated_at)
    )


@app.delete("/api/v1/conversations/{conversation_id}", status_code=204, tags=["conversations"])
def remove_conversation(conversation_id: str) -> Response:
    """Delete a conversation and cascade-delete its messages."""
    _conversation_api_call(lambda: delete_conversation(conversation_id))
    return Response(status_code=204)


@app.post("/api/v1/conversations/{conversation_id}/messages", tags=["conversations"])
def post_conversation_message(
    conversation_id: str,
    payload: ConversationMessageInput,
) -> dict[str, Any]:
    """Append one message idempotently using its stable frontend-generated ID."""
    message = payload.model_dump(by_alias=True)
    return _conversation_api_call(lambda: append_message(conversation_id, message))


@app.post("/api/v1/conversations/import", tags=["conversations"])
def import_local_conversations(payload: ConversationImportInput) -> dict[str, int]:
    """Import a bounded localStorage export without removing its browser copy."""
    records = [_validated_conversation(record) for record in payload.conversations]
    return _conversation_api_call(lambda: import_conversations(records))


@app.post(
    "/api/v1/chat/test",
    response_model=TestMessageResponse,
    tags=["chat"],
)
def test_message(payload: TestMessageRequest) -> TestMessageResponse:
    """Generate a reply using the configured local Ollama model."""
    request = ollama_chat_request(payload, stream=False)
    try:
        with urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read())
    except HTTPError as exc:
        logger.error("Ollama returned HTTP %s while generating a chat reply.", exc.code)
        raise HTTPException(status_code=502, detail="The local model could not generate a response.") from None
    except (TimeoutError, URLError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or isinstance(exc, TimeoutError):
            logger.warning("Ollama request timed out.")
        else:
            logger.warning("Ollama is unavailable or refused the connection.")
        raise HTTPException(status_code=503, detail="The local AI service is unavailable.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.error("Ollama returned invalid JSON.")
        raise HTTPException(status_code=502, detail="The local model returned an invalid response.") from None
    except OSError:
        logger.warning("Ollama is unavailable or refused the connection.")
        raise HTTPException(status_code=503, detail="The local AI service is unavailable.") from None

    message = result.get("message") if isinstance(result, dict) else None
    reply = message.get("content") if isinstance(message, dict) else None
    if not isinstance(reply, str) or not reply.strip():
        logger.error("Ollama returned an unexpected or empty chat response.")
        raise HTTPException(status_code=502, detail="The local model returned an invalid response.")
    return TestMessageResponse(
        success=True,
        message=payload.message,
        reply=reply,
    )


async def open_ollama_stream(ollama_request: URLRequest) -> Any:
    """Open Ollama's streaming response without blocking the event loop."""
    try:
        return await asyncio.to_thread(
            urlopen,
            ollama_request,
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
    except HTTPError as exc:
        exc.close()
        logger.error("Ollama returned HTTP %s while opening a chat stream.", exc.code)
        raise HTTPException(status_code=502, detail="The local model could not generate a response.") from None
    except (TimeoutError, URLError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError) or isinstance(exc, TimeoutError):
            logger.warning("Ollama chat stream timed out while connecting.")
        else:
            logger.warning("Ollama chat stream is unavailable or refused the connection.")
        raise HTTPException(status_code=503, detail="The local AI service is unavailable.") from None
    except OSError:
        logger.warning("Ollama chat stream is unavailable or refused the connection.")
        raise HTTPException(status_code=503, detail="The local AI service is unavailable.") from None


async def ollama_content_events(
    upstream: Any,
    request: Request,
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    """Yield answer deltas and terminal events, closing Ollama on every exit."""
    received_content = False
    try:
        while True:
            if await request.is_disconnected():
                logger.info("Client disconnected from the Ollama chat stream.")
                return

            line = await asyncio.to_thread(upstream.readline)
            if not line:
                break
            if not line.strip():
                continue

            try:
                chunk = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                logger.error("Ollama returned an invalid JSON line in the chat stream.")
                yield "error", {"message": "The local model returned an invalid response."}
                return

            if not isinstance(chunk, dict):
                logger.error("Ollama returned an unexpected chat stream chunk.")
                yield "error", {"message": "The local model returned an invalid response."}
                return
            if "error" in chunk:
                logger.error("Ollama reported a model error during the chat stream.")
                yield "error", {"message": "The local model could not generate a response."}
                return

            message = chunk.get("message")
            if not isinstance(message, dict):
                logger.error("Ollama returned an unexpected chat message in the stream.")
                yield "error", {"message": "The local model returned an invalid response."}
                return

            content = message.get("content", "")
            done = chunk.get("done")
            if not isinstance(content, str) or not isinstance(done, bool):
                logger.error("Ollama returned invalid fields in a chat stream chunk.")
                yield "error", {"message": "The local model returned an invalid response."}
                return

            # Deliberately ignore message.thinking; only answer content is forwarded.
            if content:
                received_content = True
                yield "delta", {"content": content}
            if done:
                if not received_content:
                    logger.error("Ollama chat stream completed without answer content.")
                    yield "error", {"message": "The local model returned an empty response."}
                    return
                yield "done", {"success": True}
                return

        logger.error("Ollama chat stream ended before its done marker.")
        yield "error", {"message": "The local model stream ended unexpectedly."}
    except asyncio.CancelledError:
        logger.info("Ollama chat stream cancelled after client disconnect.")
        raise
    except (TimeoutError, URLError):
        logger.warning("Ollama chat stream became unavailable while reading.")
        yield "error", {"message": "The local AI service is unavailable."}
    except OSError:
        logger.warning("Ollama chat stream connection failed while reading.")
        yield "error", {"message": "The local AI service is unavailable."}
    except Exception:
        logger.error("Unexpected error while reading Ollama chat stream.", exc_info=True)
        yield "error", {"message": "The local model returned an invalid response."}
    finally:
        try:
            await asyncio.to_thread(upstream.close)
        except OSError:
            logger.warning("Could not cleanly close the Ollama chat stream.")


def search_failure_message() -> str:
    return (
        "I couldn't retrieve live search results, so I can't reliably verify the latest information. "
        "Please try again when web search is available."
    )


def prepare_conversation_turn(payload: TestMessageRequest) -> list[dict[str, Any]] | None:
    """Persist the current user turn and return recent history, if metadata exists."""
    if not isinstance(payload, ConversationChatRequest) or not payload.conversation_id:
        return None
    import time
    user_created_at = payload.user_created_at if payload.user_created_at is not None else int(time.time() * 1000)
    try:
        ensure_conversation(
            payload.conversation_id,
            payload.conversation_title or payload.message.strip()[:200],
            payload.conversation_created_at if payload.conversation_created_at is not None else user_created_at,
        )
        return begin_turn(
            payload.conversation_id,
            {"id": payload.user_message_id, "role": "user", "content": payload.message, "createdAt": user_created_at},
            payload.assistant_message_id,
            history_limit=CHAT_HISTORY_MAX_MESSAGES + 1,
        )
    except (NotFoundError, ConflictError, InvalidDataError, StorageError) as exc:
        status = 404 if isinstance(exc, NotFoundError) else 409 if isinstance(exc, ConflictError) else 422 if isinstance(exc, InvalidDataError) else 500
        detail = "Conversation storage is unavailable." if isinstance(exc, StorageError) else str(exc)
        raise HTTPException(status_code=status, detail=detail) from None


async def saved_content_events(
    upstream: Any,
    request: Request,
    payload: TestMessageRequest,
    history: list[dict[str, Any]] | None,
    completion_suffix: str = "",
) -> AsyncIterator[tuple[str, dict[str, object]]]:
    """Save only a complete answer, holding the SSE done event until storage succeeds."""
    answer: list[str] = []
    async for event_name, data in ollama_content_events(upstream, request):
        if event_name == "delta":
            answer.append(str(data.get("content", "")))
            yield event_name, data
        elif event_name == "done":
            if completion_suffix:
                answer.append(completion_suffix)
                yield "delta", {"content": completion_suffix}
            if isinstance(payload, ConversationChatRequest) and payload.assistant_message_id and payload.conversation_id:
                import time
                created_at = payload.assistant_created_at if payload.assistant_created_at is not None else int(time.time() * 1000)
                try:
                    complete_turn(
                        payload.user_message_id,
                        payload.conversation_id,
                        {"id": payload.assistant_message_id, "role": "assistant", "content": "".join(answer), "createdAt": created_at},
                        int(time.time() * 1000),
                    )
                except (NotFoundError, ConflictError, InvalidDataError, StorageError):
                    logger.error("Could not persist a completed assistant chat response.")
                    yield "error", {"message": "The response could not be saved to conversation history."}
                    return
            yield event_name, data
        else:
            yield event_name, data


@app.post("/api/v1/chat/stream", tags=["chat"])
async def stream_message(payload: ConversationChatRequest, request: Request) -> StreamingResponse:
    """Stream local answers, optionally grounding current-information questions in Bing results."""
    history = prepare_conversation_turn(payload)
    current_message_id = payload.user_message_id if isinstance(payload, ConversationChatRequest) else None
    history = [item for item in history or [] if item.get("id") != current_message_id]
    if needs_web_search(payload.message):
        async def search_event_stream():
            yield sse_event("start", {"success": True})

            if not WEB_SEARCH_ENABLED:
                yield sse_event(
                    "error",
                    {
                        "message": "Web search is disabled. Set TIA_WEB_SEARCH_ENABLED=true before starting the backend to verify current information."
                    },
                )
                return

            result_limit = min(WEB_SEARCH_MAX_RESULTS, MAX_CHAT_SEARCH_RESULTS)

            async def retrieve_search_sources() -> list[WebSearchResult]:
                search_results = await search_web(payload.message, result_limit)
                return await retrieve_search_content(search_results)

            search_task = asyncio.create_task(retrieve_search_sources())
            try:
                while not search_task.done():
                    if await request.is_disconnected():
                        search_task.cancel()
                        await asyncio.gather(search_task, return_exceptions=True)
                        logger.info("Client disconnected while Bing search was running.")
                        return
                    completed, _ = await asyncio.wait(
                        (search_task,),
                        timeout=SEARCH_HEARTBEAT_INTERVAL_SECONDS,
                    )
                    if not completed:
                        yield b": search-in-progress\n\n"
                results = await search_task
            except asyncio.CancelledError:
                search_task.cancel()
                await asyncio.gather(search_task, return_exceptions=True)
                raise
            except WebSearchTimeoutError:
                yield sse_event("error", {"message": search_failure_message()})
                return
            except WebSearchError:
                yield sse_event("error", {"message": search_failure_message()})
                return

            if await request.is_disconnected():
                logger.info("Client disconnected after Bing search completed.")
                return

            context_results = bounded_search_results(results)
            if not context_results:
                yield sse_event(
                    "error",
                    {
                        "message": "I couldn't find verifiable live search results, so I can't reliably answer this as current."
                    },
                )
                return

            if isinstance(payload, ConversationChatRequest) and payload.user_message_id:
                try:
                    mark_turn_search_used(payload.user_message_id)
                except (NotFoundError, ConflictError, InvalidDataError, StorageError):
                    logger.error("Could not save chat turn search provenance.")
                    yield sse_event("error", {"message": "The conversation turn could not be saved."})
                    return

            ollama_request = ollama_chat_request(
                payload,
                stream=True,
                search_results=context_results,
                history=history,
                current_message_id=current_message_id,
            )
            try:
                upstream = await open_ollama_stream(ollama_request)
            except HTTPException as exc:
                yield sse_event("error", {"message": exc.detail})
                return

            sources = build_sources_markdown(context_results)
            async for event_name, data in saved_content_events(
                upstream, request, payload, history, completion_suffix=sources
            ):
                yield sse_event(event_name, data)

        return StreamingResponse(
            search_event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    ollama_request = ollama_chat_request(payload, stream=True, history=history, current_message_id=current_message_id)
    upstream = await open_ollama_stream(ollama_request)

    async def event_stream():
        yield sse_event("start", {"success": True})
        async for event_name, data in saved_content_events(upstream, request, payload, history):
            yield sse_event(event_name, data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/v1/search", response_model=WebSearchResponse, tags=["search"])
async def web_search_endpoint(payload: WebSearchRequest) -> WebSearchResponse:
    """Search Bing for text results without fetching result pages."""
    if not WEB_SEARCH_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Web search is disabled. Set TIA_WEB_SEARCH_ENABLED=true to enable it.",
        )

    try:
        results: list[WebSearchResult] = await search_web(payload.query, payload.max_results)
    except WebSearchTimeoutError:
        raise HTTPException(status_code=504, detail="Bing search timed out.") from None
    except WebSearchError:
        raise HTTPException(status_code=502, detail="Bing search is unavailable.") from None

    response_results = [
        WebSearchResultResponse(
            title=result.title,
            url=result.url,
            snippet=result.snippet,
            published=result.published,
        )
        for result in results
    ]
    return WebSearchResponse(
        success=True,
        query=payload.query,
        results=response_results,
        result_count=len(response_results),
    )
