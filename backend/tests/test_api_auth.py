"""Local API auth and CORS enforcement tests without an HTTP client dependency."""

import asyncio
import unittest
from unittest.mock import patch

from starlette.requests import Request
from starlette.responses import Response

from app import main
from app.core.config import API_ALLOWED_HOSTS, CORS_ALLOWED_ORIGINS

TOKEN = "A" * 43


def asgi_request(path, *, method="GET", token=None, origin=None, host="127.0.0.1:8000", client="127.0.0.1", body=b"", extra_headers=None):
    headers = [(b"host", host.encode("ascii"))]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode("ascii")))
    if origin is not None:
        headers.append((b"origin", origin.encode("ascii")))
    headers.extend(extra_headers or [])
    return Request({
        "type": "http", "http_version": "1.1", "method": method, "scheme": "http",
        "path": path, "raw_path": path.encode("ascii"), "query_string": b"", "root_path": "",
        "headers": headers, "client": (client, 43100), "server": ("127.0.0.1", 8000),
    })


def invoke_middleware(request):
    async def call_next(_request):
        return Response("accepted", status_code=200)
    return asyncio.run(main.require_local_api_auth(request, call_next))


def invoke_app(path, *, method="GET", token=None, origin=None, headers=None, body=b""):
    request_headers = [(b"host", b"127.0.0.1:8000")]
    if token is not None:
        request_headers.append((b"authorization", f"Bearer {token}".encode("ascii")))
    if origin is not None:
        request_headers.append((b"origin", origin.encode("ascii")))
    request_headers.extend(headers or [])
    messages = []
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http", "http_version": "1.1", "method": method, "scheme": "http",
        "path": path, "raw_path": path.encode("ascii"), "query_string": b"", "root_path": "",
        "headers": request_headers, "client": ("127.0.0.1", 43100), "server": ("127.0.0.1", 8000),
        "asgi": {"version": "3.0", "spec_version": "2.3"},
    }
    asyncio.run(main.app(scope, receive, send))
    start = next(message for message in messages if message["type"] == "http.response.start")
    response_headers = {key.lower(): value for key, value in start.get("headers", [])}
    response_body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], response_headers, response_body


class ApiAuthTests(unittest.TestCase):
    def test_missing_and_invalid_credentials_are_rejected(self):
        with patch.dict("os.environ", {"TIA_API_TOKEN": TOKEN}, clear=False):
            self.assertEqual(invoke_middleware(asgi_request("/api/v1/conversations")).status_code, 401)
            self.assertEqual(invoke_middleware(asgi_request("/api/v1/conversations", token="B" * 43)).status_code, 401)

    def test_valid_credential_is_accepted(self):
        with patch.dict("os.environ", {"TIA_API_TOKEN": TOKEN}, clear=False):
            self.assertEqual(invoke_middleware(asgi_request("/api/v1/conversations", token=TOKEN)).status_code, 200)

    def test_every_application_api_group_is_protected(self):
        paths = (
            "/api/v1/conversations", "/api/v1/chat/test", "/api/v1/chat/stream",
            "/api/v1/search", "/api/v1/memories", "/openapi.json",
        )
        with patch.dict("os.environ", {"TIA_API_TOKEN": TOKEN}, clear=False):
            for path in paths:
                with self.subTest(path=path):
                    response = invoke_middleware(asgi_request(path))
                    self.assertEqual(response.status_code, 401)

    def test_actual_asgi_routes_reject_missing_credentials_and_accept_a_valid_token(self):
        with patch.dict("os.environ", {"TIA_API_TOKEN": TOKEN}, clear=False):
            for path in ("/api/v1/conversations", "/api/v1/chat/test", "/api/v1/chat/stream", "/api/v1/search"):
                with self.subTest(path=path):
                    status, _, _ = invoke_app(path)
                    self.assertEqual(status, 401)
            status, _, body = invoke_app(
                "/api/v1/search", method="POST", token=TOKEN,
                headers=[(b"content-type", b"application/json")], body=b'{"query":"test"}',
            )
            self.assertEqual(status, 503, body)

    def test_cors_preflight_allows_only_exact_app_origins(self):
        preflight_headers = [
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"authorization,content-type"),
        ]
        allowed_status, allowed_headers, _ = invoke_app(
            "/api/v1/search", method="OPTIONS", origin="http://tauri.localhost", headers=preflight_headers,
        )
        self.assertEqual(allowed_status, 200)
        self.assertEqual(allowed_headers[b"access-control-allow-origin"], b"http://tauri.localhost")
        rejected_status, rejected_headers, _ = invoke_app(
            "/api/v1/search", method="OPTIONS", origin="http://evil.example", headers=preflight_headers,
        )
        self.assertEqual(rejected_status, 403)
        self.assertNotIn(b"access-control-allow-origin", rejected_headers)

    def test_health_is_exempt_but_only_reports_its_existing_minimal_contract(self):
        with patch.dict("os.environ", {}, clear=False):
            response = invoke_middleware(asgi_request("/health"))
            self.assertEqual(response.status_code, 200)

    def test_unconfigured_backend_fails_closed(self):
        with patch.dict("os.environ", {}, clear=True):
            response = invoke_middleware(asgi_request("/api/v1/conversations"))
        self.assertEqual(response.status_code, 503)

    def test_arbitrary_origins_and_remote_peers_are_rejected(self):
        with patch.dict("os.environ", {"TIA_API_TOKEN": TOKEN}, clear=False):
            self.assertEqual(
                invoke_middleware(asgi_request("/health", origin="http://evil.example")).status_code,
                403,
            )
            self.assertEqual(
                invoke_middleware(asgi_request("/health", client="192.0.2.9")).status_code,
                403,
            )
            self.assertEqual(
                invoke_middleware(asgi_request("/api/v1/search", token=TOKEN, host="api.example:8000")).status_code,
                403,
            )

    def test_cors_is_exact_and_allows_authorization_header(self):
        self.assertEqual(CORS_ALLOWED_ORIGINS, ("http://localhost:1420", "http://tauri.localhost"))
        self.assertNotIn("*", CORS_ALLOWED_ORIGINS)
        self.assertEqual(API_ALLOWED_HOSTS, ("127.0.0.1:8000", "localhost:8000"))
        cors = next(middleware for middleware in main.app.user_middleware if middleware.cls.__name__ == "CORSMiddleware")
        self.assertIn("authorization", {header.lower() for header in cors.kwargs["allow_headers"]})
        self.assertFalse(cors.kwargs["allow_credentials"])


if __name__ == "__main__":
    unittest.main()
