"""Saving files: links the agent asks for and downloads a click starts, within the site policy and the size limits."""

import pytest

from scoutskit.browser import ActionError, FileStore, open_session
from scoutskit.browser import files as files_module
from scoutskit.browser.files import FileRefused, safe_name


async def test_save_file_keeps_a_linked_file_and_never_overwrites(portal, tmp_path):
    store = FileStore(tmp_path / "files")
    async with open_session(portal + "/files.html", files=store) as session:
        await session.goto(portal + "/files.html")
        first = await session.save_file("report.pdf")  # relative to the page
        second = await session.save_file(portal + "/report.pdf")
    assert (first.name, second.name) == ("report.pdf", "report-2.pdf")
    assert (tmp_path / "files" / "report.pdf").read_bytes().startswith(b"%PDF")
    assert first.size > 0 and first.url.endswith("/report.pdf")


async def test_save_file_obeys_the_site_policy(portal, tmp_path):
    async with open_session(portal + "/files.html", files=FileStore(tmp_path)) as session:
        await session.goto(portal + "/files.html")
        with pytest.raises(ActionError):
            await session.save_file("http://169.254.169.254/latest/meta-data")


async def test_a_click_on_a_download_link_is_saved_and_reported(portal, tmp_path):
    seen = []
    store = FileStore(tmp_path / "files", on_saved=seen.append)
    async with open_session(portal + "/files.html", files=store) as session:
        await session.goto(portal + "/files.html")
        tree, _ = await session.snapshot()
        ref = next(line.split("[ref=")[1].split("]")[0] for line in tree.splitlines() if "Download report" in line)
        saved = await session.downloads_after(session.click(ref))
    assert [f.name for f in saved] == ["report.pdf"] and seen == saved


async def test_a_session_without_a_store_saves_nothing(portal):
    async with open_session(portal + "/files.html") as session:
        await session.goto(portal + "/files.html")
        with pytest.raises(ActionError, match="does not save files"):
            await session.save_file("report.pdf")


def test_limits_and_safe_names(tmp_path, monkeypatch):
    monkeypatch.setattr(files_module, "MAX_FILE_BYTES", 10)
    store = FileStore(tmp_path)
    with pytest.raises(FileRefused, match="limit"):
        store.save_bytes(b"x" * 11, "https://a.example/big.bin")
    with pytest.raises(FileRefused, match="empty"):
        store.save_bytes(b"", "https://a.example/x")
    assert safe_name("", "https://a.example/docs/My%20Syllabus%20(2024).pdf") == "My_Syllabus_2024_.pdf"
    assert safe_name("../../etc/passwd", "https://a.example/") == "etc_passwd"
