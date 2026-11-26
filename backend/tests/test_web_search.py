"""Bing discovery, provider fallback, validation, lifecycle, and API tests."""

import asyncio
import base64
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlencode

from fastapi import HTTPException
from pydantic import ValidationError
from scrapling.parser import Selector

from app import main
from app.core import config
from app.services import web_search


def bing_html(entries: list[tuple[str, str, str]]) -> str:
    blocks = []
    for title, url, snippet in entries:
        encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
        redirect = "https://www.bing.com/ck/a?" + urlencode({"u": "a1" + encoded})
        blocks.append(
            "<li class='b_algo'><h2><a href='{}'>{}</a></h2>"
            "<div class='b_caption'><p>{}</p></div></li>".format(redirect, title, snippet)
        )
    return "<html><head><title>Query - Search</title></head><body>{}</body></html>".format("".join(blocks))


class FakeResponse:
    def __init__(self, html: str, status: int = 200) -> None:
        self.status = status
        self._selector = Selector(content=html)

    def xpath(self, selector: str):
        return self._selector.xpath(selector)

    def get_all_text(self) -> str:
        return str(self._selector.get_all_text())


class FakePage:
    def __init__(self, html: str, status: int = 200) -> None:
        self.html = html
        self.status = status

    async def goto(self, *_args, **_kwargs):
        return MagicMock(status=self.status)

    async def content(self) -> str:
        return self.html


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.closed = False

    async def route(self, *_args, **_kwargs):
        return None

    async def new_page(self):
        return self.page

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self.context = FakeContext(page)
        self.context_count = 0

    async def new_context(self):
        self.context_count += 1
        return self.context


class WebSearchProviderTests(unittest.TestCase):
    def provider(self) -> web_search.BingSearchProvider:
        return web_search.BingSearchProvider()

    def test_scrapling_success_extracts_and_validates_organic_result(self):
        response = FakeResponse(
            bing_html([("Example title", "https://example.com/article", "A useful snippet.")])
        )
        provider = self.provider()

        async def run():
            with patch.object(web_search.AsyncFetcher, "get", new=AsyncMock(return_value=response)) as fetch:
                results = await provider.search("example query", 3)
            fetch.assert_awaited_once()
            self.assertEqual(fetch.await_args.kwargs["retries"], 1)
            return results

        self.assertEqual(
            asyncio.run(run()),
            [web_search.WebSearchResult("Example title", "https://example.com/article", "A useful snippet.", None)],
        )

    def test_scrapling_block_page_triggers_playwright_fallback(self):
        provider = self.provider()
        browser = FakeBrowser(
            FakePage(bing_html([("Fallback", "https://example.org", "Browser result")]))
        )
        provider._browser = browser

        async def run():
            with patch.object(
                web_search.AsyncFetcher,
                "get",
                new=AsyncMock(return_value=FakeResponse("<html><body>Verify you are human CAPTCHA</body></html>")),
            ):
                return await provider.search("query", 2)

        results = asyncio.run(run())
        self.assertEqual(results[0].title, "Fallback")
        self.assertEqual(browser.context_count, 1)
        self.assertTrue(browser.context.closed)

    def test_scrapling_timeout_uses_playwright_fallback(self):
        provider = self.provider()
        provider._browser = FakeBrowser(
            FakePage(bing_html([("Fallback", "https://example.org", "Browser result")]))
        )

        async def run():
            with patch.object(web_search.AsyncFetcher, "get", new=AsyncMock(side_effect=TimeoutError)):
                return await provider.search("query", 2)

        self.assertEqual(asyncio.run(run())[0].title, "Fallback")

    def test_both_providers_failing_returns_sanitized_error(self):
        provider = self.provider()
        provider._browser = FakeBrowser(FakePage("<html><body>CAPTCHA</body></html>"))

        async def run():
            with patch.object(
                web_search.AsyncFetcher,
                "get",
                new=AsyncMock(side_effect=RuntimeError("private detail")),
            ):
                with self.assertRaises(web_search.WebSearchProviderError) as caught:
                    await provider.search("query", 2)
                self.assertNotIn("private detail", str(caught.exception))

        asyncio.run(run())

    def test_invalid_urls_and_duplicate_results_are_rejected(self):
        entries = [
            ("Local", "http://127.0.0.1/", "Unsafe"),
            ("Short loopback", "http://127.1/", "Unsafe"),
            ("Hex loopback", "http://0x7f000001/", "Unsafe"),
            ("Private", "http://10.0.0.1/", "Unsafe"),
            ("Malformed", "javascript:alert(1)", "Unsafe"),
            ("Bing nav", "https://www.bing.com/news", "Navigation"),
            ("Good", "https://example.com/page#first", "First snippet"),
            ("Duplicate", "https://EXAMPLE.com/page#second", "Second snippet"),
        ]
        results = web_search._parse_results(FakeResponse(bing_html(entries)), 10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].url, "https://example.com/page")

    def test_ad_result_blocks_are_rejected(self):
        html = bing_html(
            [
                ("Sponsored", "https://ads.example.com", "Ad snippet"),
                ("Organic", "https://example.com", "Organic snippet"),
            ]
        ).replace("class='b_algo'", "class='b_ad b_algo'", 1)
        results = web_search._parse_results(FakeResponse(html), 5)
        self.assertEqual([result.title for result in results], ["Organic"])

    def test_captcha_consent_and_bot_pages_are_detected(self):
        blocked_pages = (
            "<html><body>CAPTCHA</body></html>",
            "<html><body>Before you continue, please review your privacy choices.</body></html>",
            "<html><body>We detected unusual traffic from this network.</body></html>",
            "<html><body>Your request has been blocked.</body></html>",
        )
        for content in blocked_pages:
            with self.subTest(content=content), self.assertRaises(web_search.WebSearchProviderError):
                web_search._parse_results(FakeResponse(content), 5)

    def test_concurrent_searches_are_bounded_by_semaphore(self):
        provider = self.provider()
        active = 0
        peak = 0

        async def fetch(*_args, **_kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            return FakeResponse(bing_html([("Result", "https://example.com", "Snippet")]))

        async def run():
            with patch.object(web_search.AsyncFetcher, "get", new=AsyncMock(side_effect=fetch)):
                await asyncio.gather(*(provider.search(f"query {index}", 1) for index in range(12)))

        asyncio.run(run())
        self.assertLessEqual(peak, web_search._MAX_CONCURRENT_SEARCHES)
        self.assertGreater(peak, 1)

    def test_browser_startup_and_shutdown_manage_single_shared_instance(self):
        browser = MagicMock()
        browser.close = AsyncMock()
        playwright = MagicMock()
        playwright.chromium.launch = AsyncMock(return_value=browser)
        playwright.stop = AsyncMock()
        manager = MagicMock()
        manager.start = AsyncMock(return_value=playwright)
        provider = self.provider()
        provider._safe_proxy.start = AsyncMock(return_value="http://127.0.0.1:12345")
        provider._safe_proxy.close = AsyncMock()

        async def run():
            with patch("app.services.web_search.async_playwright", return_value=manager):
                await provider.start()
                await provider.start()
                await provider.close()

        asyncio.run(run())
        manager.start.assert_awaited_once()
        playwright.chromium.launch.assert_awaited_once_with(
            headless=True,
            proxy={
                "server": "http://127.0.0.1:12345",
                "bypass": "",
                "username": provider._safe_proxy.username,
                "password": provider._safe_proxy.password,
            },
        )
        browser.close.assert_awaited_once()
        playwright.stop.assert_awaited_once()
        provider._safe_proxy.close.assert_awaited_once()
        self.assertIsNone(provider._browser)


class WebSearchEndpointTests(unittest.TestCase):
    def test_request_validation_rejects_empty_long_and_excessive_values(self):
        for query in ("", "   ", "q" * 401):
            with self.subTest(query_length=len(query)), self.assertRaises(ValidationError):
                main.WebSearchRequest(query=query)
        with self.assertRaises(ValidationError):
            main.WebSearchRequest(query="hello", max_results=config.WEB_SEARCH_MAX_RESULTS + 1)

    def test_disabled_endpoint_returns_clear_503(self):
        with patch.object(main, "WEB_SEARCH_ENABLED", False):
            with self.assertRaises(HTTPException) as caught:
                asyncio.run(main.web_search_endpoint(main.WebSearchRequest(query="hello")))
        self.assertEqual(caught.exception.status_code, 503)
        self.assertIn("TIA_WEB_SEARCH_ENABLED=true", caught.exception.detail)

    def test_enabled_endpoint_preserves_typed_response_contract(self):
        expected = [web_search.WebSearchResult("Title", "https://example.com", "Snippet", None)]

        async def run():
            with (
                patch.object(main, "WEB_SEARCH_ENABLED", True),
                patch("app.main.search_web", new=AsyncMock(return_value=expected)) as search,
            ):
                response = await main.web_search_endpoint(main.WebSearchRequest(query=" hello "))
            search.assert_awaited_once_with("hello", config.WEB_SEARCH_MAX_RESULTS)
            return response

        response = asyncio.run(run())
        self.assertEqual(
            response.model_dump(),
            {
                "success": True,
                "query": "hello",
                "results": [{"title": "Title", "url": "https://example.com", "snippet": "Snippet", "published": None}],
                "result_count": 1,
            },
        )

    def test_endpoint_maps_provider_error_and_timeout(self):
        payload = main.WebSearchRequest(query="hello")
        cases = (
            (web_search.WebSearchProviderError("private provider details"), 502),
            (web_search.WebSearchTimeoutError("private timeout detail"), 504),
        )
        for error, expected_status in cases:
            with self.subTest(status=expected_status):
                async def run():
                    with (
                        patch.object(main, "WEB_SEARCH_ENABLED", True),
                        patch("app.main.search_web", new=AsyncMock(side_effect=error)),
                    ):
                        with self.assertRaises(HTTPException) as caught:
                            await main.web_search_endpoint(payload)
                    self.assertEqual(caught.exception.status_code, expected_status)
                    self.assertNotIn("private", caught.exception.detail)

                asyncio.run(run())


class ExistingEndpointRegressionTests(unittest.TestCase):
    def test_health_endpoint_still_responds(self):
        self.assertEqual(main.health_check().status, "healthy")

    @patch("app.main.urlopen")
    def test_non_streaming_chat_still_uses_ollama_response(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({"message": {"content": "Hello"}}).encode()
        urlopen.return_value = response

        result = main.test_message(main.TestMessageRequest(message="Hi"))
        self.assertEqual(result.reply, "Hello")

    def test_chat_stream_route_still_returns_sse(self):
        upstream = MagicMock()
        upstream.readline.side_effect = [
            b'{"message":{"content":"Hello"},"done":false}\n',
            b'{"message":{"content":" world"},"done":true}\n',
            b"",
        ]
        request = MagicMock()
        request.is_disconnected = AsyncMock(return_value=False)

        async def exercise():
            with patch("app.main.urlopen", return_value=upstream):
                response = await main.stream_message(main.TestMessageRequest(message="Hi"), request)
            frames = [frame async for frame in response.body_iterator]
            return response, b"".join(frames)

        response, body = asyncio.run(exercise())
        self.assertEqual(response.media_type, "text/event-stream")
        self.assertIn(b"event: delta", body)
        self.assertIn(b"event: done", body)


if __name__ == "__main__":
    unittest.main()
