"""The HTTP and WebSocket interface the web UI talks to. Local use: it binds to 127.0.0.1 and checks the Origin of every browser."""

from __future__ import annotations

import asyncio
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from ..control import Decision
from .input_pump import InputPump
from .runs import RunManager, TooManyRuns

UI_DIST = Path(__file__).resolve().parents[3] / "ui" / "dist"
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # the Vite dev server
SHOT = re.compile(r"^(?:a\d+-)?step\d+\.png$")
# What a saved file may be shown as in the browser. The type comes from this table, never from the file or the site it came from,
# and only these: HTML and SVG could run script on this server's origin, so they are always downloads.
INLINE_TYPES = {
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".csv": "text/plain; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".json": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
    ".log": "text/plain; charset=utf-8", ".tsv": "text/plain; charset=utf-8",
}
SAVED = re.compile(r"^[\w.\-]{1,130}$")  # names the file store gives saved files
DOWNLOADS = {"result.csv": "text/csv", "result.json": "application/json", "recipe.json": "application/json", "actions.jsonl": "application/x-ndjson"}


class FocusRequest(BaseModel):
    agent: str = Field(pattern=r"^a\d{1,2}$")


class ControlRequest(BaseModel):
    mode: Literal["user", "agent"]
    note: Literal["", "skip"] = ""  # with "agent": skip the site the agent asked for help with


class PlanAnswer(BaseModel):
    action: Literal["approve", "revise"]
    context: str = Field(default="", max_length=2000)


class StartRequest(BaseModel):
    task: str = Field(min_length=3, max_length=2000)
    url: str | None = None
    provider: str | None = None
    strict: bool = False
    web: bool = False  # may visit any public website
    max_steps: int | None = Field(default=None, ge=1, le=100)
    autonomous: bool = False  # follow the plan without waiting for approval

    @field_validator("url")
    @classmethod
    def web_address(cls, value: str | None) -> str | None:
        if value and urlparse(value).scheme not in ("http", "https"):
            raise ValueError("the start URL must begin with http:// or https://")
        return value or None


def create_app(runs_dir: Path, execute=None, origins: list[str] | None = None) -> FastAPI:
    if execute is None:
        from ..runner import execute
    allowed = origins if origins is not None else DEV_ORIGINS
    manager = RunManager(runs_dir, execute)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        for run_id in list(manager.active):
            await manager.stop(run_id)

    app = FastAPI(title="ScoutsKit", lifespan=lifespan)
    app.state.manager = manager
    app.add_middleware(CORSMiddleware, allow_origins=allowed, allow_methods=["GET", "POST"], allow_headers=["content-type"])

    def known(run_id: str) -> str:
        if not manager.valid(run_id) and run_id not in manager.active:
            raise HTTPException(404, "no such run")
        return run_id

    @app.post("/api/runs", status_code=201)
    async def start_run(request: StartRequest) -> dict:
        options = {"url": request.url, "provider_name": request.provider, "strict": request.strict, "web": request.web, "max_steps": request.max_steps}
        try:
            return {"id": manager.start(request.task, ask_first=not request.autonomous, **options).id}
        except TooManyRuns as error:
            raise HTTPException(429, str(error)) from error

    @app.get("/api/runs")
    async def list_runs() -> list[dict]:
        return manager.list()

    @app.get("/api/runs/{run_id}")
    async def run_detail(run_id: str) -> dict:
        return manager.summary(known(run_id))

    @app.post("/api/runs/{run_id}/stop")
    async def stop_run(run_id: str) -> dict:
        return {"stopped": await manager.stop(known(run_id))}

    @app.post("/api/runs/{run_id}/control")
    async def control(run_id: str, request: ControlRequest) -> dict:
        try:
            return {"mode": manager.take_over(known(run_id), request.mode, request.note)}
        except LookupError as error:
            raise HTTPException(409, str(error)) from error

    @app.post("/api/runs/{run_id}/answer")
    async def answer(run_id: str, request: PlanAnswer) -> dict:
        """Answers what the run is waiting on: its plan (approve, or revise with context) or a sub-agent's result (accept or reject)."""
        if request.action == "revise" and not request.context.strip() and manager.waiting_on(known(run_id)) == "plan":
            raise HTTPException(422, "say what to change: add some context")
        if not manager.answer(known(run_id), Decision(request.action == "approve", request.context.strip())):
            raise HTTPException(409, "nothing is waiting for an answer")
        return {"ok": True}

    @app.post("/api/runs/{run_id}/focus")
    async def focus(run_id: str, request: FocusRequest) -> dict:
        if not await manager.focus(known(run_id), request.agent):
            raise HTTPException(409, "that sub-agent's browser cannot be shown now")
        return {"agent": request.agent}

    @app.get("/api/runs/{run_id}/saved/{name}")
    async def saved_file(run_id: str, name: str, download: bool = False):
        folder = (runs_dir / known(run_id) / "files").resolve()
        path = (folder / name).resolve()
        if not SAVED.match(name) or name.startswith(".") or path.parent != folder or not path.is_file():
            raise HTTPException(404, "no such file")
        shown_as = INLINE_TYPES.get(path.suffix.lower())
        headers = {"X-Content-Type-Options": "nosniff"}  # the type above is final; (a strict CSP here would also stop Chrome's PDF viewer)
        if shown_as is None or download:
            return FileResponse(path, filename=name, media_type="application/octet-stream", headers=headers)  # a download, never rendered
        return FileResponse(path, media_type=shown_as, content_disposition_type="inline", filename=name, headers=headers)

    @app.get("/api/runs/{run_id}/files/{name}")
    async def download(run_id: str, name: str):
        path = runs_dir / known(run_id) / name
        if name not in DOWNLOADS or not path.is_file():
            raise HTTPException(404, "no such file")
        return FileResponse(path, media_type=DOWNLOADS[name])

    @app.get("/api/runs/{run_id}/screenshots/{name}")
    async def screenshot(run_id: str, name: str):
        path = runs_dir / known(run_id) / "screenshots" / name
        if not SHOT.match(name) or not path.is_file():
            raise HTTPException(404, "no such screenshot")
        return FileResponse(path, media_type="image/png")

    @app.websocket("/api/runs/{run_id}/stream")
    async def stream(websocket: WebSocket, run_id: str) -> None:
        origin = websocket.headers.get("origin")  # browsers always send it; a page on another site must not drive this server
        if origin and origin not in allowed and urlparse(origin).netloc != websocket.headers.get("host"):
            await websocket.close(code=1008)
            return
        channel = manager.channel(run_id)
        if channel is None:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        sending = asyncio.Lock()  # the watcher and the input reader both write to this socket

        async def refuse(reason: str) -> None:
            async with sending:
                await websocket.send_json({"type": "input_refused", "reason": reason})

        pump = InputPump(lambda message: manager.remote_input(run_id, message), refuse)

        async def read_input() -> None:
            """Reads at once and never waits for the browser: the pump applies what arrives (merging floods, running slow ones aside)."""
            while True:
                try:
                    message = await websocket.receive_json()
                except WebSocketDisconnect:
                    return
                except ValueError:
                    message = None  # not JSON: refused like any other input that is not allowed
                pump.put(message)

        applying = asyncio.create_task(pump.run())
        reader = asyncio.create_task(read_input())
        try:
            async for message in channel.watch():
                async with sending:
                    await (websocket.send_bytes(message) if isinstance(message, bytes) else websocket.send_json(message))
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            reader.cancel()
            applying.cancel()

    if UI_DIST.is_dir():  # the built web UI (`npm run build` in ui/): one command, one address
        app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")
    return app
