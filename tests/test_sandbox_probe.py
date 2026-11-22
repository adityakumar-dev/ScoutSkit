"""The sandbox must say why it is unavailable, and refuse code instead of running it unsandboxed."""

import pytest

from scoutskit import sandbox
from scoutskit.browser import ActionError


@pytest.fixture(autouse=True)
def fresh_probe():
    sandbox.unavailable_reason.cache_clear()
    yield
    sandbox.unavailable_reason.cache_clear()


def test_missing_bwrap_is_reported(monkeypatch):
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: None)
    assert "not installed" in sandbox.unavailable_reason()
    assert not sandbox.available()


def test_installed_but_unusable_bwrap_is_reported_with_the_real_error(monkeypatch):
    class Failed:
        returncode = 1
        stderr = "bwrap: Creating new namespace failed: Function not implemented\n"

    monkeypatch.setattr(sandbox.shutil, "which", lambda name: "/usr/bin/bwrap")
    monkeypatch.setattr(sandbox.subprocess, "run", lambda *args, **kwargs: Failed())
    reason = sandbox.unavailable_reason()
    assert "cannot create a sandbox" in reason and "Function not implemented" in reason


async def test_code_is_refused_when_no_sandbox_works(monkeypatch, tmp_path):
    monkeypatch.setattr(sandbox, "unavailable_reason", lambda: "bubblewrap (bwrap) is not installed")
    page = tmp_path / "page.html"
    page.write_text("x")
    with pytest.raises(ActionError, match="code execution is disabled"):
        await sandbox.run_python("print(1)", work=tmp_path / "work", raw_html=page, rendered_html=page)
