"""Find the list of repeated items on a page, whatever it is built from: table rows, cards, list entries.

The accessibility tree names roles and refs, not the HTML a script has to select. So the agent guessed ("table id e40" was a ref).
This looks at the live DOM for sibling elements that look alike (same tag and nearly the same classes: a card whose colour class
changes with its difficulty is still the same kind of card), chooses the list that holds the page's content, builds a CSS selector
that matches exactly those items, counts them in the raw source too, and maps what one item contains.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

MIN_ITEMS = 5  # fewer repeats are not a list worth announcing
SAMPLE_HTML_CHARS = 1_600
MAX_FIELDS = 30

# Runs in the page. Clusters the children of each element by tag and class similarity (Jaccard >= 0.7), scores each cluster by how many
# items it has and how much text each carries (chips and menu entries repeat a lot but say little), and describes the best one.
FIND_JS = r"""(minItems) => {
  const SAFE = /^[A-Za-z0-9_-]+$/;
  const classes = e => [...e.classList];
  const jaccard = (a, b) => { const A = new Set(a), B = new Set(b); let i = 0; for (const x of A) if (B.has(x)) i++; const u = A.size + B.size - i; return u ? i / u : 1; };
  const text = e => (e.innerText || e.textContent || '').trim();
  // A page's navigation, header, footer and sidebars repeat links, and hidden menus repeat them again: that is not the page's content.
  const CHROME = 'nav, header, footer, aside, [role="navigation"], [role="menu"], [role="menubar"], [role="banner"], [role="contentinfo"]';
  const shown = e => e.getClientRects().length > 0;
  let best = null;
  for (const parent of document.querySelectorAll('body, body *')) {
    if (parent.closest(CHROME) || !shown(parent)) continue;
    const kids = [...parent.children].filter(k => !['SCRIPT', 'STYLE', 'OPTION', 'BR', 'HR', 'SVG', 'PATH', 'LINK', 'META', 'TH', 'TD'].includes(k.tagName.toUpperCase()) && shown(k));
    if (kids.length < minItems) continue;
    const clusters = [];
    for (const kid of kids) {
      const home = clusters.find(c => c.tag === kid.tagName && c.slot === (kid.getAttribute('data-slot') || '') && jaccard(c.classes, classes(kid)) >= 0.7);
      if (home) home.items.push(kid); else clusters.push({ tag: kid.tagName, slot: kid.getAttribute('data-slot') || '', classes: classes(kid), items: [kid] });
    }
    // clusters of the same kind that only differ by a colour or state class are one list
    const merged = [];
    for (const c of clusters) {
      const same = merged.find(m => m.tag === c.tag && m.slot === c.slot && jaccard(m.classes, c.classes) >= 0.5);
      if (same) same.items.push(...c.items); else merged.push({ ...c });
    }
    for (const c of merged) {
      if (c.items.length < minItems) continue;
      const lengths = c.items.map(i => text(i).length);
      const avg = lengths.reduce((a, b) => a + b, 0) / lengths.length;
      if (avg < 12) continue;
      const score = c.items.length * Math.min(avg, 240);
      if (!best || score > best.score) best = { score, parent, tag: c.tag, slot: c.slot, items: c.items };
    }
  }
  if (!best) return null;
  const items = best.items;
  const common = classes(items[0]).filter(k => SAFE.test(k) && items.every(i => i.classList.contains(k)));
  const attr = best.slot ? `[data-slot="${best.slot}"]` : '';
  const base = best.tag.toLowerCase() + attr + common.map(k => '.' + k).join('');
  const pathOf = el => {
    if (el.id && SAFE.test(el.id)) return '#' + el.id;
    const own = el.tagName.toLowerCase() + [...el.classList].filter(k => SAFE.test(k)).slice(0, 2).map(k => '.' + k).join('');
    return own;
  };
  const head = best.tag.toLowerCase() + attr;
  const candidates = [head, head + common.slice(0, 2).map(k => '.' + k).join(''), head + common.slice(0, 4).map(k => '.' + k).join(''), base, pathOf(best.parent) + ' > ' + base];
  let selector = candidates.find(s => { try { return document.querySelectorAll(s).length === items.length; } catch (e) { return false; } });
  if (!selector) selector = candidates.find(s => { try { return document.querySelectorAll(s).length >= items.length; } catch (e) { return false; } }) || base;
  // what one item contains: each element that holds text of its own, with a short path, so the script can select the field
  const fields = [];
  const walk = (el, depth) => {
    if (fields.length >= 40 || depth > 6) return;
    const own = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).filter(Boolean).join(' ');
    if (own) {
      const slot = el.getAttribute && el.getAttribute('data-slot');
      const cls = [...el.classList].filter(k => SAFE.test(k)).slice(0, 2).map(k => '.' + k).join('');
      fields.push([el.tagName.toLowerCase() + (slot ? `[data-slot="${slot}"]` : '') + cls, own.slice(0, 90)]);
    }
    for (const c of el.children) walk(c, depth + 1);
  };
  const first = items[0];
  walk(first, 0);
  return { selector, count: items.length, tag: best.tag.toLowerCase(), html: first.outerHTML.slice(0, 20000), text: text(first).slice(0, 200), fields, second: text(items[1] || first).slice(0, 200) };
}"""


@dataclass(frozen=True)
class Repeats:
    selector: str
    live: int  # matching items in the live page
    raw: int  # matching items in the raw source the server sent (-1: the selector does not work on it)
    tag: str
    text: str  # the text of the first item
    sample_html: str
    fields: list[tuple[str, str]] = field(default_factory=list)  # (element, text) for the first item

    def sentence(self) -> str:
        if self.raw < 0:
            where = "check the raw source with the same selector"
        elif self.raw == 0:
            where = "none are in the raw source (the page draws them with script): read RENDERED_PATH, or look for the data request with network_log"
        elif self.raw < self.live:
            where = f"only {self.raw} are in the raw source (HTML_PATH): use RENDERED_PATH for all of them"
        else:
            where = f"all {self.raw} are also in the raw source (HTML_PATH)"
        return f"THE PAGE REPEATS ONE ELEMENT {self.live} TIMES (CSS selector {self.selector!r}); {where}. Call find_items to see what one item contains"

    def describe(self) -> str:
        lines = [f"{self.live} items on the live page match the CSS selector  {self.selector}",
                 f"{self.raw} match it in the raw source (HTML_PATH) when parsed with BeautifulSoup .select()" if self.raw >= 0
                 else "that selector could not be applied to the raw source: check it with grep_source or use RENDERED_PATH",
                 "", "First item's text:", f"  {self.text}", "", "Elements of the first item that hold text (use these to select each field inside one item):"]
        lines += [f"  {path:60.60}  {value!r}" for path, value in self.fields[:MAX_FIELDS]]
        lines += ["", f"First item's HTML (cut at {SAMPLE_HTML_CHARS} characters):", self.sample_html[:SAMPLE_HTML_CHARS]]
        lines += ["", "Write ONE script: for item in BeautifulSoup(HTML, 'lxml').select(<selector>): build one dict per item from the elements above; "
                      "check len(rows) against the count; save with json.dump(rows, open(OUT_PATH, 'w')); then call use_script_output."]
        return "\n".join(lines)


def raw_count(raw_html: str, selector: str) -> int:
    try:
        return len(BeautifulSoup(raw_html, "lxml").select(selector))
    except Exception:  # a selector the parser cannot take (unusual characters): reported as unknown
        return -1


async def locate(page) -> dict | None:
    """The page's main list of repeated items as the page's own script describes it, or None when there is no list of at least MIN_ITEMS."""
    return await page.evaluate(FIND_JS, MIN_ITEMS)


def build(found: dict, raw: int) -> Repeats:
    return Repeats(found["selector"], found["count"], raw, found["tag"], found["text"], found["html"], [(p, v) for p, v in found["fields"]])
