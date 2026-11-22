"""The server: start a run, watch it live (events and picture), stop it, read its files. The agent itself is replaced by a stand-in."""

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from scoutskit.browser import open_session
from scoutskit.runner import Outcome
from scoutskit.server import create_app
from scoutskit.server.events import Channel, to_event


def outcome(status="completed", items=2):
    return SimpleNamespace(status=status, items=items, steps=2, message="", recipe_saved=False)


async def stand_in(task, *, say, attach, recorder, url=None, hold=0.0, **_):
    """Like runner.execute: opens a real browser on the page, reports steps, saves a result."""
    say("planning")
    recorder.log(event="start", task=task)
    async with open_session(url) as session:
        await attach(session)
        await session.goto(url)
        recorder.log(step=1, tool="goto", ok=True)
        await asyncio.sleep(hold)
        recorder.log(step=2, tool="done", ok=True)
    recorder.save_result([{"a": "1"}, {"a": "2"}], ["a"], {"task": task, "status": "completed", "items": 2})
    return outcome()


def client(tmp_path, execute=stand_in):
    return TestClient(create_app(tmp_path, execute))


def wait_until(check, seconds=20):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if check():
            return
        time.sleep(0.1)
    raise AssertionError("timed out")


def test_a_run_streams_events_and_live_frames_then_finishes(portal, tmp_path):
    with client(tmp_path) as http:
        run_id = http.post("/api/runs", json={"task": "look at the feed", "url": portal + "/feed.html"}).json()["id"]
        seen, frames = [], 0
        with http.websocket_connect(f"/api/runs/{run_id}/stream") as socket:
            while True:
                message = socket.receive()
                if message.get("bytes") is not None:
                    assert message["bytes"][:2] == b"\xff\xd8"  # a JPEG
                    frames += 1
                else:
                    event = json.loads(message["text"])
                    seen.append(event["type"])
                    if event["type"] == "finished":
                        break
        assert seen[:2] == ["notice", "start"] and seen[-1] == "finished" and "step" in seen
        assert frames >= 1
        listing = http.get("/api/runs").json()
        assert listing[0]["id"] == run_id and listing[0]["status"] == "completed" and listing[0]["items"] == 2
        assert http.get(f"/api/runs/{run_id}/files/result.csv").text.splitlines() == ["a", "1", "2"]


def test_a_viewer_that_arrives_after_the_run_still_gets_its_whole_history(portal, tmp_path):
    with client(tmp_path) as http:
        run_id = http.post("/api/runs", json={"task": "look at the feed", "url": portal + "/feed.html"}).json()["id"]
        wait_until(lambda: http.get(f"/api/runs/{run_id}").json()["status"] == "completed")
        with http.websocket_connect(f"/api/runs/{run_id}/stream") as socket:
            types = []
            while True:
                message = socket.receive()
                if message["type"] == "websocket.close":
                    break
                if message.get("bytes") is None:  # (the last picture is replayed too)
                    types.append(json.loads(message["text"])["type"])
        assert types[0] == "notice" and types[-1] == "finished"


def test_a_running_run_can_be_stopped(portal, tmp_path):
    async def slow(task, *, say, attach, recorder, url=None, **_):
        return await stand_in(task, say=say, attach=attach, recorder=recorder, url=url, hold=60)

    with client(tmp_path, slow) as http:
        run_id = http.post("/api/runs", json={"task": "a long task", "url": portal + "/feed.html"}).json()["id"]
        wait_until(lambda: any(e["type"] == "step" for e in http.app.state.manager.active[run_id].channel.events))
        assert http.post(f"/api/runs/{run_id}/stop").json() == {"stopped": True}
        assert http.get(f"/api/runs/{run_id}").json()["status"] == "cancelled"
        assert http.post(f"/api/runs/{run_id}/stop").json() == {"stopped": False}


def test_a_run_that_cannot_start_is_reported_as_failed_not_a_crash(tmp_path):
    async def broken(task, **_):
        raise RuntimeError("no provider works")

    with client(tmp_path, broken) as http:
        run_id = http.post("/api/runs", json={"task": "anything at all"}).json()["id"]
        wait_until(lambda: http.get(f"/api/runs/{run_id}").json()["status"] == "failed")
        events = http.app.state.manager.active[run_id].channel.events
        assert events[-1]["type"] == "finished" and "no provider works" in events[-1]["message"]


def test_bad_requests_and_unknown_runs_are_refused(tmp_path):
    with client(tmp_path) as http:
        assert http.post("/api/runs", json={"task": "x"}).status_code == 422
        assert http.post("/api/runs", json={"task": "a real task", "url": "file:///etc/passwd"}).status_code == 422
        assert http.get("/api/runs/20250101-000000").status_code == 404
        assert http.get("/api/runs/..%2f..%2fetc").status_code == 404
        (tmp_path / "20250101-000000").mkdir()
        assert http.get("/api/runs/20250101-000000/files/..%2fsecret").status_code == 404
        assert http.get("/api/runs/20250101-000000/files/result.csv").status_code == 404


def test_only_the_local_ui_may_open_the_stream(tmp_path):
    from starlette.websockets import WebSocketDisconnect

    (tmp_path / "20250101-000000").mkdir()
    with client(tmp_path) as http:
        with pytest.raises(WebSocketDisconnect):
            with http.websocket_connect("/api/runs/20250101-000000/stream", headers={"origin": "https://evil.example"}):
                pass
        with http.websocket_connect("/api/runs/20250101-000000/stream", headers={"origin": "http://localhost:5173"}) as socket:
            assert json.loads(socket.receive()["text"])["type"] == "finished"
            assert socket.receive()["type"] == "websocket.close"


def test_too_many_parallel_runs_are_refused(portal, tmp_path):
    async def slow(task, *, say, attach, recorder, url=None, **_):
        return await stand_in(task, say=say, attach=attach, recorder=recorder, url=url, hold=60)

    with client(tmp_path, slow) as http:
        codes = [http.post("/api/runs", json={"task": f"task number {i}", "url": portal + "/feed.html"}).status_code for i in range(4)]
        assert codes == [201, 201, 201, 429]
        for run_id in list(http.app.state.manager.active):
            http.post(f"/api/runs/{run_id}/stop")


async def test_a_slow_viewer_gets_only_the_newest_frame_but_every_event():
    channel = Channel()
    watcher = channel.watch()
    channel.publish({"type": "a"})
    first = await anext(watcher)
    for n in range(5):
        channel.publish_frame(bytes([n]))
    channel.publish({"type": "b"})
    channel.close()
    rest = [message async for message in watcher]
    assert first == {"type": "a"} and rest == [{"type": "b"}, bytes([4])]


def test_recorder_entries_become_typed_events():
    assert to_event({"event": "notice", "text": "hi"}) == {"type": "notice", "text": "hi"}
    assert to_event({"step": 1, "tool": "click"}) == {"type": "step", "step": 1, "tool": "click"}


def test_a_run_folder_without_a_result_is_listed_as_interrupted_with_its_task(tmp_path):
    folder = tmp_path / "20250101-000000"
    folder.mkdir()
    (folder / "actions.jsonl").write_text(json.dumps({"event": "start", "task": "an unfinished task"}) + "\n")
    with client(tmp_path) as http:
        (entry,) = http.get("/api/runs").json()
        assert entry["status"] == "interrupted" and entry["task"] == "an unfinished task" and entry["items"] == 0
        with http.websocket_connect("/api/runs/20250101-000000/stream") as socket:  # a past run ends its replay with how it ended
            events = []
            while (message := socket.receive())["type"] != "websocket.close":
                events.append(json.loads(message["text"]))
        assert events[-1] == {"type": "finished", "status": "interrupted", "items": 0, "message": "", "recipe": False}


def test_a_run_that_failed_while_planning_still_shows_its_task(tmp_path):
    folder = tmp_path / "20250101-000001"
    folder.mkdir()
    (folder / "actions.jsonl").write_text(json.dumps({"event": "task", "task": "find the syllabus"}) + "\n" + json.dumps({"event": "error", "error": "LLMError"}) + "\n")
    with client(tmp_path) as http:
        assert http.get("/api/runs").json()[0]["task"] == "find the syllabus"


def test_a_person_can_take_over_type_and_hand_back_and_what_they_typed_is_never_recorded(portal, tmp_path):
    secret = "correct-horse-battery-staple"

    async def drivable(task, *, say, attach, recorder, control, url=None, **_):
        """Like the agent: take a step, check in, and carry on once the person has handed the browser back."""
        recorder.log(event="start", task=task)
        async with open_session(url) as session:
            await attach(session)
            await session.goto(url)
            handed_back = False
            for step in range(1, 400):
                handed_back = await control.checkpoint() or handed_back
                recorder.log(step=step, tool="wait", ok=True)
                if handed_back:
                    break
                await asyncio.sleep(0.05)
            value = await session.page.evaluate("document.getElementById('field').value")
        recorder.save_result([{"typed": value}], ["typed"], {"task": task, "status": "completed", "items": 1})
        return outcome(items=1)

    def messages(socket):
        while True:
            message = socket.receive()
            if message.get("text"):
                yield json.loads(message["text"])
            elif message["type"] == "websocket.close":
                return

    with client(tmp_path, drivable) as http:
        run_id = http.post("/api/runs", json={"task": "log in by hand", "url": portal + "/typing.html"}).json()["id"]
        manager = http.app.state.manager
        with http.websocket_connect(f"/api/runs/{run_id}/stream") as socket:
            wait_until(lambda: manager.active[run_id].session is not None)
            socket.send_json({"kind": "type", "text": secret})  # not driving yet: refused, and nothing reaches the page
            assert "take over first" in next(e for e in messages(socket) if e["type"] == "input_refused")["reason"]
            assert http.post(f"/api/runs/{run_id}/control", json={"mode": "user"}).status_code == 200
            wait_until(lambda: manager.active[run_id].control.user_driving)
            socket.send_json({"kind": "eval", "code": "alert(1)"})  # not an allowed input
            assert "not allowed" in next(e for e in messages(socket) if e["type"] == "input_refused")["reason"]
            socket.send_json({"kind": "type", "text": secret})  # the page's input has the focus
            time.sleep(0.5)
            http.post(f"/api/runs/{run_id}/control", json={"mode": "agent"})
        wait_until(lambda: http.get(f"/api/runs/{run_id}").json()["status"] == "completed")
        folder = tmp_path / run_id
        assert json.loads((folder / "result.json").read_text())["rows"] == [{"typed": secret}]  # it reached the page
        evidence = [path for path in folder.rglob("*") if path.is_file() and path.name not in ("result.json", "result.csv") and path.suffix != ".png"]
        assert evidence and all(secret not in path.read_text(errors="ignore") for path in evidence)  # the log and every other record
        log = (folder / "actions.jsonl").read_text()
        assert '"mode": "requested"' in log and '"mode": "user"' in log and '"mode": "agent"' in log
        assert http.post(f"/api/runs/{run_id}/control", json={"mode": "user"}).status_code == 409  # a finished run cannot be taken over


def test_the_plan_waits_for_approval_and_context_sends_it_back(tmp_path):
    answers = []

    async def asks_first(task, *, recorder, gate=None, **_):
        while not (decision := await gate.ask()).approve:
            answers.append(decision.context)
        recorder.save_result([], [], {"task": task, "status": "completed", "items": 0})
        return Outcome("completed", 0, 0, "", recorder.dir, False, {})

    with client(tmp_path, asks_first) as http:
        run_id = http.post("/api/runs", json={"task": "plan first"}).json()["id"]
        gate = http.app.state.manager.active[run_id].gate
        wait_until(lambda: gate.waiting)
        assert http.post(f"/api/runs/{run_id}/answer", json={"action": "revise", "context": "  "}).status_code == 422
        assert http.post(f"/api/runs/{run_id}/answer", json={"action": "revise", "context": "use uni.example"}).json() == {"ok": True}
        wait_until(lambda: gate.waiting)
        assert http.post(f"/api/runs/{run_id}/answer", json={"action": "approve"}).json() == {"ok": True}
        wait_until(lambda: http.get(f"/api/runs/{run_id}").json()["status"] == "completed")
        assert answers == ["use uni.example"]
        assert http.post(f"/api/runs/{run_id}/answer", json={"action": "approve"}).status_code == 409
        states = [e["state"] for e in http.app.state.manager.active[run_id].channel.events if e["type"] == "approval"]
        assert states == ["waiting", "revising", "waiting", "approved"]


def test_an_autonomous_run_has_no_gate(tmp_path):
    seen = {}

    async def notes_gate(task, *, recorder, gate=None, **_):
        seen["gate"] = gate
        return Outcome("completed", 0, 0, "", recorder.dir, False, {})

    with client(tmp_path, notes_gate) as http:
        http.post("/api/runs", json={"task": "just go", "autonomous": True})
        wait_until(lambda: "gate" in seen)
        assert seen["gate"] is None


def test_saved_files_are_shown_inline_only_when_that_is_safe(tmp_path):
    folder = tmp_path / "20250101-000002" / "files"
    folder.mkdir(parents=True)
    for name, data in (("report.pdf", b"%PDF-1.4"), ("data.csv", b"a,b\n1,2\n"), ("page.html", b"<script>alert(1)</script>"), ("logo.svg", b"<svg onload=alert(1)/>"), ("blob.bin", b"\x00")):
        (folder / name).write_bytes(data)
    with client(tmp_path) as http:
        base = "/api/runs/20250101-000002/saved/"
        pdf = http.get(base + "report.pdf")
        assert pdf.headers["content-type"] == "application/pdf" and pdf.headers["content-disposition"].startswith("inline")
        assert pdf.headers["x-content-type-options"] == "nosniff"
        csv = http.get(base + "data.csv")  # shown as plain text, so the browser never treats it as a page
        assert csv.headers["content-type"].startswith("text/plain") and csv.text == "a,b\n1,2\n"
        for risky in ("page.html", "logo.svg", "blob.bin"):  # could run script on this origin, or unknown: always a download
            reply = http.get(base + risky)
            assert reply.headers["content-type"] == "application/octet-stream" and reply.headers["content-disposition"].startswith("attachment"), risky
        assert http.get(base + "report.pdf?download=true").headers["content-disposition"].startswith("attachment")
        assert http.get(base + "..%2Fresult.json").status_code == 404 and http.get(base + "missing.pdf").status_code == 404


def test_a_sub_agent_that_needs_help_gets_its_browser_shown_and_the_person_can_skip(portal, tmp_path):
    notes = []

    async def needs_help(task, *, say, attach, recorder, control, url=None, **_):
        async with open_session(url) as first, open_session(url) as second:
            await attach(first, "a1")
            await attach(second, "a2")
            await first.goto(url)
            recorder.log(event="help_needed", kind="captcha", host="example.test", url=url, agent="a2")  # the second sub-agent hit a CAPTCHA
            control.request_user()
            await control.checkpoint()
            notes.append(control.take_note())
        recorder.save_result([], [], {"task": task, "status": "completed", "items": 0})
        return outcome()

    with client(tmp_path, needs_help) as http:
        run_id = http.post("/api/runs", json={"task": "needs a person", "url": portal + "/feed.html"}).json()["id"]
        run = http.app.state.manager.active[run_id]
        wait_until(lambda: run.control.user_driving)
        wait_until(lambda: run.focus == "a2")  # the browser to drive is the one that asked
        assert any(e["type"] == "focus" and e["agent"] == "a2" for e in run.channel.events)
        assert http.post(f"/api/runs/{run_id}/control", json={"mode": "agent", "note": "skip"}).json() == {"mode": "agent"}
        wait_until(lambda: http.get(f"/api/runs/{run_id}").json()["status"] == "completed")
        assert notes == ["skip"]
        assert http.post(f"/api/runs/{run_id}/control", json={"mode": "agent", "note": "bogus"}).status_code == 422


def test_a_person_driving_one_of_two_sub_agents_reaches_exactly_that_browser(portal, tmp_path):
    """Two sub-agents, each with its own browser; the person takes over the one being watched and clicks and types in it."""
    seen = {}

    async def two_scouts(task, *, say, attach, recorder, control, url=None, **_):
        async with open_session(url) as first, open_session(url) as second:
            await attach(first, "a1")
            await attach(second, "a2")
            await first.goto(url)
            await second.goto(url)
            control.request_user()
            await control.checkpoint()  # the person drives until they hand back
            seen["a1"] = await first.page.evaluate("document.querySelector('input').value")
            seen["a2"] = await second.page.evaluate("document.querySelector('input').value")
        recorder.save_result([], [], {"task": task, "status": "completed", "items": 0})
        return outcome()

    with client(tmp_path, two_scouts) as http:
        run_id = http.post("/api/runs", json={"task": "drive it", "url": portal + "/typing.html"}).json()["id"]
        run = http.app.state.manager.active[run_id]
        wait_until(lambda: run.control.user_driving and run.session is not None)
        box = run.session  # the watched one: a1
        point = http.portal.call(box.page.evaluate, "(() => { const r = document.querySelector('input').getBoundingClientRect(); return [(r.x + r.width / 2) / innerWidth, (r.y + r.height / 2) / innerHeight]; })()") if hasattr(http, "portal") else None
        assert point is not None
        with http.websocket_connect(f"/api/runs/{run_id}/stream") as socket:
            socket.send_json({"kind": "click", "x": point[0], "y": point[1]})
            socket.send_json({"kind": "type", "text": "hello"})
            wait_until(lambda: http.portal.call(box.page.evaluate, "document.querySelector('input').value") == "hello", 10)
        http.post(f"/api/runs/{run_id}/control", json={"mode": "agent"})
        wait_until(lambda: http.get(f"/api/runs/{run_id}").json()["status"] == "completed")
        assert seen == {"a1": "hello", "a2": ""}  # typed into the watched browser only


def test_a_viewer_who_arrives_at_a_still_page_gets_its_picture_at_once():
    import asyncio as aio

    async def go():
        channel = Channel()
        channel.publish_frame(b"\xff\xd8 still page")
        watcher = channel.watch()
        first = await aio.wait_for(watcher.__anext__(), 2)  # no new frame was ever published: the last one is replayed
        channel.close()
        return first

    assert aio.run(go()) == b"\xff\xd8 still page"


def test_a_completed_run_can_be_replayed_as_a_new_run_with_no_model(portal, tmp_path):
    import shutil

    from scoutskit.recipe import RECIPE_FILE, Recipe, Step

    source = tmp_path / "20250101-000010"
    (source / "files").mkdir(parents=True)
    Recipe(task="get the report", start_url=portal + "/files.html", steps=[Step("save_file", {"url": portal + "/report.pdf"}, "/files.html")],
           expected_files=["report.pdf"]).save(source / RECIPE_FILE)
    (source / "actions.jsonl").write_text(json.dumps({"event": "start", "task": "get the report"}) + "\n")
    with client(tmp_path) as http:
        started = http.post("/api/runs/20250101-000010/replay")
        assert started.status_code == 201
        new_id = started.json()["id"]
        wait_until(lambda: http.get(f"/api/runs/{new_id}").json()["status"] in ("replayed", "changed", "diverged"), 40)
        summary = http.get(f"/api/runs/{new_id}").json()
        assert summary["status"] == "replayed" and summary["task"].startswith("Replay: get the report")
        assert (tmp_path / new_id / "files" / "report.pdf").exists()  # saved again, with no model involved
        assert http.get(f"/api/runs/{new_id}/saved/report.pdf").status_code == 200
        assert http.post("/api/runs/does-not-exist/replay").status_code in (404, 422, 409)
        (tmp_path / "20250101-000011").mkdir()
        assert http.post("/api/runs/20250101-000011/replay").status_code == 409  # no recipe: said so, not a crash
