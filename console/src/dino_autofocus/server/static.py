"""Serve the built React app (`web/dist`) at `/`. Node is needed to build it, not to run it.

Unknown paths outside `/api` and `/ws` fall back to `index.html` so client-side routes load.
Without a build, `/` shows how to make one.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles

# src/dino_autofocus/server/static.py -> repository root
DEFAULT_WEB_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"

NOT_BUILT = """<!doctype html>
<html><head><meta charset="utf-8"><title>dino-autofocus</title></head>
<body style="font-family: sans-serif; max-width: 40em; margin: 3em auto">
<h1>dino-autofocus server is running</h1>
<p>The web app is not built: <code>{dist}</code> has no <code>index.html</code>.</p>
<p>Build it with <code>uv run npm --prefix web run build</code>, then reload.</p>
<p>The API is up: <a href="/api/health">/api/health</a>, <a href="/docs">/docs</a>.</p>
</body></html>
"""


class SpaStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as e:
            top = path.replace("\\", "/").split("/", 1)[0]  # path is OS-normalised on Windows
            if e.status_code != 404 or top in ("api", "ws"):
                raise
            return await super().get_response("index.html", scope)


def mount_web(app: FastAPI, dist: Path | None = None) -> bool:
    """Mount after all API routes. Returns whether a build was found."""
    dist = Path(dist) if dist is not None else DEFAULT_WEB_DIST
    if (dist / "index.html").is_file():
        app.mount("/", SpaStaticFiles(directory=dist, html=True), name="web")
        return True

    @app.get("/", include_in_schema=False)
    def not_built() -> HTMLResponse:
        return HTMLResponse(NOT_BUILT.format(dist=dist))

    return False
