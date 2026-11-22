"""What a person may do in the live view during a take-over: click, scroll, type, press a few keys, and use the browser's own tools (address bar, tabs).

Everything is validated first; coordinates arrive as fractions of the picture so the UI never needs to know the page size.
The text typed is passed to the page and nowhere else: it is not logged, not recorded, not echoed back.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from ..browser import BrowserSession

KEYS = ("Enter", "Tab", "Backspace", "Delete", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown")
MAX_TYPED = 2_000  # a paste
SHORTCUT_LETTERS = "acxvzy"  # select all, copy, cut, paste, undo, redo: with Control only
MAX_SCROLL = 5_000


class _At(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class Click(_At):
    kind: Literal["click"]
    button: Literal["left", "right", "middle"] = "left"
    clicks: int = Field(default=1, ge=1, le=3)  # 2 is a double click


class Move(_At):
    kind: Literal["move"]  # hovering: menus that open on hover need it


class Scroll(_At):
    kind: Literal["scroll"]
    dy: float = Field(ge=-MAX_SCROLL, le=MAX_SCROLL)


class TypeText(BaseModel):
    kind: Literal["type"]
    text: str = Field(min_length=1, max_length=MAX_TYPED)


class Key(BaseModel):
    kind: Literal["key"]
    key: str
    mods: list[Literal["Shift", "Control", "Alt"]] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def allowed(self) -> "Key":
        """A named key from the list, or a single editing shortcut letter together with Control."""
        if self.key in KEYS or (len(self.key) == 1 and self.key.lower() in SHORTCUT_LETTERS and "Control" in self.mods):
            return self
        raise ValueError("that key is not allowed")


class Navigate(BaseModel):
    kind: Literal["navigate"]
    url: str = Field(min_length=1, max_length=2000)


class NewTab(BaseModel):
    kind: Literal["new_tab"]
    url: str = Field(min_length=1, max_length=2000)


class TabAt(BaseModel):
    kind: Literal["switch_tab", "close_tab"]
    index: int = Field(ge=0, le=50)


class Simple(BaseModel):
    kind: Literal["back", "reload", "duplicate_tab"]


Input = Click | Move | Scroll | TypeText | Key | Navigate | NewTab | TabAt | Simple
RemoteInput = Annotated[Input, Field(discriminator="kind")]
_parse = TypeAdapter(RemoteInput).validate_python


def parse(message: object) -> Input:
    """Raises pydantic.ValidationError for anything that is not one of the allowed inputs."""
    return _parse(message)


async def apply(session: BrowserSession, event: Input) -> None:
    """Raises ActionError (a message safe to show) when a tool is refused, for example by the site policy."""
    if isinstance(event, Navigate):
        await session.goto(event.url)
        return
    if isinstance(event, NewTab):
        await session.open_tab(event.url)
        return
    if isinstance(event, TabAt):
        await (session.switch_tab if event.kind == "switch_tab" else session.close_tab)(event.index)
        return
    if isinstance(event, Simple):
        if event.kind == "back":
            await session.back()
        elif event.kind == "reload":
            await session.page.reload(wait_until="domcontentloaded")
        else:
            await session.open_tab(session.page.url)
        return
    page = session.page
    size = page.viewport_size or {"width": 1280, "height": 800}
    if isinstance(event, (Click, Move, Scroll)):
        x, y = event.x * size["width"], event.y * size["height"]
    if isinstance(event, Click):
        await page.mouse.click(x, y, button=event.button, click_count=event.clicks)
    elif isinstance(event, Move):
        await page.mouse.move(x, y)
    elif isinstance(event, Scroll):
        await page.mouse.move(x, y)
        await page.mouse.wheel(0, event.dy)
    elif isinstance(event, TypeText):
        if len(event.text) > 20:
            await page.keyboard.insert_text(event.text)  # a paste: no key press for each character
        else:
            await page.keyboard.type(event.text)
    else:
        await page.keyboard.press("+".join([*event.mods, event.key]))
