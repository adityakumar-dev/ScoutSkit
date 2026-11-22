# ScoutsKit: technology and design guide

For the examiner: **what is used, why, and where it is in the code.** Everything here can be checked in the repository; file paths are relative to the repo root. Numbers come from the project's own runs and tests (the evidence is in `runs/` and `project_process_report.md`).

---

## 1. What it is, in one minute

**ScoutsKit** is an autonomous web agent. You describe a job in plain language ("download the B.Tech CSE syllabus from the uktech website", "find all the SIH 2025 problem statements"). It:

1. **researches** the web and picks sources, then shows a **plan** that a person approves or corrects;
2. **explores** with a team of agents in separate browsers, using a bounded set of tools;
3. **checks** its own result (a list is counted against the total the page states) and asks the person to accept it;
4. saves the run as a **recipe** that can be **replayed with no language model**;
5. keeps **evidence** of everything (every step, screenshots, files, the result).

It is the first half ("Mode 1") of the project *Invisible Failure*. The second half ("Mode 2": evaluating websites under different environment profiles, with usability and accessibility checks) is the next stage; see section 9 and `IMPLEMENTATION_PLAN.md`.

```
 person ──► Interface (React) ◄──WebSocket──► Server (FastAPI) ──► Runner
                                                                      │
        research (search) ─► brief + plan ─► person approves ─► Team of agents
        src/scoutskit/search/   brief.py                         team.py
                                                                      │
                          each agent:  observe ─► decide ─► act ─► check   (LangGraph)
                                       page      model     tool    stop/continue
                                       │                    │
                                       └─ Playwright browser ┘  (own context per agent)
                                                                      │
                  result check (count vs page total) ─► person accepts ─► recipe ─► replay (no model)
```

---

## 2. Technologies: what, why, where

### Language, tooling

| Technology | Role | Why this one | Where |
|---|---|---|---|
| **Python 3.12** | Everything on the server side | Team familiarity; strong libraries for browsers, async work and later statistics (synopsis §6) | `src/scoutskit/`, `.python-version` |
| **uv** | Dependency and virtual-environment manager | One fast tool; `uv.lock` pins the exact versions so a clean machine gets the same ones | `pyproject.toml`, `uv.lock` |
| **asyncio** | Concurrency (several agents, live stream, input handling) | Browsers and model calls wait on I/O; async keeps many of them cheap | throughout, e.g. `team.py`, `server/` |

### Browser automation

| Technology | Role | Why | Where |
|---|---|---|---|
| **Playwright (Python) + Chromium** | The controlled browser; one **context per agent** (cookies, tabs and request guard are isolated) | Ships its own driver (no Node needed); gives the accessibility tree, network bodies, downloads and Chrome DevTools Protocol. Tested before adoption (`IMPLEMENTATION_PLAN.md` §2) | `src/scoutskit/browser/session.py` (`BrowserSession`, `BrowserHost`) |
| **Accessibility tree with refs** (`aria_snapshot(mode="ai")`) | What the agent "sees": the page as text with `[ref=e12]` handles | Much smaller than HTML or screenshots; stable enough to click by ref | `browser/session.py`, `browser/tree.py` |
| **Chrome DevTools Protocol screencast** | The live picture of the browser in the interface | Chrome pushes JPEG frames only when the page changes; low cost | `server/screencast.py` |
| **Site policy and request guard** | Only http(s); no private networks (localhost, 10.x, 192.168.x, cloud metadata); every request checked, redirects included; DNS checked | A language model must never be able to reach the local network | `browser/safety.py`, `browser/session.py` (`guard_request`) |

### The agent ("brain")

| Technology | Role | Why | Where |
|---|---|---|---|
| **LangGraph** | The agent loop as a small graph: **observe → decide → act → check** | Explicit states make loops, limits and hand-over to a person easy to reason about and to test | `src/scoutskit/agent.py` |
| **LangChain** (`langchain-core`, `langchain-openai`, `langchain-anthropic`) | One interface to many model providers with **native tool calling** | Tested: a model that calls tools natively behaves far better than one asked to write JSON in text. Almost every provider is OpenAI-compatible, so one class covers them | `src/scoutskit/provider/chat.py` |
| **Own JSON client (`httpx`)** | The simple one-shot model calls (research, plan, result check) with retries and quota handling | Predictable errors; keys never appear in messages | `src/scoutskit/provider/llm.py` |
| **Models** | Default `nvidia/nemotron-3.5-super-vl-120b-a12b` (NVIDIA NIM); `nemotron-3-ultra-550b-a55b` for hard cases; small `nemotron-3.5-bolt-e4b` only as last fallback; Anthropic, OpenAI, Google, Groq, OpenRouter are configured | Free or low-cost hosted models; chosen by benchmark (the small model extracted 1 of 25 rows). Local models were tried and were too weak on the available hardware | `scoutskit.toml`, `src/scoutskit/provider/config.py` |
| **Bounded tool registry** | About 30 typed tools (click, type, goto, find_links, find_items, run_python, save_file, web_search …); unknown or invalid arguments are errors the model sees | The agent can only do what a tool allows; one description feeds the prompt, the typed schema and the dispatcher | `src/scoutskit/tools/` |

### Extraction (getting the data)

| Technology | Role | Why | Where |
|---|---|---|---|
| **Model-written Python in a sandbox (bubblewrap)** | For long lists the model writes a short script; it runs with **no network and a read-only filesystem**; the model never has to retype hundreds of rows | A model asked to copy 265 rows loses some; a script does not. Tested: 265 of 265 | `src/scoutskit/sandbox.py`, `tools/extraction.py` |
| **BeautifulSoup + lxml** | HTML parsing: the script's parser, the table census, the finder of repeated items | Standard, robust | `browser/census.py`, `browser/repeats.py`, `browser/links.py` |
| **Grounding check** | Every value the agent records must be found on the page (text, source or the page's own data requests); a list is checked part by part | Stops invented rows | `src/scoutskit/grounding.py` |
| **Finder of repeated items** (own) | Finds the page's main list (table rows, cards, entries) and a short CSS selector; ignores menus, headers and table cells | Small models guessed selectors from the accessibility tree and failed; this gives them the real structure | `src/scoutskit/browser/repeats.py` |
| **Link finder** (own) | Searches every link in the page, including hidden dropdown and collapsed sections, with its real address | The tree does not show hover menus; the model guessed URLs | `src/scoutskit/browser/links.py` |
| **Network feed detection** | If the page loads its data from a request (JSON), the same data can be read directly | Cheapest and most exact source; used by replay too | `browser/feeds.py`, `recipe/source.py` |

### Research (finding sources)

| Technology | Role | Why | Where |
|---|---|---|---|
| **`ddgs`** (metasearch library) + **Wikipedia / Wikidata API** | Free web search as **data**, not as a browser page | Search engines answer automated browsers with block pages or CAPTCHAs (observed: HTTP 418, reCAPTCHA); the library reads results without a browser. Free, no key | `src/scoutskit/search/` |
| **Sources chosen by number** | The model picks results by their number, never by writing a URL | It cannot invent an address | `src/scoutskit/brief.py` |
| **Peek** | Each candidate page is loaded and measured **without a model** (holds a list? says "no data"?) before any agent starts | An empty official page was tried first and wasted a run | `src/scoutskit/peek.py` |

### Teamwork, control and safety

| Technology | Role | Where |
|---|---|---|
| **Team of sub-agents** | One agent per source, in parallel, isolated; fail-over to the next source; the first accepted result wins | `src/scoutskit/team.py` |
| **Token budget** | A shared limit; each agent may use a third, so a failing source cannot burn everything | `src/scoutskit/budget.py` |
| **Result check by counting** | If the item count equals the total the page states, completeness is settled by counting; the model is asked only whether these are the right kind of items | `team.py` (`_verify`) |
| **Human in the loop** | Plan approval; accepting the result; **take control** of the live browser (click, scroll, type, paste); a **CAPTCHA is handed to a person and never bypassed** | `control.py`, `server/remote_input.py`, `server/input_pump.py`, `agent.py` |
| **Refusals are findings** | HTTP 403/418/429 or a block page is recorded and never worked around | `browser/session.py`, `agent.py` |
| **File saving** | Downloads are stored, never opened; web pages and error pages are refused as "files"; size and total limits | `src/scoutskit/browser/files.py` |

### Recipes and replay

| Technology | Role | Where |
|---|---|---|
| **Recipe** (JSON) | What a successful run did: steps located by **role + name + position** (not by volatile refs), the extraction script or data request, expected counts and files | `src/scoutskit/recipe/model.py`, `build.py` |
| **Replay with no model** | Repeats the recipe; reports a **finding** when the page changed instead of guessing. SIH: 101 rows in 2 s; the syllabus PDF downloaded again in 11 s | `src/scoutskit/recipe/replay.py`, `runner.py` (`replay_recipe`) |

### Server and interface

| Technology | Role | Why | Where |
|---|---|---|---|
| **FastAPI + uvicorn** | HTTP API and a **WebSocket** per run (events plus live picture plus the person's input) | Typed, small, async | `src/scoutskit/server/` |
| **pydantic** | Validates everything the browser may send (a discriminated union of allowed inputs) and the configuration | The input channel is a security boundary | `server/remote_input.py`, `provider/config.py` |
| **Typer + Rich** | Command line (`run`, `replay`, `serve`, `check`, `providers`) | Simple, readable | `src/scoutskit/cli.py` |
| **python-dotenv** | API keys live in `.env` (git-ignored); the config names only the variable | Keys never in the repository | `.env.example`, `scoutskit.toml` |
| **React 19 + TypeScript + Vite** | The web interface | Plain React, single user, local only; fast builds | `ui/` |
| **pdf.js** | PDFs drawn inside the page, loaded only when one is opened | Identical in every browser | `ui/src/components/PdfView.tsx` |
| **lucide-react, IBM Plex (fontsource)** | Icons and fonts, bundled (works offline) | Consistent look | `ui/src/main.tsx` |
| **Vitest** | UI logic tests (event reducer, settings, input maths) | | `ui/src/*.test.ts` |
| **pytest + pytest-asyncio** | Python tests | | `tests/` |

---

## 3. A run, step by step (with the code)

1. **Start**: `NewRun.tsx` posts to `server/app.py` → `server/runs.py` (`RunManager.start`, at most 3 parallel runs).
2. **Research** (`runner.py` → `brief.py`): the model proposes queries; `search/` gathers results; the model picks sources **by number** and writes a plan. Event `brief` goes to the interface.
3. **Approval** (`control.py` `PlanGate`): the run waits for **Continue** or **Add context** (which re-plans, keeping earlier sources).
4. **Look** (`peek.py`): candidate sources are measured; those with data go first.
5. **Team** (`team.py`): agents start in separate browser contexts (`browser/session.py`).
6. **Each agent** (`agent.py`, LangGraph): *observe* (page tree plus advice such as "this page repeats one element 238 times") → *decide* (model chooses one tool) → *act* (tool runs) → *check* (limits, loops, refusals, CAPTCHA hand-over).
7. **Finish**: the agent calls `done`; the team checks the result by counting and asks the person to accept (`ResultCheckCard.tsx`).
8. **Save**: `recorder.py` writes `runs/<id>/` (steps, screenshots, `result.csv/json`, `files/`); `recipe/build.py` writes `recipe.json`.
9. **Replay** (button in `MissionView.tsx`): `server/runs.py` → `runner.replay_recipe` → `recipe/replay.py`.

---

## 4. Why it is designed this way (each choice came from a failure)

| Decision | Evidence that led to it |
|---|---|
| Own bounded tools, not a ready-made agent framework (Stagehand dropped) | It listed hidden elements, needed a model for concrete actions, and added an extension and a placeholder model (`IMPLEMENTATION_PLAN.md` D2) |
| Native tool calling | JSON-in-prompt failed at the decisive step; native calls fixed it |
| Code-writing extraction | Screen reading got 100 of 265 rows and reported "completed"; a script got 265 of 265 |
| Grounding + counting | A model invented plausible rows; counts catch missing ones |
| Search as data | Search pages in the browser returned HTTP 418 and CAPTCHAs |
| Finders for lists and links | Small models used accessibility *roles* and *refs* as if they were HTML and guessed URLs; with the real structure they succeed |
| Peek, budget, fail-over | One run spent 600,000 tokens on an official page that held no data |
| Recipes keyed by role + name + position | Refs (`e12`) change at every load |
| Replay with no model | The synopsis's core idea: the model explores once, repetition is cheap and reproducible |
| Safety in code, not in the prompt | The model typed `admin` into a login field despite the instruction; the tool now refuses such fields |

The full story with dates is in `project_process_report.md`.

---

## 5. Repository map

```
src/scoutskit/
  agent.py            the agent loop (LangGraph) and its prompts
  brief.py            research -> sources -> plan
  team.py             parallel sub-agents, fail-over, result check, budget shares
  peek.py             first look at candidate sources (no model)
  budget.py           shared token budget
  runner.py           one task start to finish; replay_recipe
  control.py          who drives the browser; plan/result approval gates
  grounding.py        values must be on the page
  sandbox.py          model-written Python without network (bubblewrap)
  recorder.py         evidence per run
  preflight.py        `scoutskit check`
  cli.py              command line
  browser/            session, safety policy, tree, repeats, links, files, feeds, census
  tools/              the bounded tool set (actions, reading, extraction, web, control)
  provider/           configuration, model clients, key checks
  search/             web search sources
  recipe/             build and replay recipes
  server/             API, WebSocket, screencast, remote input
ui/src/               React interface (components, state reducer, settings)
benchmarks/portal/    local test pages (hidden menus, paged tables, CAPTCHA, cards, accordion, feeds)
tests/                Python tests
runs/                 evidence of every run (git-ignored)
scoutskit.toml        providers and settings        .env.example  key names only
IMPLEMENTATION_PLAN.md  plan, decisions, status      project_process_report.md  diary
DEMO.md               how to present it             README.md  how to run it
```

---

## 6. Safety and ethics: what is enforced in code

- **No private networks**, ever (names, literal IPs, DNS results, redirects). `browser/safety.py`
- **Refusals are findings**: HTTP 403/418/429 or a block page is logged and never bypassed. **CAPTCHAs are handed to a person**; nothing solves or hides them.
- **Page text is data, never instructions**: a prompt rule *and* tool limits (the agent cannot log in, pay or enter personal data; the fill tool refuses such fields).
- **Passwords** typed by a person during a take-over are hidden from the model and the logs.
- **Files are stored, never executed**; error pages are not accepted as files.
- **Model-written code runs in a sandbox** with no network and a read-only filesystem; if the sandbox is unavailable, code is refused, never run unsandboxed.
- **The server listens on 127.0.0.1 only** and refuses WebSocket connections from other websites.
- API keys only in `.env` (git-ignored).

---

## 7. Testing and evidence

- **253 Python tests and 37 UI tests** pass (`uv run pytest`, `cd ui && npm test`). They cover the agent loop with scripted models, the browser tools on local pages, safety rules, the server and its WebSocket, recipes and replay, the finders, files, the team (fail-over, budget, result check), the pre-flight, and the interface logic.
- **Live runs with real models on real sites** (all kept in `runs/`):

| Task | Result |
|---|---|
| SIH 2026 problem statements (paged table, 3 MB page) | 265 of 265 rows, all fields |
| SIH 2025 problem statements | 101 rows in 4 steps (about 31,000 tokens), counted against the page's own total |
| "Download the B.Tech CSE syllabus" (uktech) | 7 steps, the real 3.8 MB PDF; 1 minute 20 s through the interface |
| "Download the cyber security syllabus" | 4 steps, 1.4 MB PDF |
| Replay without a model | SIH: 101 rows in 2 s; syllabus: the PDF downloaded again in 11 s |
| Local benchmark portal (hidden menu, dropdown, pagination) | 40 of 40 records |

Failures are recorded too (for example a 66-step run that ended incomplete; the causes and the fixes are in `project_process_report.md`).

---

## 8. How to run it

```bash
uv sync && uv run playwright install chromium
cp .env.example .env              # add NVIDIA_API_KEY
(cd ui && npm install && npm run build)
uv run scoutskit check            # pre-flight: browser, sandbox, model, search, interface
uv run scoutskit serve --open     # http://127.0.0.1:8000
```

---

## 9. Scope against the synopsis, and honest limits

**Done:** Mode 1 (objectives 1 and 2, about 90%), recipes and replay (objective 3, about 75%), parallel isolated agents (part of 7). **Not yet:** environment profiles, functional and usability evaluators, axe-core and keyboard checks, a unified report, a benchmark site with injected faults, workflow discovery (planned for January). Overall about 35–40% of the whole project; about half of the synopsis's 40% demonstration list (§5.8). Full tables: `IMPLEMENTATION_PLAN.md`, "Status on 2026-11-23".

**Limits to state openly:**
1. **`robots.txt`**: the check is implemented and tested (`browser/safety.py`) but **switched off in runs** (`respect_robots=False` in `runner.py` and `team.py`). The synopsis (§5.9) says robots.txt is respected; either switch it on (one setting) or state this as a deviation.
2. **Search** uses a free, unofficial metasearch library that fails now and then (it retries and reports notes). An official search API with a key would be more dependable.
3. **Two mirror sites** list 101 and 238 SIH 2025 problem statements; the run takes the first whose total matches. Which is the true list cannot be known from the pages alone.
4. **Product comparison on shops** is unreliable (shops often refuse automated browsers; such refusals are recorded, not bypassed). **Bulk downloads** (about 70 large PDFs) hit the file-size limit.
5. **Real CAPTCHAs** (Google and similar) were not tried; the hand-over was tested on a test page. A site may still refuse the browser after a person ticks the box.
6. **Small models** make wrong choices; much of the structure above exists to help them (real page structure, loop limits, budgets). The default model was chosen by benchmark, not by name.
7. Tested in **Chromium only**; the interface was checked in Chromium.

---

## 10. Questions an examiner may ask

**Why not just use an existing agent (Stagehand, browser-use, ChatGPT agent)?** The project's aim is evidence and reproducibility. We need every action recorded, bounded tools, replay without a model, and later per-profile replay. Ready-made agents hide actions behind a model and cannot replay deterministically. We trialled Stagehand and dropped it with evidence (section 4).

**How do you know the data is right?** Three layers: every value must be found on the page (grounding); a list is counted against the total the page states; a second model call judges relevance. The SIH 2026 run was compared with the page's raw HTML (265 of 265).

**What stops the agent doing something harmful?** Section 6: tool limits in code (no login, payment or personal data), no private networks, a sandbox for code, refusals logged not bypassed, a person approves the plan and the result, and can take over at any time.

**What does replay prove?** That the first run found a repeatable path: the same data or file is obtained again with no model, and a changed page is reported as a specific finding (page changed, element missing, result changed) instead of silently returning something else.

**What is new compared with existing work?** Mode 1 combines research, an approved plan, parallel isolated agents, deterministic checks and replay into one evidence-keeping workflow. The planned Mode 2 (profiles, personas, usability and accessibility evaluation, failure localisation by changing one condition at a time) is the research contribution and is the next stage.

**What are you least sure of?** The evaluation half has not been built; the free search source is unofficial; and results on sites that refuse automation vary. These are listed in section 9.
