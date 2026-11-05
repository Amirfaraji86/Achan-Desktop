"""DNS-over-HTTPS resolver adapted from Web Immortal Guards' Python core."""
from __future__ import annotations

import base64
import ipaddress
import threading
import time
from typing import Callable

import dns.message
import dns.rdatatype
import requests


class DohResolver:
    def __init__(
        self,
        proxy_url: str,
        doh_url: str = "https://sky.rethinkdns.com/?dns=",
        bootstrap: dict[str, str] | None = None,
        logger: Callable[[str], None] | None = None,
        timeout: float = 18.0,
    ) -> None:
        self.proxy_url = proxy_url
        self.doh_url = doh_url
        self.bootstrap = {k.lower().rstrip("."): v for k, v in (bootstrap or {
            "sky.rethinkdns.com": "172.67.162.27"
        }).items()}
        self.logger = logger or (lambda _message: None)
        self.timeout = timeout
        self._cache: dict[str, tuple[float, list[str]]] = {}
        self._cache_lock = threading.Lock()
        self._local = threading.local()

    def _session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            session.trust_env = False
            session.proxies = {"https": self.proxy_url}
            self._local.session = session
        return session

    def _query_type(self, hostname: str, qtype: str) -> tuple[list[str], int]:
        query = dns.message.make_query(hostname, qtype)
        wire = query.to_wire()
        encoded = base64.urlsafe_b64encode(wire).decode("ascii").rstrip("=")
        url = self.doh_url + encoded
        response = self._session().get(
            url,
            params={"type": qtype, "ct": "application/dns-message"},
            headers={"accept": "application/dns-message"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/dns-message":
            raise ValueError(f"Unexpected DoH content type: {content_type or '(missing)'}")

        answer = dns.message.from_wire(response.content)
        expected = dns.rdatatype.from_text(qtype)
        addresses: list[str] = []
        ttl = 300
        for rrset in answer.answer:
            if rrset.rdtype == expected:
                ttl = min(ttl, max(30, int(rrset.ttl)))
                for record in rrset:
                    candidate = str(record).strip()
                    try:
                        ip = ipaddress.ip_address(candidate)
                    except ValueError:
                        continue
                    if (qtype == "A" and ip.version == 4) or (qtype == "AAAA" and ip.version == 6):
                        addresses.append(str(ip))
        return list(dict.fromkeys(addresses)), ttl

    def resolve(self, hostname: str) -> list[str]:
        host = hostname.strip().strip("[]").rstrip(".").lower()
        if not host:
            raise ValueError("Empty destination hostname.")
        try:
            return [str(ipaddress.ip_address(host))]
        except ValueError:
            pass

        if host in self.bootstrap:
            return [self.bootstrap[host]]

        now = time.monotonic()
        with self._cache_lock:
            cached = self._cache.get(host)
            if cached and cached[0] > now:
                self.logger(f"DNS cache: {host} -> {', '.join(cached[1])}")
                return list(cached[1])

        errors: list[str] = []
        for qtype in ("A", "AAAA"):
            try:
                addresses, ttl = self._query_type(host, qtype)
                if addresses:
                    with self._cache_lock:
                        self._cache[host] = (time.monotonic() + ttl, addresses)
                    self.logger(f"DoH {qtype}: {host} -> {', '.join(addresses)}")
                    return addresses
            except Exception as exc:  # continue with AAAA after an A lookup failure
                errors.append(f"{qtype}: {exc}")

        detail = "; ".join(errors) if errors else "No A/AAAA record was returned."
        raise OSError(f"DoH could not resolve {host}: {detail}")
