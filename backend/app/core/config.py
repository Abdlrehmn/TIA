"""Settings shared by the TIA backend."""

import ipaddress
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

APP_NAME = "TIA"
APP_VERSION = "0.1.0"


def _data_directory() -> Path:
    """Choose the per-user application data directory, with an explicit override."""
    configured = os.environ.get("TIA_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "TIA"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "tia"


TIA_DATA_DIR = _data_directory()
_configured_database = os.environ.get("TIA_DATABASE_PATH")
DATABASE_PATH = (
    Path(_configured_database).expanduser().resolve()
    if _configured_database
    else TIA_DATA_DIR / "tia.sqlite3"
)

CORS_ALLOWED_ORIGINS = ("http://localhost:1420", "http://tauri.localhost")
API_PORT = int(os.environ.get("TIA_API_PORT", "8000"))
if not 1 <= API_PORT <= 65535:
    raise ValueError("TIA_API_PORT must be between 1 and 65535.")
API_ALLOWED_HOSTS = (f"127.0.0.1:{API_PORT}", f"localhost:{API_PORT}")

OLLAMA_SYSTEM_PROMPT = os.environ.get(
    "TIA_OLLAMA_SYSTEM_PROMPT",
    """You are TIA, a professional, friendly personal AI assistant.

Answer directly and naturally.
Be concise by default, but provide detailed explanations when explicitly requested.
Use clear and professional language.
Avoid unnecessary emojis, decorative headings, repeated conclusions, and filler.
Use standard Markdown only when it improves readability.
Be honest when you are uncertain or lack current information.
Never invent facts.
Never expose private reasoning, scratch work, or internal deliberation.
Provide the answer and, when useful, a brief explanation.""",
).strip()


def _ollama_base_url() -> str:
    """Read and validate a local-only Ollama URL."""
    value = os.environ.get("TIA_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme != "http" or not parsed.hostname or parsed.port is None:
        raise ValueError("TIA_OLLAMA_BASE_URL must be an http URL with an explicit port.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("TIA_OLLAMA_BASE_URL must not include credentials, query, or fragment.")
    hostname = parsed.hostname.lower()
    is_loopback = hostname == "localhost"
    try:
        is_loopback = is_loopback or ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        pass
    if not is_loopback:
        raise ValueError("TIA_OLLAMA_BASE_URL must use a loopback host.")
    return value


OLLAMA_BASE_URL = _ollama_base_url()
OLLAMA_MODEL = os.environ.get("TIA_OLLAMA_MODEL", "qwen3:4b").strip()
OLLAMA_TIMEOUT_SECONDS = float(os.environ.get("TIA_OLLAMA_TIMEOUT", "120"))
OLLAMA_KEEP_ALIVE = os.environ.get("TIA_OLLAMA_KEEP_ALIVE", "10m").strip()
CHAT_HISTORY_MAX_MESSAGES = int(os.environ.get("TIA_CHAT_HISTORY_MAX_MESSAGES", "12"))
CHAT_HISTORY_MAX_CHARS = int(os.environ.get("TIA_CHAT_HISTORY_MAX_CHARS", "12000"))

if not OLLAMA_MODEL:
    raise ValueError("TIA_OLLAMA_MODEL must not be empty.")
if OLLAMA_TIMEOUT_SECONDS <= 0:
    raise ValueError("TIA_OLLAMA_TIMEOUT must be greater than zero.")
if not OLLAMA_KEEP_ALIVE:
    raise ValueError("TIA_OLLAMA_KEEP_ALIVE must not be empty.")
if not 1 <= CHAT_HISTORY_MAX_MESSAGES <= 100:
    raise ValueError("TIA_CHAT_HISTORY_MAX_MESSAGES must be between 1 and 100.")
if not 1_000 <= CHAT_HISTORY_MAX_CHARS <= 100_000:
    raise ValueError("TIA_CHAT_HISTORY_MAX_CHARS must be between 1000 and 100000.")


def _env_bool(name: str, default: bool) -> bool:
    """Parse a boolean environment variable without truthy-string surprises."""
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false.")


WEB_SEARCH_ENABLED = _env_bool("TIA_WEB_SEARCH_ENABLED", False)
WEB_SEARCH_TIMEOUT_SECONDS = int(os.environ.get("TIA_WEB_SEARCH_TIMEOUT", "10"))
WEB_SEARCH_MAX_RESULTS = int(os.environ.get("TIA_WEB_SEARCH_MAX_RESULTS", "5"))
WEB_SEARCH_SAFESEARCH = os.environ.get("TIA_WEB_SEARCH_SAFESEARCH", "moderate").strip().lower()
WEB_SEARCH_REGION = os.environ.get("TIA_WEB_SEARCH_REGION", "us-en").strip().lower()
WEB_SEARCH_MAX_PAGES = int(os.environ.get("TIA_WEB_SEARCH_MAX_PAGES", "3"))
WEB_SEARCH_PAGE_TIMEOUT_SECONDS = int(os.environ.get("TIA_WEB_SEARCH_PAGE_TIMEOUT", "8"))
WEB_SEARCH_TOTAL_CONTENT_TIMEOUT_SECONDS = int(os.environ.get("TIA_WEB_SEARCH_TOTAL_CONTENT_TIMEOUT", "25"))
WEB_SEARCH_MAX_PAGE_BYTES = int(os.environ.get("TIA_WEB_SEARCH_MAX_PAGE_BYTES", str(2 * 1024 * 1024)))
WEB_SEARCH_MAX_PAGE_CHARS = int(os.environ.get("TIA_WEB_SEARCH_MAX_PAGE_CHARS", "5000"))

if not 1 <= WEB_SEARCH_TIMEOUT_SECONDS <= 120:
    raise ValueError("TIA_WEB_SEARCH_TIMEOUT must be between 1 and 120 seconds.")
if not 1 <= WEB_SEARCH_MAX_RESULTS <= 20:
    raise ValueError("TIA_WEB_SEARCH_MAX_RESULTS must be between 1 and 20.")
if not 1 <= WEB_SEARCH_MAX_PAGES <= 5:
    raise ValueError("TIA_WEB_SEARCH_MAX_PAGES must be between 1 and 5.")
if not 1 <= WEB_SEARCH_PAGE_TIMEOUT_SECONDS <= 30:
    raise ValueError("TIA_WEB_SEARCH_PAGE_TIMEOUT must be between 1 and 30 seconds.")
if not WEB_SEARCH_PAGE_TIMEOUT_SECONDS <= WEB_SEARCH_TOTAL_CONTENT_TIMEOUT_SECONDS <= 120:
    raise ValueError("TIA_WEB_SEARCH_TOTAL_CONTENT_TIMEOUT must be at least the page timeout and at most 120 seconds.")
if not 64 * 1024 <= WEB_SEARCH_MAX_PAGE_BYTES <= 10 * 1024 * 1024:
    raise ValueError("TIA_WEB_SEARCH_MAX_PAGE_BYTES must be between 65536 and 10485760.")
if not 1_000 <= WEB_SEARCH_MAX_PAGE_CHARS <= 20_000:
    raise ValueError("TIA_WEB_SEARCH_MAX_PAGE_CHARS must be between 1000 and 20000.")
if WEB_SEARCH_SAFESEARCH not in {"on", "moderate", "off"}:
    raise ValueError("TIA_WEB_SEARCH_SAFESEARCH must be on, moderate, or off.")
if not re.fullmatch(r"[a-z]{2}-[a-z]{2}", WEB_SEARCH_REGION):
    raise ValueError("TIA_WEB_SEARCH_REGION must use a language-region code such as us-en.")
