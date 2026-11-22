"""Read-only JavaScript for the agent: evaluate an expression in the page and return its value as JSON.

This is a policy check, not a sandbox: page code runs with the page's own privileges. The check refuses
code that talks to the network, navigates, or changes the page, so the tool is for *reading* (computed
styles, a data table's rows, a global variable) while the real actions stay in the audited tools.
"""

from __future__ import annotations

import re

# Order matters: the most specific reason first, because the first match is the one reported.
FORBIDDEN = (
    (r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts|postMessage)\b", "it uses the network or messaging"),
    (r"\bimport\s*\(|\beval\s*\(|new\s+Function\b", "it loads or builds code at run time"),
    (r"\.(click|submit|focus|remove|setAttribute|removeAttribute|appendChild|insertBefore|replaceWith)\s*\(|\bdispatchEvent\b", "it changes or triggers the page"),
    (r"\b(location|window\.location|document\.location)(\.\w+)?\s*=(?!=)|\blocation\.(assign|replace|reload)\b|\bwindow\.open\b", "it navigates"),
    (r"\b(innerHTML|outerHTML|innerText|textContent|value|checked|selected|href|src)\s*=(?!=)", "it assigns to the page"),
    (r"\b(localStorage|sessionStorage)\.(setItem|removeItem|clear)\b|document\.cookie\s*=(?!=)|\bindexedDB\b|document\.write", "it writes browser storage or the document"),
)


def violation(code: str) -> str | None:
    """Why this code is not read-only, or None when it passes the check."""
    for pattern, reason in FORBIDDEN:
        if re.search(pattern, code):
            return reason
    return None
