"""Checks at the edge of the server, before any route (public-release audit S5, S6, S8).

* **Proxied requests are refused (S5).** "Loopback" means "the microscope PC" (stops without a
  login, shutdown, first-run setup). A port forwarder or reverse proxy on this PC (ssh -L/-R,
  ngrok, cloudflared, Tailscale serve, an IDE's port forwarding) makes remote traffic arrive
  from 127.0.0.1. Most of them add a forwarding header; a request that carries one is refused
  with 403, HTTP and WebSocket alike. A forwarder that adds none is not caught here: never
  forward or proxy the server port (docs/runbooks/launcher.md). The Vite dev proxy adds none
  (`xfwd` is off), so `npm run dev` still works.
* **API docs only on this PC (S6).** `/docs`, `/redoc` and `/openapi.json` answer 404 to other
  PCs (remote view); they are outside `/api/`, so the login check does not cover them.
* **Security headers (S8)** on every HTTP response: `nosniff`, no framing, no referrer, and a
  Content-Security-Policy for the web app (same-origin scripts, connections and frames only).
  The Swagger and ReDoc pages load their scripts from a CDN, so they get no CSP beyond
  `frame-ancestors`.
"""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .api import is_loopback_host

#: Headers a forwarder or proxy adds. Lower case, as ASGI gives them.
FORWARDING_HEADERS = frozenset({
    b"forwarded", b"via", b"x-forwarded-for", b"x-forwarded-host", b"x-forwarded-proto",
    b"x-forwarded-port", b"x-real-ip", b"x-original-forwarded-for", b"cf-connecting-ip",
    b"true-client-ip", b"x-client-ip", b"x-cluster-client-ip", b"fastly-client-ip",
})
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"})

APP_CSP = "; ".join((
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",  # React style props and libraries' injected styles
    "img-src 'self' data: blob:",  # live frames arrive as blob URLs
    "font-src 'self' data:",
    "connect-src 'self'",  # same-origin fetch and WebSocket (CSP 3 lets 'self' match ws:)
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
))
DOCS_CSP = "frame-ancestors 'none'"
COMMON_HEADERS = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
)


class EdgeMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        if any(name in FORWARDING_HEADERS for name, _ in scope.get("headers", ())):
            await _refuse(scope, receive, send, 403, "proxied",
                          "requests through a proxy or port forwarder are refused")
            return
        path = scope.get("path", "")
        if path in DOCS_PATHS:
            client = scope.get("client")
            if not is_loopback_host(client[0] if client else None):
                await _refuse(scope, receive, send, 404, "not_found", "Not Found")
                return
        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return
        csp = (DOCS_CSP if path in DOCS_PATHS else APP_CSP).encode()

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", ()))
                have = {name.lower() for name, _ in headers}
                extra = [*COMMON_HEADERS, (b"content-security-policy", csp)]
                headers += [(n, v) for n, v in extra if n not in have]
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _refuse(scope: Scope, receive: Receive, send: Send, status: int, code: str,
                  message: str) -> None:
    if scope["type"] == "websocket":
        await receive()  # websocket.connect
        await send({"type": "websocket.close", "code": 1008, "reason": message[:120]})
        return
    body = json.dumps({"detail": {"code": code, "message": message}}).encode()
    await send({"type": "http.response.start", "status": status, "headers": [
        (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
        (b"x-dinoaf-refusal", code.encode()), *COMMON_HEADERS]})
    await send({"type": "http.response.body", "body": body})
