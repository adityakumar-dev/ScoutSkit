"""The real HTML behind an element of the accessibility tree.

The tree names elements by their computed ARIA role (grid, rowgroup, gridcell); the HTML uses table, tr and td.
A model that writes selectors from the tree's names finds nothing, so this shows the actual tag, id, classes,
a CSS selector and what the element contains.
"""

from __future__ import annotations

ELEMENT_INFO_JS = """e => {
  const path = [];
  for (let n = e; n && n.nodeType === 1 && n !== document.documentElement; n = n.parentElement) {
    let part = n.tagName.toLowerCase();
    if (n.id) { path.unshift(part + '#' + n.id); break; }
    part += [...n.classList].slice(0, 2).map(c => '.' + CSS.escape(c)).join('');
    const same = n.parentElement ? [...n.parentElement.children].filter(c => c.tagName === n.tagName) : [];
    if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(n) + 1) + ')';
    path.unshift(part);
  }
  const count = selector => e.querySelectorAll(selector).length;
  return {
    tag: e.tagName.toLowerCase(), id: e.id || '', classes: [...e.classList], role: e.getAttribute('role') || '',
    selector: path.join(' > '), children: e.children.length,
    inside: {tr: count('tr'), td: count('td'), li: count('li'), a: count('a'), input: count('input'), button: count('button')},
    html: e.outerHTML.slice(0, 400),
  };
}"""


def describe(info: dict) -> str:
    opening = f"<{info['tag']}" + (f' id="{info["id"]}"' if info["id"] else "") + (f' class="{" ".join(info["classes"])}"' if info["classes"] else "") + ">"
    role = f'role="{info["role"]}" is written in the HTML' if info["role"] else "no role attribute in the HTML (the tree's role name is computed by the browser, not a tag or attribute)"
    inside = ", ".join(f"{count} <{tag}>" for tag, count in info["inside"].items() if count) or "no table rows, list items, links or inputs"
    return f"{opening}\nCSS selector: {info['selector']}\n{role}\ndirect children: {info['children']}; inside it: {inside}\nstarts with: {info['html']}"
