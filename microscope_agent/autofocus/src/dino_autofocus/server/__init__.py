"""Local web app back end (FastAPI): owns the engine, exposes REST and WebSocket, serves web/dist.

Importing this package pulls in no torch, pymmcore or UI toolkit (tests/server checks it).
Run with `uv run python -m dino_autofocus.server`.
"""

from .api import command_refusal
from .app import create_app
from .schemas import EngineAPI, FrameSource

__all__ = ["EngineAPI", "FrameSource", "command_refusal", "create_app"]
