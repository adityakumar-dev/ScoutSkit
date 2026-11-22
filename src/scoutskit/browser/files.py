"""Files a run saves: links the agent asks for (save_file) and downloads a click starts, kept in the run's files/ folder.

Files are only stored, never opened or run. Names are made safe and unique; each file and the run as a whole have a size limit.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_RUN_BYTES = 200 * 1024 * 1024
SAFE_NAME = re.compile(r"[^\w.\-]+")


class FileRefused(Exception):
    """Too large, or nothing to save; the message says which."""


@dataclass
class SavedFile:
    name: str
    url: str
    size: int
    content_type: str

    def as_dict(self) -> dict:
        return asdict(self)


DOCUMENT_TYPES = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt", ".zip", ".odt", ".ods", ".epub")


def looks_like_file(url: str) -> bool:
    """Does the address name a document (by its extension)? Used to save search results that are the file itself."""
    return urlparse(url).path.lower().endswith(DOCUMENT_TYPES)


PAGE_START = (b"<!doctype html", b"<html", b"<?xml", b"<head", b"<body")
WEB_EXTENSIONS = (".html", ".htm", ".xhtml", ".php", ".asp", ".aspx", "")  # addresses that name a page, not a file


def not_a_file(url: str, content_type: str, data: bytes, name: str = "", pages_ok: bool = True) -> str | None:
    """Why these bytes are not the file the link promised (None when they look right). A server that no longer has a file often answers with its
    error page and a 200: saving that as "the file" would pass for success."""
    ext = Path(name).suffix.lower() or Path(urlparse(url).path).suffix.lower()  # the name it will be saved under counts too
    head = data[:200].lstrip().lower()
    is_page = content_type.lower().startswith(("text/html", "application/xhtml")) or head.startswith(PAGE_START)
    if is_page and (not pages_ok or ext not in (".html", ".htm", ".xhtml")):
        return "the server sent a web page (usually an error page), not a file; open the address with goto if you want to read it"
    if ext == ".pdf" and not data.lstrip()[:5] == b"%PDF-":
        return "it is not a PDF (it does not start like one)"
    if ext in DOCUMENT_TYPES and len(data) < 20:
        return f"only {len(data)} bytes: not a real {ext} file"
    return None


def safe_name(hint: str, url: str) -> str:
    name = hint or unquote(Path(urlparse(url).path).name) or "download"
    name = SAFE_NAME.sub("_", name).strip("._") or "download"
    return name[-120:]


class FileStore:
    def __init__(self, folder: Path, on_saved: Callable[[SavedFile], None] = lambda saved: None) -> None:
        self.folder, self.on_saved = folder, on_saved
        self.saved: list[SavedFile] = []

    @property
    def used(self) -> int:
        return sum(f.size for f in self.saved)

    def have(self, url: str) -> SavedFile | None:
        """The file already saved from this address in this run (several sub-agents often reach for the same document)."""
        return next((f for f in self.saved if f.url == url), None)

    def check_size(self, size: int) -> None:
        if size > MAX_FILE_BYTES:
            raise FileRefused(f"the file is {size / 1e6:.1f} MB; the limit is {MAX_FILE_BYTES // 1_000_000} MB per file")
        if self.used + size > MAX_RUN_BYTES:
            raise FileRefused(f"this run has saved {self.used / 1e6:.0f} MB already; the limit is {MAX_RUN_BYTES // 1_000_000} MB")

    def _free_path(self, name: str) -> Path:
        self.folder.mkdir(parents=True, exist_ok=True)
        path, stem, suffix, n = self.folder / name, Path(name).stem, Path(name).suffix, 1
        while path.exists():
            n += 1
            path = self.folder / f"{stem}-{n}{suffix}"
        return path

    def _record(self, path: Path, url: str, content_type: str) -> SavedFile:
        saved = SavedFile(path.name, url, path.stat().st_size, content_type)
        self.saved.append(saved)
        self.on_saved(saved)
        return saved

    def save_bytes(self, data: bytes, url: str, content_type: str = "", hint: str = "") -> SavedFile:
        if not data:
            raise FileRefused("the link returned an empty file")
        if reason := not_a_file(url, content_type, data, hint, pages_ok=False):  # save_file is for documents: a page is opened, not saved
            raise FileRefused(reason)
        self.check_size(len(data))
        path = self._free_path(safe_name(hint, url))
        path.write_bytes(data)
        return self._record(path, url, content_type)

    async def save_download(self, download) -> SavedFile:
        """A download the page started (a click on a file link). Kept only if it fits the limits."""
        path = self._free_path(safe_name(download.suggested_filename, download.url))
        await download.save_as(path)
        try:
            self.check_size(path.stat().st_size)
            if reason := not_a_file(download.suggested_filename or download.url, "", path.read_bytes()[:4096]):
                raise FileRefused(reason)
        except FileRefused:
            path.unlink(missing_ok=True)
            raise
        return self._record(path, download.url, "")
