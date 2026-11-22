# ScoutsKit — Implementation Plan

Product: **ScoutsKit**. Project: **Invisible Failure** (B.Tech final-year, UTU Dehradun, 2026–27).
Status date: **2026-11-23** (see the status section below; the older sections are kept as the history of the decisions). First working module (40%) is presented after **2026-11-20**.

This file is the single source of truth for *what we build, in what order, and what could stop us*.
Nothing in a step below is built until you approve it.

## Status on 2026-11-23

**Short answer: Mode 1 (the agent that does a task) is far ahead of the plan; Mode 2 (testing under profiles, usability and accessibility) has not been started.** Measured against the synopsis's own list for the 40% demonstration (§5.8), about **half** of the items are done; measured against all eight objectives, the project is at about **35–40%**, unevenly: very strong on the agent, near zero on evaluation.

### The 40% demonstration scope (synopsis §5.8), item by item

| # | Item in the synopsis | Status | Evidence |
|---|---|---|---|
| 1 | Natural-language task input and basic decomposition | **Done, beyond the plan** | Research (free web search), a plan with sources and steps, approval or added context, then sub-agents. |
| 2 | Controlled browser execution with DOM and accessibility-tree inspection | **Done** | Playwright session; tree with refs; finders for lists and links; request log and bodies; sandboxed scripts. |
| 3 | Recording and replay of a task as a recipe | **Done** | Recipes replay with no model (SIH: 101 rows in 2 s; the syllabus PDF downloaded again). Replay button in the UI. *Not yet:* recording a recipe from a person's own actions. |
| 4 | Orchestrator running several agents in parallel in isolated sessions | **Partial** | Sub-agents run in parallel, each in its own browser context, with a token budget and fail-over. *Not yet:* parallel **replay** of one recipe under several profiles (that is the synopsis's point). |
| 5 | At least three environment profiles | **Not done** | Network and CPU throttling was only proven on one page (spike); no profile module. |
| 6 | Basic functional testing and usability metrics | **Not done** | We keep raw data (steps, time, failures, findings such as blocked pages and changed pages) but there is no evaluator and no difficulty metric. |
| 7 | axe-core integration and keyboard checks | **Not done** | |
| 8 | Screenshots, structured logs, unified initial report | **Partial** | Screenshots and logs for every run; the interface shows them. *Not yet:* one unified report file per evaluation. |
| 9 | Controlled demonstration websites | **Partial** | Local test pages (tables, hidden menus, CAPTCHA, feeds, cards, accordions). *Not yet:* a site with **injected faults** whose detection can be scored. |

Score: 3 done + 3 partial of 9. The finished part is the harder one (an agent that works on real sites); the missing part is mostly engineering on top of what exists (Playwright CDP, axe-core injection, a report).

### Objectives of the synopsis (§3)

| # | Objective | Now | Remarks |
|---|---|---|---|
| 1 | Plan natural-language tasks, execute with tools, validate, produce output (Mode 1) | **~90%** | Validated against the page's own totals; every run leaves evidence. |
| 2 | Controlled interaction engine on Playwright, bounded tools, structured action record | **~90%** | Tools are bounded; site policy, request guard, no private networks. |
| 3 | Explore once, compile a recipe, replay under different conditions | **~75%** | Replay works; "under different conditions" needs profiles. |
| 4 | Automatic workflow discovery | **0%** | Planned for January. The research step is a first, different kind of discovery. |
| 5 | Functional, usability and accessibility evaluation; validated difficulty metric | **~5%** | Only the raw data exists. The volunteer study is still a logistics risk. |
| 6 | Predefined and custom environment profiles | **0%** | |
| 7 | Hierarchical orchestrator, replay agents, localisation by changing one condition | **~25%** | Parallel isolated sessions and a budget exist; replay agents and localisation do not. |
| 8 | Controlled benchmarks with known faults; parallel vs sequential; comparison with Lighthouse / axe / scripted Playwright | **~10%** | Test pages and a replayable benchmark task exist; no fault injection, no comparisons. |

### What was built beyond the plan (and why)
- **Research before browsing**: free web search (a metasearch library plus Wikipedia), sources picked by number so the model cannot invent a URL, a plan the person approves or corrects. Reason: the first runs started from a search page in the browser and were blocked (HTTP 418, CAPTCHA); search as data is reliable and visible.
- **Sub-agents with a check**: parallel scouts, a first look at each source (no model), fail-over, a token budget, and a verification that counts against what the page states.
- **Human in the loop**: take control of the live browser, CAPTCHA hand-over (never bypassed), result acceptance.
- **Files**: downloads with refusal of error pages, a viewer for PDF, CSV, JSON, text and images.
- **Interface**: a web workbench with settings; one-command start and a pre-flight check (`scoutskit check`).
- **Lessons recorded** in `project_process_report.md`: small models chose wrong methods because the tools hid the real page structure; the fixes were structural (finders, checks, budgets) and helped every model.

### Risks, updated
| Risk | State |
|---|---|
| R1 Real sites reject or stall Playwright | **Resolved for the tasks tried** (sih.gov.in, uktech.ac.in, ubter.in load and work). Some shops answer HTTP 403: recorded as findings, never bypassed. |
| R2 Locators unstable → replay fails | **Mostly resolved**: role + name + position recipes replayed on SIH and uktech; a changed page is reported as a finding. |
| R3 Parallel throttling not independent | **Still untested** (needs the profiles work). |
| R4 Quota/latency; synopsis requires a **mock mode** | Fallback chain exists. **A mock/cached model mode is not built.** |
| R6 Volunteer study | Not started. |
| R7 Time | The cut list in section 7 now matters: profiles, axe-core + keyboard and a report are the missing 40% items. |
| New: free metasearch is unofficial and fails now and then | Retries and notes; a search API key would make it dependable. |
| New: the two SIH 2025 mirrors disagree (101 vs 238) | The run takes the first whose total matches; stated openly. |

### Suggested next steps (ordered by value for the 40% scope and for the research question)
1. **Profiles + parallel replay** (~1–2 days): three profiles (desktop, low-end mobile, slow network) from Playwright CDP; replay one recipe in parallel isolated contexts; record time, failures and a comparison table. This also answers R3 and gives the "parallel vs sequential" measurement.
2. **axe-core + keyboard checks** (~1 day): inject axe-core into the replayed pages; a Tab-traversal check; findings into the same record.
3. **Unified report** (~1 day): JSON + Markdown/HTML per evaluation with evidence links (screenshots, steps, files).
4. **Benchmark site with injected faults** (~1–2 days): a small site (Docker or local) with 3–4 known faults so detection can be scored.
5. **Mock model mode** (~½ day): record and replay model answers so tests and demos run offline.
6. Then the semester-8 items: workflow discovery, custom profiles, replay agents, Hindi checks, comparison with Lighthouse / axe / scripted Playwright, the volunteer study.

### How to describe it honestly to the guide
"The agent half is working on real sites, with replay without a model and parallel sub-agents. The evaluation half (profiles, usability metrics, accessibility checks, report) is next and builds on the same session and recipe code; nothing in the design has to change."

---

## Progress log

| Date | Step | Result |
|---|---|---|
| 11-11 | **Step 0 cleanup** | **Done.** Backup taken first (source + config, no `.env`). Stagehand and 6 dependencies removed; provider layer simplified; zero Stagehand references left. `runs/` kept (gitignored). |
| 11-11 | **Step 2 browser + tools** | **Machinery done and tested.** `browser/` (Playwright session, safety policy), `tools.py` (registry of 12 tools), agent loop rebuilt. 13 tests pass, including an end-to-end run **with no LLM** that collected all 40 portal records through the hidden menu, dropdown and pagination. |
| 11-11 | Step 2 with a **real model** (first try) | Blocked: `nvidia_super` was congested (35–143 s for a 27-token prompt); `nvidia_bolt` wandered. |
| 11-13 | **Step 3 spike: code-writing extraction** | **Works.** IDE-style tools (`view`, `grep`, `run_python` in a `bwrap` sandbox, no network) on SIH's 3.1 MB HTML, **model never sees the page**. `nemotron-super`: 265/265 records, 100% of fields, twice (14 turns, ~20 s). `gpt-oss-120b` (Groq): 100% in 7 turns. `ernie` 88%, `qwen3.8-27b` 72%, local `bonsai-2` 0% (looped on grep). Peak prompt 3–9k tokens. |
| 11-13 | **Decision: LangChain + LangGraph, native tool calling, NVIDIA Nemotron primary** | JSON-in-prompt tool calls failed at the decisive step (model wrote its plan in `thought` but omitted `tool`). Agent rebuilt as a LangGraph (observe → decide → act → check), typed strict tool schemas, provider factory (`provider/chat.py`). **`nvidia_super` needs thinking ON**: wrong element 4/4 with it off, sensible 4/4 with it on. |
| 11-13 | **Step 2 accepted with a real model** | Portal task (hidden menu → Records → dropdown → pagination), `nvidia_super`: **4 of 5 runs completed 40/40** (9–13 steps); the 5th was reaching the right button when my 100 s limit killed it. Earlier, before the "untried controls" nudge: 2 of 3. 14 tests pass. Small sample: treat as "works", not "reliable". |

### Findings from Step 2 (keep: these shaped fixes)
- **Local models are out** for the brain on this hardware (RTX 3050 6 GB): `bonsai-2` (9B, 2-bit) loops; downloads of `qwen2.5-coder:7b`, `deepseek-r1:8b`, `ornith:9b` were cancelled by decision. Hosted: NVIDIA primary, Groq `gpt-oss-120b` fallback, Anthropic via API key as a demo-day option.
- A model that makes **tool calls natively** behaves far better than one asked to write JSON in text; tool arguments are now validated against strict typed schemas (unknown args are errors the model sees).
- **When an action repeats**, feedback lists the controls not yet tried. This turned the stuck case (searchbox clicked 3×) into 4 of 5 passes.
- **Vision** is a separate sub-agent: a `look(question)` tool that screenshots and asks a hosted vision model, returning a short text answer. The brain stays text-only. Not built yet.
- A **prompt rule is not a safety control.** The model typed `admin` into a username field despite "never log in". The `fill` tool now refuses login/personal-data fields in code.
- The **planner invented columns** (`id, name, status, created_at`). Fields now come from the page's own columns unless the user names them.
- Playwright's snapshot omits closed-menu items, so Stagehand's "hidden link" workaround is gone.
- A transient provider failure (HTTP 503) was cached for 24 h. Failures are now re-checked after 10 minutes.
- **Free hosted models are not a dependable brain** for 15–25 step runs (Gemini: 20 requests/day; NVIDIA 120B: queue delays; 4B: too weak).

---

## 1. How we work (approval gates)

Every step runs the same five stages. A step that fails its spike is replanned; it does not get built.

| Stage | What happens |
|---|---|
| 1. Question | What could make this step impossible? |
| 2. Spike | Smallest test (≤ 2 h) that answers the question. Results are written into this file. |
| 3. **Your decision** | Go / Change / Stop. Nothing is built before this. |
| 4. Build | Only what the step lists. |
| 5. **Acceptance** | A concrete pass/fail test. Your sign-off before the next step starts. |

**Why this limits rewrites:** layers talk through five small interfaces (section 4). If one layer
fails, only that layer is replaced, and the others do not change.

---

## 2. Current state (facts, not hopes)

### Built and tested
| Piece | Evidence |
|---|---|
| Provider layer: `scoutskit.toml` + `.env`, key checks, live model probe, fallback order, quota fail-fast | Offline tests + real keys; Google, NVIDIA verified. |
| Own LLM client (`provider/llm.py`): Google, Anthropic, OpenAI-compatible (incl. NVIDIA NIM, OpenRouter) | Real calls made. |
| Planner (`plan_task`) and explore loop with repeat detection and provider rotation | Ran end to end on `sih.gov.in` (Stagehand-based; must be re-based). |
| Run evidence: `actions.jsonl`, screenshots, `result.json/csv` | 4 runs on disk. |

### Proven by experiment (this week)
- Playwright 1.64 (Python) **needs no Node install**; it ships its own driver.
- `page.aria_snapshot(mode="ai")` gives `[ref=eN]` refs; `aria-ref=eN` locators click; hidden menu items are *not* listed.
- Network response **bodies** can be read (`response.json()`).
- CDP network + CPU throttling works on one context (400 ms / 50 KB/s / 4× CPU: page loaded in 1.3 s).
- `sih.gov.in/sih2026PS` raw HTML contains **all 265** problem statements (IDs 26001–26265, no gaps, 10 fields). A structural HTML parse gets them with **0 LLM tokens**.

### Disproven / learned the hard way
- LLM-driven screen scraping is the wrong tool for tables: best run got 100/265 rows with a 50-row gap and still reported "completed".
- Small model (`nemotron-3.5-bolt-e4b`) extracts 1 of 25 rows. `nemotron-3.5-super-vl-120b` works (≈5 s/call, 3/3 on the element-picking test).
- Free tiers do not sustain agent runs (Gemini: 20 requests/day; OpenRouter: no credits). A key being *valid* does not mean it has quota.
- A model being *listed* does not mean it is live (5 of 9 NVIDIA candidates were dead, degraded or timed out; Llama 3.3 70B is end-of-life).
- Stagehand's tree lists hidden elements (failed clicks); `act` demands a model even for concrete actions; Python 4.4 has no agent loop.

### Not tested yet (these are the open risks)
Parallel throttling independence · replay locator stability · axe-core injection · keyboard checks · Hindi/Devanagari checks ·
Docker benchmark sites · Lighthouse baseline · usability-metric study · **Playwright on real sites** (see risk R1).

---

## 3. Decisions already made

| # | Decision | Why |
|---|---|---|
| D1 | **Python 3.12 + Playwright** for the browser; own tool layer | Matches synopsis. Tested: snapshot, refs, network bodies, CDP. |
| D2 | **Drop Stagehand** (synopsis names it for exploration) | We use none of its LLM features; it adds an extension, a placeholder model and hidden-element bugs. **Disclose to your guide.** |
| D3 | Brain = our own provider layer; any provider can be used | Works under quota/outage conditions via fallback. |
| D4 | Extraction order: **JSON the page loads → embedded JSON → structural HTML record sets → rendered page + LLM** | Cheapest and most exact first. Validated on SIH. |
| D5 | The agent explores; **recipes replay without an LLM** | Core idea of the synopsis; makes conditions the only variable. |
| D6 | Respect `robots.txt` and site access policies; no evasion of bot detection | Synopsis §5.9. A site that rejects automation is reported, not circumvented. |

---

## 4. Target architecture and flow

```
CLI  (later: FastAPI portal)
  │
Orchestrator ── asyncio + semaphore, per-site cap, budget
  │   jobs = (workflow × profile)
  ▼
Run Agent ───► Brain: provider layer ──► LLM   (decides which tool)
  │
  ▼
Tool registry ──► Browser session  (Playwright context + CDP profile)
  │       snapshot · click/fill/select by ref · navigate · page_text · screenshot
  │       console_log · network_log(+bodies) · dialogs · extract_records · evaluate(guarded)
  ▼
Evidence: actions.jsonl · screenshots · trace · network/console logs
  ▼
Recipe compiler: agent actions → role+name locators + expected state
  ▼
Replay (no LLM) × profiles ──► Evaluators: functional · usability · axe-core/keyboard ──► Report
  └─ on failure: replay agents change ONE condition (Semester 8)
```

**Mode 1 (task):** instruction → plan → explore with tools → extraction strategy order (D4) → validate → CSV + evidence.
**Mode 2 (testing):** workflow → explore once → compile recipe → replay in N profiles in parallel → evaluate → report.

### The five interfaces (the blast-radius limiters)
1. **BrowserSession**: `goto, snapshot, click(ref), fill(ref,text), select(ref,opt), press, scroll, text, screenshot, console, network, close`. Nothing above it imports Playwright.
2. **Tool**: `name, description, input_schema, handler(session, **args)`. One registry feeds the JSON-action prompt, native tool calling, or an MCP server.
3. **Brain**: `decide(system, user) -> JSON`. Already built.
4. **Recipe**: JSON, versioned. Steps = intent + locator (role, name, context) + expected state/outcome.
5. **Evidence layout**: `runs/<id>/{actions.jsonl, screenshots/, trace.zip, result.json}`.

---

## 5. Can the synopsis be completed? (verdict per objective)

Verdict key: **Proven** (tested) · **Likely** (no known blocker, untested) · **At risk** (needs a spike or scoping).

| # | Synopsis objective | Verdict | Basis / what could go wrong |
|---|---|---|---|
| 1 | NL task → subtasks → tools → validate → output (Mode 1) | **Likely** | Plan + loop ran end to end. The validator was weak; the structural extractor fixes it (SIH 265/265). Needs re-basing on Playwright. |
| 2 | Playwright engine, bounded tools, structured record | **Likely** | Snapshot, refs, network and CDP proven on a local page. **Real-site loading is unresolved (R1).** |
| 3 | Explore once → recipe → replay | **At risk** | Not started. Refs (`e3`) are not stable across loads, so recipes must use role+name locators. Spike S2. |
| 4 | Automatic workflow discovery | **At risk** | Open-ended. Scope it: crawl links/forms, LLM proposes candidates, user picks; measure on benchmark sites. Semester 8. |
| 5 | Functional + usability + accessibility; difficulty metric validated experimentally | **At risk** | Functional and usability counts come from the action log. axe-core untested. **Validation needs human volunteers**, which is a logistics risk, not a coding one. |
| 6 | Predefined and custom profiles | **Likely** | Network, CPU, viewport, locale, offline are straightforward. Jitter and packet loss may need route delays; the synopsis already says "where supported". Verify in S3. |
| 7 | Hierarchical parallel orchestrator, replay agents, one-condition-at-a-time localisation | **At risk** | Parallel contexts are easy. **Independence of throttling across parallel sessions is unverified** (the synopsis itself lists this as a first task). Localisation accuracy depends on measurement noise. |
| 8 | Benchmarks with known faults, parallel vs sequential, vs Lighthouse / axe-core / scripted Playwright | **Likely** | Mostly effort (Docker sites). Lighthouse is a Node tool, so Node is needed for the baseline only (Node 26 is installed). |

### Synopsis §5.8: the 40% demo scope
| Item | Status |
|---|---|
| NL input + basic decomposition | Built (`plan_task`) |
| Controlled browser, DOM + accessibility-tree inspection | Re-base on Playwright (Step 2) |
| Record + replay a task as a recipe | Not started (Step 4) |
| Orchestrator, parallel isolated sessions | Not started (Step 5) |
| ≥ 3 environment profiles | CDP proven on one page (Step 5) |
| Basic functional testing + usability metrics | Not started (Step 6) |
| axe-core + keyboard checks | Not started (Step 6) |
| Screenshots, structured logs, unified report | Recorder exists; report not started (Step 7) |
| Controlled demonstration websites | Local test site drafted (Step 7) |

### Honest limits to state in the report
- The "screen-reader user" persona is an **approximation** (accessibility-tree-only, keyboard-only navigation), not NVDA/Orca.
- Hindi/Devanagari checks cover what is *measurable* (overflow/clipping, missing glyphs/fallback fonts); judging "correct" rendering is not automatable.
- Throttled runs are **simulations**, not physical devices (synopsis already says this).
- Conclusion: **completable** if we keep the synopsis's own 8th-semester split. Three items carry real risk: S3 (parallel throttling), the volunteer study, and workflow-discovery scope. The 20 Nov demo is tight but achievable with the cut list in section 7.

### Deviations from the submitted synopsis (to tell the guide)
1. Stagehand replaced by Playwright + our own LLM loop (evidence in section 2).
2. New extraction-strategy order (network/JSON/structural HTML before LLM).
3. Vision-capable models may be used later for visual checks; not committed.

---

## 6. Steps (each needs your approval to start and to finish)

Days are counted from 2026-11-11. Estimates are mine.

### Step 0 — Cleanup — **DONE (2026-11-11)**
Executed per section 8 (backup copy instead of a commit; `runs/` and default provider left as they were).

### Step 1 — Feasibility spikes (Nov 12) — kill-switch before any build
| Spike | Question | Pass | If it fails |
|---|---|---|---|
| S1 | Does Playwright load real sites? (SIH + 2 others, default launch, robots respected) | Loads, or a clear reason | Report as "not testable"; demo on our benchmark site; no evasion (D6). |
| S2 | Can a ref be turned into a locator that survives a reload and a re-render? | role+name round trip works on local site + 2 pages | Add context/text anchors; if still unstable, recipes record intent + fuzzy match. |
| S3 | Do 3 parallel contexts keep **independent** throttling? What does packet loss/jitter need? | 3 profiles measurably different and stable | Isolate by browser *process*, lower the concurrency cap. |
| S4 | Can axe-core be injected and a Tab-traversal check run? | Violations + focus order reported on the local site | Fall back to `@axe-core/playwright` via Node (documented). |
| S5 | `<select>`, iframe, DataTables/paged tables via snapshot+refs | Each works or has a known workaround | Add the specific tool or rule. |

**Approval:** [ ] Go  [ ] Change: ______

### Step 2 — Browser session + tool registry (Nov 13–14)
Build: `BrowserSession`, the tools in section 4, safety rules (domain allowlist, URL re-check before mutation, no login/payment/download, robots.txt), rebase the agent loop, remove Stagehand.
**Acceptance:** local site task completes with two different providers; `actions.jsonl` complete; no Stagehand import remains.

### Step 3 — Extraction + validator (Nov 14–15)
Build: `extract_records` (header tables, key-value blocks, card lists; raw response vs rendered DOM), header-driven fields, validators (unique IDs, no gaps, count vs page text, "Next" state).
**Acceptance:** SIH returns **265 unique rows, 0 gaps, 10 fields**, with no LLM extraction.

### Step 4 — Recipe record + replay (Nov 15–16)
Build: recipe v0 schema, compiler (refs → role+name), replay with no LLM, state/outcome assertions.
**Acceptance:** replay of an explored workflow reproduces the original outcome on the local site, 5/5 runs.

### Step 5 — Profiles + parallel orchestrator (Nov 16–17)
Build: 3 profiles (desktop, low-end mobile, slow network), semaphore cap, isolated contexts, equivalence check.
**Acceptance:** parallel and sequential runs report the same findings; time saved is recorded.

### Step 6 — Evaluators (Nov 17–18)
Build: functional (failed requests, page errors, duplicate submit), usability counts (steps, time, failures, backtracking), axe-core + keyboard.
**Acceptance:** each **injected fault** on the benchmark site is detected.

### Step 7 — Benchmark site + report (Nov 18–19)
Build: one Docker site with 3–4 injected faults; unified JSON + HTML report with evidence links.
**Acceptance:** one command produces the report from a clean run.

### Step 8 — Rehearsal (Nov 19–20)
Demo script, bug fixes, README with run instructions.

### After the demo (Semester 8, per the synopsis)
Workflow discovery (Jan) · custom profiles, personas, mid-request disconnect (Feb) · replay agents + Hindi checks (Mar) ·
benchmarks, Lighthouse/axe/Playwright baselines, volunteer study (Apr) · report and paper.

---

## 7. Risk register and cut list

| Risk | If it happens | Early test | Fallback |
|---|---|---|---|
| R1 Real sites stall or reject Playwright (SIH timed out in default launch; cause unknown) | Only target choice changes | S1 | Benchmark sites for demo; plain HTTP fetch for extraction; never evade bot checks. |
| R2 Locators unstable → replay fails | Recipe format changes | S2 | Role+name+context anchors. |
| R3 Parallel throttling not independent/noisy | Orchestrator isolation level | S3 | Process-level isolation; lower concurrency; report noise. |
| R4 LLM quota/latency | None (provider layer) | Key check + live probe | Fallback chain; **LLM response cache/mock mode** (synopsis requires a mock mode). |
| R5 Weak models mis-extract | None | Validators | Structural extraction; stronger model only for decisions. |
| R6 Volunteer study cannot be run | Objective 5 scope | Plan early | Report as exploratory, small n, with stated limits (synopsis already says not a standard). |
| R7 Time (9 days) | Demo scope | Daily check | **Cut list below.** |
| R8 Unsafe actions on real sites | Reputation/ethics | Rules in Step 2 | Destructive scenarios only on our own sites. |

**Cut list if time slips (in order):** HTML report → JSON + Markdown · usability metrics → raw counts only ·
keyboard checks → axe-core only · second provider test → one provider. **Never cut:** recipe replay, parallel profiles, injected-fault detection.

---

## 8. Step 0 cleanup list (not done yet)

Nothing is committed. Safest path: **commit a snapshot first**, so everything below stays recoverable. (I will only commit if you ask.)

| Item | Action | Reason |
|---|---|---|
| `pyproject.toml`: `stagehand>=4.4.0` | Remove, then `uv lock` | Dropped (D2). Removes browserbase, opentelemetry, websockets etc. |
| `src/scoutskit/browser.py` | Replace in Step 2 | Stagehand launcher + placeholder-model hack. |
| `agent.py`, `recorder.py`, `cli.py` | **Edit** in Step 2 (not delete) | Stagehand imports/calls; keep planner, prompts, repeat detection, provider rotation, `_merge`. |
| `provider/config.py`, `quick_test.py` | Simplify | `NATIVE_PREFIXES`, `CALLBACK_PREFIXES`, `needs_callback`, `CALLBACK_READY` only existed because of Stagehand. |
| `scoutskit.toml` | Edit | Remove Stagehand comments; decide on `nvidia_bolt` (failed extraction); set a default provider that has a key (currently `anthropic`, no key). |
| `runs/` (17 MB, 4 test runs) | Delete or keep 1–2 | Results are summarised in section 2; gitignored. **Your call.** |
| `.scoutskit/provider_status.json` | Leave | Regenerable cache, gitignored. |
| `README.md` | Write in Step 8 | Currently empty. |
| `Project_Synopsis_Invisible_Failure (2)-1.md` | Optional: move to `docs/synopsis.md` | Tidier name. |
| `.env` | **Do not touch** | Holds your keys. |

---

## 9. Decisions I need from you

1. **Snapshot commit first** before cleanup? (yes/no)
2. **Approve D2** (drop Stagehand) and tell your guide?
3. **Default provider for development:** `nvidia_super` (works, ≈5 s/call) or another key you can add?
4. **SIH policy:** use it only as a Mode 1 extraction example via plain fetch, and demo browser automation on our own benchmark site?
5. **Cleanup list** in section 8: approve as is, or change?
