"""Tools that act on the page: click, type, choose, scroll, navigate."""

from __future__ import annotations

from ..browser import ActionError
from ..browser.files import SavedFile
from ..search import is_search_page
from .context import ToolContext
from .registry import Tool, ToolRegistry


def _size(n: int) -> str:
    return f"{n / 1_000_000:.1f} MB" if n >= 1_000_000 else f"{max(1, n // 1000)} KB"


def _saved_note(files: list[SavedFile]) -> str:
    if not files:
        return ""
    names = ", ".join(f"{f.name} ({_size(f.size)})" for f in files)
    return f"; this downloaded {names}: saved in the run's files for the user"


def _not_a_search_page(url: str) -> None:
    if is_search_page(url):
        raise ActionError("search engines refuse automated browsers (a block page or a CAPTCHA): call web_search(query) instead, it returns the same links as text")


def register(registry: ToolRegistry, ctx: ToolContext) -> None:
    session = ctx.session

    async def click(ref: str) -> str:
        return "clicked" + _saved_note(await session.downloads_after(session.click(str(ref))))

    async def save_file(url: str, name: str = "") -> str:
        saved = await session.save_file(str(url), str(name or ""))
        return f"saved {saved.name} ({_size(saved.size)}, {saved.content_type or 'unknown type'}) in the run's files for the user"

    async def fill(ref: str, text: str) -> str:
        await session.fill(str(ref), str(text))
        return "filled"

    async def select(ref: str, option: str) -> str:
        await session.select(str(ref), str(option))
        return f"selected {option}"

    async def press(key: str) -> str:
        await session.press(str(key))
        return f"pressed {key}"

    async def scroll(direction: str = "down", ref: str | None = None) -> str:
        return await session.scroll(str(direction), ref)

    async def hover(ref: str) -> str:
        await session.hover(str(ref))
        return "hovering"

    async def wait_for(text: str | None = None, seconds: float = 0, timeout: float = 10) -> str:
        return await session.wait_for(text, float(seconds), float(timeout))

    async def list_tabs() -> str:
        return await session.list_tabs()

    async def open_tab(url: str) -> str:
        _not_a_search_page(str(url))
        return await session.open_tab(url)

    async def switch_tab(index: int) -> str:
        return await session.switch_tab(int(index))

    async def close_tab(index: int) -> str:
        return await session.close_tab(int(index))

    async def goto(url: str) -> str:
        _not_a_search_page(str(url))
        note = _saved_note(await session.downloads_after(session.goto(str(url))))
        return f"opened {session.page.url}{note}"

    async def back() -> str:
        await session.back()
        return "went back"

    for tool in (
        Tool("click", "Click an element.", {"ref": "the [ref=...] id from the page tree"}, click),
        Tool("fill", "Type into a text field (never a password).", {"ref": "the field's ref", "text": "text to type"}, fill),
        Tool("select", "Choose an option in a dropdown (use the select's ref; never click its options).",
             {"ref": "the dropdown's ref", "option": "the option's label"}, select),
        Tool("press", "Press a key.", {"key": "e.g. Enter, Tab, Escape"}, press),
        Tool("scroll", "Scroll the page, or a table/list/dialog that scrolls on its own (pass its ref). Says when the end is reached.",
             {"direction": "down or up?", "ref": "ref of the scrolling container?"}, scroll),
        Tool("hover", "Move the pointer over an element: menus that open on hover reveal their items this way.", {"ref": "the element's ref"}, hover),
        Tool("wait_for", "Wait until some text is visible on the page, or pause for a few seconds (for slow or dynamic pages).",
             {"text": "text to wait for?", "seconds": "pause length, at most 10?", "timeout": "seconds to wait for the text?"}, wait_for, reads=True),
        Tool("list_tabs", "List the open tabs (a link may open a new one; the newest same-site tab becomes active).", {}, list_tabs, reads=True),
        Tool("open_tab", "Open a new tab on a URL and make it the active one (keeps the current page open).", {"url": "full http(s) address"}, open_tab),
        Tool("switch_tab", "Make another tab the active one.", {"index": "tab number from list_tabs"}, switch_tab),
        Tool("close_tab", "Close a tab (never the last one).", {"index": "tab number from list_tabs"}, close_tab),
        Tool("goto", "Open a URL on the same website.", {"url": "full URL"}, goto),
        Tool("back", "Go back one page.", {}, back),
        Tool("save_file", "Download a file (PDF, spreadsheet, document, image, archive...) from a link and keep it for the user. "
             "Use the link's address (href); relative links are fine. The file is stored, never opened.",
             {"url": "the file's address", "name": "file name to save as?"}, save_file),
    ):
        registry.register(tool)
