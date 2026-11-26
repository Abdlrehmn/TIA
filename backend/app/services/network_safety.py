"""Public-destination validation and DNS-pinned outbound networking."""

import asyncio
import base64
import hmac
import ipaddress
import logging
import re
import secrets
import socket
from asyncio import AbstractServer, StreamReader, StreamWriter
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

_LOCAL_SUFFIXES = (
    ".localhost", ".local", ".home.arpa", ".internal", ".lan", ".home",
    ".test", ".invalid", ".example", ".onion",
)


def normalize_public_hostname(hostname: str) -> str | None:
    """Return a normalized public DNS name or globally routable IP literal."""
    normalized = hostname.rstrip(".").lower()
    if not normalized or normalized == "localhost" or normalized.endswith(_LOCAL_SUFFIXES):
        return None
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        labels = normalized.split(".")
        if all(label.isdigit() for label in labels) or re.fullmatch(
            r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+)){0,3}",
            normalized,
        ):
            return None
        try:
            ascii_host = normalized.encode("idna").decode("ascii")
        except UnicodeError:
            return None
        if len(ascii_host) > 253 or any(
            not label
            or len(label) > 63
            or re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) is None
            for label in ascii_host.split(".")
        ):
            return None
        return ascii_host if "." in ascii_host else None
    return normalized if address.is_global else None


def valid_http_url(value: object, *, allowed_ports: set[int] | None = None) -> str | None:
    """Validate an absolute HTTP(S) URL without credentials or local hosts."""
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url or "\\" in url or any(character.isspace() or ord(character) < 33 for character in url):
        return None
    if re.search(r"%(?![0-9a-fA-F]{2})", url):
        return None
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not hostname:
        return None
    if "%" in hostname or parsed.username is not None or parsed.password is not None:
        return None
    if port is not None and not 1 <= port <= 65535:
        return None
    if normalize_public_hostname(hostname) is None:
        return None
    if allowed_ports is not None:
        effective_port = port or (443 if parsed.scheme.lower() == "https" else 80)
        if effective_port not in allowed_ports:
            return None
    return url


async def public_browser_route(route: object, resolve_timeout_seconds: float = 3) -> None:
    """Validate every Playwright request; the proxy pins the actual socket."""
    request = route.request
    parsed = urlsplit(request.url)
    if parsed.scheme in {"about", "data", "blob"}:
        await route.continue_()
        return
    url = valid_http_url(request.url, allowed_ports={80, 443})
    if url is None or request.resource_type in {"image", "media", "font"}:
        await route.abort()
        return
    if request.is_navigation_request():
        redirects = 0
        previous = request.redirected_from
        while previous is not None:
            redirects += 1
            previous = previous.redirected_from
        if redirects > 5:
            await route.abort()
            return
    try:
        parsed = urlsplit(url)
        await resolve_public_addresses(parsed.hostname or "", parsed.port or (443 if parsed.scheme == "https" else 80), resolve_timeout_seconds)
        await route.continue_()
    except Exception as exc:
        logger.debug("Safe browser request was blocked (%s).", type(exc).__name__)
        try:
            await route.abort()
        except Exception:
            pass


def _validate_resolved_addresses(addresses: list[str]) -> list[str]:
    if not addresses:
        raise ValueError("Destination has no resolved addresses.")
    normalized: list[str] = []
    for value in dict.fromkeys(addresses):
        address = ipaddress.ip_address(value)
        if not address.is_global:
            raise ValueError("Destination resolved to a non-public IP address.")
        normalized.append(address.compressed)
    return normalized


async def resolve_public_addresses(hostname: str, port: int, timeout_seconds: float) -> list[str]:
    """Resolve once, reject any non-public answer, and return IPs for pinning."""
    normalized = normalize_public_hostname(hostname)
    if normalized is None:
        raise ValueError("Destination hostname is not public.")
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        address = None
    if address is not None:
        return _validate_resolved_addresses([address.compressed])

    loop = asyncio.get_running_loop()
    records = await asyncio.wait_for(
        loop.getaddrinfo(normalized, port, type=socket.SOCK_STREAM),
        timeout=timeout_seconds,
    )
    return _validate_resolved_addresses([record[4][0] for record in records])


class PublicOnlyHTTPProxy:
    """An authenticated loopback HTTP proxy that pins browser connections to public IPs."""

    def __init__(
        self,
        *,
        resolve_timeout_seconds: float = 3,
        connect_timeout_seconds: float = 4,
        max_tunnel_bytes: int = 8 * 1024 * 1024,
        max_connections: int = 48,
    ) -> None:
        self.resolve_timeout_seconds = resolve_timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self.max_tunnel_bytes = max_tunnel_bytes
        self._connection_slots = asyncio.Semaphore(max_connections)
        self.username = secrets.token_urlsafe(24)
        self.password = secrets.token_urlsafe(32)
        self._server: AbstractServer | None = None
        self._port: int | None = None

    @property
    def endpoint(self) -> str | None:
        return f"http://127.0.0.1:{self._port}" if self._port is not None else None

    async def start(self) -> str:
        if self._server is None:
            self._server = await asyncio.start_server(self._handle_client, "127.0.0.1", 0)
            socket_info = self._server.sockets[0].getsockname()
            self._port = int(socket_info[1])
        endpoint = self.endpoint
        if endpoint is None:
            raise RuntimeError("The safe browsing proxy did not start.")
        return endpoint

    async def close(self) -> None:
        server, self._server = self._server, None
        self._port = None
        if server is not None:
            server.close()
            await server.wait_closed()

    async def _handle_client(self, reader: StreamReader, writer: StreamWriter) -> None:
        upstream_writer: StreamWriter | None = None
        response_started = False
        try:
            async with self._connection_slots:
                header_block = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 3)
                if len(header_block) > 64 * 1024:
                    await self._respond(writer, 431, "Request Header Fields Too Large")
                    response_started = True
                    return
                lines = header_block.decode("iso-8859-1").split("\r\n")
                method, target, _version = lines[0].split(" ", 2)
                headers: dict[str, str] = {}
                raw_headers: list[tuple[str, str]] = []
                for line in lines[1:]:
                    if not line or ":" not in line:
                        continue
                    name, value = line.split(":", 1)
                    normalized_name = name.strip().lower()
                    normalized_value = value.strip()
                    headers[normalized_name] = normalized_value
                    raw_headers.append((name.strip(), normalized_value))
                if not self._authorized(headers.get("proxy-authorization", "")):
                    await self._respond(writer, 407, "Proxy Authentication Required", proxy_auth=True)
                    response_started = True
                    return

                if method.upper() == "CONNECT":
                    authority = urlsplit(f"//{target}")
                    hostname = authority.hostname or ""
                    port = authority.port or 443
                    if port != 443:
                        await self._respond(writer, 403, "Forbidden")
                        response_started = True
                        return
                    request_bytes = b""
                else:
                    url = valid_http_url(target, allowed_ports={80})
                    if url is None or urlsplit(url).scheme.lower() != "http":
                        await self._respond(writer, 403, "Forbidden")
                        response_started = True
                        return
                    target_parts = urlsplit(url)
                    hostname = target_parts.hostname or ""
                    port = target_parts.port or 80
                    host_header = headers.get("host", "").split(":", 1)[0].strip("[]").lower()
                    if host_header and host_header != hostname.lower():
                        await self._respond(writer, 403, "Forbidden")
                        response_started = True
                        return
                    path = target_parts.path or "/"
                    if target_parts.query:
                        path += f"?{target_parts.query}"
                    forwarded_headers = [
                        (name, value)
                        for name, value in raw_headers
                        if name.lower() not in {"proxy-authorization", "proxy-connection", "connection", "keep-alive"}
                    ]
                    forwarded_headers.append(("Connection", "close"))
                    request_bytes = (
                        f"{method} {path} HTTP/1.1\r\n"
                        + "".join(f"{name}: {value}\r\n" for name, value in forwarded_headers)
                        + "\r\n"
                    ).encode("iso-8859-1")

                if port not in {80, 443}:
                    await self._respond(writer, 403, "Forbidden")
                    response_started = True
                    return
                addresses = await resolve_public_addresses(hostname, port, self.resolve_timeout_seconds)

                last_error: Exception | None = None
                for address in addresses:
                    try:
                        upstream_reader, upstream_writer = await asyncio.wait_for(
                            asyncio.open_connection(address, port),
                            timeout=self.connect_timeout_seconds,
                        )
                        break
                    except (OSError, asyncio.TimeoutError) as exc:
                        last_error = exc
                else:
                    raise OSError("Could not connect to the validated public destination.") from last_error

                if method.upper() == "CONNECT":
                    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    response_started = True
                else:
                    upstream_writer.write(request_bytes)
                await writer.drain()
                await upstream_writer.drain()
                await self._relay(reader, writer, upstream_reader, upstream_writer)
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, UnicodeError, ValueError, OSError) as exc:
            logger.debug("Safe browser proxy rejected or closed a connection (%s).", type(exc).__name__)
            if not response_started:
                try:
                    await self._respond(writer, 403, "Forbidden")
                except (ConnectionError, OSError):
                    pass
        finally:
            if upstream_writer is not None:
                upstream_writer.close()
                try:
                    await upstream_writer.wait_closed()
                except (ConnectionError, OSError):
                    pass
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    def _authorized(self, value: str) -> bool:
        scheme, separator, token = value.partition(" ")
        if not separator or scheme.lower() != "basic":
            return False
        try:
            supplied = base64.b64decode(token, validate=True)
        except (ValueError, base64.binascii.Error):
            return False
        expected = f"{self.username}:{self.password}".encode("ascii")
        return hmac.compare_digest(supplied, expected)

    @staticmethod
    async def _respond(writer: StreamWriter, status: int, reason: str, *, proxy_auth: bool = False) -> None:
        headers = "Proxy-Authenticate: Basic realm=\"TIA safe web fetch\"\r\n" if proxy_auth else ""
        body = f"{status} {reason}\n".encode("ascii")
        writer.write(
            f"HTTP/1.1 {status} {reason}\r\n{headers}Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode("ascii")
            + body
        )
        await writer.drain()

    async def _relay(
        self,
        client_reader: StreamReader,
        client_writer: StreamWriter,
        upstream_reader: StreamReader,
        upstream_writer: StreamWriter,
    ) -> None:
        transferred = 0

        async def pipe(source: StreamReader, destination: StreamWriter) -> None:
            nonlocal transferred
            while True:
                chunk = await source.read(64 * 1024)
                if not chunk:
                    return
                transferred += len(chunk)
                if transferred > self.max_tunnel_bytes:
                    raise ValueError("Browser tunnel response exceeded its transfer limit.")
                destination.write(chunk)
                await destination.drain()

        tasks = {
            asyncio.create_task(pipe(client_reader, upstream_writer)),
            asyncio.create_task(pipe(upstream_reader, client_writer)),
        }
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()
