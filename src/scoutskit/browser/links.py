"""Every link on the page, including the ones the accessibility tree does not show (a hover menu, a collapsed panel).

The tree lists only what is visible, so "Academics > Syllabus" in a dropdown is invisible to `find`, and the agent guessed an address
instead. The links are in the page's DOM all the time: this searches them by their words (text, address, the row or list entry around them).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_LINKS = 12
STOP = {"the", "a", "an", "of", "for", "to", "and", "from", "in", "on", "pdf", "download", "file", "page", "site", "website", "get", "find", "all"}

FIND_LINKS_JS = r"""() => {
  const out = [];
  const seen = new Set();
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.href;
    if (!href || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:') || href === location.href + '#') continue;
    const text = (a.innerText || a.textContent || a.getAttribute('aria-label') || a.title || '').replace(/\s+/g, ' ').trim();
    const holder = a.closest('tr, li, dd, p, article, section, div');
    const context = holder ? (holder.innerText || holder.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160) : '';
    const key = href + '|' + text;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ text: text.slice(0, 120), href, context, shown: a.getClientRects().length > 0 });
  }
  return out;
}"""


@dataclass(frozen=True)
class Link:
    text: str
    href: str
    context: str
    shown: bool


def words(query: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in STOP and len(w) > 1]


def rank(links: list[dict], query: str, limit: int = MAX_LINKS) -> list[Link]:
    """The links that match the most words of the query (in the link's text, its address, or what surrounds it), best first."""
    wanted = words(query)
    scored = []
    for item in links:
        text, href, context = item["text"].lower(), item["href"].lower(), item["context"].lower()
        hits = [w for w in wanted if w in text or w in href or w in context]
        if not hits:
            continue
        score = len(hits) * 3 + sum(2 for w in wanted if w in text) + (1 if href.endswith((".pdf", ".xlsx", ".docx", ".csv", ".zip")) else 0) + (1 if item["shown"] else 0)
        scored.append((score, Link(item["text"], item["href"], item["context"], item["shown"])))
    scored.sort(key=lambda pair: -pair[0])
    return [link for _, link in scored[:limit]]


def describe(found: list[Link], query: str) -> str:
    if not found:
        return f"no link on this page matches {query!r}: try other words, or look at the page with read_page"
    lines = []
    for n, link in enumerate(found, 1):
        where = "" if link.shown else "   (hidden in a menu or collapsed section: goto its address, or open the menu)"
        lines.append(f"{n}. {link.text or '(no text)'}\n   {link.href}{where}" + (f"\n   around it: {link.context}" if link.context and link.context != link.text else ""))
    return "\n".join(lines) + "\n(addresses are real: use goto(address) for a page, save_file(address) for a document; never guess an address)"
