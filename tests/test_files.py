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
        second = await session.save_file(portal + "/report.pdf?copy=2")  # another address with the same file name
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


async def test_a_web_page_is_not_saved_as_a_file_and_a_real_pdf_must_look_like_one(portal, tmp_path):
    """A server that lost a file often answers 200 with its error page: that is not success."""
    store = FileStore(tmp_path / "files")
    async with open_session(portal + "/files.html", files=store) as session:
        await session.goto(portal + "/files.html")
        with pytest.raises(ActionError, match="web page"):
            await session.save_file(portal + "/files.html")  # a page, not a file
        with pytest.raises(ActionError, match="not saved"):
            await session.save_file(portal + "/details.html", "syllabus.pdf")  # named like a pdf, but a page
        assert (await session.save_file(portal + "/report.pdf")).name == "report.pdf"  # the real one still works
    assert [f.name for f in store.saved] == ["report.pdf"]


def test_not_a_file_rules():
    from scoutskit.browser.files import not_a_file

    assert not_a_file("https://x.example/a.pdf", "application/pdf", b"%PDF-1.5 a real looking document body") is None
    assert "web page" in not_a_file("https://x.example/a.pdf", "text/html; charset=utf-8", b"<!DOCTYPE html><html>")
    assert "web page" in not_a_file("https://x.example/frmHttpErrorPage.aspx", "", b"\n\n<!DOCTYPE html>\n<html")
    assert "not a PDF" in not_a_file("https://x.example/a.pdf", "application/octet-stream", b"hello this is text")
    assert "bytes" in not_a_file("https://x.example/a.xlsx", "application/vnd.ms-excel", b"x")
    assert not_a_file("https://x.example/index.html", "text/html", b"<html>") is None  # a browser download of an html address may be html
    assert "web page" in not_a_file("https://x.example/index.html", "text/html", b"<html>", pages_ok=False)  # but save_file is for documents
    assert not_a_file("https://x.example/data.csv", "text/csv", b"a,b\n1,2\n" * 20) is None


async def test_the_same_address_is_saved_once_per_run(portal, tmp_path):
    store = FileStore(tmp_path / "files")
    async with open_session(portal + "/files.html", files=store) as session:
        await session.goto(portal + "/files.html")
        first = await session.save_file(portal + "/report.pdf")
        again = await session.save_file("report.pdf")  # the same address, written relatively
    assert again is first and [f.name for f in store.saved] == ["report.pdf"]
