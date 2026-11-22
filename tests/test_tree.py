from scoutskit.browser import tree
from scoutskit.browser.tree import fold, parse, render


def table(rows: int, cells: int = 3) -> str:
    lines = ["- table [ref=e1]:", "  - rowgroup [ref=e2]:"]
    for i in range(rows):
        base = 10 + i * (cells + 1)
        lines.append(f"    - row [ref=e{base}]:")
        lines += [f'      - cell "R{i:03d} value {c}" [ref=e{base + 1 + c}]' for c in range(cells)]
    return "\n".join(lines)


PAGE = (
    '- generic [ref=e0]:\n  - heading "Records" [level=1] [ref=e3]\n  - button "Show entries" [ref=e4]\n'
    + "\n".join("  " + line for line in table(300).splitlines())
    + '\n  - navigation "Pages" [ref=e5]:\n    - list [ref=e6]:\n'
    + "\n".join(f'      - listitem [ref=e{900 + n}]:\n        - link "{n}" [ref=e{950 + n}]' for n in range(1, 12))
    + '\n  - button "Next" [ref=e999]'
)


def test_a_tree_within_budget_is_returned_unchanged():
    assert fold(table(5), budget=10_000) == table(5)


def test_parse_and_render_round_trip():
    assert "\n".join(render(parse(PAGE))) == PAGE


def test_a_long_table_is_folded_to_the_budget_and_keeps_head_tail_and_controls():
    folded = fold(PAGE, budget=4_000)
    assert len(folded) <= 4_000 and len(folded) < len(PAGE) * 0.2  # >80% smaller
    assert "R000 value 0" in folded and "R002 value 0" in folded  # the first three rows
    assert "R299 value 0" in folded  # the last row stays, so the end of the list is visible
    assert "R150 value 0" not in folded
    assert "… 296 more row items like the ones above [refs e" in folded and "read_page(ref)" in folded
    assert 'button "Next"' in folded and 'button "Show entries"' in folded and 'heading "Records"' in folded


def test_pagination_links_survive_while_the_big_table_absorbs_the_folding():
    folded = fold(PAGE, budget=6_000)
    assert all(f'link "{n}"' in folded for n in range(1, 12))


def test_folding_is_repeatable_on_its_own_output():
    once = fold(PAGE, budget=4_000)
    assert fold(once, budget=4_000) == once


def test_short_runs_are_never_folded():
    short = table(tree.MIN_RUN - 1)
    assert fold(short, budget=10) == short  # impossible budget, but nothing is long enough to fold
