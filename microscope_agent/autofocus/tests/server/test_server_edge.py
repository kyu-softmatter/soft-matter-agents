"""Edge checks (public-release audit S5, S6, S8): proxied requests refused, API docs only on
this PC, security headers. Fake engine and example.test accounts only."""

from __future__ import annotations

import pytest
from starlette.websockets import WebSocketDisconnect


@pytest.mark.parametrize("header", ["X-Forwarded-For", "Forwarded", "Via", "X-Real-IP",
                                    "CF-Connecting-IP"])
def test_a_forwarded_request_from_loopback_is_refused(engine, make_client, header):
    c = make_client(engine)
    assert c.get("/api/state").status_code == 200
    r = c.get("/api/state", headers={header: "203.0.113.7"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "proxied"
    assert r.headers["x-dinoaf-refusal"] == "proxied"
    r = c.post("/api/commands", json={"kind": "abort"}, headers={header: "203.0.113.7"})
    assert r.status_code == 403
    assert engine.commands == []


def test_a_forwarded_websocket_is_refused(engine, make_client):
    c = make_client(engine)
    with pytest.raises(WebSocketDisconnect), \
            c.websocket_connect("/ws/events", headers={"X-Forwarded-For": "203.0.113.7"},
                                raw=True) as ws:
        ws.receive_text()
    assert engine.sinks == []


def test_api_docs_only_on_this_pc(engine, make_client):
    local = make_client(engine, login=None)
    remote = make_client(engine, remote=True, remote_view=True, login=None)
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert local.get(path).status_code == 200, path
        assert remote.get(path).status_code == 404, path
    assert remote.get("/api/health").status_code == 200


def test_security_headers_on_every_response(engine, make_client):
    c = make_client(engine, login=None)
    for path in ("/", "/api/health", "/api/state"):  # page, open read, refused read
        h = c.get(path).headers
        assert h["x-content-type-options"] == "nosniff", path
        assert h["x-frame-options"] == "DENY", path
        assert h["referrer-policy"] == "no-referrer", path
        csp = h["content-security-policy"]
        assert "frame-ancestors 'none'" in csp and "script-src 'self'" in csp, path
    docs_csp = c.get("/docs").headers["content-security-policy"]
    assert docs_csp == "frame-ancestors 'none'"  # Swagger UI loads its scripts from a CDN
