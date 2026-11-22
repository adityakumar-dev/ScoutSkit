import functools
import http.server
import threading
from pathlib import Path

import pytest

PORTAL = Path(__file__).resolve().parent.parent / "benchmarks" / "portal"


@pytest.fixture(scope="session")
def portal() -> str:
    """The local benchmark portal served on a free port; returns its base URL."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(PORTAL))
    handler.func.log_message = lambda *args, **kwargs: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
