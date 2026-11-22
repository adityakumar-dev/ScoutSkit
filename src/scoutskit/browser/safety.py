"""Navigation policy: speak http(s) only, honour robots.txt, and stay where the run is allowed to be.

Two scopes. "site" (the default) keeps the run on the start site. "web" lets it visit any public website, plus the
start host; addresses on private networks (localhost, 10.x, 192.168.x, cloud metadata, ...) stay off limits, because
a page the agent visits must never be a way into the user's own network.

A page that cannot be visited is reported to the agent as a plain error, never worked around.
"""

from __future__ import annotations

import asyncio
import ipaddress
import time
from typing import Literal
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "ScoutsKit"
Scope = Literal["site", "web"]
PRIVATE_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".corp", ".intranet")
DNS_CACHE_S = 300


class SafetyError(Exception):
    """An action was refused by policy. The message is shown to the agent."""


def base_host(url: str) -> str:
    return (urlparse(url).hostname or "").removeprefix("www.")


def looks_public(host: str) -> bool:
    """Judged from the name alone: a literal address must be a public one, a name must not look internal."""
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        pass
    return "." in host and host != "localhost" and not host.endswith(PRIVATE_SUFFIXES)


async def resolve(host: str) -> list[str]:
    """Every address a host name points to (empty if it does not resolve)."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except OSError:
        return []
    return sorted({info[4][0] for info in infos})


class Policy:
    def __init__(self, start_url: str, *, respect_robots: bool = True, scope: Scope = "site") -> None:
        self.host = base_host(start_url)
        self.respect_robots = respect_robots
        self.scope = scope
        self._robots: dict[str, RobotFileParser | None] = {}
        self._dns: dict[str, tuple[float, bool]] = {}

    def host_ok(self, url: str) -> bool:
        """Is this address one the run may be on? (By name only: use check() before opening it.)"""
        host = base_host(url)
        if host == self.host or host.endswith("." + self.host):
            return True
        return self.scope == "web" and looks_public(host)

    def check_scheme_and_host(self, url: str) -> None:
        if urlparse(url).scheme not in ("http", "https"):
            raise SafetyError(f"refused: only http(s) pages may be opened, not {url!r}")
        if not self.host_ok(url):
            reason = "is not a public website" if self.scope == "web" else f"is outside {self.host}"
            raise SafetyError(f"refused: {url!r} {reason}")

    async def resolves_public(self, url: str) -> bool:
        """A public-looking name can still point at a private address; look where it really goes (cached)."""
        host = base_host(url)
        if host == self.host or self.scope != "web":
            return True
        cached = self._dns.get(host)
        if cached and time.monotonic() - cached[0] < DNS_CACHE_S:
            return cached[1]
        addresses = await resolve(host)
        ok = bool(addresses) and all(ipaddress.ip_address(a).is_global for a in addresses)
        self._dns[host] = (time.monotonic(), ok)
        return ok

    async def check(self, url: str) -> None:
        self.check_scheme_and_host(url)
        if not await self.resolves_public(url):
            raise SafetyError(f"refused: {urlparse(url).netloc} points to a private or unknown address")
        if self.respect_robots and not await self._robots_allow(url):
            raise SafetyError(f"refused: robots.txt of {urlparse(url).netloc} disallows {urlparse(url).path or '/'}")

    async def _robots_allow(self, url: str) -> bool:
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._robots[origin] = await _fetch_robots(origin)
        parser = self._robots[origin]
        return True if parser is None else parser.can_fetch(USER_AGENT, url)


async def _fetch_robots(origin: str) -> RobotFileParser | None:
    """None means 'no usable robots.txt', which allows everything (only a 200 is parsed)."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(f"{origin}/robots.txt")
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser
