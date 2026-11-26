"""Bounded webpage retrieval for validated results returned by Bing search."""

import asyncio
import ipaddress
import logging
import re
import unicodedata
from dataclasses import replace
from typing import Any
from urllib.parse import urljoin, urlsplit

from curl_cffi import CurlOpt
from curl_cffi.curl import CURL_WRITEFUNC_ERROR
from curl_cffi.requests import AsyncSession
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from scrapling.engines.static import AsyncFetcherClient
from scrapling.parser import Selector

from app.core.config import (
    WEB_SEARCH_MAX_PAGE_BYTES,
    WEB_SEARCH_MAX_PAGE_CHARS,
    WEB_SEARCH_MAX_PAGES,
    WEB_SEARCH_PAGE_TIMEOUT_SECONDS,
    WEB_SEARCH_TOTAL_CONTENT_TIMEOUT_SECONDS,
)
from app.services.network_safety import normalize_public_hostname, public_browser_route, resolve_public_addresses, valid_http_url
from app.services.web_search import WebSearchResult, search_provider, _canonical_url

logger = logging.getLogger(__name__)

_MAX_REDIRECTS = 5
_ALLOWED_CONTENT_PORTS = {80, 443}
_TEXT_MIME_TYPES = {"text/html", "application/xhtml+xml"}
_DROP_TEXT_ANCESTOR_XPATH = (
    "ancestor::script or ancestor::style or ancestor::noscript or ancestor::svg "
    "or ancestor::nav or ancestor::header or ancestor::footer or ancestor::aside "
    "or ancestor::form or ancestor::button or ancestor::select or ancestor::textarea "
    "or ancestor::iframe or ancestor::*[@hidden or @aria-hidden='true' or @role='complementary'] "
    "or ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' advertisement ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' advert ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' ad ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' ads ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' sponsored ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' promo ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' menu ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' navigation ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' topnav ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' w3-bar ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' w3-sidebar ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' searchbox ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' header ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' sidebar ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' cookie-banner ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' breadcrumb ') "
    "or contains(concat(' ', normalize-space(@class), ' '), ' social-share ') "
    "or contains(concat(' ', normalize-space(@id), ' '), ' leftmenu ') "
    "or contains(concat(' ', normalize-space(@id), ' '), ' topnav ') "
    "or contains(concat(' ', normalize-space(@id), ' '), ' searchbox ') "
    "or contains(concat(' ', normalize-space(@id), ' '), ' footer ')]"
)


class PageFetchError(Exception):
    """Raised for a rejected or unusable external page."""


class PageTooLargeError(PageFetchError):
    """Raised when a response exceeds the configured byte limit."""


def _content_url(value: object) -> str | None:
    url = valid_http_url(value, allowed_ports=_ALLOWED_CONTENT_PORTS)
    if url is None:
        return None
    parsed = urlsplit(url)
    expected_port = 443 if parsed.scheme.lower() == "https" else 80
    if parsed.port not in {None, expected_port}:
        return None
    return url


def _public_ip(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise PageFetchError("The page destination did not resolve safely.") from None
    if not address.is_global:
        raise PageFetchError("The page destination did not resolve safely.")
    return address.compressed


def _resolve_pin(hostname: str, port: int, address: str) -> str:
    normalized_host = normalize_public_hostname(hostname)
    if normalized_host is None:
        raise PageFetchError("The page destination is not public.")
    address = _public_ip(address)
    resolve_address = f"[{address}]" if ":" in address else address
    return f"{normalized_host}:{port}:{resolve_address}"


def _main_text_from_selector(page: Any) -> tuple[str, str]:
    title = " ".join(page.xpath("//title//text()").getall())
    title = _sanitize_text(title, 300)
    selectors = ("//article", "//main", "//*[@role='main']", "//body")
    excluded_text = f"not({_DROP_TEXT_ANCESTOR_XPATH})"
    text = ""
    for selector in selectors:
        candidates = page.xpath(selector)
        candidate_texts = []
        for node in candidates:
            value = " ".join(node.xpath(f".//text()[{excluded_text}]").getall())
            value = _sanitize_text(value, WEB_SEARCH_MAX_PAGE_CHARS)
            if value:
                candidate_texts.append(value)
        if candidate_texts:
            text = max(candidate_texts, key=len)
            break
    text = text[:WEB_SEARCH_MAX_PAGE_CHARS]
    return title, text


def _sanitize_text(value: str, limit: int) -> str:
    value = "".join(
        character for character in value
        if character in "\t\n\r" or not unicodedata.category(character).startswith("C")
    )
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _needs_browser_fallback(text: str) -> bool:
    lowered = text.lower()
    return len(text.strip()) < 120 or any(
        marker in lowered
        for marker in (
            "enable javascript",
            "javascript is required",
            "please turn on javascript",
            "this page requires javascript",
            "verify you are human",
            "unusual traffic",
            "checking your browser",
            "complete the security check",
            "access denied",
            "before you continue",
            "consent_required",
            "captcha",
        )
    )


def _is_block_page(title: str, text: str) -> bool:
    title = title.lower()
    text = text.lower()
    return any(marker in title for marker in ("captcha", "robot check", "access denied", "security check")) or any(
        marker in text
        for marker in (
            "verify you are human",
            "unusual traffic",
            "checking your browser",
            "complete the security check",
            "request has been blocked",
            "consent_required",
            "before you continue",
        )
    )


class WebContentRetriever:
    """Fetch a few search result pages using pinned Scrapling requests first."""

    def __init__(self, max_concurrent: int = 4) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def enrich(self, results: list[WebSearchResult]) -> list[WebSearchResult]:
        if not results:
            return []
        output = list(results)
        seen: set[str] = set()
        page_indices: list[int] = []
        for index, result in enumerate(results):
            safe_url = _content_url(result.url)
            if safe_url is None:
                continue
            canonical = _canonical_url(safe_url)
            if canonical in seen:
                continue
            seen.add(canonical)
            if len(page_indices) < WEB_SEARCH_MAX_PAGES:
                page_indices.append(index)

        async def fetch_all() -> None:
            tasks = [asyncio.create_task(self._enrich_one(output[index])) for index in page_indices]
            values = await asyncio.gather(*tasks, return_exceptions=True)
            for index, value in zip(page_indices, values, strict=True):
                if isinstance(value, WebSearchResult):
                    output[index] = value
                elif isinstance(value, BaseException) and not isinstance(value, asyncio.CancelledError):
                    logger.warning("Search result content was unavailable (%s).", type(value).__name__)

        try:
            await asyncio.wait_for(fetch_all(), timeout=WEB_SEARCH_TOTAL_CONTENT_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning("Total webpage content retrieval timed out; using available search snippets.")
        return output

    async def _enrich_one(self, result: WebSearchResult) -> WebSearchResult:
        async with self._semaphore:
            url = _content_url(result.url)
            if url is None:
                return result
            try:
                title, text = await asyncio.wait_for(
                    self._fetch_with_scrapling(url), timeout=WEB_SEARCH_PAGE_TIMEOUT_SECONDS
                )
                if not text or _needs_browser_fallback(text) or _is_block_page(title, text):
                    title, text = await self._fetch_with_browser(url)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.info("Scrapling page retrieval failed (%s); trying browser fallback.", type(exc).__name__)
                try:
                    title, text = await self._fetch_with_browser(url)
                except asyncio.CancelledError:
                    raise
                except Exception as fallback_exc:
                    logger.info("Browser page retrieval failed (%s); retaining search snippet.", type(fallback_exc).__name__)
                    return result
            if not text.strip() or _is_block_page(title, text):
                return result
            return replace(result, title=title or result.title, content=text[:WEB_SEARCH_MAX_PAGE_CHARS])

    async def _fetch_with_scrapling(self, initial_url: str) -> tuple[str, str]:
        current_url = initial_url
        for redirect_count in range(_MAX_REDIRECTS + 1):
            current_url = _content_url(current_url) or ""
            if not current_url:
                raise PageFetchError("The page redirected to an unsafe destination.")
            parsed = urlsplit(current_url)
            hostname = normalize_public_hostname(parsed.hostname or "")
            if hostname is None:
                raise PageFetchError("The page destination is not public.")
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            addresses = await resolve_public_addresses(hostname, port, min(3, WEB_SEARCH_PAGE_TIMEOUT_SECONDS))
            pins = [_resolve_pin(hostname, port, address) for address in addresses]

            body = bytearray()
            oversized = False

            def collect_chunk(chunk: bytes) -> int:
                nonlocal oversized
                if len(body) + len(chunk) > WEB_SEARCH_MAX_PAGE_BYTES:
                    oversized = True
                    return CURL_WRITEFUNC_ERROR
                body.extend(chunk)
                return len(chunk)

            session = AsyncSession(
                timeout=WEB_SEARCH_PAGE_TIMEOUT_SECONDS,
                trust_env=False,
                curl_options={CurlOpt.RESOLVE: pins},
            )
            fetcher = AsyncFetcherClient(
                timeout=WEB_SEARCH_PAGE_TIMEOUT_SECONDS,
                retries=1,
                retry_delay=0,
                follow_redirects=False,
                max_redirects=0,
                stealthy_headers=False,
            )
            # Scrapling's fetcher client accepts a caller-owned curl session;
            # CURLOPT_RESOLVE pins TLS and TCP to the addresses validated above.
            fetcher._async_curl_session = session
            try:
                response = await fetcher.get(
                    current_url,
                    timeout=WEB_SEARCH_PAGE_TIMEOUT_SECONDS,
                    follow_redirects=False,
                    max_redirects=0,
                    retries=1,
                    retry_delay=0,
                    content_callback=collect_chunk,
                )
            except Exception as exc:
                if oversized:
                    raise PageTooLargeError("The page response exceeded the configured size limit.") from None
                raise PageFetchError("The page could not be retrieved safely.") from exc
            finally:
                await session.close()

            if oversized or len(body) > WEB_SEARCH_MAX_PAGE_BYTES:
                raise PageTooLargeError("The page response exceeded the configured size limit.")
            status = int(getattr(response, "status", 0))
            headers = getattr(response, "headers", {})
            location = headers.get("location") if hasattr(headers, "get") else None
            if status in {301, 302, 303, 307, 308}:
                if not location or redirect_count >= _MAX_REDIRECTS:
                    raise PageFetchError("The page redirect could not be followed safely.")
                current_url = urljoin(current_url, str(location))
                if _content_url(current_url) is None:
                    raise PageFetchError("The page redirected to an unsafe destination.")
                continue
            if status < 200 or status >= 300:
                raise PageFetchError("The page returned an unsuccessful response.")
            content_type = str(headers.get("content-type", "")).split(";", 1)[0].lower()
            if content_type not in _TEXT_MIME_TYPES:
                raise PageFetchError("The page is not an HTML document.")
            return _main_text_from_selector(Selector(content=bytes(body), url=current_url))
        raise PageFetchError("The page exceeded the redirect limit.")

    async def _fetch_with_browser(self, url: str) -> tuple[str, str]:
        browser = search_provider._browser
        if browser is None:
            raise PageFetchError("The browser fallback is unavailable.")
        safe_url = _content_url(url)
        if safe_url is None:
            raise PageFetchError("The page URL is not safe.")
        context = await browser.new_context(accept_downloads=False)
        try:
            await context.route("**/*", lambda route: public_browser_route(route))
            page = await context.new_page()
            response = await asyncio.wait_for(
                page.goto(
                    safe_url,
                    wait_until="domcontentloaded",
                    timeout=WEB_SEARCH_PAGE_TIMEOUT_SECONDS * 1000,
                ),
                timeout=WEB_SEARCH_PAGE_TIMEOUT_SECONDS,
            )
            if response is None or response.status < 200 or response.status >= 300:
                raise PageFetchError("The page returned an unsuccessful browser response.")
            html = await asyncio.wait_for(page.content(), timeout=WEB_SEARCH_PAGE_TIMEOUT_SECONDS)
            if len(html.encode("utf-8")) > WEB_SEARCH_MAX_PAGE_BYTES:
                raise PageTooLargeError("The rendered page exceeded the configured size limit.")
            return _main_text_from_selector(Selector(content=html, url=safe_url))
        except PlaywrightTimeoutError as exc:
            raise TimeoutError("The page browser navigation timed out.") from exc
        finally:
            await context.close()


web_content_retriever = WebContentRetriever()


async def retrieve_search_content(results: list[WebSearchResult]) -> list[WebSearchResult]:
    """Enrich search results with bounded page text, retaining snippets on failure."""
    return await web_content_retriever.enrich(results)
