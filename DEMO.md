# Demo guide

## Ten minutes before

```bash
uv run scoutskit check            # every line must be green
uv run scoutskit serve --open     # http://127.0.0.1:8000
```

Needs the internet and the NVIDIA key in `.env`. Close other heavy programs (the browser runs headless, but it is still Chromium).
Record a screen video tonight as a backup. If the network misbehaves, every earlier run is in the sidebar with its evidence, and **Replay** works on any completed run.

## Say this first (30 seconds): where it stands against the synopsis

Mode 1, the agent that does a task, works on real sites and can replay without a model. Mode 2, testing under environment profiles with usability and accessibility checks and a report, is the next step and builds on the same session and recipe code. Of the nine items in the 40% scope (§5.8): three are done, three partly done (parallel agents, logs and screenshots, test pages), three not yet (profiles, usability metrics and functional evaluators, axe-core and keyboard checks). Full table: `IMPLEMENTATION_PLAN.md`, "Status on 2026-11-23".

## The story (about eight minutes)

**1. Download a document (about 1½ minutes)**
New run → *"download the btech cse syllabus from uktech"* → leave **Search the web** and **Show me the plan first** → Start.
- Say: it researches first; this is its plan and why it chose those sources. *(Plan card)*
- Click **Continue**. Watch the live browser: it finds the Syllabus link even though it hides in a menu, opens the page, saves the PDF.
- The green banner is the brain's check; click **Accept**. Open the file from the Data tab (the PDF viewer) .
- Click **Replay without a model**: the same PDF again, no model, about ten seconds.

**2. Collect a whole table (about two minutes)**
*"find all the sih 2025 problem statements"* → Continue. The official page is empty ("Total 0"); the first look at each source puts the one with data first. Result: 101 rows, checked against the page's own total. Open the table (Full view), filter it, download the CSV. **Replay**: 101 rows in two seconds.

**3. Human in the loop (one minute)**
During any run press **Take control** in the browser bar: click, scroll, type in the live browser, then **Hand back**. Mention that a CAPTCHA is handed to a person and never bypassed.

**4. Customize (30 seconds)**
Settings: dark theme, accent colour, inspector at the bottom, text size.

## Talking points

- **Evidence, not trust:** every step, screenshot and file is saved; the result is checked by counting against what the page states, and by a second model call.
- **Explore once, replay many:** the first run costs tokens; the recipe replays with none.
- **Safety:** nothing private is reachable, blocks are findings, page text never gives orders.
- **Small models fail in specific ways, so the system helps them:** finds the real links and lists, refuses error pages as files, stops loops, caps the budget.

## What not to demo (known limits)

- *"Download all the diploma syllabi"* (about 70 files, many larger than the 50 MB limit): the agent saves a few and the check says it is partial.
- Comparing products across two shops: shops often refuse automated browsers; results vary.
- Real CAPTCHAs (Google and the like) were not tried; the hand-over was tested on a test page.
- Two mirror sites list 101 and 238 SIH 2025 problem statements; the run takes the first one whose total matches. Say so if asked.
- Search results come from a free metasearch library that fails now and then; it retries, and the interface shows when a source failed.

## If something goes wrong on stage

| Problem | Do this |
|---|---|
| A run is slow | Say what it is doing from the Activity tab; the plan card and sources are already a good story. |
| A run fails | Open the previous run of the same task in the sidebar. |
| The model does not answer | Settings → New-run defaults → Model, or type `nvidia_ultra` in the model field of the form. |
| Browser looks stuck | Press **Take control**, click in it, **Hand back**. |
| Everything is down | Replay a saved run: it needs no model. |
