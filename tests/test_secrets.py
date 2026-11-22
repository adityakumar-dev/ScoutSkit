"""Password values never reach the model or the logs, whoever typed them."""

from scoutskit.browser import open_session
from scoutskit.tools import Collector, build_registry

SECRET = "s3cret-pass"


async def typed_page(portal):
    session_cm = open_session(portal + "/password.html")
    session = await session_cm.__aenter__()
    await session.goto(portal + "/password.html")
    await session.page.fill("#user", "alice-visible")
    await session.page.fill("#pass", SECRET)  # typed by anyone: the agent, a person taking over, autofill
    return session_cm, session


async def test_the_tree_the_model_reads_hides_the_password_but_not_ordinary_fields(portal):
    cm, session = await typed_page(portal)
    try:
        tree, _ = await session.snapshot()
        assert SECRET not in tree and "••••" in tree and "alice-visible" in tree
        assert SECRET not in session.last_tree
    finally:
        await cm.__aexit__(None, None, None)


async def test_no_tool_can_hand_the_password_over(portal):
    cm, session = await typed_page(portal)
    try:
        registry = build_registry(session, Collector([], ""))
        for name, args in [("javascript_tool", {"expression": "document.getElementById('pass').value"}),
                           ("javascript_tool", {"expression": "document.getElementById('pass').value.split('').join('')"}),
                           ("read_page", {}), ("find", {"query": "Password"}), ("page_text", {})]:
            text, _ = await registry.call(name, args)
            assert SECRET not in text, f"{name} leaked the password"
        text, _ = await registry.call("javascript_tool", {"expression": "document.getElementById('user').value"})
        assert "alice-visible" in text
    finally:
        await cm.__aexit__(None, None, None)


async def test_the_password_stays_hidden_after_the_page_has_changed(portal):
    cm, session = await typed_page(portal)
    try:
        await session.snapshot()  # sees the value once
        await session.goto(portal + "/index.html")  # the field is gone
        registry = build_registry(session, Collector([], ""))
        text, _ = await registry.call("javascript_tool", {"expression": f"'echoed: {SECRET}'"})
        assert SECRET not in text and "echoed: ••••" in text
    finally:
        await cm.__aexit__(None, None, None)


async def test_short_values_are_not_treated_as_secrets(portal):
    async with open_session(portal + "/password.html") as session:
        await session.goto(portal + "/password.html")
        await session.page.fill("#pass", "ab")
        assert await session.scrub("the ab and abc words") == "the ab and abc words"
