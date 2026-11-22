"""`done` is judged by evidence from the page itself, not by the model's say-so."""

from test_agent_loop import table_rows
from test_code_tools import Navigator, run


async def test_done_is_refused_once_with_the_evidence_then_a_subset_reason_is_accepted_with_a_warning(portal, tmp_path):
    seen, state = [], {"extracted": False, "done_calls": 0}

    async def subset_asker(turn, page):
        seen.append(page)
        if not state["extracted"]:
            state["extracted"] = True
            return {"tool": "extract_rows", "args": {"rows": table_rows(page.split("TREE:\n", 1)[1])}}  # the 10 rows on screen
        state["done_calls"] += 1
        return {"tool": "done", "args": {"reason": "the task only asked for the first group"}}

    result, recorder = await run(portal, tmp_path, subset_asker, min_items=5)
    assert state["done_calls"] == 2  # refused once, then accepted
    assert result.status == "completed" and len(result.rows) == 10
    assert "WARNING" in result.message and "only asked for the first group" in result.message
    assert any("HOLDS 60 ROWS IN TABLE#ITEMS" in page for page in seen)  # the census is shown to the model every turn
    import json

    log = [json.loads(line) for line in (recorder.dir / "actions.jsonl").read_text().splitlines()]
    first_done = next(e for e in log if e.get("tool") == "done")
    assert not first_done["ok"] and "you have collected 10" in first_done["error"]


async def test_done_without_a_reason_is_always_refused_while_the_evidence_stands(portal, tmp_path):
    state = {"extracted": False, "done_calls": 0}

    async def impatient(turn, page):
        if not state["extracted"]:
            state["extracted"] = True
            return {"tool": "extract_rows", "args": {"rows": table_rows(page.split("TREE:\n", 1)[1])}}
        state["done_calls"] += 1
        return {"tool": "done", "args": {}} if state["done_calls"] < 6 else {"tool": "fail", "args": {"reason": "stop"}}

    result, _ = await run(portal, tmp_path, impatient, min_items=5)
    assert result.status == "incomplete" and len(result.rows) == 10  # three refusals end the run; nothing was waved through
