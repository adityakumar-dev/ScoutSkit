"""Make the page's accessibility tree small enough to read without hiding what the agent may need.

A long table or list repeats the same structure hundreds of times. When the tree is over its
budget, the largest runs of identical sibling items are folded: the first few and the last one
stay, and the middle becomes one summary line saying how many items it hides and which refs they
span. Small runs (pagination links, menus) are only folded if nothing else is left to fold.
read_page(ref) shows any hidden part in full.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

LINE = re.compile(r"^( *)- (.*)$")
REF = re.compile(r"\[ref=([\w-]+)\]")
ROLE = re.compile(r"[\w-]+")
INDENT = "  "
MIN_RUN = 8  # a run shorter than this is never folded
KEEP_HEAD = 3  # items kept at the start of a folded run
KEEP_TAIL = 1  # items kept at its end, so the agent can see where the list stops


@dataclass
class Node:
    text: str  # the line without its indent and leading "- "
    children: list[Node] = field(default_factory=list)
    is_summary: bool = False

    @property
    def role(self) -> str:
        match = ROLE.match(self.text)
        return match.group(0) if match else ""


def parse(tree: str) -> list[Node]:
    roots: list[Node] = []
    stack: list[tuple[int, Node]] = []
    for line in tree.splitlines():
        match = LINE.match(line)
        if not match:  # a wrapped continuation of the previous line
            if stack:
                stack[-1][1].text += " " + line.strip()
            continue
        depth = len(match.group(1)) // len(INDENT)
        node = Node(match.group(2))
        while stack and stack[-1][0] >= depth:
            stack.pop()
        (stack[-1][1].children if stack else roots).append(node)
        stack.append((depth, node))
    return roots


def render(nodes: list[Node], depth: int = 0) -> list[str]:
    lines: list[str] = []
    for node in nodes:
        lines.append(f"{INDENT * depth}- {node.text}")
        lines.extend(render(node.children, depth + 1))
    return lines


def _size(node: Node, depth: int = 0) -> int:
    own = len(INDENT) * depth + 2 + len(node.text) + 1
    return own + sum(_size(child, depth + 1) for child in node.children)


def _shape(node: Node, cache: dict[int, str]) -> str:
    """The structure of a subtree without its names, so rows with different text still compare equal."""
    key = id(node)
    if key not in cache:
        cache[key] = f"{node.role}({','.join(_shape(child, cache) for child in node.children)})"
    return cache[key]


def _sibling_lists(roots: list[Node]) -> Iterator[list[Node]]:
    yield roots
    for node in roots:
        if node.children:
            yield from _sibling_lists(node.children)


def _summary(hidden: list[Node]) -> Node:
    refs = [match.group(1) for node in (hidden[0], hidden[-1]) if (match := REF.search(node.text))]
    span = f" [refs {refs[0]}–{refs[-1]}]" if len(refs) == 2 else ""
    return Node(f"… {len(hidden)} more {hidden[0].role} items like the ones above{span}; read_page(ref) shows a part, and for all of them write code (grep_source, run_python)", is_summary=True)


def _best_fold(roots: list[Node]) -> tuple[list[Node], int, int] | None:
    """The run of identical structured siblings whose folding saves the most: (siblings, start, end)."""
    cache: dict[int, str] = {}
    best: tuple[int, list[Node], int, int] | None = None
    for siblings in _sibling_lists(roots):
        start = 0
        while start < len(siblings):
            end = start + 1
            shape = _shape(siblings[start], cache)
            while end < len(siblings) and _shape(siblings[end], cache) == shape:
                end += 1
            first = siblings[start]
            if end - start >= MIN_RUN and first.children and not first.is_summary:
                hidden = siblings[start + KEEP_HEAD : end - KEEP_TAIL]
                saved = sum(_size(node) for node in hidden) - len(_summary(hidden).text)
                if saved > 0 and (best is None or saved > best[0]):
                    best = (saved, siblings, start, end)
            start = end
    return None if best is None else best[1:]


def fold(tree: str, budget: int) -> str:
    """The tree unchanged if it fits the budget, otherwise with its largest repeated runs folded until it does."""
    if len(tree) <= budget:
        return tree
    roots = parse(tree)
    while sum(_size(node) for node in roots) > budget:
        found = _best_fold(roots)
        if found is None:
            break
        siblings, start, end = found
        siblings[start + KEEP_HEAD : end - KEEP_TAIL] = [_summary(siblings[start + KEEP_HEAD : end - KEEP_TAIL])]
    return "\n".join(render(roots))


INTERACTIVE = re.compile(r"- (button|link|textbox|searchbox|combobox|checkbox|radio|tab|menuitem|option|switch)\b")


def find(tree: str, query: str, limit: int = 15) -> list[str]:
    """Lines of the tree that contain every word of `query`: interactive elements first, then the tightest matches."""
    words = query.lower().split()
    if not words:
        return []
    matches = []
    for number, line in enumerate(tree.splitlines()):
        text = line.strip().lower()
        if all(word in text for word in words):
            matches.append((not INTERACTIVE.match(text), len(text), number, line.strip()))
    return [match[-1] for match in sorted(matches)[:limit]]
