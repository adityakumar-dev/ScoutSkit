"""The input pump: floods are merged, slow actions run aside, order is kept, refusals reach the person."""

import asyncio

from scoutskit.server.input_pump import InputPump


async def pumped(messages, apply, settle=0.3):
    refused = []

    async def refuse(reason):
        refused.append(reason)

    pump = InputPump(apply, refuse)
    runner = asyncio.create_task(pump.run())
    for message in messages:
        pump.put(message)
    await asyncio.sleep(settle)
    runner.cancel()
    return refused


async def test_a_flood_of_scroll_events_becomes_one_scroll_and_a_click_is_not_held_up():
    applied = []

    async def apply(message):
        applied.append(message)
        await asyncio.sleep(0.04)  # what one scroll costs the browser

    flood = [{"kind": "scroll", "x": 0.5, "y": 0.5 + i / 1000, "dy": 100} for i in range(60)]
    await pumped([*flood, {"kind": "click", "x": 0.2, "y": 0.3}], apply, settle=0.25)  # sequentially these would take 2.4 s
    assert [m["kind"] for m in applied] == ["scroll", "click"]
    assert applied[0]["dy"] == 5000  # 60 x 100, merged and capped
    assert applied[0]["y"] == 0.5 + 59 / 1000  # the pointer is where the last event left it


async def test_hovers_merge_but_clicks_and_keys_keep_their_order():
    applied = []

    async def apply(message):
        applied.append((message["kind"], message.get("x", message.get("key"))))

    await pumped([{"kind": "move", "x": 0.1, "y": 0}, {"kind": "move", "x": 0.2, "y": 0}, {"kind": "click", "x": 0.3, "y": 0},
                  {"kind": "key", "key": "Enter"}, {"kind": "click", "x": 0.4, "y": 0}], apply)
    assert applied == [("move", 0.2), ("click", 0.3), ("key", "Enter"), ("click", 0.4)]


async def test_a_slow_navigation_does_not_hold_up_clicks_and_navigations_stay_in_order():
    events = []

    async def apply(message):
        events.append(("start", message["kind"], message.get("url")))
        if message["kind"] == "navigate":
            await asyncio.sleep(0.3)
        events.append(("end", message["kind"], message.get("url")))

    await pumped([{"kind": "navigate", "url": "a"}, {"kind": "click", "x": 0, "y": 0}, {"kind": "navigate", "url": "b"}], apply, settle=0.9)
    assert events.index(("end", "click", None)) < events.index(("end", "navigate", "a"))  # the click did not wait for the page to load
    assert events.index(("end", "navigate", "a")) < events.index(("start", "navigate", "b"))  # but navigations are not overlapped


async def test_a_refusal_is_reported_and_the_pump_carries_on():
    applied = []

    async def apply(message):
        if message.get("bad"):
            return "that input is not allowed"
        applied.append(message["kind"])

    refused = await pumped([{"kind": "click", "bad": True}, {"kind": "click"}], apply)
    assert refused == ["that input is not allowed"] and applied == ["click"]


async def test_the_backlog_is_bounded_by_dropping_old_scrolls_only():
    from scoutskit.server import input_pump

    pump = InputPump(lambda m: asyncio.sleep(0), lambda r: asyncio.sleep(0))
    pump.put({"kind": "click", "x": 0, "y": 0})
    for i in range(input_pump.MAX_PENDING + 50):
        pump.put({"kind": "scroll", "x": 0, "y": 0, "dy": 1})
    assert len(pump._pending) <= input_pump.MAX_PENDING + 1 and pump._pending[0]["kind"] == "click"
