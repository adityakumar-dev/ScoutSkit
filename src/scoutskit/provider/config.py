"""Settings and provider resolution.

scoutskit.toml names the providers and the default; .env supplies the keys.
resolve_provider() is the single place a (model_name, api_key) pair is built,
so a future web portal can pass a per-user key in without touching the agent.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, Field, model_validator

CONFIG_NAME = "scoutskit.toml"
# Providers ScoutsKit's own LLM client (provider/llm.py) can call from the model prefix alone.
KNOWN_PREFIXES = ("openai", "anthropic", "google", "groq", "cerebras", "openrouter")
# Any other OpenAI-compatible endpoint is configured with base_url instead of a known prefix.
COMPATIBLE = "openai_compatible"


class ConfigError(Exception):
    """Raised for a missing or invalid configuration, with a fix in the message."""


class ProviderConfig(BaseModel):
    model: str
    api_key_env: str
    # Any OpenAI-compatible endpoint (NVIDIA NIM, a local NIM, Ollama, ...): set base_url.
    base_url: str | None = None
    extra_body: dict = Field(default_factory=dict)  # merged into the request, e.g. chat_template_kwargs
    max_tokens: int = Field(4000, ge=256)  # output cap per reply; thinking models spend part of it on reasoning
    is_working: bool | None = None  # set in memory by provider.quick_test, never read from the toml

    @model_validator(mode="after")
    def _check_model(self) -> ProviderConfig:
        if self.base_url:
            return self
        prefix = self.model.split("/", 1)[0]
        if "/" not in self.model or prefix not in KNOWN_PREFIXES:
            raise ValueError(
                f"model {self.model!r} must look like '<provider>/<model>' "
                f"with provider in {', '.join(KNOWN_PREFIXES)}"
            )
        return self

    @property
    def kind(self) -> str:
        return COMPATIBLE if self.base_url else self.model.split("/", 1)[0]

    @property
    def api_model(self) -> str:
        """The model id sent to the API: the full id for custom endpoints, else without the provider prefix."""
        return self.model if self.base_url else self.model.split("/", 1)[1]


class AgentConfig(BaseModel):
    max_steps: int = Field(25, ge=1)
    step_timeout_s: float = Field(60, gt=0)
    headless: bool = True
    team_token_budget: int = 600_000  # prompt + completion tokens all sub-agents of one run may use together; 0 = no limit
    search_sources: list[str] = ["web", "wikipedia"]  # where the brief looks for context when no site is named


class RunsConfig(BaseModel):
    dir: str = "runs"


class Settings(BaseModel):
    default_provider: str
    providers: dict[str, ProviderConfig]
    agent: AgentConfig = AgentConfig()
    runs: RunsConfig = RunsConfig()
    root: Path = Path(".")

    @model_validator(mode="after")
    def _check_default(self) -> Settings:
        if self.default_provider not in self.providers:
            raise ValueError(
                f"default_provider {self.default_provider!r} is not defined under [providers]"
            )
        return self

    @property
    def runs_dir(self) -> Path:
        path = Path(self.runs.dir)
        return path if path.is_absolute() else self.root / path


class ResolvedProvider(BaseModel):
    name: str
    model_name: str  # as written in the config, e.g. "google/gemini-2.5-flash"
    api_key: str
    kind: str  # google | anthropic | openai | groq | cerebras | openrouter | openai_compatible
    api_model: str  # the id to send to the API
    base_url: str | None = None
    extra_body: dict = Field(default_factory=dict)
    max_tokens: int = 4000


def _find_config(start: Path) -> Path:
    override = os.environ.get("SCOUTSKIT_CONFIG")
    if override:
        path = Path(override)
        if not path.is_file():
            raise ConfigError(f"SCOUTSKIT_CONFIG points to {path}, which does not exist")
        return path
    for folder in (start, *start.parents):
        candidate = folder / CONFIG_NAME
        if candidate.is_file():
            return candidate
    raise ConfigError(f"No {CONFIG_NAME} found in {start} or any parent folder")


def load_settings(start: Path | None = None) -> Settings:
    load_dotenv(find_dotenv(usecwd=True))
    path = _find_config((start or Path.cwd()).resolve())
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    env_default = os.environ.get("SCOUTSKIT_PROVIDER")
    if env_default:
        raw["default_provider"] = env_default
    try:
        return Settings.model_validate({**raw, "root": path.parent})
    except ValueError as error:
        raise ConfigError(f"Invalid {path}: {error}") from error


def resolve_provider(
    settings: Settings, name: str | None = None, *, api_key: str | None = None
) -> ResolvedProvider:
    """Build the (model_name, api_key) pair for a provider.

    api_key, when given, wins over the environment (used by the future portal).
    """
    chosen = name or settings.default_provider
    config = settings.providers.get(chosen)
    if config is None:
        known = ", ".join(settings.providers)
        raise ConfigError(f"Unknown provider {chosen!r}. Configured: {known}")
    key = api_key or os.environ.get(config.api_key_env, "").strip()
    if not key:
        raise ConfigError(
            f"No API key for provider {chosen!r}. Set {config.api_key_env} in .env "
            f"or pick another provider with --provider."
        )
    return ResolvedProvider(
        name=chosen, model_name=config.model, api_key=key, kind=config.kind,
        api_model=config.api_model, base_url=config.base_url, extra_body=config.extra_body, max_tokens=config.max_tokens,
    )


def key_status(settings: Settings) -> dict[str, bool]:
    return {
        name: bool(os.environ.get(cfg.api_key_env, "").strip())
        for name, cfg in settings.providers.items()
    }
