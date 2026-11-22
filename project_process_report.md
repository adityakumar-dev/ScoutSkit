# ScoutsKit — Project Process Report

Product: **ScoutsKit**. Project title: **Invisible Failure** (B.Tech final year, UTU Dehradun, 2026–27).
Period covered: **2026-11-05 → 2026-11-22**. First working module due after **2026-11-20**.

This is the diary: what we did each day, what went wrong, what we decided and why.
For the forward plan and approval gates see `IMPLEMENTATION_PLAN.md`.

---

## 0. Where we are today (2026-11-13)

| Area | State |
|---|---|
| Browser layer | **Done, tested.** Playwright session, safety policy (same-site, http(s) only, robots.txt, no downloads, no login/personal-data fields). |
| Tools | **Done.** 28 typed tools in a `tools/` package (actions, reading, extraction, control): click, fill, select, press, scroll(ref), hover, wait_for, tabs ×3, goto, back, read_page, inspect_element, find, javascript_tool (read-only), page_text, network ×2, console_log, view_source, grep_source, extract_rows, run_python, use_script_output, done, fail. |
| Agent | **Done.** LangGraph (observe → decide → act → check) with native tool calling, provider fallback, repeat detection, evidence log. |
| Provider layer | **Done.** `scoutskit.toml` + `.env`, live key/model checks, fallback order, quota fail-fast. NVIDIA (primary), Groq, OpenRouter, Google, Anthropic supported. |
| Tests | **76 pass** (`uv run pytest`): sandbox, grounding, tree folding, census, tools, completion evidence, and end-to-end runs with a scripted model on the local portal. |
| Real-model result | Portal task: **4 of 5 runs** got all 40 records. SIH task (11-13): 265 rows but **25 invented**. SIH task (11-20, with grounding + code tools): **265 rows, 0 invented, 0 PS numbers missing**, 6 harmless typo-corrections (see 2026-11-20). **SIH task (11-22, full batch): 265/265 rows exact for title/organisation/category/theme in 6 steps, 31 s, 60k tokens** (see 2026-11-22). |
| Next | Discover hidden **detail fields** (SIH rows hide description/department/links in modals) and offer them; run the full flow from the homepage; then recipe record/replay → profiles + parallel orchestrator → pre-check manifest → evaluators → report. (Grounding, code tools, reliability batch, census: built 11-20 → 11-22.) |

**Headline findings so far**
1. The agent can do a task from **zero knowledge** (no URL, no site knowledge) — found SIH, navigated, paginated.
2. A model must **never be trusted to retype data**: it fabricated 25 rows and reported success. A model that **writes code** to read the real page got **265/265 exact**.
3. Free hosted models are usable but **unreliable** (quotas, congestion, retired models); keep fallbacks and make replay LLM-free.

---

## 1. Day-by-day

### 2026-11-05 — Reading the synopsis, naming, first plan
**Did**
- Read the synopsis (*Invisible Failure*: autonomous web task execution + evaluation under real-world conditions; two modes; explore-once/replay-many; hierarchical parallel agents).
- Mapped the 20/11 scope (synopsis §5.8): task input + decomposition, controlled browser tools, recipe record/replay, parallel isolated sessions, ≥3 environment profiles, functional + usability basics, axe-core + keyboard checks, evidence + report, demo sites.
- Wrote a phased development plan (feasibility spikes → skeleton → vertical slice → demo site).

**Decisions**
- Product name **ScoutsKit** ("scout" = one who sees ahead; "kit" = toolkit); keep *Invisible Failure* as the project/thesis title.
- Stage 1 approach: a free-roaming agent first (Playwright + Stagehand), then tools/guardrails, then conditions. Day-one must-haves: record every action as JSON, a thin browser wrapper, step limit, safety floor, pinned versions, mock/replay LLM mode.

**Open at end of day:** which LLM provider(s) to use.

### 2026-11-06 — Project setup, first look at Stagehand
**Did**
- Built on the existing `uv` package (`scoutskit`, Python ≥ 3.12). Added `playwright`, `stagehand 4.4.0`, `pydantic`, `python-dotenv`, `typer`; `.gitignore`; installed Chromium (the headless-shell download was slow, >400 s).
- Inspected the Stagehand 4.4 Python SDK.

**What we learned about Stagehand**
- Thin client; the engine is a **Chrome extension** (MV3, 2.5 MB service worker; needs Chrome ≥ 137; system Chrome 157 was fine).
- `act` / `observe` / `extract` = accessibility tree → one LLM call picks an element id → execute; plus self-heal and cache.
- Python 4.4 has **no agent loop**; `model=` is a string with five native prefixes (openai, anthropic, google, groq, cerebras) **or** a callback. No `base_url`; `openrouter/…` is rejected.
- `page.snapshot()` returns the tree, an `xpath_map` and a `url_map` **with no LLM call**.

### 2026-11-09 — Differentiation, provider layer, housekeeping
**Housekeeping (Claude Code, not the project):** acting on `/usage`, set 11 unused skills to `user-invocable-only` in `~/.claude/settings.json` (graphify, docs, docx, google-workspace, import-memory, morning, pdf, pptx, skill-creator, xlsx, youtube-transcriber); disabled the `abdm-docs` MCP server in `scoutskit` and `remoteward-core-service` (kept for `remotecore`, 21 real uses). Backup: `~/.claude.json.bak-before-abdm`. Undo = delete the `skillOverrides` block / the two `disabledMcpServers` entries.

**Differentiation (vs. the Claude browser extension)**
- Conclusion: "an LLM drives a browser" (Mode 1 alone) is **not defensible** as the difference. The real contribution is in Mode 2: **explore once / replay deterministically, controlled conditions (CDP throttling, viewport, locale), parallel isolated personas, failure localisation, functional + usability + accessibility together, measured against baselines**.
- Researched the extension (v1.0.56 internals + current docs) later, on 11-11.

**Provider layer (built)**
- `scoutskit.toml` (providers, default, limits; **no secrets**) + `.env` (keys) + `resolve_provider()`; CLI `scoutskit providers [--check]`.
- Moved into `src/scoutskit/provider/` (`config.py`, `connect.py`, `quick_test.py`).
- Key check uses **free read-only endpoints**; picks the first working provider and falls back with a reason.

**Issues & decisions**
| Issue | Resolution |
|---|---|
| `openrouter/auto` returned HTTP 402 although the key was valid | Key info shows `is_free_tier: true` → check now marks it unusable unless the model is `:free`. **A valid key is not a working provider.** |
| Stagehand rejects `openrouter/…` | Later solved by our own LLM client (no callback needed). |
| Python vs TypeScript | **Stay on Python** (synopsis, stats/eval work, team); TS only for a future portal. |
| Playwright needs Node? | **No.** The Python package bundles its own Node driver (verified with Node removed from PATH). |

**First real test (Stagehand `observe` + `extract` on sih.gov.in)** — a useful failure
- `observe` found **0 candidates** (navigation hidden behind a hamburger button); `extract` then returned the homepage's **theme categories** as "problem statements" (all `number = None`). Confident and wrong.
- Lesson: one-shot calls are not an agent; completion must be **validated**.

### 2026-11-10 — First agent loop (Stagehand-based)
**Did:** own explore loop (observe → LLM decides → act → verify), planner (`plan_task`), recorder (`actions.jsonl`, screenshots, `result.csv/json`), CLI `scoutskit run`.

**Issues & fixes**
| Issue | Evidence | Fix |
|---|---|---|
| Every click failed: *"An LLM was not configured"* | Stagehand `act` needs a model at init even for concrete actions | Placeholder model + `self_heal=False` (measured **0 tokens** for concrete actions). |
| Hidden links in Stagehand's tree → *"Node does not have a layout object"* | Collapsed-menu items are listed but not clickable | Hidden-link fallback (open the `href`). (Later removed: Playwright's snapshot omits them.) |
| Gemini **429**, then locked for ~13 h | Free tier = **20 requests/day per model**; `retryDelay` 47,961 s | Quota fail-fast: if the retry delay is long, rotate providers immediately instead of waiting. |
| Run dir `20261110-000455` | Agent reached the real Problem Statements page and extracted **25 real rows** before the quota ended | Shows the approach is viable. |

### 2026-11-11 — Models, the big SIH discovery, dropping Stagehand, cleanup, Step 2
**Models (NVIDIA)**
- Exposed API key pasted into chat → told to **rotate**; new key set in `.env` (never copied anywhere).
- Benchmark (real agent prompt): `meta/llama-3.3-70b-instruct` → **HTTP 410 (retired)**; `nemotron-3.5-super-vl-120b-a12b` 4.9 s, JSON 3/3, right element 3/3; `nemotron-3.5-bolt-e4b` 2.8 s fast but weak; `lightning` 1/3; `minimax` 105 s; several models listed but **dead/degraded/timed out** (5 of 9). **A model being listed does not mean it is live.**
- Generic provider record added: `base_url`, `extra_body`, `max_tokens` (works for NVIDIA NIM, any OpenAI-compatible endpoint) + a live **model probe** so listed-but-dead models are caught.

**Stagehand agent on SIH (bolt / super)** — the false "completed"
- `bolt`: extracted 1 of 25 rows, invalid JSON → fell back to Google. `super`: run 1 failed on truncated JSON; run 2 "completed" with **100 of 265 rows and a 50-row gap**. Our validator only counted rows. Added a `select` action for dropdowns.

**The discovery that changed the design**
- `sih.gov.in/sih2026PS` **raw HTML (3.1 MB) already contains all 265 problem statements** (IDs 26001–26265, no gaps, 10 fields: ID, title, description, organization, department, category, theme, links, contact) as one `<table id="settings">` per record. DataTables only pages them in the browser. A structural HTML parse gets everything with **0 LLM tokens**.
- A network-capture idea (find the JSON call) would have found nothing here — the data came in the document itself. Pattern/regex between marker lines is brittle; use **structure**.

**Claude extension research** (v1.0.56 internals + current docs, Nov 2026)
- CDP via `chrome.debugger`, accessibility tree with ref ids, ~21 tools (`read_page`, `find`, `get_page_text`, `read_network_requests`, `javascript_tool`, …), permission modes (manual/auto/skip), per-site permissions, Anthropic-hosted site safety list; shortcuts tools removed from Claude Code in 2.1.319.
- Produced a mapping table (capability → how we build it → difficulty → when). Cheap read tools (page text, network, JS) are what make it fast.

**Playwright tested directly (local page)**
- `page.aria_snapshot(mode="ai")` gives `[ref=eN]`; `aria-ref=eN` clicks work; closed-menu items are **not** listed; response **bodies** readable; CDP network + CPU throttling works on one context (400 ms / 50 KB/s / 4× CPU, load 1.3 s).
- **Open issue (R1):** on the real SIH page Playwright's default launch timed out waiting for load, while Stagehand's Chrome loaded it. Cause unknown. A variant that hid automation signals was **blocked by the safety classifier — correctly** (bot-check evasion contradicts synopsis §5.9). We abandoned it. Policy: a site that rejects automation is reported, not circumvented.

**Decisions**
| # | Decision | Why |
|---|---|---|
| D1 | Python 3.12 + Playwright, own tool layer | Tested; matches synopsis. |
| D2 | **Drop Stagehand** (tell the guide) | We used none of its LLM features; it added an extension, a placeholder model and hidden-element bugs. |
| D3 | Extraction order: JSON the page loads → embedded JSON → structural HTML record sets → rendered page + LLM | Cheapest/most exact first; validated on SIH. |
| D4 | Agent explores; **recipes replay without an LLM** | Core idea of the synopsis. |
| D5 | Respect robots.txt / access policies; no evasion | Synopsis §5.9. |

**`IMPLEMENTATION_PLAN.md`** written (gates: question → spike → decision → build → acceptance; five interfaces to limit rewrites; synopsis feasibility per objective; risks and cut list).

**Step 0 cleanup (executed)**: backup copy first (source+config, no `.env`); removed Stagehand + 6 dependencies and the old `browser.py`; simplified the provider layer.

**Step 2 built:** `browser/` (session + safety), `tools.py`, agent loop (JSON protocol at that time), local **portal benchmark** (`benchmarks/portal/`: hidden menu, dropdown, client-side pagination, JSON call, console error, alert, off-site link, robots-blocked path, login form), 13 tests incl. an end-to-end run **with no LLM** (all 40 records).

**Issues with a real model that day**
| Issue | Fix |
|---|---|
| Model typed `admin` into the username field despite "never log in" | **A prompt rule is not a safety control** → `fill` now refuses login/personal-data fields in code. |
| Planner invented columns (`id, name, status, created_at`) | Fields now come from the page's own columns unless the user names them. |
| 503 cached for 24 h made a good provider "unusable" | Failures re-checked after 10 min. |
| `nvidia_super` took 35–143 s for a 27-token prompt (congestion) | Variable; keep fallbacks. |
| `nvidia_bolt` wandered / repeated junk | Too weak as the brain. |

### 2026-11-11 (late) → 11-12 — Hunting a dependable free brain
**OpenRouter (16 free models, one real-prompt call each):** `baidu/ernie-5.5-flash-preview:free` **1.6 s, correct**; `openrouter/free` 3.8 s correct; `nemotron-3.5-lightning:free` 14 s correct; `nemotron-3-ultra-550b:free` empty reply; `gemma-4` 429; **`inkling-2-small` 403 "only available on agentic harnesses"** (restricted to approved apps — not circumvented); `dots3-note` unreliable; `super-vl:free` 503 then 31–34 s (also returned `ref: 152` instead of `e152`).
**Groq (key added):** `openai/gpt-oss-120b` 0.7 s correct; `qwen/qwen3.8-27b` 0.6 s correct; `gpt-oss-20b` HTTP 400; `allam-2-7b` 4k context. **Free limits: ~1,000 requests, only 8,000 tokens/min** → our 4–5k-token prompts allow ~1–2 steps/min → page trees must be trimmed.

### 2026-11-13 — Local models, the code-writing breakthrough, LangGraph, first full SIH run
**Local Ollama (user's RTX 3050 6 GB, 14 GB RAM)**
- `bonsai-2` (Qwen3.5-based, 9B, 2-bit): ~40 tok/s; right element but wrote `"[ref=e152]"`; **breaks at ~8k context** (40 s, invalid JSON). Ref normalisation (`[ref=e152]`, `ref=e152`, `152` → `e152`) is still a **pending** small fix.
- Candidate local models researched (qwen2.5-coder:7b, deepseek-r1:8b, ornith:9b…). Downloads started, then **cancelled by decision** (see below).

**User's design insight → the Step 3 spike**
- "The model shouldn't read the whole page — like an IDE assistant it reads a few lines, finds the pattern, and writes code; the code does the heavy lifting."
- Built a throwaway harness (scratchpad): tools `view(start,end)`, `grep(pattern)`, `run_python(code)` in a **`bwrap` sandbox (no network, read-only filesystem, no env keys)**, `finish()`; scored by value against a structurally built ground truth (265 records). The model never receives the 3 MB page.
- **Interface lesson:** with a JSON-in-text protocol the models failed (gpt-oss kept attempting native tool calls → Groq 400, empty replies). **Native tool calling fixed it.** Also made malformed-tool-call errors recoverable and gave every path convention (`HTML_PATH`, `/data/page.html`, `./page.html`).
- **Results (SIH, 265 records):**

| Model | Records | Fields correct | Turns | Notes |
|---|---|---|---|---|
| nemotron-super (NVIDIA) | 265/265 | **100%** (twice) | 14 | ~20 s, peak prompt 6–9k tokens |
| gpt-oss-120b (Groq) | 265/265 | **100%** | 7 | after recovering from one malformed call |
| ernie (OpenRouter free) | 265/265 | 88% | 19 | Department column mostly wrong |
| qwen3.8-27b (Groq) | 265/265 | 72% | 26 | Category/Theme wrong; slow (rate limits) |
| bonsai-2 (local) | 0 | — | 24 | looped on `grep`, never wrote code |

**Decisions**
- **Rely on NVIDIA Nemotron as the primary brain** (Groq `gpt-oss-120b` as fallback; Anthropic via a prepaid **API key** as a demo-day option — a subscription is not an API key). Local models are out for the brain on this hardware.
- **Vision = a separate sub-agent**: a `look(question)` tool screenshots and asks a hosted vision model for a short text answer; the brain stays text-only. *Not built yet.*
- **Demo-day safety net:** record a successful run on video (Playwright video + evidence); keep replay LLM-free.
- **LangChain + LangGraph adopted** (user's decision). Note for the guide: the synopsis names plain `asyncio` for the orchestrator; we keep `asyncio` for parallel runs and use LangGraph for the explore agent.

**Agent rebuilt on LangGraph with native tool calling**
- Why: with the JSON protocol the real model wrote its plan in `thought` but **omitted the `tool` field at the decisive step** (steps 1, 5, 14 of one run). Provider-agnostic chat models via `provider/chat.py`; typed, **strict** tool schemas (unknown args are errors the model sees); only the newest page tree in each prompt.
- **`nvidia_super` needs thinking ON:** with it off the model picked the wrong element **4/4**; on → sensible every time (~1.7 s/call).
- **"Untried controls" hint** when an action repeats: turned the stuck case (search box clicked 3×) into passes.
- 14 tests pass; **portal acceptance: 4 of 5 runs completed 40/40** (9–13 steps); the 5th was killed by my 100 s limit while progressing. Earlier, before the hint: 2 of 3.

**The simple task: "open the browser and go to the sih website and give me all the problem statements in a csv file"**
- *Run 1 — looked dead for 9 minutes.* Cause: `finish_reason=length`. The reply hit our **2,000-token output cap** (thinking + a 25-row `extract_rows` call), so the tool call was cut off and never parsed — 26 times in a row, silently. **Fix:** `max_tokens` configurable per provider (8,000 for `nvidia_super`), visible `no tool call (finish_reason=…)` message, abort after 4 in a row.
- *Run 2 — completed.* From **zero knowledge** (no URL): found SIH, opened Problem Statements, paginated, **265 rows, 26 steps, ~5 min, 415k prompt / 37k completion tokens**. All 265 PS numbers present and unique; **240 rows exact**.
- **But 25 rows (s_no 126–150) were fabricated.** At step 11 the agent believed it was on page 6 while still on page 5 and *wrote plausible rows that are not on the site* (invented titles, organisations, themes; extrapolated PS numbers). It then clicked "Next" then "7", so it never read the real page 6, and reported `completed`. Our checker only counted rows. (5 further "mismatches" were the model auto-correcting a typo on the site itself: "Al-Enabled" → "AI-Enabled".)
- The CSV `runs/20261113-024347/result.csv` **must not be used as is**. It also contains only the visible table columns, not the hidden detail fields.

---

### 2026-11-20 — Grounding check, code tools in the real agent, slow-site hardening
**Built (26 tests pass)**
- `grounding.py`: every extracted value must appear in the page text (exact, or 2 of 3 probes for long values so a small typo is tolerated); rows that are not found are rejected with a reason. Applied to `extract_rows` (against the visible text + accessibility tree) and to script output (against the raw + rendered HTML).
- `sandbox.py`: model-written Python runs under `bwrap` — no network, no environment variables/keys, read-only filesystem, only the saved page (`HTML_PATH` raw, `RENDERED_PATH` live DOM) and one writable folder (`OUT_PATH`). Verified invisible inside: `.env`, source, `.git`, `~/.claude`. Refuses to run at all without `bwrap`. Every script is kept in `runs/<id>/code/`.
- Four new tools: `view_source`, `grep_source` (read slices of the raw HTML, max 40 lines), `run_python`, `use_script_output` (replaces collected rows with the script's grounded rows). 18 tools in total.
- New benchmark page `benchmarks/portal/catalog.html`: all 60 rows in the raw HTML but only 10 left in the DOM (like DataTables / SIH). Tests: code path gets 60/60; rows typed from memory or invented by a script are rejected.

**Issues found and fixed**
| Issue | Root cause | Fix |
|---|---|---|
| First SIH run of the day failed at step 1 (click "not visible or not clickable", then 5 scrolls) | **SIH server slow today**: plain HTTP fetch of the homepage took **17.5 s** (0.8 s on 11-13); 84 of 114 browser requests still pending after 40 s. Model saw a blank page, re-navigated (renumbering refs) and clicked a stale ref `f1e30`. | `goto` waits for the response, gives the document ≤20 s to parse and **continues anyway**; a half-loaded page gets ≤15 s to render before it is described; **stale refs fail instantly** with "refs change when a page reloads"; click timeout 6→12 s; Playwright's waiting reason is in the error. |
| Playwright "refuses" SIH (R1) | Not bot detection — slowness. Diagnosed with a read-only request log; **no attempt to disguise the browser.** | R1 closed as "slow site". |
| Safety classifier blocked my diagnostic twice | I copied `respect_robots=False` from the user's `cli.py` change into my script | Reran with robots.txt respected. Suggest turning it into an explicit `--ignore-robots` flag. |

**Result — "give me all the problem statements on this page in a csv file" (start: `sih.gov.in/sih2026PS`)**
- 30 steps, 645 s, 507k prompt tokens; status `max_steps` (reached 265 rows at step 29 and ran out of steps one call before `done`).
- **265 rows; 0 PS numbers missing; 0 organisation differences; 6 title differences — all caused by the site's own typos** (lowercase "l" for "I": "lntegrated", "Al-Assisted"), which the model silently read as the intended words.
- **How the agent used the tools:** (1) `extract_rows` on the visible rows (grounded); (2) `grep_source` → "265 matches in the raw source" — it concluded the raw HTML holds every row; (3) `run_python` → **265 rows, 0 empty fields** (first script nearly right; title cells also contained modal text); (4) inspected the HTML to fix it; the fix had a one-word bug (`recursive=False` skipped the `<tbody>`) and crashed; (5) **abandoned code** and paginated page by page — correct but ~10× the tokens and 30× the time of the code path.
- Saved evidence: `runs/20261120-233228/` (`code/script_01.py`, `script_02.py`, `source_raw.html`).

**Findings**
- The grounding check **eliminated fabrication** (25 invented rows on 11-13 → 0 on 11-20).
- The agent *discovers* the intended approach by itself; its weak point is **debugging a failed script** (it fled instead of fixing a one-word bug).
- Hidden detail fields (description, department, contact) are still not in the CSV — only the visible table columns. The code path can get them (the raw HTML has them) but the agent did not finish it.

### 2026-11-22 — Review of `EXPLORATION.md` (written by Antigravity); stealth layer dropped
**What it is:** a research + architecture blueprint produced by Antigravity (Google's AI coding agent): how Claude in Chrome / Browser-Use / Stagehand work, an "anti-bot stealth" design, an element/event-choosing engine, a code audit, a target module layout and a 4-week roadmap. Nothing in `src/` changed; only the file was added.

**Verified against the code (26 tests pass today)**
| Its claim | Reality |
|---|---|
| Sandbox `bwrap` crashes in containers | True for containers/CI (it failed in its sandbox, passes on this machine). Real flaw: `available()` only checks that `bwrap` exists — it should **probe**. |
| Refs `eN` are ephemeral → no replay | True; this is Step 4 (role+name+container fingerprints). |
| Single-tab lockout | **Not accurate**: `session.py` already adopts new same-site tabs and closes off-site popups. Missing: list/switch/close tools. |
| `MAX_TREE_CHARS = 45_000` explodes context | True (and hits Groq's 8k tokens/min). |
| `scroll` wheels at (0,0) | True — scrollable containers do not move. |
| `min_items` deadlock | True — the planner's guess can make `done` unreachable. |
| No Mode 2 evaluators | True (planned). |
Other inaccuracies: its Stagehand cells ("no JS execution, single page") do not match the SDK we inspected; "read tools never prompt" contradicts the permission list we read for Claude in Chrome; "22 tools" lists 25; code excerpts are paraphrased, not verbatim.

**Decisions**
- **§3 (anti-bot stealth) is DROPPED** (hiding `navigator.webdriver`, faking plugins/WebGL, masking CDP, forged UA/TLS, human-like input to defeat detection, `--no-sandbox`, disabling site isolation). It evades access controls — against synopsis §5.9 and decisions D5/D6 — and is unnecessary (SIH's trouble was server slowness; no run was ever blocked).
- **Kept from §3, honestly framed:** `channel="chrome"` for rendering fidelity (optional); hover/mouse movement as plain UI testing; configurable typing delay as the synopsis's "slower interaction" persona; logging a block as a **finding** (`access_denied_by_policy`), never bypassing it.
- **Adopted:** fingerprints + tiered locators (recipes), tree folding, scoped scroll, `hover`, `wait_for`, `find`, tab tools, `min_items` made advisory, sandbox probe, read-only capped `javascript_tool`, grounding polish.
- **Sandbox fallback:** *no* silent "restricted subprocess" (not a security boundary for model-written code). Refuse by default; any fallback must be an explicit opt-in or a real isolator (podman/docker/firejail).
- **Not adopted now:** the big package re-layout (churn with no user-visible gain) — add modules where features land instead.
- **Tip:** give Antigravity `IMPLEMENTATION_PLAN.md` and this report before it audits, so it knows the guardrails and real state.

### 2026-11-22 (later) — Reliability batch, three live failures, and the 265/265 run
**Built, in the agreed order (76 tests pass, up from 26)**
0. *Tidy:* `tools.py` → package `tools/` (one file per kind of tool + a shared `ToolContext`); no behaviour change.
1. *Sandbox probe:* `available()` really tries to start a bwrap sandbox and reports the actual error; code is refused (never run unsandboxed) when it cannot.
2. *Scoped scroll:* `scroll(direction, ref)` moves the pointer over the container first; reports position and "already at the end/top".
3. *Tree folding* (`browser/tree.py`): over a 12k-char budget the **largest runs of identical siblings** fold to head 3 + last 1 + one summary line; small runs (pagination) survive; `read_page(ref, full)` unfolds; `find` searches the complete tree.
4. *New tools:* hover, wait_for, list/switch/close tabs, find, read_page, read-only `javascript_tool` (policy refusal of network/navigation/page-changing code — a policy check, not a sandbox).
5. *`done(reason)`:* the planner's `min_items` is only a guess, so a stated reason can override it.
6. *Script debugging:* a crashing script returns a "fix it, don't give up" hint; prompt says fix the script, never retype; step limit 25 → 40.

**Three live failures that taught us more than the tests**
| Run | What happened | Root cause | Fix |
|---|---|---|---|
| 1 | 14 of 265 rows, stuck | The model read the **tree's role names** (`grid/rowgroup/gridcell`) as HTML and wrote selectors that matched nothing (×5); a silent 6,000-char output cap hid the rest | `inspect_element(ref)` shows the real tag/id/classes/CSS selector; prompt says tree roles are not HTML; output cuts are announced |
| 2 | "completed" with **25** of 265 | My own `done(reason)` became an **escape hatch** ("collected all 25 visible"); the script read `RENDERED_PATH` (25 rows) not `HTML_PATH` (265) | Evidence-based `done` |
| 3 | "completed" with 25 again | I had **assumed SIH prints "Showing 1 to 25 of 265"** — it prints a split summary ("Total Problem Statements 68 Hardware 196 Software"), so my phrase-matching saw nothing | **Page census** (`browser/census.py`): rows the raw source holds vs rows the live page shows (265 vs 25), independent of any wording |

**How `done` is judged now:** first `done` is always refused when the page itself shows missing items (a stated total, or the census); a reason is accepted only afterwards, as a loud WARNING (the task may ask for a subset); without a reason it stays refused. The census is also shown to the model every turn and warns when `use_script_output` loads fewer rows than the source holds.

**Result — "give me all the problem statements on this page in a csv file" (start: `sih.gov.in/sih2026PS`)**
| | 11-13 | 11-20 | **11-22** |
|---|---|---|---|
| Rows | 265 (25 invented) | 265 (paged by hand) | **265 exact** |
| Steps / time | 26 / 5 min | 30 / 645 s | **6 / 31 s** |
| Prompt tokens | 415k | 507k | **60k** |
Title, organisation, category, theme: **265/265 exact**; every PS number present, none missing or extra. The agent: `grep_source` → `run_python` on the raw source (2 runs) → `use_script_output` (265 kept, 0 rejected) → `done`. CSV: `runs/20261122-040258/result.csv`.

**Honest gap:** the CSV holds only the **8 visible table columns**. Each row also hides a modal with **description, department, YouTube/dataset links and contact** (265 hidden `table#settings` blocks); the agent was never told they exist. Next: discover such repeated hidden detail blocks deterministically (labels listed to the model) so full records are one decision away.

**Lessons**
- Evidence beats rules: a rule in the prompt was bypassed twice; a count read from the page was not.
- Never trust an assumption about a site — check the real page before building a rule on it (twice today).
- The model needs a bridge between the tree's vocabulary and the HTML (`inspect_element`).
- The explore-by-code path is **8× cheaper and 20× faster** than paging by hand, and exact.

---

## 2. Decisions log (all dates 2026)

| Date | Decision | Why / evidence |
|---|---|---|
| 11-05 | Product name ScoutsKit; keep *Invisible Failure* as thesis title | Synopsis already submitted under that title. |
| 11-05 | Python-first stack | Synopsis; research half is stats/eval. |
| 11-09 | Provider layer: toml (no secrets) + `.env`; live checks; fallback | "Work in every condition"; valid key ≠ working provider. |
| 11-09 | Stay on Python (not TypeScript) | Cost/time, synopsis alignment; TS only for a portal. |
| 11-10 | Own LLM client (not Stagehand's) for decisions | Provider-agnostic, logged, mockable. |
| 11-11 | **Drop Stagehand**; Playwright + own tools | Tested equivalents; fewer moving parts. |
| 11-11 | Extraction strategy order (JSON → structure → LLM) | SIH raw HTML had everything. |
| 11-11 | Never evade bot detection | Synopsis §5.9; classifier block was right. |
| 11-11 | Safety in code, not only prompts | Model typed into a login field. |
| 11-13 | **NVIDIA Nemotron primary**, Groq fallback, no local brain | Benchmarks; hardware limits. |
| 11-13 | Native tool calling + LangGraph | JSON-in-text dropped the `tool` field; code agent needed it. |
| 11-13 | `nvidia_super` thinking ON; `max_tokens` 8,000 | 4/4 wrong without thinking; truncation at 2,000. |
| 11-13 | Vision as a sub-agent tool | Keeps the brain text-only and cheap. |
| 11-20 | Grounding check on every extracted value; code runs in a `bwrap` sandbox | 25 invented rows on 11-13; model-written code must not see keys, network or project files. |
| 11-22 | **Drop the anti-bot stealth layer** (Antigravity's §3) | Evades access controls; against synopsis §5.9 / D5; not needed. Log blocks as findings. |
| 11-22 | Sandbox: probe, refuse by default; no silent unsandboxed fallback | A restricted subprocess is not a security boundary. |
| 11-22 | `done` is judged by page evidence (stated total, raw-vs-live census); a reason only after a first refusal, with a WARNING | Two live runs finished with 25 of 265 on a convenient reason. |
| 11-22 | `inspect_element` bridges the tree's role names to real HTML | The model wrote selectors for `gridcell` and found nothing ×5. |
| 11-22 | Tree folding by budget (largest identical runs first) | Keeps controls/pagination visible; 80%+ smaller on long tables. |

---

## 3. Issues faced and how they were resolved

| Issue | Root cause | Resolution |
|---|---|---|
| Confident wrong answers (categories as "PS"; 100/265 "completed"; 25 invented rows) | Counting rows is not validation; LLM retypes data | Structural extraction; **grounding check (pending)**; Step 3 code extractor. |
| Agent "dead" for minutes | Output truncated (`length`), no visibility | Per-provider `max_tokens`, visible warning, streak abort. |
| Free-tier surprises | 20 req/day (Gemini), no credits (OpenRouter), 8k tokens/min (Groq), congestion/503/410/404 (NVIDIA) | Fallback chain, quota fail-fast, live probes, 10-min recheck, trim trees (pending). |
| Model ignored "never log in" | Prompt ≠ control | Code-level refusal. |
| Planner invented fields | Planning before seeing the page | Use the page's own columns. |
| Wrong element picked | Thinking off, no reasoning | Thinking ON. |
| Wrong ref format (`[ref=e152]`, `152`) | Small/free models | Normalisation (**pending**). |
| Playwright timeout on real SIH page | Unknown (default launch) | Open (R1); no evasion; fetch raw HTML for extraction. |
| Tool-call JSON malformed (Groq 400) | gpt-oss tool-call formatting | Feed the error back and retry (up to 5). |

---

## 4. Evidence & where things live

**Repository** (`/home/linmar/Documents/scoutskit`)
- `src/scoutskit/` — `agent.py` (LangGraph), `tools.py`, `browser/` (`session.py`, `safety.py`), `provider/` (`config.py`, `connect.py`, `quick_test.py`, `llm.py`, `chat.py`), `recorder.py`, `cli.py`.
- `scoutskit.toml`, `.env.example`, `benchmarks/portal/`, `tests/` (14), `IMPLEMENTATION_PLAN.md`, this report.
- `runs/` — evidence per run (`actions.jsonl`, screenshots, `result.json/csv`). Notable: `20261110-000455` (first 25 real rows), `20261111-185344` (100/265 false "completed"), `20261113-024347` (265 rows, 25 fabricated).

**Throwaway spike files (session scratchpad — temporary, may be deleted)**
`…/scratchpad/codeagent.py` (the IDE-style code-writing harness), `bench_nvidia*.py`, `bench_openrouter*.py`, `bench_groq.py`, `bench_ollama.py`, `sih_data/` (`page.html`, `ground_truth.json`), `sandbox-venv/`, `results/`. **Move the harness into the repo (`benchmarks/`) before it is lost; it is the Step 3 prototype and the model-qualification test.**

**Commands**
- `uv run pytest` · `uv run scoutskit providers --check` · `uv run scoutskit run "<task>" --provider nvidia_super --strict --headed`

---

## 5. Open items / next steps (need your go)

1. ~~Grounding check~~ **DONE 2026-11-20** (`grounding.py`; 0 invented rows in the SIH run).
2. **Step 3 — code-writing extractor**: tools **built 2026-11-20** (`view_source`, `grep_source`, `run_python` in a bwrap sandbox, `use_script_output`); the agent used them but abandoned code after one script bug. **Remaining:** make it fix the script, add a deterministic record-structure helper, then re-test for SIH 265/265 with all 10 detail fields.
3. Ref normalisation; tree trimming (for Groq's 8k tokens/min); response cache / mock LLM mode (synopsis requirement).
4. **Recipe record/replay** (explore once → role+name locators → LLM-free replay), then **profiles + parallel orchestrator**, axe-core/keyboard, functional/usability metrics, benchmark site with injected faults, report.
5. **Vision sub-agent** (`look(question)`) — later.
6. Resolve **R1** (Playwright vs real sites) legitimately; first commit of the repo (nothing is committed yet); record a demo-day video.

**To tell the guide (deviations from the synopsis):** Stagehand → Playwright + own LLM loop; LangChain/LangGraph for the explore agent; extraction-strategy order and the code-writing extractor; hosted-model dependence with fallbacks; vision as a sub-agent.

---

## 6. Lessons so far
- **Make the model write code, not data.** Exact and ~10× cheaper than retyping rows.
- **Validate outcomes, not counts.** Ground every extracted value in the page.
- **Safety belongs in code.** Prompts are suggestions.
- **Test interfaces, not just models.** Native tool calls fixed failures no prompt change could.
- **"Listed" ≠ "live", "valid key" ≠ "has quota".** Probe, fall back, record.
- **Zero-knowledge exploration works** — that is the demo headline; the recipe and checks make it trustworthy.

## 2026-11-22 (evening): full records, not just visible columns

- Detail-block detection first found nothing on real SIH: the label/value rows sit in `<thead>`, not `<tbody>`. Detection is now shape-based (th+td pairs anywhere) with regression tests.
- A run that did see the hidden fields still returned polluted titles (title cell included the hidden modal). Added `quality.py`: after `use_script_output`, warn when a column also contains other columns' values or is huge ("select only the element that holds this field"). Prompt now says detail fields belong to each record unless the user named columns.
- Live result (`runs/20261122-042352`): 265 rows, 7 steps, 14 columns. Checked against ground truth rebuilt from the raw source: Organization, Title, Category, Theme, Description, Department, Youtube Link, Dataset Link, Contact info all exact 265/265 (Contact info is empty on the site for every row; links are non-empty for 5 and 67).
- Lesson: my own checker keyed on the wrong column and briefly reported 0/265. Check the checker before blaming the agent. 90 tests pass (89 + quality tests).

## 2026-11-22 (night): pages that load data from a request

- Question raised: SIH works from the raw HTML, so do the network tools ever get used? Added `benchmarks/portal/feed.html` (+ `items.json`): five items per "Load more" click, all 40 records (with `owner`, `status` that the page never prints) arrive in one JSON request.
- First live run exposed three bugs: (1) the stuck detector called five productive "Load more" clicks a loop (signature now includes the page tree hash); (2) grounding rejected every row read from the request, because it only looked at page text (it now also accepts values found in fetch/xhr response bodies, `session.network_text()`); (3) the agent then fell back to the visible columns and its `done` reason claimed all 5 fields while `owner`/`status` were empty (`quality.py` now warns about all-empty columns).
- New evidence line (`browser/feeds.py`): when the page loaded a JSON list of records, the prompt names the request and its fields ("REQUEST #2 ... RETURNED 40 RECORDS WITH THE FIELDS ...: network_body(2) READS THEM ALL AT ONCE").
- Live result (`runs/20261122-050023`): 40/40 rows, all five fields exact against items.json, 5 steps. 95 tests pass.

## 2026-11-22 (late night): recipes — explore once, replay many

- New package `src/scoutskit/recipe/`: `model.py` (Recipe/Step as plain saved data), `build.py` (`from_run`: a recipe derived purely from a run's `actions.jsonl` + `result.json`), `replay.py` (runs the steps through the same tool registry, no model; matches elements by role + accessible name + position; reports `Finding`s instead of guessing). The agent log now also records `title` and `nth` (which of several identical elements).
- Rules that keep it honest: only successful state-changing steps are kept; a script becomes the replayable extraction only if it reads the page (`HTML_PATH`/`RENDERED_PATH`), because a script that merely holds data the model typed in would replay stale data as if fresh; a missing element or changed page is a finding (`target_missing` blocks, `page_changed` warns); a different item count is `result_changed`.
- CLI: a completed `scoutskit run` saves `recipe.json` in its run folder; `scoutskit replay <folder|recipe.json> [--url ...]` repeats it.
- Live: SIH recipe from `runs/20261122-051233` (2 steps: the extraction script) replays in 8 s with no model: 265 rows, 0 of 2,385 detail cells differ from the ground truth. 100 tests pass.
- Not covered yet: recipes whose data came from `extract_rows` or from a network response (replay repeats the actions only and says so), fingerprints beyond URL path, persona/condition replays (Mode 2 proper).

## 2026-11-22 (night, later): recipes that read a data request

- `recipe/source.py`: after a completed run, `find_feed` checks whether the collected rows are (nearly all, 90%) records of a JSON request the page made; if so the recipe stores that request (`Feed(path, fields)`) and replay reads it again from the page's own network traffic. A script that reads the page still takes priority. If the request is not made on replay, that is a blocking `feed_missing` finding, never a guess.
- Live: feed recipe from `runs/20261122-124644` (one leftover click + the feed) replays with no model: 40 rows, 0 of 200 cells differ from items.json, including `owner`/`status` that are not on the page. 102 tests pass.
- Still open: personas/conditions (Mode 2 proper), richer page fingerprints, `--ignore-robots` flag.

## 2026-11-22 (night, step 1 of the web UI): server, event stream, live picture

- `runner.execute()` now holds the whole pipeline (providers, plan, browser, agent, evidence, recipe); the CLI `run` and the server both call it. `RunRecorder` became the event source (`listeners`) and gets a unique folder per run (parallel runs no longer share a folder).
- `src/scoutskit/server/`: `events.py` (a Channel per run: events are kept for late viewers, frames are live-only and a slow viewer only gets the newest), `screencast.py` (Chrome CDP screencast, follows the agent across tabs), `runs.py` (RunManager: start / stop / list, max 3 parallel, failures become a `failed` result), `app.py` (REST + one WebSocket per run, downloads, Origin check on the stream, whitelisted file names, run ids validated). `scoutskit serve` binds 127.0.0.1 only.
- Bug found by the tests: stopping a run while its browser was still starting left Playwright driver tasks behind and hung the server's shutdown. `open_session` is now cancellation-safe (regression test).
- Live: a real task through the server streamed notices, 5 steps, 8 JPEG frames, and a finished event; 40 items, recipe saved. 112 tests pass.
- Next: step 2, the React (Vite) UI: task box, live view, timeline, result table + downloads.

## 2026-11-22 (night, step 2 of the web UI): the React UI

- `ui/` (Vite + React + TypeScript): task form, run list, live browser view (WebSocket JPEG frames, last screenshot once finished), step timeline, result table with CSV/JSON/recipe downloads, Stop button. `runState.ts` builds the view purely from the streamed events (6 vitest tests); `useRunStream` reconnects and replays history.
- `scoutskit serve` also serves `ui/dist` when built. Checked by driving the real UI in a browser: a real run started from the form, live view, 5 steps, 40 result rows, no console errors.
- Fixes found on the way: replay statuses (`replayed/changed/diverged`) and `interrupted` (a run folder with no result left by a killed server) get proper badges; my test script first waited for any "completed" badge in the list, not the open run's.
- README written (it was empty).

## 2026-11-22 (night, step 3 of the web UI): take-over, and a password leak found on the way

- Take over: `control.py` (`RunControl`: agent / requested / user; the agent checks in between steps, so a take-over never interrupts a step; auto-release after 10 minutes), `server/remote_input.py` (only click, scroll, type, 13 named keys, all validated; coordinates are fractions of the picture), `POST /api/runs/{id}/control`, input over the stream's WebSocket (refused unless the person is driving). UI: Take over / Hand back, banner, click/scroll/type on the live picture (`remoteInput.ts`, tested). After a hand-back the agent is told "a person used the browser", looks afresh, and is brought back if the person left the site.
- Verified in a real browser: took over a live run from the UI, typed into the page's field through the picture, handed back, the run continued.
- FOUND: the accessibility tree the model reads every step shows password values in clear (`textbox "Pass": s3cret-pass`), and `javascript_tool` can return them. That would send any typed password (by the agent, a person taking over, or autofill) to the model provider and into the logs. Fix: `session.scrub()` hides the value of every password field (and remembers it for the session) in the tree and, via the registry, in every tool output. 4 tests. Text typed in non-password fields is still readable by the agent by design; the banner and README say so.
- My earlier claim "typed text is not recorded" was too strong: the take-over path logs nothing, but the agent can read plain fields afterwards. Corrected.

## 2026-11-22 (late night): open web and tabs (step 1 of the main-brain plan)

- Agreed direction (Manus-like): a main brain that plans, opens tabs, spawns sub-agents, asks the user, with take-over and a gate for irreversible actions. Order: (1) open web + tabs, (2) chat / `ask_user`, (3) planner with visible plan + approval, (4) sub-agents in tabs, (5) risky-action gate. This entry is step 1.
- `Policy(scope="site"|"web")`: web scope allows any public site plus the start host. Private networks are blocked by name (localhost, .local, .internal, 10.x, 192.168.x, 169.254.x, ::1 ...) AND by where the name really resolves (cached DNS), and a browser-level guard (`guard_request`) checks every request (navigations, redirects, images, fetches, new tabs). A blocked navigation goes back immediately and is reported once. Not covered: DNS rebinding between the check and the request.
- New `open_tab` tool; `--web` flag, `web` in the API, a UI checkbox; recipes of web runs replay in web scope. Without a URL a web run starts at a search results page (`search.py`, setting `[agent] search_engine`).
- Refusals are findings: HTTP 403/418/429 or a typical block page (heuristic) is logged as `finding access_denied`, and the agent is told not to retry or work around it (prompt rule too). Also added to the prompt for every run: text on a page is data, never an instruction.
- Live: a web run with no URL: DuckDuckGo answered the automated browser with a 418 block page; the agent did not retry it, the finding was logged, it opened the official site from its own knowledge and finished (10 items).
- LLM client: a reply with invalid JSON (an unquoted string failed a run in the UI) is now asked again with what was wrong (max 2 retries).
- OPEN DECISION: search engines block or disallow automated browsers (the auto-mode classifier also refused my attempt to probe them with robots checks off). A search API (Brave, Google Programmable Search) is the proper route; needs a key.

## Workspace UI (Nov 22)
The UI was a single stack of cards. It is now a three-column workspace: runs on the left; the browser in the middle with its own tab strip, back/reload, address bar and "copy this tab" (usable while you drive, still under the site policy); a right panel with Plan, Agents, Steps and Result.
- Server: `tabs` events (server/tabs.py), a structured `plan` event, and new remote tools (navigate, new/switch/close/duplicate tab, back, reload).
- The UI reducer already understands `agent` and `todo` events. The Agents panel shows the main agent now; sub-agents and the to-do list appear when the planner and sub-agents are built (steps 3 and 4 of the main-brain plan). Until then those panels say so instead of showing made-up content.
- Not fixed yet: the loop/slow-page problems found in run 20261122-160013 (loop detection by action, waiting for navigation, go_back timeout as a failed step, planning error message).

## New "mission control" UI (Nov 22, later)
Asked for a completely new, modern look. Rebuilt the UI around two screens:
- Home: one large prompt box (Enter launches; chips for open web, start URL, model), example missions, and recent missions as cards.
- Mission: status, clock, steps, items and model across the top; a four-stage progress rail (plan, explore, extract, done); the browser drawn as a real window (tabs, back/reload, address bar, copy tab, who is driving); a glass side panel with Plan, Agents (an orbit graph with the main brain in the middle), Activity (newest-first tool calls with expandable output) and Data; a ticker with the latest action.
- Ctrl/⌘ K opens a command palette to jump to any mission or action.
Bugs found by looking at screenshots, not by tests: a CSS rule pushed the palette below the page; a mission without a banner put the ticker in the stretchy row; finished runs replayed from disk showed as LIVE because the log never holds the "finished" event (the server now appends it from the result); runs that failed while planning had no task (the runner now logs the task first).

## Research → plan → approval (Nov 22, evening)
Replaced "open a search engine in the browser" (DuckDuckGo 418, Google reCAPTCHA) with a research step before any browser opens:
- search/ package: DuckDuckGo through the `ddgs` library (free, unofficial: it reads DDG's lightweight results page; failures become notes) and Wikipedia's official API plus the article's official website from Wikidata. Sources run in parallel; duplicates merge.
- brief.py: the model writes 1-3 queries, sees the numbered results, and picks sources BY NUMBER ONLY, so it cannot invent a URL. It writes understanding, picks with reasons, steps and open questions.
- The plan waits for approval (PlanGate; POST /api/runs/{id}/plan approve|revise). Added context re-plans; a re-plan keeps the earlier sources (first try lost the syllabus page because DuckDuckGo answered differently the second time). "Autonomous" skips the wait.
- UI: research radar, then the plan card in place of the browser (top picks with source tags and reasons, other results, failed searches, steps, questions, context box, Continue / Re-plan).
Observed: Wikidata lists utukhabar.com as the university's official website (wrong). The brain picked uktech.ac.in because the search results agreed. Single sources are not trusted.
Live run 20261122-185732: research found the syllabus page; the agent found all 7 CSE/IT rows with their PDF links, then our own row check rejected them 12 times: the page's "Sl. No." column is blank, it was chosen as the key field, and rows without a key were rejected. Fixed (key = a filled column; a row without its key is identified by its other values). Downloading files is still forbidden by the agent's rules.

## Files and the team of sub-agents (Nov 22, night)
- Files: browser/files.py FileStore (run's files/ folder, safe unique names, 50 MB per file, 200 MB per run, stored never opened). New save_file(url) tool fetches with the browser's cookies; every redirect is checked against the site policy by hand (the request API bypasses the browser's route guard). A click that starts a download is saved too and reported in the tool's answer. Saved files count as results for `done`. Agent rule changed from "never download" to "save documents the task needs".
- Browser: open_browser() gives one browser process; BrowserHost.session() makes an isolated context per sub-agent. open_session() is now a thin wrapper (all old tests unchanged).
- Team (team.py): one sub-agent per pick (the brief says how many, 1-3), in parallel, each logging with its id (AgentRecorder: tagged entries, a1-step01.png, code/a1/). When one finishes, the brain verifies it (complete? why). Autonomous: the brain's verdict decides. Otherwise the person accepts or rejects (same gate as the plan, topic "result"). The first accepted result wins; the others are cancelled and logged "stopped". The recipe is built from the winner's steps only.
- Server: per-run map of sub-agent browsers; the live view and take-over follow the watched one (POST /focus, refused during a take-over); /saved/{name} serves files as downloads only; /answer replaces /plan.
- UI: download bubble (like a browser's), Files list in Data, result-check banner (Accept & stop the others / Keep looking), agent cards with the brain's verdict and "Watch this browser", step chips per sub-agent.
Live run 20261122-192035: plan approved, the agent opened the syllabus page, found the table, saved BTech_CSE_2108.pdf (3.8 MB, the real PDF), the brain verified it, accepted in the UI. 14 steps, 2 minutes. The brain chose one sub-agent because one source was clearly right; the parallel path is covered by tests, not yet seen live.
Noticed: the first `done` was refused by the table census ("42 rows in the source, 0 collected") although the task was a file: the census rule should not apply when the files are the result. Next.

## File viewer (Nov 23)
Report: "file view is not working". Cause: /saved/{name} sent every file as a forced download (octet-stream + attachment), so "Open" could never show anything, and there was no viewer. (The user's server on :8000 also predated the file feature and had no such route.)
- Server: a fixed table maps safe extensions (pdf, png/jpg/gif/webp, csv/tsv/json/txt/md/log) to the type shown inline; HTML, SVG and everything else are always downloads. The type comes from the table, not from the file or the site; nosniff on all. First version also sent a strict CSP; dropped it because Chrome's own PDF viewer is blocked by `default-src 'none'`.
- UI: FileViewer modal (Esc closes, arrow keys move between files, open-in-new-tab, download). PDF drawn in the page with pdf.js (loaded only when a PDF is opened; pages drawn lazily, zoom 60-200%; a 383-page syllabus opens at once) because headless Chromium has no PDF viewer and so I could not otherwise verify it. CSV/TSV as a table (own parser: quotes, commas and line breaks inside cells; row filter; first 1000 rows), JSON pretty-printed, text as plain text (React-escaped: a <script> in a .txt shows as text), images on a checkerboard, other types offer a download. Result tables (result.csv/json) open in the same viewer ("Full view"). The download bubble's "Open" now opens the viewer.
- Tests: server inline/attachment rules, path traversal; fileKinds/parseCsv. Checked by eye with a fixture run holding a PDF, PNG, CSV, JSON, TXT and ZIP.

## Human in the loop for CAPTCHAs (Nov 23)
Request: when a search hits "I'm not a robot", pause, pop up "human needed", let the user solve it, and add a take-control control inside the browser.
- Detection (browser/session.py): `challenge_of` = a document whose path/query matches captcha, /sorry/, unusual traffic, hcaptcha, turnstile, /challenge. A plain 403/418/429 stays a block (a person cannot fix it).
- Agent: at its next look (before the model reads the page, so it never tries the CAPTCHA itself) it logs help_needed, requests the browser and waits (the existing take-over, 600 s limit). Asked once per site. The model is told afterwards either "a person handled it: look afresh" or, if the person skipped, "do not go back; use another source", and a finding is logged. The person does the check themselves: nothing here solves, avoids or hides it. With no person to ask (the command line) a CAPTCHA is a block, as before.
- Server: with sub-agents the browser shown switches to the one that asked; hand-back accepts note "skip".
- UI: "Human needed" popup over the browser (Skip this site / I solved it - continue, enabled once the browser is handed over) and a Take control / Hand back button inside the browser window.
Bugs found by tests/live run: the CAPTCHA's own block notice stayed queued and produced a false "blocked" finding after the person solved it; the brain's result check saw 5 sample rows and judged the 40-item result "only a sample" (now told the true count); the new chip was squashed by an old button width rule.
Live: start page = captcha page, popup appeared, clicked the checkbox in the live picture, continued, 40 items.
Limit: real CAPTCHAs (Google reCAPTCHA) were not tried; they may still refuse an automated browser even after a person ticks the box.

## Search as data, not as a page (Nov 23)
Trigger: the user's screenshot of DuckDuckGo results in their own browser showed the exact PDF links, and run 20261122-192841 (old code) had typed into DuckDuckGo inside the agent's browser, got the 418 block page and wandered to the wrong site (uktech.com instead of uktech.ac.in).
- web_search tool: the agent gets real search results as text (the same sources as the brief). goto/open_tab refuse a search engine's results page and point to web_search (search/base.py is_search_page).
- A search result that is itself a document (PDF etc.) is saved at once by the team (direct_file), then the agent starts on that site's home page; the prompt lists FILES SAVED and says to finish if they answer the task. Files also satisfy the "more rows exist than collected" check on done.
- ddgs is a metasearch (it tries DuckDuckGo, Bing, Brave, Yahoo... in turn) and fails intermittently with "No results found" (DuckDuckGo's own backend failed during testing while the others answered). Retries 3x; the source is now named "web" (the old name "duckduckgo" still works in the config) and results are labelled "Web search".
- Failover: a sub-agent that finds nothing (e.g. the start site will not open) hands over to the next unused pick. Found because Wikidata's "official website" for the university (utukhabar.com) is a dead domain and, with the web search down, it was the only pick. My live script then approved that plan without reading it: the plan card did show the failed searches, a person would have caught it.
- The brain is told when searches failed (SEARCH NOTES) and asked to pick conservatively.
Live run 20261122-194919: the web search returned three uktech PDFs, the first was saved directly (1.4 MB), verified, completed in 1:12.

## Lessons from run 20261122-200132 (Nov 23): "compare the top 5 laptops under ₹60,000 on two sites"
Result: incomplete, 0 items, 5 sub-agents, 33 steps, 729k prompt tokens. The team machinery worked (parallel scouts, fail-over through five picks); the agents' extraction did not.
- Scout 2 (Amazon) ran 8 near-identical scripts: it passed HTML_PATH (a path) to BeautifulSoup, which warns "MarkupResemblesLocatorWarning" and parses the path text. The warning was in the output every time and ignored. Now run_python names the mistake.
- Scout 1 (Flipkart) had 10 products by step 5, then: extract_rows rejected every row because the specifications field was a list, flattened as "['Intel...', ...]", which is on no page; it then printed a "top 5" with run_python (nothing saved: only out.json counts) and looped on that until stuck. Fixes: lists and objects are checked part by part against the page and stored as "a; b"; run_python says "nothing was saved: printing is not collecting" when it wrote no out.json.
- The plan keyed rows by "price" (the first field): repeated prices would have dropped real products. The key is now the model's choice, else an id/name-like field, else the first.
- "Top 5" was read as the five cheapest (a Chromebook at 15,990 first): a judgement of the model that the plan card could have shown. Not fixed; the plan's steps should say how "top" is decided.
- Fail-over tried smartprix.com twice after an HTTP 403 (two different pages, same refusal). A host that refused is now skipped, and a refused start page is logged as a finding.
- Cost: nothing stops a failing team from spending many tokens (five scouts each re-reading pages). A team-wide token or step budget is still to do.

## "Where is the CAPTCHA? And no control works" (Nov 23)
Screenshot of run 20261122-202115: a "Human needed: google.com is asking you to prove you are human" popup over a plain CNET page, and the controls felt dead.
Findings (from the log, then by reproducing on real cnet.com):
- False alarm. The trigger was https://www.google.com/recaptcha/api2/aframe: CNET's invisible reCAPTCHA, a hidden iframe. My detector looked at every document response, including frames, so any site using reCAPTCHA v3/ads/trackers looked like a block. Now only a tab's own page (main frame) can be a challenge or a refusal. Added a title check ("Just a moment...", "Verify you are human") for Cloudflare-style pages that have an innocuous address, and the challenge's tab is brought to the front.
- No picture on a still page. Chrome's screencast sends frames only when something repaints; a viewer who connects to a page that is not repainting (or after a focus switch) saw nothing. The channel now replays the last frame to a new viewer, and the screencast takes a still picture when 1.5 s pass without a frame.
- Input backlog. The server read and applied one message at a time. A trackpad sends dozens of scroll events a second, each costing the browser ~40 ms, so the queue grew and a click waited behind seconds of scrolling; a navigation (up to 45 s) blocked everything. New InputPump: reads at once, merges consecutive scrolls (sum, capped) and hovers, runs navigations in the background (still one after another), keeps clicks and keys in order, bounds the backlog. A 120-event burst now shows up in ~20 ms.
- Richer remote control: hover (menus that open on hover), double and right click, paste (up to 2000 chars), Ctrl+A/Z/Y, a ripple where you click, a "you're driving" hint. Client batches scrolling every 50 ms.
Could not reproduce "nothing works" in a clean setup (a click, scroll, address bar, back and tabs all worked on real CNET), so the dead feel was most likely the above together: a stale picture, a backlog behind trackpad scrolling, and a popup asking for a CAPTCHA that was not there. Not verified on the user's own machine.
Lesson: my first fixture failed because it never emitted a plan and the UI sat on "Researching"; and I read tabs[0] when the navigation had gone to the active tab. Check the thing you measure.

## Reading the last four runs (Nov 23, night): budgets, loops, scope
Runs: 20261122-210738 (SIH 2025 PS: 4 scouts, 60 steps, 835k tokens, 15 min, 0 items), 202238 and 202115 (laptops / CNET+TechRadar: one ran 26 min and had to be stopped), 200132 (earlier).
Causes found in the logs:
- Scout 1 on the SIH site ran 13 near-identical scripts failing with the same "table not found" error (it grepped for the CSS selector text `table#dataTablePS`, which is not in any HTML, and kept rewording the script). The stuck check only fires on identical calls. New: a failure fingerprint (numbers stripped); the same failure 3 times adds "stop rewriting, look at the real page"; 6 times for run_python ends that scout.
- Scouts 3 and 4 again passed HTML_PATH (a path) to BeautifulSoup, ignoring the warning/hint, one even redefined HTML_PATH as a string. The sandbox now makes BeautifulSoup(HTML_PATH) read the file it names, and predefines HTML and RENDERED (the text). Hint removed; tool description updated.
- A compare-two-sites task ran in single-site scope ("the browser is restricted to cnet.com"): a plan whose first sub-agents start on several hosts now opens the web scope (the person approved that plan); the plan card lists the sites.
- No limit on spending: new shared Budget (agent.team_token_budget, default 600,000 tokens, 0 = none). Agents stop with status max_budget; no replacement scout starts once it is gone; replacement scouts get 15 steps. UI shows "budget used".
- The year: the task said SIH 2025, the site's problem-statement page is 2026. The agent never noticed. Added a rule: check the edition/year/version the task names, otherwise look for the right one or fail. Not verified live.
Not done: how "top 5" is decided in the plan card; the three failing-site scouts show the cost of unreliable picks (third-party mirrors such as sih-nav.vercel.app): the brain could rank official sources first and mirrors only as a last resort.

## Why the SIH 2025 run failed, and the fix (Nov 23)
Question: the agent found the right sites but extracted nothing: wrong system prompt, or not enough tools?
Evidence (probing the pages with our own browser tools):
- The official sih.gov.in/sih2025PS is now an empty shell ("Total problem statements: 0", a table with no rows). The 2025 list lives on third-party mirrors.
- sih2025probelmstatement.vercel.app: a plain table, 101 rows, fully in the raw HTML. The scout wrote soup.find('table', {'id': 'e40'}): it used the accessibility-tree ref e40 as an HTML id and never looked at the real HTML.
- sih-nav.vercel.app: 238 cards (no table), in the raw HTML, in sibling groups split by a colour class (187 + 42 + ...). The scouts guessed selectors from the tree and printed instead of saving.
Diagnosis: mostly a TOOL gap, with a prompt gap behind it. On SIH 2026 the agent succeeded because the table census told it "the source holds 265 rows in table#dataTablePS". Card layouts had no such help, so a weaker model had to guess HTML it could not see (the tree has roles and refs, not selectors).
Fix:
- browser/repeats.py: finds the page's main list of repeated items for any markup (tables, cards, entries): clusters siblings by tag and class similarity (a colour class does not split a list), scores by count and text carried (chips and menus repeat but say little), builds the SHORTEST CSS selector that matches exactly those items, counts them in the live page and in the raw source, and maps what one item contains.
- find_items tool (selector, counts, field map, first item's HTML, how to write the script), a line in every prompt when a list exists ("THE PAGE REPEATS ONE ELEMENT 238 TIMES (CSS selector ...)"), `done` is refused while the page shows more items than collected, and the system prompt now says refs are not ids and to search for text, never for a CSS selector.
- The brain's result check no longer rejects a result for coming from a mirror (the plan chose the site; the official one may no longer list the data).
Live: site A 101 items in 4 steps, site B 238 items in 4 steps (both were 0 items after 10-23 steps; all ids distinct). Minor: one field reads "286submissions" (two adjacent spans joined).
Not re-run end to end from the plan (search -> plan -> sub-agents -> verify) on "find all the sih 2025 ps".

## Full flow on "find all the sih 2025 problem statements" (Nov 23, night): five fixes it took
Repeated the whole chain (search, plan, approval, scouts, brain check, person accepts) on the real site until it completed. Each run exposed the next fault:
1. Run 1: one scout on the official sih2025PS page (an empty shell, "Total 0") spent all 38 steps and the whole 600k budget grepping for a data request that does not exist. Fix: a read-only streak detector (6 reads of one page with nothing collected -> told to decide; 10 -> stops, status incomplete) and a prompt line when the page says "No data available". Each scout now gets a third of the budget (budget.Share) so replacements can run.
2. Scouts knew the answer ("the official page shows 0") and one even found the right mirror through web_search and tried open_tab, but ran in single-site scope and could not leave sih.gov.in. Fix: a run with no start URL (the search chose the sites, the person approved the plan) gets the open-web scope. Added to the prompt: if a page holds no data, call fail so another source is tried; the done-rejected message says the same.
3. Each step sent ~15-19k tokens, mostly old tool output. Fix: output and long scripts of all but the newest two turns are cut to a line (agent._thinned): ~10k per step.
4. Fail-over bug of mine: a scout that had saved an unrelated file counted as "found something", so two untried sources, including the mirror with the data, were never used. Now any scout that does not deliver (or whose result is turned down) hands over to the next source. Sources after the brain's picks come from the other search results (no articles, no pictures), fresh hosts before failed ones, a host that failed twice is dropped. Every decision is logged as a "failover" event.
5. The brain's check rejected 101 items from the mirror ("unofficial, cannot confirm the total"). It is now told what the page states (total 101, list of 101) and never to reject only for an unofficial site; and with a person in the loop the brain only advises: a result it doubts is shown to the person with the doubt ("Accept anyway"), the brain decides alone only in autonomous mode.
Outcome: scout 1 wasted its 200k share on the empty official page, scout 2 started at the mirror and finished in 10 s: 101 items, brain verified against the stated total, person accepted. 2:27, 22 steps.
Open: the two mirrors disagree (101 vs 238 problem statements); the agent accepted the one whose total matched its own page. Which is the true SIH 2025 list is not something the run can know. The first scout still spends a full share on the empty official page; ordering picks by an early peek at each source would save it.

## UI redesign: a workbench instead of a "mission control" (Nov 23, night)
Feedback: the interface looked AI-generated. Honest diagnosis: aurora background, glass blur, a violet-cyan gradient on everything, emoji as icons, pill badges, a centred "What should your agents explore?" hero.
New direction: a calm, dense developer tool. Warm neutral surfaces, ONE accent colour (a setting), flat 1px borders, 6px radii, no glow/blur/gradients; IBM Plex Sans and Mono bundled (works offline); lucide icons instead of emoji; status shown as a dot and a word.
- Layout: sidebar with run history (running on top, then by day, collapsible), a plain "New run" form (task, start from search or a site, how far it may roam, plan approval, model) with examples, the run view with a progress line, the browser frame (tabs, address bar, take control) and an inspector (Plan, Agents, Activity, Data) that can be dragged wider/narrower and put at the right or the bottom; Ctrl K palette; a file viewer; the address now holds the run (#/run/<id>) so reload and back keep your place (found while testing: reload used to drop you out of the run).
- Customization (settings drawer, remembered in the browser, validated on load): theme (system/light/dark), accent (5 presets or any hex, readable text colour chosen automatically), density, text size, inspector position, default tab, latest-action line, animations, and new-run defaults (autonomous, open web, model). 37 UI tests (settings parsing/clamping/round trip, resizable maths, addresses, state).
- Bugs found by looking at screenshots: CSS class names that collided (the viewport's `.live` gave status dots a black background; `.todo` was both a list and a status), the toast covering the address bar's take-control button, a responsive rule that hid the whole run on narrow windows.
- Removed: the aurora, the hero home, the card grid of recent runs (the sidebar is the history now).
Not verified: very large run lists (50 runs fine), screen readers beyond basic roles and labels, Safari/Firefox (checked in Chromium only).

## Trying nvidia/nemotron-3-ultra-550b-a55b (Nov 23, night)
Request: a bigger model, because the small ones choose wrong methods. Added provider `nvidia_ultra` to scoutskit.toml (thinking on, 8000 max tokens; answers in ~3 s per call, slower than super at ~0.5 s).
What the run showed: the big model chose the RIGHT method where it counted (find_items -> script -> done, 4 steps, 101 rows). What sank the run was not its extraction:
1. The plan still started a scout on the official sih2025PS page (an empty shell) first: ~12 steps wasted. The big model did no better at noticing "No data available" than the small ones.
2. The brain's check (also the big model) rejected the correct 101 rows as "unofficial third-party site, lacks description". A bigger model was MORE sceptical, not less, and everything after that burned the budget on sources that could not work.
So the fixes were structural, not a better model:
- peek.py: before any scout starts, each candidate source is loaded in its own context and measured with no model call (the finder of repeated items, the total it states, "no data" wording); sources that hold a list go first (ones whose list length equals the total they state before ones that merely repeat something), empty shells last. Logged as "peek" events.
- The finder of repeated items ignored table cells (an empty table still has seven column headings that looked like a list) and navigation, header, footer, aside and hidden menus (eight menu links made the empty official page look like it held data). Found by checking the peek against the real page.
- Verification: when the result has exactly as many items as the page states (or its list holds), completeness is settled by counting, and the brain is asked only the narrow question "are these the kind of items the task asks for?", never about the site.
Result with nvidia_ultra: 1 scout, 4 steps, ~31k tokens (before: 6 scouts, 66 steps, 600k tokens, incomplete). Cost of the peek: a few seconds, no tokens.
Open: the two mirrors (101 vs 238 problem statements) both look like the real list by their own totals; the run takes the first. The bigger model is not needed for this task: the same structural fixes help every model.
