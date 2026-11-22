# ScoutsKit (*Invisible Failure*) — Deep Technical Exploration & Architecture Blueprint

> **Project:** *Invisible Failure: An Autonomous Web Task Execution and Evaluation Platform for Real-World Functional, Usability and Accessibility Testing*  
> **Product:** **ScoutsKit** (B.Tech Final Year, UTU Dehradun, 2026–2027)  
> **Document Purpose:** Comprehensive state-of-the-art research (Claude in Chrome, Stagehand, Browser-Use, Playwright Stealth), codebase diagnostic audit, anti-bot stealth architecture, resilient element/event choosing engine, and full target system structure.

---

## Table of Contents
1. [Executive Summary & Vision](#1-executive-summary--vision)
2. [State-of-the-Art Research: How Modern In-Browser Agents Work](#2-state-of-the-art-research-how-modern-in-browser-agents-work)
   - 2.1 [Anthropic Claude in Chrome & Claude Computer Use](#21-anthropic-claude-in-chrome--claude-computer-use)
   - 2.2 [Browser-Use (Open-Source Architecture)](#22-browser-use-open-source-architecture)
   - 2.3 [Stagehand (Browserbase) & Self-Healing Locators](#23-stagehand-browserbase--self-healing-locators)
   - 2.4 [OpenAI Operator / CUA / WebVoyager (Visual vs. Semantic Tradeoffs)](#24-openai-operator--cua--webvoyager-visual-vs-semantic-tradeoffs)
   - 2.5 [Comparative Feature Matrix](#25-comparative-feature-matrix)
3. [Anti-Bot Proof System: Stealth, Fingerprinting & Humanization](#3-anti-bot-proof-system-stealth-fingerprinting--humanization)
   - 3.1 [What Anti-Bot Firewalls Detect (Cloudflare, Datadome, Akamai)](#31-what-anti-bot-firewalls-detect-cloudflare-datadome-akamai)
   - 3.2 [Browser & CDP Flag Masking](#32-browser--cdp-flag-masking)
   - 3.3 [Humanized Input Synthesis (Bezier Mouse & Gaussian Keypresses)](#33-humanized-input-synthesis-bezier-mouse--gaussian-keypresses)
   - 3.4 [TLS Fingerprint & Session Continuity](#34-tls-fingerprint--session-continuity)
   - 3.5 [Academic & Safety Guardrail Boundary](#35-academic--safety-guardrail-boundary)
4. [The Event & Element Choosing System](#4-the-event--element-choosing-system)
   - 4.1 [The Event Choosing Hierarchy (Interaction Dispatcher)](#41-the-event-choosing-hierarchy-interaction-dispatcher)
   - 4.2 [The Element Choosing Engine (Multi-Attribute Fingerprinting)](#42-the-element-choosing-engine-multi-attribute-fingerprinting)
   - 4.3 [Self-Healing Locator Resolution (4-Tier Fallback Cascade)](#43-self-healing-locator-resolution-4-tier-fallback-cascade)
   - 4.4 [Grounding & Output Verification](#44-grounding--output-verification)
5. [Codebase Diagnostic Audit: What is Fragile in ScoutsKit Right Now](#5-codebase-diagnostic-audit-what-is-fragile-in-scoutskit-right-now)
   - 5.1 [Sandbox `bwrap` Namespace Crash in Virtualized/Container Hosts](#51-sandbox-bwrap-namespace-crash-in-virtualizedcontainer-hosts)
   - 5.2 [Ephemeral `[ref=eN]` Locators & Replay Impossibility](#52-ephemeral-refe-locators--replay-impossibility)
   - 5.3 [Single-Tab Lockout (`target="_blank"` Blindness)](#53-single-tab-lockout-target_blank-blindness)
   - 5.4 [Context Token Explosion (`MAX_TREE_CHARS = 45_000`)](#54-context-token-explosion-max_tree_chars--45_000)
   - 5.5 [Unscoped Blind Scrolling](#55-unscoped-blind-scrolling)
   - 5.6 [The `min_items` Deadlock Trap](#56-the-min_items-deadlock-trap)
   - 5.7 [Missing Mode 2 Evaluator Infrastructure](#57-missing-mode-2-evaluator-infrastructure)
6. [Target System Architecture & Module Structure](#6-target-system-architecture--module-structure)
   - 6.1 [Clean Repository Layout](#61-clean-repository-layout)
   - 6.2 [Detailed Module Responsibilities](#62-detailed-module-responsibilities)
   - 6.3 [Expanded Toolset Registry (22 Tools)](#63-expanded-toolset-registry-22-tools)
   - 6.4 [Recipe Schema for Deterministic Mode 2 Replay](#64-recipe-schema-for-deterministic-mode-2-replay)
7. [Step-by-Step Implementation Roadmap](#7-step-by-step-implementation-roadmap)

---

## 1. Executive Summary & Vision

The core thesis of **Invisible Failure** is founded on a critical observation:
> *Websites tested under ideal developer setups (high-speed broadband, high-end workstations, English interfaces) consistently pass automated CI/CD checks, yet invisibly fail for real-world citizens operating on low-end devices, congested mobile networks (2G/3G/4G), regional languages (Devanagari/Hindi), or assistive technologies.*

To prove and solve this, ScoutsKit operates across two coupled modes:
1. **Mode 1 (Autonomous Task Execution):** Explores websites with zero prior knowledge to execute complex natural-language tasks (e.g. finding hackathon problems, paginating portals, discovering hidden forms, extracting data with 100% precision via sandboxed code generation).
2. **Mode 2 (Automated Evaluation & Recipe Replay):** Compiles an explored trajectory into a **deterministic, locator-stable Recipe**, then replays it in parallel across multiple simulated environment profiles (network throttling, CPU slowdown, small viewports, screen-reader passes, WCAG contrast audits) to identify exact failure triggers.

To build an AI browser agent that survives in the wild, the system must integrate:
- **A reliable perception layer** that doesn't waste 12,000 tokens on boilerplate HTML.
- **An anti-bot stealth stack** that avoids being blocked by Cloudflare, Datadome, or Akamai.
- **An intelligent event and element choosing system** capable of handling dynamic single-page applications (SPAs), flyout menus, and DOM changes.
- **A self-healing replay engine** that decouples brittle model generation from test execution.

---

## 2. State-of-the-Art Research: How Modern In-Browser Agents Work

### 2.1 Anthropic Claude in Chrome & Claude Computer Use

Anthropic's official browser extension (`Claude in Chrome`, v1.0.56+) bridges generative AI with browser automation directly inside the user's live browser.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         Google Chrome (User Session)                         │
│                                                                              │
│  ┌─────────────────────────┐             ┌────────────────────────────────┐  │
│  │   Side Panel (React UI) │             │    Active Webpage Tab          │  │
│  │  - Anthropic SDK        │             │   - Logged-in state            │  │
│  │  - Streaming turn loop  │             │   - Real user cookies / storage│  │
│  └────────────┬────────────┘             └────────────────▲───────────────┘  │
│               │                                           │                  │
│               ▼                                           │                  │
│  ┌────────────────────────────────────────────────────────┴───────────────┐  │
│  │   Background Service Worker (chrome.debugger / CDP Bridge)             │  │
│  │  - chrome.debugger.attach(tabId, "1.3")                                │  │
│  │  - Input.dispatchMouseEvent (hardware-level clicks, moves, hovers)     │  │
│  │  - Input.insertText / Input.dispatchKeyEvent (OS-level typing)         │  │
│  │  - Accessibility.getFullAXTree (compact, semantic node graph)          │  │
│  │  - Runtime.evaluate (javascript_tool execution in page context)        │  │
│  │  - Network.enable / Log.enable (live telemetry interception)          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Key Architecture Principles:
1. **Low-Level CDP Event Dispatching over DOM Injections:**  
   Standard `element.click()` or synthetic JavaScript events set `event.isTrusted = false`. Modern web frameworks and security systems (Cloudflare, reCAPTCHA, Datadome) immediately detect and ignore untrusted events.  
   Claude attaches to the tab via `chrome.debugger.attach(tabId, "1.3")` and uses CDP's `Input` domain:
   - `Input.dispatchMouseEvent` with `type="mousePressed"` followed by `mouseReleased`.
   - `Input.insertText` or `Input.dispatchKeyEvent` to send raw scancodes and characters.
   - This dispatches authentic, hardware-level events that trigger browser rendering pipelines, CSS `:hover` states, and native form validation.
2. **Accessibility Tree (AXTree) as the Semantic Ground Truth:**  
   Instead of parsing massive DOM HTML or relying on expensive multimodal screenshot processing for every basic action, Claude reads the browser's accessibility tree via tools like `read_page`.  
   - Strips non-semantic layout divs, CSS stylesheets, inline SVGs, and hidden scripts.
   - Preserves semantic roles (`button`, `link`, `combobox`), accessible names, states (`aria-expanded="true"`, `aria-disabled`), and values.
   - Tags interactive nodes with reference identifiers (`ref=e12`).
3. **In-Page JavaScript Execution (`javascript_tool`):**  
   Exposes a native JavaScript execution tool via CDP `Runtime.evaluate`. When standard accessibility trees are insufficient (e.g. querying a complex data table, reading `window.__INITIAL_STATE__`, or checking computed styles), Claude executes a short JS expression directly in the page context.
4. **Multi-Tab Awareness:**  
   Maintains tab lifecycle through `chrome.tabs`. Exposes `new_tab`, `switch_tab`, `close_tab`, and `list_tabs` so multi-window workflows (e.g., clicking a link with `target="_blank"`) never lose tracking.
5. **Tiered Permission Model:**  
   - **Read-only tools** (`read_page`, `find`, `get_page_text`, `read_network_requests`) execute automatically with zero prompts.
   - **State-changing actions** (`click`, `fill`, `navigate`, `javascript_tool`) can run in manual confirmation mode or auto-approve mode based on user trust.

---

### 2.2 Browser-Use (Open-Source Architecture)

`browser-use` is an open-source Python framework designed to let AI agents control Playwright browsers using LLMs.

#### Core Mechanics:
1. **DOM Tree Pre-Processing & Indexing:**
   - Injects a small JavaScript script (`buildDomTree.js`) into the browser context.
   - Filters out invisible elements (`display: none`, `visibility: hidden`, `opacity: 0`, off-screen bounding boxes).
   - Generates a numbered interactive element map:
     ```
     [12] <button id="submit-btn">Submit</button>
     [13] <input type="text" placeholder="Search...">
     ```
   - Matches element numbers directly to Playwright locator handles.
2. **Vision-Augmented Fallback (Set-of-Marks - SoM):**
   - In complex visual layouts (canvases, charts, SVG maps), `browser-use` can take a screenshot, overlay bounding-box labels matching the element numbers, and send both the text tree and annotated image to a vision model (GPT-4o / Claude 3.5 Sonnet).
3. **Execution REPL:**
   - Instead of restricting the LLM to one tool call per turn, `browser-use` can batch actions (e.g., `fill([13], "term")` then `click([12])`) or run lightweight Python automation scripts that interact with Playwright handles directly.

---

### 2.3 Stagehand (Browserbase) & Self-Healing Locators

Stagehand is built around 3 high-level primitives:
- `stagehand.act("Click the search button")`
- `stagehand.observe("Find all navigation links")`
- `stagehand.extract({ schema: ProblemStatementSchema })`

#### The Self-Healing Locator Engine:
When an element is first observed or clicked:
1. Stagehand records multiple attributes of the element:
   - ARIA role and accessible name.
   - Text content and surrounding text context.
   - Optimized CSS path (e.g., `div.nav-container > ul > li:nth-child(2) > a`).
   - Structural XPath (e.g., `//button[contains(text(), 'Search')]`).
   - Bounding box coordinates and parent container hierarchy.
2. **Replay & Self-Healing:**  
   When replaying an action or when the DOM mutates, Stagehand tries the locators in priority order. If a class name or ID changes (e.g., from `.btn-blue` to `.btn-primary`), the semantic role + text match resolves the correct element **without calling an LLM**, self-healing the test script.

---

### 2.4 OpenAI Operator / CUA / WebVoyager (Visual vs. Semantic Tradeoffs)

| Dimension | Pure Visual / Coordinate (CUA / Operator) | Pure Semantic / AXTree (ScoutsKit / Claude) | Hybrid (Recommended Target) |
|---|---|---|---|
| **Perception Input** | Full page screenshots (PNG/JPEG) | Compact accessibility tree text | Compact AXTree + On-demand Vision `look()` |
| **Element Targeting** | Pixel coordinates `(x, y)` | Semantic references `[ref=eN]` | Semantic locators + coordinate fallback |
| **Token Cost** | Very High (1,000–2,500 tokens / image) | Low (800–2,500 tokens / tree) | Low baseline; vision used only on visual blockers |
| **Latency** | High (2–5 seconds / vision call) | Low (300ms–1.2s / text call) | Sub-second standard turns |
| **Canvas / SVG Support** | Perfect | Poor | Perfect (delegates to Vision/Coordinates) |
| **Resolution Drift** | Fragile across viewports | Immune to resolution changes | Highly resilient |

---

### 2.5 Comparative Feature Matrix

| Feature | Claude in Chrome | Stagehand | Browser-Use | ScoutsKit (Current) | ScoutsKit (Target) |
|---|---|---|---|---|---|
| **Protocol** | Chrome Extension CDP | Playwright / CDP | Playwright | Playwright | Playwright + CDP Hooks |
| **Tree Representation** | AXTree + Refs | Cleaned DOM + XPath | Filtered DOM + Indices | AXTree (`[ref=eN]`) | Token-Pruned AXTree + Fingerprint |
| **In-Page JS Execution** | ✅ `javascript_tool` | ❌ None | ⚠️ Partial | ❌ Only offline bwrap | ✅ `javascript_tool` (page.evaluate) |
| **Hover / Mouse Move** | ✅ Native CDP | ✅ Native | ✅ Native | ❌ Click only | ✅ Native CDP Hover & Move |
| **Multi-Tab Routing** | ✅ Full support | ❌ Single Page | ⚠️ Partial | ❌ Crashes / ignores | ✅ Automatic Tab Manager |
| **Anti-Bot Stealth** | Inherits User Profile | Browserbase Cloud | Basic | Bare Chromium | Custom Stealth + Masking |
| **Recipe Compilation** | ❌ None | ✅ Self-healing cache| ❌ None | ❌ Ephemeral only | ✅ Deterministic Replay Recipes |
| **Accessibility Audit** | DevTools MCP | ❌ None | ❌ None | ❌ Not implemented | ✅ Integrated axe-core & WCAG |

---

## 3. Anti-Bot Proof System: Stealth, Fingerprinting & Humanization

Modern websites (especially government portals, university results systems, and cloud-hosted platforms) deploy Web Application Firewalls (Cloudflare Turnstile/Bot Management, Datadome, Akamai Bot Manager, AWS WAF, PerimeterX/HUMAN).  

To prevent benign academic evaluation workflows from being flagged, ScoutsKit requires a resilient stealth architecture.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ScoutsKit Anti-Bot Defense Layers                     │
│                                                                             │
│  [Layer 1: Network & TLS]                                                   │
│   ├── Real Chrome TLS Fingerprint (HTTP/2 frames, cipher suites)            │
│   └── Consistent User-Agent + Client Hints (sec-ch-ua)                      │
│                                                                             │
│  [Layer 2: Browser Binary & CDP Masking]                                    │
│   ├── channel="chrome" (Real installed browser, not bare Chromium)          │
│   ├── --disable-blink-features=AutomationControlled                         │
│   ├── navigator.webdriver = undefined override                             │
│   └── Masked Runtime.enable / CDP internal leak prevention                 │
│                                                                             │
│  [Layer 3: Humanized Input Synthesis]                                       │
│   ├── Mouse: Cubic Bezier curves + Fitts's Law trajectories                 │
│   ├── Typing: Variable Gaussian delays (50ms–140ms per keystroke)           │
│   └── Scrolling: Smooth scroll physics with inertia and viewport settle     │
│                                                                             │
│  [Layer 4: Persistent Session Continuity]                                   │
│   └── Persistent browser context (retains local cache, fonts, cookies)      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 What Anti-Bot Firewalls Detect

1. **`navigator.webdriver === true`:**  
   Standard automated Playwright/Puppeteer sets this flag in the JavaScript runtime. Any firewall checks `navigator.webdriver` on script initialization.
2. **CDP Automation Artifacts:**  
   Standard CDP calls inject `window.cdc_adoQpoasnfa76pfcZLmcfl_Array` or leak symbols when `Runtime.enable` is evaluated.
3. **Headless Chrome Signature Mismatches:**  
   - `navigator.plugins.length === 0` (Real desktop Chrome has default PDF/Widevine plugins).
   - `navigator.languages` empty or mismatched with system locale.
   - WebGL renderer strings reporting `Google SwiftShader` or `Mesa Offscreen` instead of real GPU drivers (e.g. `NVIDIA GeForce RTX 3050 / ANGLE`).
   - Broken window dimensions: `window.outerWidth === 0` or `window.screen.availHeight !== window.innerHeight + taskbar`.
4. **Behavioral Inhumanity:**  
   - Instantaneous mouse teleportation (clicking coordinates `(400, 800)` from `(0, 0)` in 0 milliseconds).
   - Clicks executed without a preceding `hover` or `mouseenter` event.
   - Keystrokes inserted with 0ms delta between characters.
   - Non-human scrolling (instantaneous `window.scrollTo(0, 5000)` without triggering smooth scroll events).

---

### 3.2 Browser & CDP Flag Masking

To eliminate automated signatures in Playwright, ScoutsKit must launch browsers with targeted engine flags and initialization scripts.

#### A. Launch Configuration:
```python
# scoutskit/browser/stealth.py
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-background-networking",
    "--disable-features=IsolateOrigins,site-per-process",
    "--window-size=1920,1080",
]

async def launch_stealth_browser(playwright, headless: bool = True, user_data_dir: Path | None = None):
    # Launch installed Google Chrome if available, falling back to bundled chromium
    launch_kwargs = {
        "args": STEALTH_ARGS,
        "headless": headless,
        "channel": "chrome",  # Uses genuine Google Chrome binary with real codecs and TLS
    }
    
    if user_data_dir:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            **launch_kwargs,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="Asia/Kolkata",
        )
    else:
        browser = await playwright.chromium.launch(**launch_kwargs)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
    
    await apply_evasions(context)
    return context
```

#### B. JavaScript Runtime Evasions (`apply_evasions`):
Must be injected into every new document before page scripts load (`context.add_init_script`):

```javascript
// Remove navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});

// Mock realistic plugins array
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
        { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
    ],
});

// Ensure navigator.languages is properly populated
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en', 'hi'],
});

// Chrome runtime stub (indicates real Chrome extension ecosystem)
window.chrome = {
    runtime: {
        id: undefined,
        connect: function() {},
        sendMessage: function() {},
    },
    loadTimes: function() {},
    csi: function() {},
};

// Mask WebGL vendor / renderer if running in headless software rendering
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    // UNMASKED_VENDOR_WEBGL
    if (parameter === 37445) return 'Google Inc. (NVIDIA)';
    // UNMASKED_RENDERER_WEBGL
    if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3050 Direct3D11 vs_5_0 ps_5_0, D3D11)';
    return getParameter.apply(this, arguments);
};
```

---

### 3.3 Humanized Input Synthesis (Bezier Mouse & Gaussian Keypresses)

Anti-bot systems monitor pointer paths using event listeners (`mousemove`, `pointermove`).  
- **Robotic:** Cursor teleports straight to the target point, or moves in a mathematically straight line.
- **Human:** Follows curved paths with micro-tremors, accelerations, decelerations, and occasional overshoots (Fitts's Law).

#### Cubic Bezier Mouse Trajectory Algorithm:
```python
import math
import random
import asyncio

def bezier_point(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], t: float) -> tuple[float, float]:
    """Calculates a point along a Cubic Bezier curve at parameter t in [0, 1]."""
    x = (1-t)**3 * p0[0] + 3*(1-t)**2 * t * p1[0] + 3*(1-t) * t**2 * p2[0] + t**3 * p3[0]
    y = (1-t)**3 * p0[1] + 3*(1-t)**2 * t * p1[1] + 3*(1-t) * t**2 * p2[1] + t**3 * p3[1]
    return (x, y)

async def human_mouse_move(page, start_x: float, start_y: float, target_x: float, target_y: float, steps: int = 25):
    """Generates natural human-like mouse movement with curve control points and variable speed."""
    distance = math.hypot(target_x - start_x, target_y - start_y)
    if distance < 5:
        await page.mouse.move(target_x, target_y)
        return

    # Generate two control points offset perpendicularly to create natural curve
    deviation = min(120.0, distance * 0.3)
    p1 = (start_x + (target_x - start_x) * 0.25 + random.uniform(-deviation, deviation),
          start_y + (target_y - start_y) * 0.25 + random.uniform(-deviation, deviation))
    p2 = (start_x + (target_x - start_x) * 0.75 + random.uniform(-deviation, deviation),
          start_y + (target_y - start_y) * 0.75 + random.uniform(-deviation, deviation))
    
    p0 = (start_x, start_y)
    p3 = (target_x, target_y)

    for i in range(1, steps + 1):
        t = i / steps
        # Easing curve: ease-in, ease-out (fast in middle, slow at ends)
        t_eased = math.sin(t * math.pi / 2) if t < 0.5 else 1 - math.cos(t * math.pi / 2)
        cur_x, cur_y = bezier_point(p0, p1, p2, p3, t)
        await page.mouse.move(cur_x, cur_y)
        # Micro sleep: 5ms to 18ms
        await asyncio.sleep(random.uniform(0.005, 0.018))
```

#### Humanized Typing Cadence:
```python
async def human_type(page, text: str):
    """Types text with variable inter-keystroke intervals simulating human muscle movement."""
    for char in text:
        await page.keyboard.type(char)
        # Normal distribution around 85ms delay; punctuation gets slightly longer pause
        delay = random.gauss(0.085, 0.025)
        if char in " .,?!@\n":
            delay += random.uniform(0.12, 0.28)
        await asyncio.sleep(max(0.02, delay))
```

---

### 3.4 TLS Fingerprint & Session Continuity

1. **Use Real Chrome (`channel="chrome"`):**  
   Standard `playwright.chromium` compiles its own network stack, which can produce slightly different JA3/JA4 TLS cipher orderings compared to official retail Google Chrome. Using `channel="chrome"` executes the official Google Chrome binary on the host machine, guaranteeing standard Google TLS signatures.
2. **Persistent Contexts (`launch_persistent_context`):**  
   Instead of launching empty temporary incognito profiles on every run (which triggers suspicion on heavily protected endpoints), ScoutsKit supports a persistent profile directory (`.scoutskit/profile/`). It preserves cookies, cache headers, service workers, and local storage, establishing trusted session age.

---

### 3.5 Academic & Safety Guardrail Boundary

In accordance with Section 5.9 of the *Invisible Failure* thesis synopsis:
- **ScoutsKit does NOT break or solve CAPTCHAs, bypass paywalls, or defeat authentication security.**
- If a website disallows access via `robots.txt` or blocks access with a cryptographic challenge, the agent logs:
  ```json
  {"status": "blocked", "reason": "access_denied_by_policy", "url": "https://..."}
  ```
- The goal of the anti-bot layer is strictly **evasion of false-positive headless flags** on benign, public web pages.

---

## 4. The Event & Element Choosing System

A core failure mode in browser agents is choosing the wrong element (clicking a label instead of a checkbox, clicking a container instead of a button) or choosing the wrong event (calling `click()` when the UI required a `hover` to reveal a dropdown).

ScoutsKit’s interaction engine must decouple high-level agent intent from low-level DOM mechanics through a dual-engine architecture:
1. **The Event Choosing Hierarchy (Interaction Dispatcher)**
2. **The Element Choosing Engine (Multi-Attribute Fingerprinting & Self-Healing)**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Event & Element Resolution Architecture                  │
│                                                                             │
│   Agent Decision: Intent = "Select B.Tech in Course Dropdown"               │
│                                                                             │
│   Step 1: Element Choosing Engine (Fingerprint Matching)                    │
│   ├── Level 1: Semantic ARIA Match: role='combobox', name='Course'          │
│   ├── Level 2: Text / Label Anchor: label[for='course-select']              │
│   ├── Level 3: Scoped DOM Structure: form.admission-form select#course     │
│   └── Level 4: Fuzzy Matcher (Self-Healing Fallback)                        │
│                                                                             │
│   Step 2: Event Choosing Hierarchy (Interaction Dispatcher)                 │
│   ├── Check Tag & ARIA Role: Is it a native <select> or custom ARIA combo?  │
│   │   ├── If Native <select>: Dispatch selectOption()                       │
│   │   └── If Custom Combobox:                                               │
│   │       ├── 1. Human Move cursor to target bounding box                   │
│   │       ├── 2. Dispatch click to open dropdown                            │
│   │       ├── 3. Wait for options container (role='listbox') to become visible│
│   │       └── 4. Human Move & Click target option item                      │
│   └── Verification: Assert value updated or state expanded                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 The Event Choosing Hierarchy (Interaction Dispatcher)

Rather than treating every action as a raw `click` or `fill`, the dispatcher determines the precise sequence of DOM/CDP events based on element characteristics:

```python
# Conceptual Event Dispatching Decision Matrix
class InteractionDispatcher:
    def __init__(self, page):
        self.page = page

    async def interact(self, element_handle, action_type: str, value: str | None = None):
        # 1. Ensure element is visible in viewport before any action
        await element_handle.scroll_into_view_if_needed()
        box = await element_handle.bounding_box()
        if not box:
            raise ActionError("Element has zero bounding box (hidden or off-screen)")

        center_x = box["x"] + box["width"] / 2
        center_y = box["y"] + box["height"] / 2

        tag_name = await element_handle.evaluate("el => el.tagName.toLowerCase()")
        role = await element_handle.evaluate("el => el.getAttribute('role') || ''")

        if action_type == "hover":
            await human_mouse_move(self.page, await self._get_cursor_x(), await self._get_cursor_y(), center_x, center_y)
            await element_handle.hover()
            return "hovered"

        elif action_type == "click":
            # Natural sequence: Move -> Hover -> Mousedown -> Micro-pause -> Mouseup
            await human_mouse_move(self.page, await self._get_cursor_x(), await self._get_cursor_y(), center_x, center_y)
            await asyncio.sleep(random.uniform(0.04, 0.09))
            await element_handle.click(delay=random.randint(40, 95))
            return "clicked"

        elif action_type == "fill":
            # Safety check: block passwords/personal data
            if await self._is_sensitive(element_handle):
                raise ActionError("Refused: field is an authentication or personal data input.")
            
            await human_mouse_move(self.page, await self._get_cursor_x(), await self._get_cursor_y(), center_x, center_y)
            await element_handle.click()
            # Select existing text and clear
            await self.page.keyboard.press("ControlOrMeta+A")
            await self.page.keyboard.press("Backspace")
            await human_type(self.page, value or "")
            return f"typed {value}"

        elif action_type == "select":
            if tag_name == "select":
                await element_handle.select_option(label=value)
            else:
                # Custom ARIA combobox: click to open, then click matching role="option"
                await element_handle.click()
                await self.page.wait_for_selector("[role='option'], li", timeout=3000)
                option = self.page.get_by_role("option", name=value)
                await option.click()
            return f"selected {value}"
```

---

### 4.2 The Element Choosing Engine (Multi-Attribute Fingerprinting)

In ScoutsKit's current implementation, elements are referenced only by `ref=eN` from `aria_snapshot(mode="ai")`. This is fatal for two reasons:
1. `eN` changes whenever any part of the DOM updates or scrolls.
2. An `eN` cannot be saved into a Recipe for Mode 2 replay.

#### Multi-Attribute Fingerprint Schema:
Whenever an element is selected during exploration, the system captures a **multi-attribute fingerprint**:

```json
{
  "fingerprint_id": "fp_btn_search_01",
  "tag": "button",
  "role": "button",
  "accessible_name": "Search Problem Statements",
  "text_content": "Search",
  "attributes": {
    "id": "search-submit",
    "name": "submit",
    "type": "submit",
    "data_testid": "search-button"
  },
  "classes": ["btn", "btn-primary", "search-btn"],
  "parent_context": {
    "parent_tag": "form",
    "parent_id": "ps-filter-form",
    "parent_role": "search"
  },
  "relative_xpath": "//form[@id='ps-filter-form']//button[@type='submit']",
  "bounding_box_ratio": {
    "rel_x": 0.72,
    "rel_y": 0.18,
    "width": 120,
    "height": 38
  }
}
```

---

### 4.3 Self-Healing Locator Resolution (4-Tier Fallback Cascade)

When an action is replayed or executed after a DOM change, the locator resolver runs a deterministic 4-tier resolution cascade:

```
  Tier 1: Semantic ARIA Locator
  page.get_by_role(role, name=accessible_name)
         │
         ├── Found & Unique? ────> [EXECUTE ACTION]
         ▼ No / Ambiguous
  Tier 2: Explicit ID / TestID / Name
  page.locator("[data-testid='...'], #id, [name='...']")
         │
         ├── Found & Unique? ────> [EXECUTE ACTION]
         ▼ No / Ambiguous
  Tier 3: Scoped Container Text Anchor
  page.locator(parent_selector).get_by_text(text_content)
         │
         ├── Found & Unique? ────> [EXECUTE ACTION]
         ▼ No / Ambiguous
  Tier 4: Fuzzy Multi-Attribute Scorer (Self-Healing Engine)
  Scan candidate elements; score attributes; pick highest match >= 0.75
```

#### Self-Healing Matching Function:
```python
async def resolve_element_self_healing(page, fingerprint: dict):
    # Tier 1: Semantic ARIA
    if fingerprint.get("role") and fingerprint.get("accessible_name"):
        try:
            loc = page.get_by_role(fingerprint["role"], name=fingerprint["accessible_name"], exact=False)
            if await loc.count() == 1:
                return loc.first
        except Exception:
            pass

    # Tier 2: TestID or ID
    for attr in ("data_testid", "id"):
        val = fingerprint.get("attributes", {}).get(attr)
        if val:
            loc = page.locator(f"[{attr}='{val}']")
            if await loc.count() == 1:
                return loc.first

    # Tier 3: Relative Path
    if fingerprint.get("relative_xpath"):
        loc = page.locator(f"xpath={fingerprint['relative_xpath']}")
        if await loc.count() == 1:
            return loc.first

    # Tier 4: Fuzzy Scoring
    candidates = await page.locator(fingerprint.get("tag", "*")).all()
    best_score, best_candidate = 0.0, None
    for cand in candidates:
        score = await compute_similarity(cand, fingerprint)
        if score > best_score:
            best_score, best_candidate = score, cand

    if best_score >= 0.75 and best_candidate:
        return best_candidate

    raise ActionError(f"Self-healing resolution failed for {fingerprint['accessible_name']}")
```

---

### 4.4 Grounding & Output Verification

ScoutsKit's grounding check in [`src/scoutskit/grounding.py`](file:///home/linmar/Documents/scoutskit/src/scoutskit/grounding.py) prevents hallucinated rows by checking extracted values against the page text corpus.

#### Enhancements for Grounding:
1. **Normalization of Entities & Whitespace:** Decode HTML entities (`&amp;` → `&`, `&#8377;` → `₹`) and strip non-breaking spaces (`\u00a0`).
2. **Flexible Numeric & Date Matchers:** Match dates formatted differently (e.g. `2026-11-20` vs `20 Nov 2026`) and numbers with currency symbols or commas (`1,500` vs `1500`).
3. **Structured Table Context Validation:** When code extracts rows, verify that the column keys match headers found in the `<thead>` or table markup.

---

## 5. Codebase Diagnostic Audit: What is Fragile in ScoutsKit Right Now

An exhaustive audit of the existing codebase (`src/scoutskit/`) reveals critical flaws beyond LLM model capabilities:

### 5.1 Sandbox `bwrap` Namespace Crash in Virtualized/Container Hosts
- **Code:** [`src/scoutskit/sandbox.py`](file:///home/linmar/Documents/scoutskit/src/scoutskit/sandbox.py)
- **The Bug:** `sandbox.run_python` strictly requires `bwrap` (bubblewrap) and assumes unprivileged user namespaces (`CLONE_NEWUSER`) are supported by the kernel:
  ```python
  if not available():
      raise ActionError("bubblewrap (bwrap) is not available...")
  ```
- **Evidence:** When `uv run pytest` was executed, 5 tests failed immediately:
  ```
  bwrap: Creating new namespace failed: Function not implemented
  ```
- **Consequence:** Inside containers, cloud runners (Docker, GitHub Actions, cloud IDEs, sandbox environments), `bwrap` fails. When code execution fails, the agent cannot extract tables from raw HTML.
- **Remedy:** Implement a dual-mode sandbox:
  1. `bwrap` mode when user namespaces are functional.
  2. Isolated subprocess mode (`multiprocessing` / Python `subprocess` with resource limits `RLIMIT_AS`, no environment variables, and strict path sandboxing) when `bwrap` cannot create namespaces.

---

### 5.2 Ephemeral `[ref=eN]` Locators & Replay Impossibility
- **Code:** [`src/scoutskit/agent.py`](file:///home/linmar/Documents/scoutskit/src/scoutskit/agent.py), [`src/scoutskit/browser/session.py`](file:///home/linmar/Documents/scoutskit/src/scoutskit/browser/session.py)
- **The Bug:** All interactions use `page.locator(f"aria-ref={ref}")`. `ref=eN` is dynamically assigned by Playwright's `aria_snapshot(mode="ai")`.
- **Consequence:**
  - Any AJAX call, DOM mutation, or scroll changes `e12` to `e14`.
  - **Blocks Mode 2:** A recipe cannot store `{"tool": "click", "args": {"ref": "e12"}}` because `e12` does not exist when replaying on a mobile viewport or throttled network.
- **Remedy:** When resolving an action, immediately extract its **Multi-Attribute Fingerprint** (Role, Name, TestID, XPath) and record it in `actions.jsonl`.

---

### 5.3 Single-Tab Lockout (`target="_blank"` Blindness)
- **Code:** [`src/scoutskit/browser/session.py`](file:///home/linmar/Documents/scoutskit/src/scoutskit/browser/session.py)
- **The Bug:** `BrowserSession` initializes `self.page = await self.context.new_page()` and only ever interacts with that single page.
- **Consequence:** Many portals (university exam results, government tenders, hackathons) open links in new tabs (`<a target="_blank">` or `window.open()`). The browser opens the tab, but ScoutsKit stays locked to the first tab, reporting that the target content was never found.
- **Remedy:** Listen to `context.on("page")`, keep an active page stack, and provide `list_tabs`, `switch_tab`, and `close_tab` tools.

---

### 5.4 Context Token Explosion (`MAX_TREE_CHARS = 45_000`)
- **Code:** [`src/scoutskit/browser/session.py`](file:///home/linmar/Documents/scoutskit/src/scoutskit/browser/session.py#L27)
- **The Bug:** `MAX_TREE_CHARS = 45_000` dumps up to ~11,000 tokens of raw accessibility text into the prompt every single turn.
- **Consequence:**
  - On rate-limited providers (e.g. Groq's 6,000–8,000 tokens/minute or free tiers), a single turn triggers HTTP 429 quota exhaustion.
  - Large tables fill the context with repetitive row nodes, pushing actual buttons and pagination controls out of the window.
- **Remedy:** Implement **Tree Compression**:
  - Fold repeating sibling items (e.g., if 50 table rows share the same structure, output rows 1–3 and summarize: `... [47 identical row items collapsed] ...`).
  - Add a `find(query)` tool so the agent can request specific subtrees without receiving the entire page.

---

### 5.5 Unscoped Blind Scrolling
- **Code:** [`src/scoutskit/browser/session.py`](file:///home/linmar/Documents/scoutskit/src/scoutskit/browser/session.py#L173)
- **The Bug:**
  ```python
  async def scroll(self, direction: str = "down") -> None:
      delta = 600 if direction == "down" else -600
      await self.page.mouse.wheel(0, delta)
  ```
- **Consequence:** Dispatches wheel ticks to `(0, 0)`. If a data grid, table, or modal uses `overflow-y: scroll`, global wheel events are ignored and the container never scrolls.
- **Remedy:** Support `scroll(direction="down", ref="e12")` to scroll specific container elements, and use `scroll_into_view_if_needed()` before interacting.

---

### 5.6 The `min_items` Deadlock Trap
- **Code:** [`src/scoutskit/agent.py`](file:///home/linmar/Documents/scoutskit/src/scoutskit/agent.py#L32)
- **The Bug:** The planner guesses `min_items` upfront before navigating to the website.
  If the planner guesses `min_items: 50` for a site that only has 14 items, the `done` tool is rejected 3 times (`only 14 items collected; expected at least 50`), and the agent aborts with status `"incomplete"`.
- **Remedy:** Allow `done` to accept a `reason` explaining that no more items exist, or dynamically adjust `min_items` based on detected page pagination text (e.g. "Showing 1 to 14 of 14 entries").

---

### 5.7 Missing Mode 2 Evaluator Infrastructure
- **Status:** Mode 1 (exploration) has tools, but Mode 2 has no implementation in `src/scoutskit/`:
  - No axe-core accessibility scanner injection.
  - No keyboard navigation focus trap detector.
  - No layout shift (CLS) or render latency observers.
  - No CDP network emulation wrapper for profiles (`slow_3g`, `fast_3g`, `low_end_mobile`).

---

## 6. Target System Architecture & Module Structure

To support both Mode 1 (autonomous exploration) and Mode 2 (recipe replay under test conditions), ScoutsKit is organized into a clean, decoupled modular hierarchy:

```
src/scoutskit/
├── __init__.py
├── cli.py                     # Typer CLI (run, test, replay, providers)
├── config.py                  # Settings loader (scoutskit.toml + .env)
│
├── core/                      # Engine interfaces & shared models
│   ├── __init__.py
│   ├── types.py               # Pydantic schemas (Action, Turn, RunResult)
│   ├── state.py               # Agent memory & exploration state
│   └── recipe.py              # Recipe schema (for Mode 2 replay)
│
├── browser/                   # Browser interaction & stealth engine
│   ├── __init__.py
│   ├── session.py             # Playwright lifecycle & multi-tab manager
│   ├── stealth.py             # Evasions, flag masking, user-agent setup
│   ├── human_input.py         # Bezier mouse curves & Gaussian typing
│   ├── policy.py              # Security boundaries (same-site, robots.txt)
│   └── cdp.py                 # Chrome DevTools Protocol helper (throttling, tabs)
│
├── perception/                # Page understanding & token reduction
│   ├── __init__.py
│   ├── tree.py                # Accessibility tree builder + token pruning
│   ├── fingerprint.py         # Multi-attribute element fingerprint generator
│   ├── locator.py             # 4-tier self-healing locator resolver
│   └── grounding.py           # Output text verification & anti-hallucination
│
├── tools/                     # Bounded tools exposed to the agent (22 tools)
│   ├── __init__.py
│   ├── registry.py            # ToolRegistry & LangChain StructuredTool factory
│   ├── browser_tools.py       # click, hover, fill, select, press, scroll
│   ├── inspection_tools.py    # read_page, find, page_text, javascript_tool
│   ├── network_tools.py       # network_log, network_body, console_log
│   ├── tab_tools.py           # list_tabs, switch_tab, new_tab, close_tab
│   ├── code_tools.py          # view_source, grep_source, run_python, use_script_output
│   └── control_tools.py       # done, fail, wait_for
│
├── sandbox/                   # Sandboxed code execution
│   ├── __init__.py
│   ├── runner.py              # Dual runner: bwrap with fallback to restricted subprocess
│   └── bwrap.py               # Linux bubblewrap container runner
│
├── provider/                  # LLM integration & fallback chain
│   ├── __init__.py
│   ├── config.py              # Provider resolution (NVIDIA, Groq, Google, etc.)
│   ├── client.py              # LangChain chat model wrapper
│   └── probe.py               # Health checks & quota fail-fast
│
├── evaluators/                # Mode 2 Evaluation engines
│   ├── __init__.py
│   ├── axe.py                 # axe-core automated WCAG 2.2 scanner
│   ├── keyboard.py            # Tab-sequence & focus-trap auditor
│   ├── usability.py           # Layout shifts, latency, tap-target size evaluator
│   └── visual.py              # Text overflow & visual contrast analyzer
│
├── orchestrator/              # Mode 2 Replay & Parallel Execution
│   ├── __init__.py
│   ├── replay.py              # Replay engine (executes recipe without LLM)
│   ├── profiles.py            # Environment profiles (Network, CPU, Device, Locale)
│   └── runner.py              # Async parallel orchestrator with concurrency cap
│
└── recorder/                  # Evidence & reporting
    ├── __init__.py
    ├── recorder.py            # actions.jsonl, screenshots, video capture
    └── report.py              # Markdown & HTML evaluation report generator
```

---

### 6.3 Expanded Toolset Registry (22 Tools)

The complete target toolset exposed to the LangGraph explore agent:

```
Interaction Primitives:
  1. click(ref, button="left")         - Natural mouse movement + click
  2. hover(ref)                        - Move cursor over element (reveals dropdowns)
  3. fill(ref, text)                   - Humanized typing into input field
  4. select(ref, option)               - Select dropdown option (native or custom ARIA)
  5. press(key)                        - Press keyboard key or key chord (Enter, Tab, Escape)
  6. scroll(direction, ref=None)       - Smooth scroll viewport or target overflow container

Navigation & Tabs:
  7. goto(url)                         - Navigate to URL on same domain
  8. back()                            - Browser history back
  9. list_tabs()                       - List all open browser tabs
 10. switch_tab(tab_id)                - Switch active focus to another tab
 11. close_tab(tab_id)                 - Close a background or pop-up tab

Perception & Inspection:
 12. read_page()                       - Get token-compressed accessibility tree
 13. find(query)                       - Targeted search for specific element or section
 14. page_text(max_chars=6000)         - Read visible human-readable text
 15. javascript_tool(script)           - Execute in-page JavaScript expression via CDP
 16. network_log(pattern=None)         - Inspect HTTP requests/responses
 17. network_body(index)               - Read response body of network request
 18. console_log(errors_only=True)     - Read browser console messages

Code-Driven Extraction:
 19. view_source(start, end, source)   - Read slice of raw/rendered HTML
 20. grep_source(pattern, context)     - Search HTML source for structural repeating blocks
 21. run_python(code)                  - Execute sandboxed script extracting data
 22. use_script_output()               - Validate and load script extraction into result dataset

Flow Control:
 23. wait_for(selector_or_text, timeout) - Explicit wait for dynamic elements
 24. done(reason=None)                 - Signal task completion
 25. fail(reason)                      - Abort impossible task
```

---

### 6.4 Recipe Schema for Deterministic Mode 2 Replay

When Mode 1 completes, it outputs a compiled **`recipe.json`**.  
In Mode 2, the **Replay Engine** executes this recipe **without calling an LLM**, isolating environmental conditions as the sole variable:

```json
{
  "recipe_version": "1.0",
  "task_goal": "Extract Smart India Hackathon problem statements",
  "start_url": "https://sih.gov.in/sih2026PS",
  "expected_items": 265,
  "steps": [
    {
      "step_id": 1,
      "intent": "Open navigation menu",
      "action": "click",
      "target": {
        "role": "button",
        "accessible_name": "Toggle navigation",
        "relative_xpath": "//button[@class='navbar-toggle']",
        "css_selector": "button.navbar-toggle"
      },
      "post_condition": {
        "wait_for_selector": "a[href='/sih2026PS']",
        "timeout_ms": 5000
      }
    },
    {
      "step_id": 2,
      "intent": "Select 100 entries per page in DataTables dropdown",
      "action": "select",
      "target": {
        "role": "combobox",
        "accessible_name": "records per page",
        "css_selector": "select[name='settings_length']"
      },
      "value": "100",
      "post_condition": {
        "wait_for_network_idle": true,
        "timeout_ms": 5000
      }
    }
  ],
  "extraction_rule": {
    "strategy": "structural_table",
    "table_selector": "table#settings",
    "fields": ["id", "title", "organization", "category", "theme"]
  }
}
```

---

## 7. Step-by-Step Implementation Roadmap

```
Week 1: Core Reliability & Tool Foundations
  ├── Fix sandbox.py: Add restricted subprocess fallback when bwrap user namespaces fail
  ├── Implement javascript_tool (page.evaluate) and hover() in tools.py
  ├── Implement multi-tab awareness in BrowserSession (context.on("page"))
  └── Build token-pruning tree compressor (collapsing repetitive table nodes)

Week 2: Anti-Bot Stealth & Input Humanization
  ├── Implement stealth.py launch wrapper (channel="chrome", CDP masking, evasions)
  ├── Build human_input.py (Cubic Bezier mouse movements + Gaussian keystrokes)
  └── Wire Multi-Attribute Fingerprint extraction into every interaction

Week 3: Recipe Compilation & Mode 2 Replay Engine
  ├── Build Recipe compiler (translates actions.jsonl into locator-stable recipe.json)
  ├── Build Self-Healing Locator Resolver (4-tier cascade)
  └── Build LLM-Free Replay Engine (replaying recipes against headless sessions)

Week 4: Environment Profiles & Evaluators
  ├── Implement CDP network & CPU throttling profiles (Slow 3G, 4G, 4x CPU slowdown)
  ├── Integrate axe-core automated accessibility audits (WCAG 2.2 AA)
  ├── Implement keyboard navigation focus-trap auditor
  └── Generate comparative evaluation report (Pass/Fail vs. Environment Matrix)
```

