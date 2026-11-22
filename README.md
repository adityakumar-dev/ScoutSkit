# ScoutsKit

An agent that does a job on the web from a plain-language instruction, keeps the evidence, and can repeat what worked **without a model**.

> "Download the B.Tech CSE syllabus from uktech" → it researches, shows you a plan, opens a browser, finds the document, saves it, and checks the result. Run it again later with one click and no model.

For the full list of technologies (what, why, where in the code), see [TECHNOLOGY.md](TECHNOLOGY.md). To present it, see [DEMO.md](DEMO.md).

## What it does

1. **Research.** Searches the web (free, no key) and picks sources; you see why it picked each.
2. **Plan, then approval.** You approve the plan, or add context ("only the CSE syllabus") and it re-plans. Nothing opens before that.
3. **Explore.** Sub-agents work in their own browsers, in parallel. Each source is looked at first (no model call) so an empty page is not tried before one that holds data.
4. **Check.** The brain verifies the result (a list is counted against the total the page states); you accept it.
5. **Replay.** The run is saved as a recipe. Repeat it with no model: 101 items in two seconds, or the same PDF downloaded again.

You can take over the live browser at any time (click, scroll, type, paste) and a CAPTCHA is handed to you instead of being bypassed.

## Quick start

```bash
uv sync
uv run playwright install chromium
cp .env.example .env                  # add NVIDIA_API_KEY (or another provider's key)
(cd ui && npm install && npm run build)
uv run scoutskit check                # is everything ready? (browser, sandbox, model, search, interface)
uv run scoutskit serve --open         # http://127.0.0.1:8000
```

Terminal use:

```bash
uv run scoutskit run "download the btech cse syllabus from uktech"
uv run scoutskit run "get every problem statement" --url https://example.org/list --provider nvidia_ultra --strict
uv run scoutskit replay runs/<run-folder>          # repeat a saved recipe, no model
uv run scoutskit providers --check                 # which keys work
```

## Models

`scoutskit.toml` lists the providers; the default is `nvidia_super` (fast, reliable on the benchmark tasks). `nvidia_ultra` is the largest model (slower, use it if a smaller one picks wrong methods). Others fall back in file order. Pick one per run in the interface or with `--provider`.

## The interface

A sidebar with your runs, a new-run form, and for each run: progress, the live browser (take control any time), and an inspector with the plan, the agents, every step, and the data (tables, PDFs, images and CSVs open in a viewer). Settings (theme, accent colour, density, text size, inspector position, defaults) are remembered in your browser; Ctrl K searches runs and actions. A run's address is `#/run/<id>`, so reload keeps your place.

## Safety

- Private networks (localhost, 10.x, 192.168.x, cloud metadata) are never visited; every request is checked, redirects included.
- A site that refuses the browser (HTTP 403/418/429, a block page) is recorded as a finding and never bypassed. A CAPTCHA is handed to a person; nothing solves or hides it.
- Page text is data, never instructions to the agent. Password fields are hidden from the model and the logs.
- Saved files are only stored, never opened or run; web pages and error pages are refused as "files". The server listens on 127.0.0.1 only.
- Model-written Python runs in a sandbox (bubblewrap) with no network and a read-only filesystem.

## Every run leaves evidence

`runs/<id>/`: `actions.jsonl` (every step), screenshots, `result.csv` / `result.json`, `files/` (downloads), `recipe.json` (when it completed).

## Tests

```bash
uv run pytest            # Python (≈250 tests)
cd ui && npm test        # interface logic
```

## Layout

- `src/scoutskit/agent.py`, `tools/`, `browser/`: the agent loop, its tools, the browser session (`repeats.py` finds lists, `links.py` finds links, `files.py` saves documents).
- `src/scoutskit/brief.py`, `team.py`, `peek.py`, `budget.py`: research and plan, the team of sub-agents, the first look at each source, the token budget.
- `src/scoutskit/recipe/`: turn a run into a recipe and replay it.
- `src/scoutskit/server/`: HTTP/WebSocket server (runs, event stream, live screencast, remote input).
- `ui/`: the React (Vite) interface.
- `benchmarks/portal/`: local test pages.
- `DEMO.md`: how to present it. `project_process_report.md`: the diary of what was built and what went wrong.
