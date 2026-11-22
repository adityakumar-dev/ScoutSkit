"""A recipe: what a successful run did, as plain data that can be saved, read and replayed without a model."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

RECIPE_FILE = "recipe.json"


@dataclass(frozen=True)
class Step:
    tool: str
    args: dict
    url_path: str  # the page this step was recorded on (path only: the page it expects to find)
    target: str = ""  # role and accessible name of the element acted on, e.g. 'button "Load more"'
    nth: int = 0  # which one, when several elements share that role and name


@dataclass(frozen=True)
class Feed:
    """The data request the run's items came from: read it again on replay."""

    path: str  # the request's URL path
    fields: list[str]  # the columns the run collected from its records


@dataclass
class Recipe:
    task: str
    start_url: str
    steps: list[Step]
    fields: list[str] = field(default_factory=list)
    key_field: str = ""
    expected_items: int = 0  # what the recorded run collected: replay compares against it
    feed: Feed | None = None
    web: bool = False  # the run left its start site, so replay needs the open-web scope too
    extracts: bool = False  # True when the run's data came from a script that reads the page, so replay can repeat it

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Recipe":
        data = json.loads(path.read_text(encoding="utf-8"))
        data["steps"] = [Step(**step) for step in data["steps"]]
        data["feed"] = Feed(**data["feed"]) if data.get("feed") else None
        return cls(**data)
