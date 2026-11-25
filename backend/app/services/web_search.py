"""DuckDuckGo text search with normalized, validated result records."""

import ipaddress
import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from ddgs.engines.duckduckgo import Duckduckgo
from ddgs.exceptions import DDGSException, TimeoutException

from app.core.config import (
    WEB_SEARCH_MAX_RESULTS,
    WEB_SEARCH_REGION,
    WEB_SEARCH_SAFESEARCH,
    WEB_SEARCH_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


class WebSearchError(Exception):
    """Base class for sanitized web-search failures."""


class WebSearchTimeoutError(WebSearchError):
    """Raised when DuckDuckGo does not respond within the configured timeout."""


class WebSearchProviderError(WebSearchError):
    """Raised when DuckDuckGo cannot complete a valid search response."""


class _DuckDuckGoHTTPError(DDGSException):
    """Keep non-success HTTP responses distinct from empty search results."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"DuckDuckGo returned HTTP {status_code}.")


class _CheckedDuckduckgo(Duckduckgo):
    """DDGS engine with explicit non-200 response handling.

    ddgs 9.16.1's shared base engine treats every non-200 response as an empty
    body. Its public aggregator then reports that as "No results found", hiding
    challenges and provider errors. This subclass keeps the same DDG endpoint
    and parser while preserving the HTTP status for the service layer.
    """

    def request(self, *args: Any, **kwargs: Any) -> str:
        response = self.http_client.request(*args, **kwargs)
        if response.status_code != 200:
            raise _DuckDuckGoHTTPError(response.status_code)
        return response.text


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    """Normalized result. Snippets are untrusted external text, never instructions."""

    title: str
    url: str
    snippet: str
    published: str | None


def _is_public_hostname(hostname: str) -> bool:
    normalized = hostname.rstrip(".").lower()
    if normalized == "localhost" or normalized.endswith(
        (
            ".localhost",
            ".local",
            ".home.arpa",
            ".internal",
            ".lan",
            ".home",
            ".test",
            ".invalid",
            ".example",
            ".onion",
        )
    ):
        return False
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        # A single-label host name is commonly an intranet machine name.
        return "." in normalized
    return address.is_global


def _valid_http_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url or "\\" in url or any(character.isspace() or ord(character) < 33 for character in url):
        return None
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        return None
    if "%" in hostname:
        return None
    if parsed.username is not None or parsed.password is not None:
        return None
    if port is not None and not 1 <= port <= 65535:
        return None
    if not _is_public_hostname(hostname):
        return None
    return url


def _normalize_result(raw: object) -> WebSearchResult | None:
    if isinstance(raw, dict):
        title = raw.get("title")
        snippet = raw.get("body") or raw.get("snippet")
        url = _valid_http_url(raw.get("href") or raw.get("url"))
        published_value = raw.get("published", raw.get("date"))
    else:
        title = getattr(raw, "title", None)
        snippet = getattr(raw, "body", None)
        url = _valid_http_url(getattr(raw, "href", None))
        published_value = getattr(raw, "published", getattr(raw, "date", None))

    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(snippet, str) or not snippet.strip() or url is None:
        return None
    if published_value is not None and not isinstance(published_value, str):
        return None

    published = published_value.strip() if isinstance(published_value, str) else None
    return WebSearchResult(
        title=title.strip(),
        url=url,
        snippet=snippet.strip(),
        published=published or None,
    )


def search_web(query: str, max_results: int) -> list[WebSearchResult]:
    """Search the DuckDuckGo engine and return validated, public HTTP(S) links."""
    limit = min(max(1, max_results), WEB_SEARCH_MAX_RESULTS)
    try:
        client = _CheckedDuckduckgo(timeout=WEB_SEARCH_TIMEOUT_SECONDS)
        raw_results = client.search(
            query=query,
            region=WEB_SEARCH_REGION,
            safesearch=WEB_SEARCH_SAFESEARCH,
            timelimit=None,
            page=1,
        )
    except TimeoutException as exc:
        logger.warning("DuckDuckGo search timed out after %s seconds.", WEB_SEARCH_TIMEOUT_SECONDS)
        raise WebSearchTimeoutError("DuckDuckGo search timed out.") from exc
    except _DuckDuckGoHTTPError as exc:
        logger.warning("DuckDuckGo returned HTTP %s.", exc.status_code)
        raise WebSearchProviderError("DuckDuckGo search is unavailable.") from exc
    except DDGSException as exc:
        logger.warning("DuckDuckGo search provider failed (%s).", type(exc).__name__)
        raise WebSearchProviderError("DuckDuckGo search is unavailable.") from exc
    except Exception as exc:
        logger.warning("DuckDuckGo search failed (%s).", type(exc).__name__)
        raise WebSearchProviderError("DuckDuckGo search is unavailable.") from exc

    if raw_results is None:
        logger.warning("DuckDuckGo returned an empty HTTP response.")
        raise WebSearchProviderError("DuckDuckGo returned an invalid response.")
    if not isinstance(raw_results, list):
        logger.warning("DuckDuckGo returned an unexpected result collection.")
        raise WebSearchProviderError("DuckDuckGo returned an invalid response.")

    normalized: list[WebSearchResult] = []
    seen_urls: set[str] = set()
    for item in raw_results:
        result = _normalize_result(item)
        if result is not None and result.url not in seen_urls:
            normalized.append(result)
            seen_urls.add(result.url)
            if len(normalized) >= limit:
                break
    return normalized
