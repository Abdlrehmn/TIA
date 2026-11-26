"""Bing search-result discovery through Scrapling with a Playwright fallback."""

import asyncio
import base64
import logging
import re
import unicodedata
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from curl_cffi.requests.exceptions import Timeout as CurlTimeoutError
from curl_cffi.const import CurlOpt
from curl_cffi.requests import AsyncSession
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from scrapling.fetchers import AsyncFetcher
from scrapling.engines.static import AsyncFetcherClient
from scrapling.parser import Selector

from app.core.config import (
    WEB_SEARCH_MAX_RESULTS,
    WEB_SEARCH_MAX_PAGE_BYTES,
    WEB_SEARCH_REGION,
    WEB_SEARCH_SAFESEARCH,
    WEB_SEARCH_TIMEOUT_SECONDS,
)
from app.services.network_safety import (
    PublicOnlyHTTPProxy,
    normalize_public_hostname,
    public_browser_route,
    valid_http_url as _valid_http_url,
)

logger = logging.getLogger(__name__)

_BING_SEARCH_URL = "https://www.bing.com/search"
_MAX_CONCURRENT_SEARCHES = 4
_MAX_TITLE_CHARS = 300
_MAX_SNIPPET_CHARS = 1_000
_BLOCK_MARKERS = (
    "captcha",
    "unusual traffic",
    "automated requests",
    "automated queries",
    "verify you are human",
    "please verify you are human",
    "robot check",
    "consent_required",
    "before you continue",
    "unusual activity",
    "access denied",
    "request has been blocked",
    "temporarily blocked",
    "too many requests",
    "one last step",
)


class WebSearchError(Exception):
    """Base class for sanitized web-search failures."""


class WebSearchTimeoutError(WebSearchError):
    """Raised when neither search retrieval method completes in time."""


class WebSearchProviderError(WebSearchError):
    """Raised when Bing blocks the request or providers fail."""


@dataclass(frozen=True, slots=True)
class WebSearchResult:
    """Validated search result; snippets remain untrusted external text."""

    title: str
    url: str
    snippet: str
    published: str | None
    content: str | None = None


def _unwrap_bing_url(value: object) -> str | None:
    """Decode Bing's /ck/a redirect parameter; reject other Bing navigation URLs."""
    url = _valid_http_url(value)
    if url is None:
        return None
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if hostname == "bing.com" or hostname.endswith(".bing.com"):
        if parsed.path.rstrip("/").lower() != "/ck/a":
            return None
        encoded = parse_qs(parsed.query).get("u", [""])[0]
        if not encoded.startswith("a1"):
            return None
        try:
            padding = "=" * (-len(encoded[2:]) % 4)
            decoded = base64.urlsafe_b64decode(encoded[2:] + padding).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
        url = _valid_http_url(decoded)
        if url is None:
            return None
        parsed = urlsplit(url)
        destination_host = (parsed.hostname or "").lower().rstrip(".")
        if destination_host == "bing.com" or destination_host.endswith(".bing.com"):
            return None
    # Search results never need a fragment, and removing it deduplicates anchors.
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if ":" in hostname:
        hostname = f"[{hostname}]"
    port = parsed.port
    netloc = hostname if port is None else f"{hostname}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path, parsed.query, ""))


def _clean_text(value: str, limit: int) -> str:
    clean = unescape(value)
    clean = "".join(
        char for char in clean
        if char in "\t\n\r" or not unicodedata.category(char).startswith("C")
    )
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = re.sub(r"\s+([,.;:!?])", r"\1", clean)
    return clean[:limit]


def _is_block_page(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _BLOCK_MARKERS)


def _canonical_url(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    default_port = (parsed.scheme == "https" and port == 443) or (parsed.scheme == "http" and port == 80)
    netloc = host if port is None or default_port else f"{host}:{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path.rstrip("/"), parsed.query, ""))


def _parse_results(page: Any, max_results: int) -> list[WebSearchResult]:
    """Extract organic Bing result blocks only, validating every field."""
    body_text = str(page.get_all_text())
    page_title = _clean_text(str(page.xpath("//title/text()").get() or ""), 100).lower()
    if _is_block_page(body_text) or page_title in {"consent", "bing consent", "captcha"}:
        raise WebSearchProviderError("Bing returned a blocked or consent response.")

    nodes = page.xpath("//li[contains(concat(' ', normalize-space(@class), ' '), ' b_algo ')]")
    results: list[WebSearchResult] = []
    seen: set[str] = set()
    for node in nodes:
        classes = str(node.attrib.get("class", "")).lower().split()
        if any("ad" in class_name for class_name in classes):
            continue
        title_selector = node.xpath(".//h2/a")
        title = _clean_text(" ".join(title_selector.xpath(".//text()").getall()), _MAX_TITLE_CHARS)
        url = _unwrap_bing_url(title_selector.xpath("./@href").get())
        snippet = _clean_text(
            " ".join(
                node.xpath(
                    ".//div[contains(@class, 'b_caption')]//p//text()[not(ancestor::a)]"
                ).getall()
            ),
            _MAX_SNIPPET_CHARS,
        )
        if not title or not snippet or url is None:
            continue
        canonical = _canonical_url(url)
        if canonical in seen:
            continue
        seen.add(canonical)
        results.append(WebSearchResult(title, url, snippet, None))
        if len(results) >= max_results:
            break
    return results


def _search_url(query: str, limit: int) -> str:
    country, _, language = WEB_SEARCH_REGION.partition("-")
    params = {"q": query, "count": str(limit), "mkt": f"{language}-{country.upper()}"}
    if WEB_SEARCH_SAFESEARCH == "on":
        params["adlt"] = "strict"
    elif WEB_SEARCH_SAFESEARCH == "off":
        params["adlt"] = "off"
    else:
        params["adlt"] = "moderate"
    return f"{_BING_SEARCH_URL}?{urlencode(params)}"


class BingSearchProvider:
    """Use Scrapling first and one shared Playwright browser as the fallback."""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_SEARCHES)
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._safe_proxy = PublicOnlyHTTPProxy(max_tunnel_bytes=WEB_SEARCH_MAX_PAGE_BYTES)

    async def start(self) -> None:
        """Start the shared browser during application lifespan, if possible."""
        if self._browser is not None:
            return
        try:
            proxy_endpoint = await self._safe_proxy.start()
            self._playwright = await async_playwright().start()
            self._browser = await asyncio.wait_for(
                self._playwright.chromium.launch(
                    headless=True,
                    proxy={
                        "server": proxy_endpoint,
                        "bypass": "",
                        "username": self._safe_proxy.username,
                        "password": self._safe_proxy.password,
                    },
                ),
                timeout=WEB_SEARCH_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            logger.warning("Playwright search fallback could not start (%s).", type(exc).__name__)
            await self.close()

    async def close(self) -> None:
        """Close the shared browser and Playwright driver during shutdown."""
        browser, playwright = self._browser, self._playwright
        self._browser = None
        self._playwright = None
        if browser is not None:
            try:
                await browser.close()
            except Exception as exc:
                logger.warning("Playwright browser shutdown failed (%s).", type(exc).__name__)
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception as exc:
                logger.warning("Playwright driver shutdown failed (%s).", type(exc).__name__)
        await self._safe_proxy.close()

    async def search(self, query: str, max_results: int) -> list[WebSearchResult]:
        limit = min(max(1, max_results), WEB_SEARCH_MAX_RESULTS)
        async with self._semaphore:
            primary_timed_out = False
            try:
                response = await asyncio.wait_for(
                    AsyncFetcher.get(
                        _search_url(query, limit),
                        timeout=WEB_SEARCH_TIMEOUT_SECONDS * 1000,
                        retries=1,
                        retry_delay=0,
                    ),
                    timeout=WEB_SEARCH_TIMEOUT_SECONDS + 1,
                )
                if getattr(response, "status", 200) != 200:
                    raise WebSearchProviderError("Bing returned an unsuccessful response.")
                results = _parse_results(response, limit)
                if results:
                    return results
            except (asyncio.TimeoutError, TimeoutError, CurlTimeoutError, PlaywrightTimeoutError):
                primary_timed_out = True
                logger.warning("Scrapling Bing search timed out.")
            except WebSearchProviderError as exc:
                logger.warning("Scrapling Bing search requires fallback (%s).", str(exc))
            except Exception as exc:
                logger.warning("Scrapling Bing search failed (%s).", type(exc).__name__)

            try:
                results = await self._search_with_browser(query, limit)
                if results:
                    return results
            except (asyncio.TimeoutError, TimeoutError, PlaywrightTimeoutError):
                logger.warning("Playwright Bing search timed out.")
                raise WebSearchTimeoutError("Bing search timed out.") from None
            except WebSearchProviderError:
                if primary_timed_out:
                    raise WebSearchTimeoutError("Bing search timed out.") from None
                raise
            except (asyncio.TimeoutError, TimeoutError, PlaywrightTimeoutError):
                raise WebSearchTimeoutError("Bing search timed out.") from None
            except Exception as exc:
                logger.warning("Playwright Bing search failed (%s).", type(exc).__name__)
                if primary_timed_out:
                    raise WebSearchTimeoutError("Bing search timed out.") from None
                raise WebSearchProviderError("Bing search is unavailable.") from None
            if primary_timed_out:
                raise WebSearchTimeoutError("Bing search timed out.") from None
            return []

    async def _search_with_browser(self, query: str, limit: int) -> list[WebSearchResult]:
        browser = self._browser
        if browser is None:
            raise WebSearchProviderError("Bing search is unavailable.")
        context = await browser.new_context()
        try:
            await context.route("**/*", lambda route: public_browser_route(route))
            page = await context.new_page()
            response = await asyncio.wait_for(
                page.goto(
                    _search_url(query, limit),
                    wait_until="domcontentloaded",
                    timeout=WEB_SEARCH_TIMEOUT_SECONDS * 1000,
                ),
                timeout=WEB_SEARCH_TIMEOUT_SECONDS + 1,
            )
            if response is None or response.status != 200:
                raise WebSearchProviderError("Bing returned an unsuccessful response.")
            html = await page.content()
            return _parse_results(Selector(content=html), limit)
        finally:
            await context.close()


search_provider = BingSearchProvider()


async def start_web_search() -> None:
    await search_provider.start()


async def close_web_search() -> None:
    await search_provider.close()


async def search_web(query: str, max_results: int) -> list[WebSearchResult]:
    """Search Bing for validated links without fetching any result pages."""
    return await search_provider.search(query, max_results)
