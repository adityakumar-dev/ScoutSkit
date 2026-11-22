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
        except FileRefused:
            path.unlink(missing_ok=True)
            raise
        return self._record(path, download.url, "")
