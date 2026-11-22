"""The server behind the web UI: starts runs, streams their events and live picture."""

from .app import create_app

__all__ = ["create_app"]
