"""Loopback-only HTTP CONNECT proxy with DoH resolution and first-flight fragmentation."""
from __future__ import annotations

import ipaddress
import random
import select
import socket
import socketserver
import threading
import time
from typing import Callable
from urllib.parse import urlsplit

from .doh import DohResolver
from .windows_network import bind_socket_to_physical_interface


HEADER_LIMIT = 64 * 1024
BUFFER_SIZE = 64 * 1024


def parse_authority(authority: str) -> tuple[str, int]:
    value = authority.strip()
    if value.startswith("["):
        end = value.find("]")
        if end < 0 or end + 1 >= len(value) or value[end + 1] != ":":
            raise ValueError("Invalid bracketed IPv6 CONNECT target.")
        host, port_text = value[1:end], value[end + 2:]
    else:
        host, sep, port_text = value.rpartition(":")
        if not sep or not host:
            raise ValueError("CONNECT target must contain host:port.")
    port = int(port_text)
    if not (1 <= port <= 65535):
        raise ValueError("Destination port is outside the valid range.")
    return host, port


def fragment_payload(data: bytes, fragment_count: int = 300) -> list[bytes]:
    """Split a first-flight payload safely, including very small buffers."""
    if not data:
        return []
    parts = min(max(1, int(fragment_count)), len(data))
    if parts == 1:
        return [data]
    cut_points = sorted(random.sample(range(1, len(data)), parts - 1))
    result: list[bytes] = []
    start = 0
    for end in cut_points:
        result.append(data[start:end])
        start = end
    result.append(data[start:])
    return [part for part in result if part]


def send_fragmented(sock: socket.socket, data: bytes, count: int = 300, delay: float = 0.001) -> None:
    parts = fragment_payload(data, count)
    for index, part in enumerate(parts):
        sock.sendall(part)
        if delay > 0 and index != len(parts) - 1:
            time.sleep(delay)


class _ThreadingProxyServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    block_on_close = False

    def __init__(self, address, handler, resolver, interface_indices, logger, fragment_count, fragment_delay):
        self.resolver = resolver
        self.interface_indices = interface_indices
        self.logger = logger
        self.fragment_count = fragment_count
        self.fragment_delay = fragment_delay
        super().__init__(address, handler)


class _ProxyHandler(socketserver.BaseRequestHandler):
    def _reply(self, status: bytes, extra: bytes = b"") -> None:
        self.request.sendall(status + extra + b"\r\n")

    def _read_headers(self) -> tuple[bytes, bytes]:
        data = bytearray()
        while b"\r\n\r\n" not in data:
            chunk = self.request.recv(8192)
            if not chunk:
                raise ConnectionError("Client closed before sending proxy headers.")
            data.extend(chunk)
            if len(data) > HEADER_LIMIT:
                raise ValueError("Proxy request header is too large.")
        header, extra = bytes(data).split(b"\r\n\r\n", 1)
        return header, extra

    def _connect_upstream(self, host: str, port: int) -> tuple[socket.socket, str]:
        addresses = self.server.resolver.resolve(host)
        last_error: Exception | None = None
        for address in addresses:
            ip = ipaddress.ip_address(address)
            family = socket.AF_INET if ip.version == 4 else socket.AF_INET6
            upstream = socket.socket(family, socket.SOCK_STREAM)
            try:
                upstream.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                upstream.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                bind_socket_to_physical_interface(upstream, address, self.server.interface_indices)
                upstream.settimeout(20)
                endpoint = (address, port) if family == socket.AF_INET else (address, port, 0, 0)
                upstream.connect(endpoint)
                upstream.settimeout(None)
                return upstream, address
            except Exception as exc:
                last_error = exc
                upstream.close()
        raise OSError(f"Could not connect to {host}:{port} using DoH result(s): {last_error}")

    def _relay(self, upstream: socket.socket, initial_payload: bytes = b"") -> None:
        client = self.request
        client.settimeout(None)
        upstream.settimeout(None)
        first_client_payload = True
        if initial_payload:
            send_fragmented(
                upstream,
                initial_payload,
                self.server.fragment_count,
                self.server.fragment_delay,
            )
            first_client_payload = False

        while True:
            readable, _, exceptional = select.select([client, upstream], [], [client, upstream], 120)
            if exceptional:
                return
            if not readable:
                # Keep idle-but-open sessions alive; the application may still be active.
                continue
            for source in readable:
                payload = source.recv(BUFFER_SIZE)
                if not payload:
                    return
                if source is client:
                    if first_client_payload:
                        send_fragmented(
                            upstream,
                            payload,
                            self.server.fragment_count,
                            self.server.fragment_delay,
                        )
                        first_client_payload = False
                    else:
                        upstream.sendall(payload)
                else:
                    client.sendall(payload)

    def handle(self) -> None:
        upstream: socket.socket | None = None
        try:
            self.request.settimeout(25)
            header, initial_payload = self._read_headers()
            first_line = header.split(b"\r\n", 1)[0].decode("latin-1", "replace")
            parts = first_line.split()
            if len(parts) < 2:
                self._reply(b"HTTP/1.1 400 Bad Request\r\nProxy-Agent: Achan/1.0")
                return

            method, target = parts[0].upper(), parts[1]
            if method == "CONNECT":
                host, port = parse_authority(target)
                upstream, resolved_ip = self._connect_upstream(host, port)
                self._reply(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: Achan/1.0\r\n")
                self.server.logger(f"CONNECT {host}:{port} [{resolved_ip}]")
                self._relay(upstream, initial_payload)
            elif method in {"GET", "POST", "HEAD"}:
                if target.startswith("http://"):
                    new_location = "https://" + target[len("http://"):]
                else:
                    new_location = target
                response = (
                    "HTTP/1.1 302 Found\r\n"
                    f"Location: {new_location}\r\n"
                    "Proxy-Agent: Achan/1.0\r\n"
                    "Content-Length: 0\r\nConnection: close\r\n\r\n"
                )
                self.request.sendall(response.encode("latin-1", "replace"))
            else:
                self._reply(b"HTTP/1.1 405 Method Not Allowed\r\nProxy-Agent: Achan/1.0")
        except (OSError, ValueError, ConnectionError) as exc:
            try:
                self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\nProxy-Agent: Achan/1.0\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            self.server.logger(f"Proxy error: {exc}")
        finally:
            if upstream is not None:
                try:
                    upstream.close()
                except OSError:
                    pass


class LocalProxy:
    def __init__(
        self,
        interface_indices: dict[str, int | None],
        logger: Callable[[str], None],
        port: int = 4525,
        doh_url: str = "https://sky.rethinkdns.com/?dns=",
        bootstrap: dict[str, str] | None = None,
        fragment_count: int = 300,
        fragment_delay: float = 0.001,
    ) -> None:
        self.port = port
        self.logger = logger
        self.resolver = DohResolver(
            proxy_url=f"http://127.0.0.1:{port}",
            doh_url=doh_url,
            bootstrap=bootstrap,
            logger=logger,
        )
        self.server = _ThreadingProxyServer(
            ("127.0.0.1", port),
            _ProxyHandler,
            self.resolver,
            interface_indices,
            logger,
            fragment_count,
            fragment_delay,
        )
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.thread = threading.Thread(target=self.server.serve_forever, name="WIG-HTTP-Proxy", daemon=True)
        self.thread.start()
        # The TCPServer socket is already bound/listening; give serve_forever a moment to start.
        time.sleep(0.05)
        self.logger(f"Local HTTP proxy listening on 127.0.0.1:{self.port}")

    def stop(self) -> None:
        try:
            self.server.shutdown()
        except Exception:
            pass
        try:
            self.server.server_close()
        except Exception:
            pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
