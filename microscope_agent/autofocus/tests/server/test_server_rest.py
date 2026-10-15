from __future__ import annotations

import importlib
import pkgutil
import sys

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from dino_autofocus.agents import MockStore
from dino_autofocus.server import create_app
from dino_autofocus.server.api import include_area_routers


def test_health_and_state(engine, make_client):
    c = make_client(engine, remote_view=True)
    assert c.get("/api/health").json() == {
        "status": "ok", "engine": "fake", "remote_view": True, "remote_abort": True}
    state = c.get("/api/state").json()
    assert state["positions"]["z_um"] == 3000.0 and state["running"] == []
    assert state["owner"] is None and state["session"] is None  # typed defaults


def test_command_round_trip(engine, make_client):
    c = make_client(engine)
    r = c.post("/api/commands", json={"kind": "start", "op": "status", "args": {"n": 2}})
    assert r.status_code == 200
    assert r.json() == {"op_id": "op1"}
    (cmd,) = engine.commands
    assert (cmd.kind, cmd.op, cmd.args) == ("start", "status", {"n": 2})
    assert cmd.t > 0

    r = c.post("/api/commands", json={"kind": "abort", "op_id": "op1"})
    assert r.json() == {"op_id": "op1"}
    assert c.post("/api/commands", json={"kind": "lights_off"}).status_code == 200
    assert [x.kind for x in engine.commands] == ["start", "abort", "lights_off"]


def test_bad_commands(engine, make_client):
    c = make_client(engine)
    assert c.post("/api/commands", json={"kind": "move_z"}).status_code == 422
    r = c.post("/api/commands", json={"kind": "start", "op": "unknown_op"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "refused"
    assert "unknown_op" in r.json()["detail"]["message"]
    assert engine.commands == []


def test_remote_may_read_but_not_command(engine, make_client):
    c = make_client(engine, remote=True, remote_view=True)
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/state").status_code == 200
    r = c.post("/api/commands", json={"kind": "lights_off"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "remote_view"
    assert r.headers["X-DinoAF-Refusal"] == "remote_view"
    # any non-read method, on any path, including area routers and unknown paths
    assert c.put("/api/anything", json={}).status_code == 403
    assert c.delete("/api/anything").status_code == 403
    assert engine.commands == []


def test_commands_refused_from_foreign_pages(engine, make_client):
    c = make_client(engine)
    body = {"kind": "lights_off"}
    evil = c.post("/api/commands", json=body, headers={"origin": "https://example.com"})
    assert evil.status_code == 403
    same = c.post("/api/commands", json=body, headers={"origin": "http://127.0.0.1:8765"})
    assert same.status_code == 200
    # the Vite dev server on this PC: refused unless named with --dev-origin (T-009c)
    dev = {"origin": "http://localhost:5173"}
    assert c.post("/api/commands", json=body, headers=dev).status_code == 403
    listed = make_client(engine, dev_origins=["http://localhost:5173"])
    assert listed.post("/api/commands", json=body, headers=dev).status_code == 200
    assert len(engine.commands) == 2


def test_area_router_discovery(tmp_path, monkeypatch, engine, agent_store, seat, log_in_as):
    pkg = tmp_path / "fake_areas"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "_private.py").write_text("raise RuntimeError('must be skipped')\n")
    (pkg / "demo.py").write_text(
        "from fastapi import APIRouter\n"
        "from dino_autofocus.server.api import AgentStoreDep, Engine, IsLocal, LocalOnly\n"
        "router = APIRouter()\n"
        "@router.get('/ping')\n"
        "def ping(eng: Engine, store: AgentStoreDep, local: IsLocal) -> dict:\n"
        "    return {'pong': eng.snapshot()['running'], 'local': local,\n"
        "            'store': type(store).__name__}\n"
        "@router.put('/note', dependencies=[LocalOnly])\n"
        "def note() -> dict:\n"
        "    return {'ok': True}\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    app = FastAPI()
    app.state.engine = engine
    app.state.agent_store = agent_store
    app.state.auth = seat
    assert include_area_routers(app, "fake_areas") == ["demo"]
    local = TestClient(app, client=("127.0.0.1", 1))
    log_in_as(local, "otto@example.test")
    assert local.get("/api/demo/ping").json() == {"pong": [], "local": True,
                                                  "store": "MockStore"}
    assert local.put("/api/demo/note").json() == {"ok": True}
    remote = TestClient(app, client=("10.0.0.5", 1))
    log_in_as(remote, "otto@example.test")
    assert remote.get("/api/demo/ping").json()["local"] is False
    assert remote.put("/api/demo/note").status_code == 403

    (pkg / "broken.py").write_text("x = 1\n")
    sys.modules.pop("fake_areas", None)
    try:
        include_area_routers(FastAPI(), "fake_areas")
    except TypeError as e:
        assert "broken" in str(e)
    else:
        raise AssertionError("a module without a router must be refused")


def assert_mounted(app: FastAPI, name: str, router: APIRouter) -> int:
    """Every HTTP route of `router` is served at /api/<name>/... Read from the app's OpenAPI
    paths, not `app.routes`: with FastAPI 0.142 / Starlette 1.7 an included router is one
    `_IncludedRouter` entry without a path there. Returns how many routes were checked.
    WebSocket routes are not in the OpenAPI paths: an area that adds one needs this check to
    walk `_IncludedRouter.original_router` as well (none does today)."""
    paths = app.openapi()["paths"]
    checked = 0
    for route in router.routes:
        if isinstance(route, APIRoute) and route.include_in_schema:
            assert f"/api/{name}{route.path}" in paths, (name, route.path, sorted(paths))
            checked += 1
    return checked


def area_modules(package: str) -> list[str]:
    pkg = importlib.import_module(package)
    return sorted(m.name for m in pkgutil.iter_modules(pkg.__path__)
                  if not m.name.startswith("_") and not m.ispkg)


def test_every_area_module_is_mounted_under_its_name(engine, make_client):
    """Whatever areas exist in server/api (none named here): each non-underscore module has a
    module-level APIRouter, and create_app mounts every one of its routes at /api/<module>."""
    names = area_modules("dino_autofocus.server.api")
    app = make_client(engine).app
    for name in names:
        router = importlib.import_module(f"dino_autofocus.server.api.{name}").router
        assert isinstance(router, APIRouter), name
        assert_mounted(app, name, router)


def test_the_mount_check_sees_a_real_area(tmp_path, monkeypatch, engine, make_client):
    """The same check on a temporary package with a real router, so it is exercised (and
    would fail) on a main with no areas, exactly as it will with real ones."""
    pkg = tmp_path / "mount_areas"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "demo.py").write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n"
        "@router.get('/things/{thing_id}')\n"
        "def thing(thing_id: str) -> dict:\n"
        "    return {'id': thing_id}\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    c = make_client(engine)
    assert include_area_routers(c.app, "mount_areas") == ["demo"] == area_modules("mount_areas")
    c.app.openapi_schema = None  # routes were added after create_app
    router = importlib.import_module("mount_areas.demo").router
    assert assert_mounted(c.app, "demo", router) == 1
    assert c.get("/api/demo/things/7").json() == {"id": "7"}  # and it really answers there
    with pytest.raises(AssertionError):
        assert_mounted(c.app, "elsewhere", router)  # the check can fail


def test_agent_store_on_app_state(engine, make_client, agent_store):
    assert make_client(engine).app.state.agent_store is agent_store
    assert isinstance(create_app(engine).state.agent_store, MockStore)  # the dev default
