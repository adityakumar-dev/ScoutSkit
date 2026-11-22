"""One Playwright browser session with the operations the agent's tools need.

Elements are addressed by the refs in the page's AI snapshot (`[ref=e3]`). Every
failure that the agent can react to is raised as ActionError with a short,
plain-language message.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import BrowserContext, Page, Response, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeout

from .files import FileRefused, FileStore, SavedFile
from .safety import Policy, SafetyError, Scope
from . import census as census_module
from .census import Census, DetailBlocks
from . import feeds as feeds_module
from .element import ELEMENT_INFO_JS
from .element import describe as describe_element
from .javascript import violation
from .totals import stated_total
from .tree import find as find_in_tree
from .tree import fold

REF = re.compile(r"^[A-Za-z0-9_-]+$")
TREE_LINE = re.compile(r"^\s*- (.*?)\s*\[ref=([A-Za-z0-9_-]+)\]")
DENIED_STATUS = {403: "403 Forbidden", 418: "418 (it treats the browser as a bot)", 429: "429 Too Many Requests"}
BLOCK_PAGE = re.compile(r"captcha|/sorry/|unusual[-_]traffic|are[-_]you[-_]a[-_]robot|access[-_]denied|/blocked(?:[/?.]|$)|home-error/\d{3}", re.I)
CHALLENGE = re.compile(r"captcha|/sorry/|unusual[-_]traffic|are[-_]you[-_]a[-_]robot|hcaptcha|turnstile|/challenge", re.I)  # a check only a person can pass
MASK = "••••"
MIN_SECRET_CHARS = 4  # a shorter value would hide ordinary text everywhere
PASSWORD_VALUES_JS = "[...document.querySelectorAll('input[type=password], input[autocomplete$=password]')].map(e => e.value).filter(Boolean)"
MAX_BODY_CHARS = 2_000_000  # per response kept for grounding
MAX_NETWORK_TEXT_CHARS = 6_000_000  # all responses together
TREE_BUDGET_CHARS = 12_000  # what the agent reads each turn (about 3k tokens); longer trees get their repeated runs folded
MAX_TREE_CHARS = 30_000  # hard cap, even when the complete tree is asked for
NAV_TIMEOUT_MS = 45_000
MAX_REDIRECTS = 5
DOWNLOAD_NOTICE_S = 0.5
DOWNLOAD_WAIT_S = 60
ACTION_TIMEOUT_MS = 12_000  # slow sites need more than Playwright's usual few seconds
RENDER_WAIT_S = 15  # a half-loaded page gets this long to show content before we describe it
MIN_TREE_CHARS = 120
DOM_WAIT_MS = 20_000  # how long to wait for the document to be parsed; a slow site is not a failure
SETTLE_MS = 500
SCROLL_STEP = 700  # pixels per scroll
# Scroll position of the nearest ancestor (or the element itself) that scrolls on its own; the page's position otherwise.
SCROLL_POSITION_JS = """e => {
  for (let n = e; n && n !== document.body; n = n.parentElement) {
    const overflow = getComputedStyle(n).overflowY;
    if ((overflow === 'auto' || overflow === 'scroll') && n.scrollHeight > n.clientHeight) return n.scrollTop;
  }
  return window.scrollY;
}"""
PERSONAL_FIELD = re.compile(r"pass|pwd|user|login|e-?mail|otp|card|cvv|ssn|aadhaar|phone|mobile|tel\b", re.IGNORECASE)


class ActionError(Exception):
    """An action failed in a way the agent can read and react to."""


@dataclass
class NetEntry:
    index: int
    method: str
    url: str
    status: int  # 0 = the request failed
    resource_type: str
    content_type: str
    size: int | None
    failure: str = ""
    response: Response | None = None

    def line(self) -> str:
        size = f" {self.size}B" if self.size is not None else ""
        failure = f" FAILED: {self.failure}" if self.failure else ""
        return f"#{self.index} {self.method} {self.status} {self.resource_type} {self.content_type.split(';')[0]}{size} {self.url}{failure}"


def denial_of(url: str, status: int) -> str | None:
    """Why a page load counts as a refusal, or None. Heuristic evidence (a status, or the address of a typical block page), not proof."""
    host = urlparse(url).hostname or "the site"
    if status in DENIED_STATUS:
        return f"{host} answered HTTP {DENIED_STATUS[status]}"
    if BLOCK_PAGE.search(urlparse(url).path + "?" + urlparse(url).query):
        return f"{host} showed a block page ({urlparse(url).path or '/'})"
    return None


CHALLENGE_TITLE = re.compile(r"just a moment|attention required|verify you are human|are you a robot|checking your browser|security check|captcha|unusual traffic", re.I)


def challenge_of(url: str, status: int) -> tuple[str, str] | None:
    """(host, url) when the page is a check meant for a person (a CAPTCHA), else None. A plain 403/418/429 is a block, not a challenge."""
    parts = urlparse(url)
    if CHALLENGE.search(parts.path + "?" + parts.query):
        return parts.hostname or "the site", url
    return None


def title_is_challenge(title: str) -> bool:
    """A page that announces itself as a human check ("Just a moment...", "Verify you are human"): how Cloudflare-style checks look."""
    return bool(CHALLENGE_TITLE.search(title or ""))


def _explain(error: Exception, action: str) -> ActionError:
    first = str(error).strip().splitlines()[0] if str(error).strip() else type(error).__name__
    lowered = str(error).lower()
    if "not attached" in lowered or "detached" in lowered:
        return ActionError(f"{action} failed: that element is gone; the page changed, use the current tree")
    if isinstance(error, PlaywrightTimeout) or "timeout" in lowered:
        if "intercepts pointer events" in lowered:
            return ActionError(f"{action} failed: another element is covering it (a popup or overlay?)")
        waiting = next((line.strip() for line in str(error).splitlines() if "waiting for" in line or "not stable" in line), "")
        return ActionError(
            f"{action} failed: the element is not visible or not clickable (inside a closed menu, off-screen, disabled, or the page is still loading?)"
            + (f" [{waiting[:110]}]" if waiting else "")
        )
    return ActionError(f"{action} failed: {first[:160]}")


class BrowserSession:
    def __init__(self, page: Page, policy: Policy, context: BrowserContext, files: FileStore | None = None) -> None:
        self.page = page  # the active tab
        self.files = files  # where saved files and downloads go; None: this session saves nothing
        self.downloading = 0  # downloads started and not yet saved
        self.policy = policy
        self.context = context
        self.console: deque[tuple[str, str]] = deque(maxlen=500)
        self.network: deque[NetEntry] = deque(maxlen=500)
        self._feeds: dict[int, feeds_module.DataFeed | None] = {}
        self._bodies: dict[int, str] = {}
        self._secrets: set[str] = set()
        self.denied: list[str] = []  # pages that refused us (HTTP 403/418/429 or a block page) since the agent last looked
        self.challenges: list[tuple[str, str, Page | None]] = []  # CAPTCHA pages seen since the agent last looked: (host, url, the tab)
        self.blocked: list[str] = []  # navigations the policy stopped since the agent last looked
        self._net_index = 0
        self.last_tree = ""  # the complete, unfolded tree of the last snapshot
        self._raw_tables: dict[str, list[census_module.Table]] = {}  # raw-source tables per URL; the source does not change
        self._details: dict[str, list[DetailBlocks]] = {}
        self._wire(page)

    # ---- event capture -------------------------------------------------
    def _wire(self, page: Page) -> None:
        page.on("console", lambda m: self.console.append((m.type, m.text)))
        page.on("pageerror", lambda e: self.console.append(("pageerror", str(e))))
        page.on("dialog", lambda d: asyncio.ensure_future(self._dismiss(d)))
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_failed)
        page.on("download", lambda d: asyncio.ensure_future(self._on_download(d)))

    async def _on_download(self, download) -> None:
        """A click started a download: keep it (within the limits) and tell the agent, as a browser would show it."""
        if self.files is None:
            await download.cancel()
            return
        self.downloading += 1
        try:
            saved = await self.files.save_download(download)
            self.console.append(("download", f"saved {saved.name} ({saved.size} bytes)"))
        except (FileRefused, PlaywrightError) as error:
            self.console.append(("download", f"not saved: {error}"))
        finally:
            self.downloading -= 1

    async def downloads_after(self, action) -> list[SavedFile]:
        """Run an action and return the files it downloaded (a click on a file link), waiting for them to finish saving."""
        before = len(self.files.saved) if self.files else 0
        await action
        await asyncio.sleep(DOWNLOAD_NOTICE_S)  # the download event comes just after the click
        deadline = time.monotonic() + DOWNLOAD_WAIT_S
        while self.downloading and time.monotonic() < deadline:
            await asyncio.sleep(0.2)
        return self.files.saved[before:] if self.files else []

    async def _dismiss(self, dialog) -> None:
        self.console.append(("dialog", f"{dialog.type}: {dialog.message}"))
        await dialog.dismiss()

    def _entry(self, **fields) -> NetEntry:
        self._net_index += 1
        entry = NetEntry(index=self._net_index, **fields)
        self.network.append(entry)
        return entry

    def _on_response(self, response: Response) -> None:
        # Only the page itself counts. Pages are full of hidden frames (an invisible reCAPTCHA, ads, trackers) that answer with block-like
        # addresses and statuses while the person sees an ordinary page; they must not stop the run or ask anyone for help.
        if response.request.resource_type == "document" and response.frame.parent_frame is None:
            if denial := denial_of(response.url, response.status):
                self.denied.append(denial)
            if challenge := challenge_of(response.url, response.status):
                self.challenges.append((*challenge, response.frame.page))
        headers = response.headers
        length = headers.get("content-length")
        self._entry(
            method=response.request.method, url=response.url, status=response.status,
            resource_type=response.request.resource_type, content_type=headers.get("content-type", ""),
            size=int(length) if length and length.isdigit() else None, response=response,
        )

    def _on_failed(self, request) -> None:
        self._entry(
            method=request.method, url=request.url, status=0, resource_type=request.resource_type,
            content_type="", size=None, failure=request.failure or "failed",
        )

    # ---- reading -------------------------------------------------------
    async def url(self) -> str:
        return self.page.url

    async def title(self) -> str:
        return await self.page.title()

    async def snapshot(self, *, full: bool = False) -> tuple[str, dict[str, str]]:
        """The page as an indented tree with [ref=eN] ids, plus ref -> label for logging.

        The tree is folded to the budget unless `full`; the complete tree is kept in `last_tree`."""
        deadline = time.monotonic() + RENDER_WAIT_S
        while True:
            try:
                tree = await self.page.aria_snapshot(mode="ai", timeout=20_000)
            except PlaywrightError as error:
                raise _explain(error, "reading the page") from error
            if len(tree) >= MIN_TREE_CHARS or time.monotonic() > deadline or await self._loaded():
                break  # content is there, the time is up, or the page is fully loaded and simply small
            await self.page.wait_for_timeout(1_500)
        tree = await self.scrub(tree)
        labels = {m.group(2): m.group(1)[:80] for line in tree.splitlines() if (m := TREE_LINE.match(line))}
        self.last_tree = tree
        return self._fit(tree, full), labels

    async def scrub(self, text: str) -> str:
        """Hide the values of password fields: the model and the logs must never see a password, whoever typed it.

        Every value seen in a password field stays hidden for the rest of the session, even after the page changes."""
        try:
            seen = await self.page.evaluate(PASSWORD_VALUES_JS)
        except PlaywrightError:
            seen = []  # mid-navigation: the values already known still apply
        self._secrets.update(value for value in seen if len(value) >= MIN_SECRET_CHARS)
        for secret in sorted(self._secrets, key=len, reverse=True):
            text = text.replace(secret, MASK)
        return text

    @staticmethod
    def _fit(tree: str, full: bool) -> str:
        """The tree as shown to the agent: folded to the budget, or complete up to the hard cap."""
        shown = tree if full else fold(tree, TREE_BUDGET_CHARS)
        if len(shown) > MAX_TREE_CHARS:
            shown = shown[:MAX_TREE_CHARS] + f"\n[tree truncated: {len(shown) - MAX_TREE_CHARS} more characters; use read_page(ref) for one part]"
        return shown

    async def read_page(self, ref: str | None = None, full: bool = False) -> str:
        """The page tree again, or only the part under element `ref`. Folded to the budget unless `full`."""
        if not ref:
            return (await self.snapshot(full=full))[0]
        target = await self._resolve(ref)
        try:
            tree = await target.aria_snapshot(mode="ai", timeout=20_000)
        except PlaywrightError as error:
            raise _explain(error, "reading the element") from error
        return f"[the part of the page under ref {ref}]\n" + self._fit(tree, full)

    async def text(self, max_chars: int = 20_000) -> str:
        for selector in ("main", "article", "[role=main]", "body"):
            locator = self.page.locator(selector).first
            if await locator.count():
                content = " ".join((await locator.inner_text()).split())
                if content:
                    return content[:max_chars]
        return ""

    async def screenshot(self, path: Path) -> None:
        await self.page.screenshot(path=str(path))

    async def source_html(self, which: str = "raw") -> tuple[str, str]:
        """(html, note). raw: the document as the server sent it, so rows a script later removes from the DOM
        (like a paged data table) are still there. rendered: the live DOM."""
        if which == "rendered":
            return await self.page.content(), ""
        url = self.page.url.split("#")[0]
        for entry in reversed(self.network):
            if entry.resource_type == "document" and entry.status == 200 and entry.response is not None and entry.url.split("#")[0] == url:
                try:
                    return await entry.response.text(), ""
                except PlaywrightError:
                    break
        return await self.page.content(), "the raw source is not available for this page (no document request); showing the rendered DOM"

    async def census(self, keys=()) -> Census | None:
        """Does the raw source hold more table rows than the live page shows? (see census.py). Advice only: never raises."""
        try:
            url = self.page.url.split("#")[0]
            if url not in self._raw_tables:
                raw, _ = await self.source_html("raw")
                self._raw_tables[url] = await asyncio.to_thread(census_module.tables, raw, True)
            rendered, _ = await self.source_html("rendered")
            shown = await asyncio.to_thread(census_module.tables, rendered)
            return census_module.compare(self._raw_tables[url], shown, keys)
        except (PlaywrightError, ValueError):
            return None

    async def details(self) -> list[DetailBlocks]:
        """Repeated label/value blocks in the raw source: fields each item carries that the visible table may not show."""
        try:
            url = self.page.url.split("#")[0]
            if url not in self._details:
                raw, _ = await self.source_html("raw")
                self._details[url] = await asyncio.to_thread(census_module.detail_blocks, raw)
            return self._details[url]
        except (PlaywrightError, ValueError):
            return []

    async def network_text(self) -> str:
        """Text of the data responses (fetch/xhr, JSON or text) this page loaded: values read from them are on the page's behalf, not invented."""
        parts, used = [], 0
        for entry in list(self.network):
            if entry.resource_type not in ("fetch", "xhr") or entry.status != 200 or entry.response is None:
                continue
            if entry.index not in self._bodies:
                try:
                    body = await entry.response.text() if any(k in entry.content_type for k in ("json", "text", "xml")) else ""
                except PlaywrightError:
                    body = ""
                if "json" in entry.content_type:
                    try:
                        body += "\n" + json.dumps(json.loads(body), ensure_ascii=False)  # \u00e9 escapes read as the characters they stand for
                    except ValueError:
                        pass
                self._bodies[entry.index] = body[:MAX_BODY_CHARS]
            used += len(self._bodies[entry.index])
            if used > MAX_NETWORK_TEXT_CHARS:
                break
            parts.append(self._bodies[entry.index])
        return "\n".join(parts)

    async def data_feeds(self) -> list[feeds_module.DataFeed]:
        """JSON responses this page loaded that hold a list of records (see feeds.py). Advice only: never raises."""
        found = []
        for entry in list(self.network):
            if entry.resource_type not in ("fetch", "xhr") or entry.status != 200 or "json" not in entry.content_type or entry.response is None:
                continue
            if entry.index not in self._feeds:
                try:
                    body = await entry.response.text()
                except PlaywrightError:
                    continue
                self._feeds[entry.index] = await asyncio.to_thread(feeds_module.describe, entry.index, entry.method, entry.url, body)
            if self._feeds[entry.index]:
                found.append(self._feeds[entry.index])
        return found

    async def stated_total(self) -> int | None:
        """The item total the current page states about its list (for example 265 from "Showing 1 to 25 of 265 entries")."""
        try:
            return stated_total(await self.page.locator("body").inner_text())
        except PlaywrightError:
            return None

    async def visible_text(self) -> str:
        """Everything a reader could see on the current page: body text plus the accessibility tree (covers iframes)."""
        body = await self.page.locator("body").inner_text()
        tree, _ = await self.snapshot(full=True)  # folded rows must still count as "on the page"
        return body + "\n" + tree

    def console_log(self, errors_only: bool = False, limit: int = 30) -> list[str]:
        rows = [f"{kind}: {text}" for kind, text in self.console if not errors_only or kind in ("error", "pageerror")]
        return rows[-limit:]

    def network_log(self, pattern: str | None = None, limit: int = 30) -> list[NetEntry]:
        rows = [e for e in self.network if not pattern or re.search(pattern, e.url)]
        return rows[-limit:]

    async def network_body(self, index: int, max_chars: int = 20_000) -> str:
        entry = next((e for e in self.network if e.index == index), None)
        if entry is None or entry.response is None:
            raise ActionError(f"no recorded response #{index}")
        try:
            return (await entry.response.text())[:max_chars]
        except PlaywrightError as error:
            raise ActionError(f"response #{index} has no readable body ({str(error)[:80]})") from error

    # ---- acting --------------------------------------------------------
    async def goto(self, url: str) -> None:
        try:
            await self.policy.check(url)
        except SafetyError as error:
            raise ActionError(str(error)) from error
        try:
            response = await self.page.goto(url, wait_until="commit", timeout=NAV_TIMEOUT_MS)
        except PlaywrightTimeout as error:
            raise ActionError(f"the site did not answer within {NAV_TIMEOUT_MS // 1000}s (it is slow or unreachable from here)") from error
        except PlaywrightError as error:
            if "Download is starting" in str(error):
                return  # the address is a file: the browser downloads it instead of showing a page (see _on_download)
            raise ActionError(f"could not open {url}: {str(error).splitlines()[0][:120]}") from error
        if response is not None and response.status >= 400:
            raise ActionError(f"{url} answered HTTP {response.status}")
        await self.wait_for_document()
        await self.settle()

    async def save_file(self, url: str, name: str = "") -> SavedFile:
        """Fetch a link with the browser's cookies and keep it in the run's files. The site policy applies as for any page."""
        if self.files is None:
            raise ActionError("this run does not save files")
        url = urljoin(self.page.url, url)
        for _ in range(MAX_REDIRECTS + 1):  # redirects are followed by hand: each address must pass the policy, not just the first
            try:
                await self.policy.check(url)
            except SafetyError as error:
                raise ActionError(str(error)) from error
            try:
                response = await self.context.request.get(url, timeout=NAV_TIMEOUT_MS, max_redirects=0)
            except PlaywrightError as error:
                raise ActionError(f"could not fetch {url}: {str(error).splitlines()[0][:120]}") from error
            if response.status not in (301, 302, 303, 307, 308) or not response.headers.get("location"):
                break
            url = urljoin(url, response.headers["location"])
        else:
            raise ActionError(f"too many redirects fetching {url}")
        if response.status >= 400:
            raise ActionError(f"{url} answered HTTP {response.status}")
        if (denial := denial_of(response.url, response.status)):
            self.denied.append(denial)
        length = response.headers.get("content-length", "")
        try:
            if length.isdigit():
                self.files.check_size(int(length))
            return self.files.save_bytes(await response.body(), response.url, response.headers.get("content-type", ""), name)
        except FileRefused as error:
            raise ActionError(f"not saved: {error}") from error

    async def back(self) -> None:
        await self.page.go_back(wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        await self.settle()

    async def _loaded(self) -> bool:
        try:
            return await self.page.evaluate("document.readyState") == "complete"
        except PlaywrightError:
            return False

    async def _resolve(self, ref: str):
        """The element for a ref, or a clear error at once when the ref is stale (refs change when a page reloads)."""
        target = self._target(ref)
        if await target.count() == 0:
            raise ActionError(f"no element has the ref {ref!r} on the current page; refs change whenever a page reloads, so use the refs from the latest tree")
        return target

    def _target(self, ref: str):
        if not REF.match(ref or ""):
            raise ActionError(f"{ref!r} is not an element ref; use the [ref=...] ids from the page tree")
        return self.page.locator(f"aria-ref={ref}")

    async def click(self, ref: str) -> None:
        target = await self._resolve(ref)
        try:
            await target.click(timeout=ACTION_TIMEOUT_MS)
        except (PlaywrightError, PlaywrightTimeout) as error:
            raise _explain(error, "click") from error
        await self.settle()

    async def fill(self, ref: str, text: str) -> None:
        target = await self._resolve(ref)
        try:
            hints = " ".join(
                [(await target.get_attribute(a, timeout=ACTION_TIMEOUT_MS) or "") for a in ("type", "name", "id", "autocomplete", "aria-label", "placeholder")]
            )
            if PERSONAL_FIELD.search(hints):
                raise ActionError("refused: that looks like a login or personal-data field (password, username, email, phone, card...); ScoutsKit never fills those")
            await target.fill(text, timeout=ACTION_TIMEOUT_MS)
        except (PlaywrightError, PlaywrightTimeout) as error:
            raise _explain(error, "fill") from error
        await self.settle()

    async def select(self, ref: str, option: str) -> None:
        target = await self._resolve(ref)
        try:
            try:
                await target.select_option(label=option, timeout=ACTION_TIMEOUT_MS)
            except PlaywrightError:
                await target.select_option(value=option, timeout=ACTION_TIMEOUT_MS)
        except (PlaywrightError, PlaywrightTimeout) as error:
            raise ActionError(f"select failed: {str(error).splitlines()[0][:140]} (is that a dropdown, and is {option!r} one of its options?)") from error
        await self.settle()

    async def hover(self, ref: str) -> None:
        """Move the pointer over an element, which is how many menus reveal their items."""
        target = await self._resolve(ref)
        try:
            await target.hover(timeout=ACTION_TIMEOUT_MS)
        except (PlaywrightError, PlaywrightTimeout) as error:
            raise _explain(error, "hover") from error
        await self.settle()

    async def wait_for(self, text: str | None = None, seconds: float = 0, timeout: float = 10) -> str:
        """Wait until `text` is visible on the page (at most `timeout` s), or just pause for `seconds` (at most 10)."""
        if text:
            limit = max(1.0, min(float(timeout), 30.0))
            try:
                await self.page.wait_for_function("t => document.body && document.body.innerText.includes(t)", arg=text, timeout=limit * 1000)
            except PlaywrightTimeout:
                return f"{text!r} did not appear within {limit:g}s"
            return f"{text!r} is on the page"
        pause = max(0.0, min(float(seconds), 10.0))
        await self.page.wait_for_timeout(pause * 1000)
        return f"waited {pause:g}s"

    # ---- tabs ----------------------------------------------------------
    def tabs(self) -> list[Page]:
        return [page for page in self.context.pages if not page.is_closed()]

    async def list_tabs(self) -> str:
        lines = []
        for index, page in enumerate(self.tabs()):
            lines.append(f"{index}: {await page.title() or '(untitled)'} — {page.url}" + ("   [active]" if page is self.page else ""))
        return "\n".join(lines)

    def _tab(self, index: int) -> Page:
        pages = self.tabs()
        if not 0 <= int(index) < len(pages):
            raise ActionError(f"there is no tab {index}; tabs are numbered 0 to {len(pages) - 1}")
        return pages[int(index)]

    async def switch_tab(self, index: int) -> str:
        page = self._tab(index)
        await page.bring_to_front()
        self.page = page
        await self.settle()
        return f"switched to tab {index}: {page.url}"

    async def open_tab(self, url: str) -> str:
        """A new tab on `url` (checked by the policy first); it becomes the active tab."""
        try:
            await self.policy.check(url)
        except SafetyError as error:
            raise ActionError(str(error)) from error
        await self.context.new_page()  # adopted as the active tab by the context's "page" hook
        await self.goto(url)
        return f"opened tab {len(self.tabs()) - 1}: {self.page.url}"

    async def close_tab(self, index: int) -> str:
        page = self._tab(index)
        if len(self.tabs()) == 1:
            raise ActionError("this is the only tab; it cannot be closed")
        await page.close()
        if page is self.page:
            self.page = self.tabs()[-1]
        return f"closed tab {index}; the active tab is now {self.page.url}"

    # ---- finding and evaluating ----------------------------------------
    async def element_info(self, ref: str) -> str:
        """The real HTML behind an element of the tree: its tag, id, classes, a CSS selector and what it contains."""
        target = await self._resolve(ref)
        try:
            return describe_element(await target.evaluate(ELEMENT_INFO_JS))
        except PlaywrightError as error:
            raise _explain(error, "inspect") from error

    async def find(self, query: str, limit: int = 15) -> str:
        """Search the complete tree (also the rows that are folded away) for elements matching every word."""
        if not self.last_tree:
            await self.snapshot()
        found = find_in_tree(self.last_tree, query, int(limit))
        return "\n".join(found) if found else f"nothing on the page matches {query!r}"

    async def evaluate(self, expression: str, max_chars: int = 20_000) -> str:
        """Run read-only JavaScript in the page and return its value as JSON. An expression, or statements ending in `return`."""
        reason = violation(expression)
        if reason:
            raise ActionError(f"refused: {reason}; javascript_tool only reads data from the page")
        try:
            try:
                value = await self.page.evaluate(f"() => ({expression})")
            except PlaywrightError as error:
                if "SyntaxError" not in str(error):
                    raise
                value = await self.page.evaluate(f"() => {{ {expression} }}")  # statements: they must `return` the value
        except PlaywrightError as error:
            raise ActionError(f"the script failed: {str(error).splitlines()[0][:200]}") from error
        text = json.dumps(value, ensure_ascii=False, default=str)
        return text if len(text) <= max_chars else text[:max_chars] + f"…[{len(text) - max_chars} more characters cut]"

    async def press(self, key: str) -> None:
        try:
            await self.page.keyboard.press(key)
        except PlaywrightError as error:
            raise ActionError(f"press failed: {str(error).splitlines()[0][:120]}") from error
        await self.settle()

    async def scroll(self, direction: str = "down", ref: str | None = None) -> str:
        """Scroll the page, or the container of element `ref` (a table, list or dialog that scrolls on its own).

        The mouse wheel acts on whatever is under the pointer, so the pointer is moved over the target first.
        Returns how the scroll position changed, so the agent can tell when it has reached the end."""
        up = direction == "up"
        try:
            if ref:
                target = await self._resolve(ref)
                await target.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
                box = await target.bounding_box()
                if box:
                    await self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                position = lambda: target.evaluate(SCROLL_POSITION_JS)
            else:
                viewport = self.page.viewport_size or {"width": 1280, "height": 800}
                await self.page.mouse.move(viewport["width"] / 2, viewport["height"] / 2)
                position = lambda: self.page.evaluate("window.scrollY")
            before = await position()
            await self.page.mouse.wheel(0, -SCROLL_STEP if up else SCROLL_STEP)
            await self.page.wait_for_timeout(SETTLE_MS)
            after = await position()
        except (PlaywrightError, PlaywrightTimeout) as error:
            raise _explain(error, "scroll") from error
        if after == before:
            return f"cannot scroll {direction} any further: already at the {'top' if up else 'end'}"
        return f"scrolled {direction}: position {round(before)} -> {round(after)}"

    async def wait_for_document(self) -> None:
        """Wait for the document to be parsed, but never fail on a slow site: a page whose images or third-party
        scripts hang is still usable once its content has arrived."""
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=DOM_WAIT_MS)
        except PlaywrightTimeout:
            pass

    async def settle(self) -> None:
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=3_000)
        except PlaywrightTimeout:
            pass
        await self.page.wait_for_timeout(SETTLE_MS)

    async def ensure_on_site(self) -> str | None:
        """If an action left the allowed site, go back and say so; else None. Also reports navigations the policy blocked."""
        if self.blocked:
            urls, self.blocked = self.blocked, []
            if self.page.url.startswith("chrome-error:"):  # the aborted navigation left the browser's error page: back to where we were
                await self.page.go_back()
            return f"the policy blocked a navigation to {', '.join(dict.fromkeys(urls))}: it is not a public website you may visit"
        if self.policy.host_ok(self.page.url) or self.page.url.startswith("about:"):
            return None
        away = self.page.url
        await self.page.go_back()
        return f"that led off-site to {away}; went back"

    def challenge_pending(self, already_helped: set[str]) -> bool:
        """Is there a CAPTCHA page, on a site a person has not been asked about yet, that the agent has not looked at?"""
        return any(host not in already_helped for host, *_ in self.challenges)

    async def take_challenge(self) -> tuple[str, str] | None:
        """The first CAPTCHA page seen since the last call (host, url), or None. Only a person can pass it.
        The tab it is in becomes the active one, so the person is shown the check, not some other tab."""
        found, self.challenges = (self.challenges[0] if self.challenges else None), []
        if found is None:
            return None
        host, url, tab = found
        if tab is not None and not tab.is_closed() and tab is not self.page and tab in self.context.pages:
            self.page = tab
            with contextlib.suppress(PlaywrightError):
                await tab.bring_to_front()
        return host, url

    def take_denied(self) -> str | None:
        """What the sites refused since the last call, in words for the agent; None if nothing. Never to be retried or worked around."""
        if not self.denied:
            return None
        denied, self.denied = list(dict.fromkeys(self.denied)), []
        return ("a website refused the browser: " + "; ".join(denied)
                + ". That is a block, not a glitch: do not retry it or look for a way around it; use a different source, or finish and say what was blocked.")

    async def guard_request(self, route) -> None:
        """Web scope: nothing the browser requests may reach a private network, whatever page asked (redirects, images, new tabs)."""
        request = route.request
        parts = urlparse(request.url)
        if parts.scheme in ("data", "blob", "about"):
            await route.continue_()
        elif parts.scheme in ("http", "https", "ws", "wss") and self.policy.host_ok(request.url) and await self.policy.resolves_public(request.url):
            await route.continue_()
        else:
            if request.is_navigation_request():
                self.blocked.append(request.url)
            await route.abort("blockedbyclient")


class BrowserHost:
    """One browser process. Each session gets its own context (cookies, tabs, guard), so sub-agents never see each other's pages."""

    def __init__(self, playwright, browser) -> None:
        self.playwright, self.browser = playwright, browser

    async def session(self, start_url: str, *, respect_robots: bool = True, scope: Scope = "site", files: FileStore | None = None) -> BrowserSession:
        context = await self.browser.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=files is not None)
        page = await context.new_page()
        session = BrowserSession(page, Policy(start_url, respect_robots=respect_robots, scope=scope), context, files)
        context.on("page", lambda new: _adopt(session, new))
        if scope == "web":
            await context.route("**/*", session.guard_request)
        return session


async def _launch(headless: bool) -> BrowserHost:
    playwright = await async_playwright().start()
    try:
        return BrowserHost(playwright, await playwright.chromium.launch(headless=headless))
    except BaseException:
        await playwright.stop()
        raise


@asynccontextmanager
async def open_browser(headless: bool = True) -> AsyncIterator[BrowserHost]:
    starting = asyncio.ensure_future(_launch(headless))
    try:
        host = await asyncio.shield(starting)
    except asyncio.CancelledError:
        # stopped while the browser was still starting: let the start finish and close it, so no process or task is left behind
        with contextlib.suppress(Exception):
            host = await starting
            await host.browser.close()
            await host.playwright.stop()
        raise
    try:
        yield host
    finally:
        with contextlib.suppress(Exception):
            await host.browser.close()  # closes every context with it
        await host.playwright.stop()


@asynccontextmanager
async def open_session(
    start_url: str, *, headless: bool = True, respect_robots: bool = True, scope: Scope = "site", files: FileStore | None = None
) -> AsyncIterator[BrowserSession]:
    """One browser with one session: what a single agent (and every test) needs."""
    async with open_browser(headless) as host:
        yield await host.session(start_url, respect_robots=respect_robots, scope=scope, files=files)


def _adopt(session: BrowserSession, new_page: Page) -> None:
    """A click opened a new tab: follow it if it stays on the site, otherwise close it."""
    if session.policy.host_ok(new_page.url) or new_page.url in ("", "about:blank"):
        session.page = new_page
        session._wire(new_page)
    else:
        asyncio.ensure_future(new_page.close())
