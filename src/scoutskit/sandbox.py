"""Run model-written Python with no network and a read-only filesystem.

The code sees only the saved page (HTML_PATH = the raw document, RENDERED_PATH = the live DOM)
and one writable folder where OUT_PATH lives. Environment variables (API keys!) are not passed.
bubblewrap (bwrap) must be installed and working: otherwise code execution is refused, never run unsandboxed.
"""

from __future__ import annotations

import asyncio
import functools
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .browser import ActionError

TIMEOUT_S = 60
MEMORY_BYTES = 3 << 30
MAX_OUTPUT = 2_500
PRELUDE = f"""import resource
resource.setrlimit(resource.RLIMIT_AS, ({MEMORY_BYTES}, {MEMORY_BYTES}))
HTML_PATH = '/data/page.html'
RENDERED_PATH = '/data/rendered.html'
OUT_PATH = '/work/out.json'
HTML = open(HTML_PATH, encoding='utf-8', errors='replace').read()  # the page's text, so no script needs to open a file to get it
RENDERED = open(RENDERED_PATH, encoding='utf-8', errors='replace').read()
import bs4 as _bs4
_init = _bs4.BeautifulSoup.__init__
def _soup_init(self, markup='', *args, **kwargs):
    # models often pass HTML_PATH itself (a path) where the document belongs: read the file they meant
    if markup in (HTML_PATH, RENDERED_PATH):
        markup = open(markup, encoding='utf-8', errors='replace').read()
    _init(self, markup, *args, **kwargs)
_bs4.BeautifulSoup.__init__ = _soup_init
"""


PROBE = [
    "bwrap", "--unshare-all", "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
    "--symlink", "usr/bin", "/bin", "--proc", "/proc", "--dev", "/dev", "/usr/bin/true",
]


@functools.lru_cache(maxsize=1)
def unavailable_reason() -> str:
    """Why model-written code cannot run here, or an empty string when it can.

    Installed is not enough: containers and CI runners often forbid the user namespaces
    bubblewrap needs, so we try to start a real (empty) sandbox once.
    """
    if shutil.which("bwrap") is None:
        return "bubblewrap (bwrap) is not installed"
    try:
        probe = subprocess.run(PROBE, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"bubblewrap could not be started ({type(error).__name__})"
    if probe.returncode != 0:
        detail = (probe.stderr.strip().splitlines() or ["unknown error"])[-1]
        return f"bubblewrap is installed but cannot create a sandbox here (often a container without user namespaces): {detail}"
    return ""


def available() -> bool:
    return not unavailable_reason()


def _clip(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT else text[: MAX_OUTPUT - 700] + f"\n...[{len(text) - MAX_OUTPUT} chars cut]...\n" + text[-700:]


def _readonly_roots() -> list[str]:
    """Python's own folders, mounted read-only at the same path so the venv's symlinks resolve."""
    roots = {Path(sys.prefix)}
    interpreter_root = Path(os.path.realpath(sys.executable)).parents[2]
    if str(interpreter_root) not in ("/", "/usr") and not str(interpreter_root).startswith("/usr/"):
        roots.add(interpreter_root)
    args: list[str] = []
    for root in sorted(roots):
        args += ["--ro-bind", str(root), str(root)]
    return args


async def run_python(code: str, *, work: Path, raw_html: Path, rendered_html: Path, timeout: int = TIMEOUT_S) -> str:
    reason = unavailable_reason()
    if reason:
        raise ActionError(f"code execution is disabled: {reason}")
    work.mkdir(parents=True, exist_ok=True)
    number = len(list(work.glob("script_*.py"))) + 1
    script = work / f"script_{number:02d}.py"  # kept as evidence, and as a candidate recipe
    script.write_text(PRELUDE + code)
    command = [
        "bwrap", "--unshare-all", "--die-with-parent",
        "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/bin", "/bin",
        "--proc", "/proc", "--dev", "/dev", *_readonly_roots(),
        "--ro-bind", str(raw_html), "/data/page.html", "--ro-bind", str(rendered_html), "/data/rendered.html",
        "--bind", str(work), "/work", "--chdir", "/work", "--clearenv",
        "--setenv", "PATH", "/usr/bin", "--setenv", "HOME", "/work",
        "--setenv", "HTML_PATH", "/data/page.html", "--setenv", "RENDERED_PATH", "/data/rendered.html", "--setenv", "OUT_PATH", "/work/out.json",
        sys.executable, "-I", f"/work/{script.name}",
    ]
    process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return f"[timed out after {timeout}s]"
    output = stdout.decode("utf-8", errors="replace").strip()
    return _clip(output or "(no output)")
