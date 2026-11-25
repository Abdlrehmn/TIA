"""Focused tests for TIA's opt-in DuckDuckGo search endpoint."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ddgs.exceptions import DDGSException, TimeoutException
from fastapi import HTTPException
from pydantic import ValidationError

from app import main
from app.core import config
from app.services import web_search


class WebSearchServiceTests(unittest.TestCase):
    @patch("app.services.web_search._CheckedDuckduckgo")
    def test_search_uses_configured_duckduckgo_and_normalizes_results(self, engine_class):
        engine = MagicMock()
        engine.search.return_value = [
            {
                "title": "Example",
                "href": "https://example.com/article",
                "body": " A useful snippet ",
                "date": "2026-01-02",
                "provider_only": "discard me",
            },
            {"title": "Unsafe", "href": "javascript:alert(1)", "body": "bad"},
            None,
        ]
        engine_class.return_value = engine

        results = web_search.search_web("example query", 3)

        engine_class.assert_called_once_with(timeout=config.WEB_SEARCH_TIMEOUT_SECONDS)
        engine.search.assert_called_once_with(
            query="example query",
            region=config.WEB_SEARCH_REGION,
            safesearch=config.WEB_SEARCH_SAFESEARCH,
            timelimit=None,
            page=1,
        )
        self.assertEqual(
            results,
            [
                web_search.WebSearchResult(
                    "Example",
                    "https://example.com/article",
                    "A useful snippet",
                    "2026-01-02",
                )
            ],
        )

    @patch("app.services.web_search._CheckedDuckduckgo")
    def test_search_caps_results_and_preserves_empty_results(self, engine_class):
        engine = MagicMock()
        engine.search.return_value = [
            {"title": f"Title {index}", "href": f"https://example.com/{index}", "body": "Snippet"}
            for index in range(config.WEB_SEARCH_MAX_RESULTS + 4)
        ]
        engine_class.return_value = engine

        results = web_search.search_web("query", config.WEB_SEARCH_MAX_RESULTS + 5)
        self.assertEqual(len(results), config.WEB_SEARCH_MAX_RESULTS)
        self.assertEqual(engine.search.call_args.kwargs["page"], 1)

    @patch("app.services.web_search._CheckedDuckduckgo")
    def test_successful_empty_parse_returns_empty_results(self, engine_class):
        engine = MagicMock()
        engine.search.return_value = []
        engine_class.return_value = engine

        self.assertEqual(web_search.search_web("query", 1), [])

    @patch("app.services.web_search._CheckedDuckduckgo")
    def test_timeout_is_mapped_to_sanitized_timeout_error(self, engine_class):
        engine = MagicMock()
        engine.search.side_effect = TimeoutException("private provider detail")
        engine_class.return_value = engine

        with self.assertRaises(web_search.WebSearchTimeoutError) as caught:
            web_search.search_web("query", 1)
        self.assertNotIn("private provider detail", str(caught.exception))
        engine.search.assert_called_once()

    @patch("app.services.web_search._CheckedDuckduckgo")
    def test_provider_failure_is_mapped_to_sanitized_error(self, engine_class):
        engine = MagicMock()
        engine.search.side_effect = DDGSException("private provider detail")
        engine_class.return_value = engine

        with self.assertRaises(web_search.WebSearchProviderError) as caught:
            web_search.search_web("query", 1)
        self.assertNotIn("private provider detail", str(caught.exception))

    @patch("app.services.web_search._CheckedDuckduckgo")
    def test_no_results_from_successful_parse_becomes_empty_list(self, engine_class):
        engine = MagicMock()
        engine.search.return_value = []
        engine_class.return_value = engine

        self.assertEqual(web_search.search_web("query", 1), [])

    def test_non_200_http_response_is_not_mistaken_for_empty_results(self):
        engine = web_search._CheckedDuckduckgo.__new__(web_search._CheckedDuckduckgo)
        engine.http_client = MagicMock()
        engine.http_client.request.return_value.status_code = 202

        with self.assertRaises(web_search._DuckDuckGoHTTPError) as caught:
            engine.request("POST", "https://html.duckduckgo.com/html/")
        self.assertEqual(caught.exception.status_code, 202)

    @patch("app.services.web_search._CheckedDuckduckgo")
    def test_http_202_becomes_provider_error_instead_of_empty_results(self, engine_class):
        engine = MagicMock()
        engine.search.side_effect = web_search._DuckDuckGoHTTPError(202)
        engine_class.return_value = engine

        with self.assertRaises(web_search.WebSearchProviderError):
            web_search.search_web("query", 1)

    def test_private_local_and_non_http_urls_are_rejected(self):
        unsafe_urls = (
            "http://127.0.0.1/",
            "http://10.0.0.2/",
            "http://[::1]/",
            "http://localhost/",
            "http://gateway.internal/",
            "http://router.home/",
            "http://host.test/",
            r"http:\\127.0.0.1\admin",
            "http://printer/",
            "http://router.local/",
            "javascript:alert(1)",
        )
        for url in unsafe_urls:
            with self.subTest(url=url):
                self.assertIsNone(web_search._valid_http_url(url))

    def test_public_url_is_retained(self):
        self.assertEqual(
            web_search._valid_http_url("https://example.com/article"),
            "https://example.com/article",
        )


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

    def test_enabled_endpoint_returns_typed_result_contract(self):
        expected = [web_search.WebSearchResult("Title", "https://example.com", "Snippet", None)]
        with (
            patch.object(main, "WEB_SEARCH_ENABLED", True),
            patch.object(main, "search_web", return_value=expected) as search,
        ):
            response = asyncio.run(main.web_search_endpoint(main.WebSearchRequest(query=" hello ")))

        search.assert_called_once_with("hello", config.WEB_SEARCH_MAX_RESULTS)
        self.assertEqual(
            response.model_dump(),
            {
                "success": True,
                "query": "hello",
                "results": [
                    {
                        "title": "Title",
                        "url": "https://example.com",
                        "snippet": "Snippet",
                        "published": None,
                    }
                ],
                "result_count": 1,
            },
        )

    def test_endpoint_maps_provider_error_and_timeout(self):
        payload = main.WebSearchRequest(query="hello")
        cases = (
            (web_search.WebSearchProviderError("provider details must stay private"), 502),
            (web_search.WebSearchTimeoutError("timeout details must stay private"), 504),
        )
        for error, expected_status in cases:
            with self.subTest(status=expected_status):
                with (
                    patch.object(main, "WEB_SEARCH_ENABLED", True),
                    patch.object(main, "search_web", side_effect=error),
                ):
                    with self.assertRaises(HTTPException) as caught:
                        asyncio.run(main.web_search_endpoint(payload))
                self.assertEqual(caught.exception.status_code, expected_status)
                self.assertNotIn("private", caught.exception.detail)


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
