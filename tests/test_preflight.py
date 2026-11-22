"""The pre-flight check: each check reports in a few words, and a missing piece says what to do."""

from scoutskit import preflight
from scoutskit.preflight import Check


async def test_the_interface_check_says_how_to_build_it_when_it_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(preflight, "UI_DIST", tmp_path / "nothing")
    missing = await preflight.interface()
    assert not missing.ok and "npm run build" in missing.fix
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<html></html>")
    monkeypatch.setattr(preflight, "UI_DIST", tmp_path / "dist")
    assert (await preflight.interface()).ok


async def test_the_browser_sandbox_and_storage_checks_pass_on_a_working_machine():
    for check in (await preflight.browser(), await preflight.storage()):
        assert isinstance(check, Check) and check.ok, check
    assert (await preflight.sandbox()).name == "Code sandbox"


async def test_run_all_returns_every_check_even_when_one_raises(monkeypatch):
    async def broken() -> Check:
        raise RuntimeError("boom")

    async def fine() -> Check:
        return Check("Fine", True, "ok")

    monkeypatch.setattr(preflight, "CHECKS", [fine, broken, fine])
    results = await preflight.run_all()
    assert [c.ok for c in results] == [True, False, True] and "boom" in results[1].detail
