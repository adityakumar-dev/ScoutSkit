# ScoutsKit

An agent that does a task on a website from a plain-language instruction, keeps the evidence, and can repeat what worked without a model.

## Setup

```bash
uv sync                       # Python 3.12 dependencies
uv run playwright install chromium
cp .env.example .env          # add the API key(s) for the providers you use
uv run scoutskit providers --check
```

## Use it from the terminal

```bash
uv run scoutskit run "give me all the problem statements" --url https://sih.gov.in/sih2026PS --provider nvidia_super --strict
uv run scoutskit replay runs/<run-folder>      # repeat a saved recipe, no model
```

Open web: add `--web` (UI: "Allow other websites") to let a run visit any public website, with `open_tab` to keep several pages open. Without a `--url` it starts from a search page (`[agent] search_engine` in `scoutskit.toml`). Private networks (localhost, 10.x, 192.168.x, ...) stay blocked, a site that refuses the browser (HTTP 403/418/429, CAPTCHA page) is recorded as a finding and never retried or bypassed. Note that search engines such as DuckDuckGo answer automated browsers with a block page, so name the site with `--url` when you can.

Every run writes `runs/<id>/`: `actions.jsonl`, screenshots, `result.csv` / `result.json`, and `recipe.json` when it completed.

## Use it from the web UI

Built version (one command, one address):

```bash
(cd ui && npm install && npm run build)
uv run scoutskit serve         # http://127.0.0.1:8000
```

Development (hot reload):

```bash
uv run scoutskit serve         # terminal 1: the server on 127.0.0.1:8000
cd ui && npm run dev           # terminal 2: http://localhost:5173, proxies /api to the server
```

The UI starts runs, shows the browser live, lists the steps, and offers the result and the recipe for download. **Take over** lets you click, scroll and type in the live browser (for example to log in) while the agent waits; hand back and it continues. Values in password fields are hidden from the model and the logs; text typed in other fields can be read by the agent afterwards. The server listens on 127.0.0.1 only and refuses stream connections from other websites.

## Tests

```bash
uv run pytest                  # Python
cd ui && npm test              # UI logic
```

## Layout

- `src/scoutskit/agent.py`, `tools/`, `browser/`: the agent loop, its tools, the browser session.
- `src/scoutskit/recipe/`: turn a run into a recipe and replay it.
- `src/scoutskit/server/`: HTTP/WebSocket server (runs, event stream, live screencast).
- `ui/`: the React (Vite) web UI.
- `benchmarks/portal/`: local test pages (paged tables, hidden details, data loaded from a request).
- `project_process_report.md`, `IMPLEMENTATION_PLAN.md`: the diary and the plan.
