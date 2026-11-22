from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .provider import ConfigError, check_all, choose_provider, key_status, load_settings

app = typer.Typer(help="ScoutsKit: autonomous web task execution and evaluation.", no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """ScoutsKit command line."""


@app.command()
def providers(
    check: bool = typer.Option(False, "--check", "-c", help="Test every key with a free, read-only API call."),
) -> None:
    """List configured LLM providers; with --check, also test which keys work."""
    try:
        settings = load_settings()
        results = {r.provider: r for r in asyncio.run(check_all(settings))} if check else {}
    except ConfigError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error

    status = key_status(settings)
    table = Table(title="LLM providers")
    for column in ("", "provider", "model", "key env var", "key"):
        table.add_column(column)
    if check:
        table.add_column("check")
    for name, cfg in settings.providers.items():
        marker = "*" if name == settings.default_provider else ""
        key = "[green]set[/green]" if status[name] else "[yellow]missing[/yellow]"
        row = [marker, name, cfg.model, cfg.api_key_env, key]
        if check:
            result = results[name]
            colour = "green" if result.ok and result.model_found is not False else "yellow" if result.ok else "red"
            speed = f" {result.latency_ms}ms" if result.latency_ms is not None else ""
            row.append(f"[{colour}]{result.detail}{speed}[/{colour}]")
        table.add_row(*row)
    console.print(table)
    console.print("* = default provider")
    if check:
        try:
            name, note = choose_provider(settings, list(results.values()))
            console.print(f"[bold]Would use:[/bold] {name}" + (f"  [yellow]({note})[/yellow]" if note else ""))
        except ConfigError as error:
            console.print(f"[red]{error}[/red]")


@app.command()
def check() -> None:
    """Is everything ready? Browser, sandbox, model, search, interface and disk, in one go. Run it before a demo."""
    from .preflight import run_all

    results = asyncio.run(run_all())
    table = Table(title="ScoutsKit pre-flight")
    for column in ("", "check", "result", "if it failed"):
        table.add_column(column)
    for item in results:
        table.add_row("[green]✓[/green]" if item.ok else "[red]✗[/red]", item.name, item.detail, "" if item.ok else item.fix)
    console.print(table)
    bad = [item.name for item in results if not item.ok]
    console.print("[green]Ready.[/green]" if not bad else f"[red]Not ready:[/red] {', '.join(bad)}")
    raise typer.Exit(1 if bad else 0)


async def _run(task: str, url: str | None, provider_name: str | None, max_steps: int | None, headed: bool, strict: bool, web: bool) -> None:
    from .runner import execute

    outcome = await execute(task, url=url, provider_name=provider_name, max_steps=max_steps, headed=headed, strict=strict, web=web, say=console.print)
    colour = {"completed": "green", "incomplete": "yellow"}.get(outcome.status, "red")
    console.print(f"\n[{colour}]{outcome.status}[/{colour}]: {outcome.items} items in {outcome.steps} steps. {outcome.message}")
    console.print(f"evidence: {outcome.run_dir}")


async def _replay(recipe_path: Path, url: str | None, headed: bool) -> None:
    from .browser import FileStore, open_session
    from .recipe import Recipe, replay
    from .recorder import RunRecorder

    recipe = Recipe.load(recipe_path)
    recorder = RunRecorder(load_settings().runs_dir)
    async with open_session(url or recipe.start_url, headless=not headed, respect_robots=False,
                            scope="web" if recipe.web else "site", files=FileStore(recorder.files_dir)) as session:
        report = await replay(session, recipe, recorder.dir / "code", start_url=url, log=recorder.log)
    summary = {"task": recipe.task, "status": report.status, "steps": report.steps_done, "items": len(report.rows), "files": report.files, "recipe": str(recipe_path),
               "findings": [f.__dict__ for f in report.findings]}
    recorder.save_result(report.rows, report.fields, summary)
    colour = {"replayed": "green", "changed": "yellow"}.get(report.status, "red")
    console.print(f"[{colour}]{report.status}[/{colour}]: {report.steps_done} of {len(recipe.steps)} steps, {len(report.rows)} items{f', {len(report.files)} files' if report.files else ''}, no model used")
    for finding in report.findings:
        console.print(f"  [{'red' if finding.blocking else 'yellow'}]{finding.kind}[/] step {finding.step}: {finding.detail}")
    console.print(f"evidence: {recorder.dir}")


@app.command()
def replay(
    recipe: Path = typer.Argument(..., help="A recipe.json saved by a completed run (or the run folder that holds it)."),
    url: str | None = typer.Option(None, "--url", help="Replay against another start URL (for example a staging copy of the site)."),
    headed: bool = typer.Option(False, "--headed", help="Show the browser window."),
) -> None:
    """Repeat a recorded run with no model, and report where the site no longer matches it."""
    from .recipe import RECIPE_FILE

    path = recipe / RECIPE_FILE if recipe.is_dir() else recipe
    try:
        asyncio.run(_replay(path, url, headed))
    except (ConfigError, OSError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error


@app.command()
def run(
    task: str = typer.Argument(..., help='What to do, e.g. "open the SIH website and extract all problem statements".'),
    url: str | None = typer.Option(None, "--url", help="Start URL (otherwise the model infers it)."),
    provider: str | None = typer.Option(None, "--provider", "-p", help="Provider to use (default from scoutskit.toml)."),
    max_steps: int | None = typer.Option(None, "--max-steps", help="Override agent.max_steps."),
    headed: bool = typer.Option(False, "--headed", help="Show the browser window."),
    strict: bool = typer.Option(False, "--strict", help="Use only --provider, with no fallback to other providers."),
    web: bool = typer.Option(False, "--web", help="Allow visiting any public website (starts from a search when no --url is given)."),
) -> None:
    """Run a natural-language task in a browser and save the result with evidence."""
    from .provider.llm import LLMError

    try:
        asyncio.run(_run(task, url, provider, max_steps, headed, strict, web))
    except (ConfigError, LLMError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", help="Port to listen on (127.0.0.1 only)."),
    open_browser: bool = typer.Option(False, "--open", help="Open the interface in your browser."),
) -> None:
    """Start the local server the web UI talks to."""
    import threading
    import webbrowser

    import uvicorn

    from .server import create_app
    from .preflight import UI_DIST

    address = f"http://127.0.0.1:{port}"
    if not (UI_DIST / "index.html").is_file():
        console.print("[yellow]The interface is not built: run `cd ui && npm install && npm run build` (the API still works).[/yellow]")
    console.print(f"ScoutsKit is running at [bold]{address}[/bold]   (Ctrl C to stop)")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(address)).start()
    uvicorn.run(create_app(load_settings().runs_dir), host="127.0.0.1", port=port, log_level="warning")
