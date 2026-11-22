import pytest

from scoutskit import sandbox

pytestmark = pytest.mark.skipif(not sandbox.available(), reason="bubblewrap is not installed")


@pytest.fixture
def files(tmp_path):
    raw, rendered = tmp_path / "raw.html", tmp_path / "rendered.html"
    raw.write_text("<html><body><p id='a'>hello</p></body></html>")
    rendered.write_text("<p>rendered</p>")
    return dict(work=tmp_path / "work", raw_html=raw, rendered_html=rendered)


async def test_code_can_parse_the_page_and_keep_output(files):
    out = await sandbox.run_python(
        "from bs4 import BeautifulSoup\nimport json\nsoup = BeautifulSoup(open(HTML_PATH).read(), 'lxml')\n"
        "json.dump([{'text': soup.p.text}], open(OUT_PATH, 'w'))\nprint('ok', soup.p.text)", **files)
    assert out == "ok hello"
    assert '"hello"' in (files["work"] / "out.json").read_text()
    assert (files["work"] / "script_01.py").exists()  # scripts are kept as evidence


async def test_no_network_no_secrets_no_project_files(files):
    out = await sandbox.run_python(
        "import os, socket\ntry:\n    socket.create_connection(('1.1.1.1', 53), 2); print('NETWORK REACHABLE')\nexcept OSError: print('network blocked')\n"
        "print('keys:', [k for k in os.environ if 'KEY' in k or 'TOKEN' in k])\n"
        "print('env file visible:', os.path.exists('/home/linmar/Documents/scoutskit/.env'), '| etc/passwd:', os.path.exists('/etc/passwd'))\n"
        "try:\n    open(HTML_PATH, 'w')\nexcept OSError: print('page is read-only')", **files)
    assert "network blocked" in out and "keys: []" in out and "env file visible: False" in out and "page is read-only" in out


async def test_errors_and_timeouts_come_back_as_text(files):
    assert "ZeroDivisionError" in await sandbox.run_python("1/0", **files)
    assert "timed out" in await sandbox.run_python("while True: pass", timeout=2, **files)
