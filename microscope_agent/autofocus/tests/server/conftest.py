"""Fixtures for the server tests. The fakes live in `server_fakes` (T-015e): test modules
import them from there by name. The re-export below keeps in-flight branches working for
one transition."""

from __future__ import annotations

from typing import Any

import pytest
from server_fakes import (  # noqa: F401 - re-export for one transition (T-015e)
    ADMIN,
    LOCAL,
    OPERATOR,
    OPERATOR2,
    REMOTE,
    TEST_PASSWORD,
    USERS,
    VIEWER,
    EventsSocket,
    FakeEngine,
    FakeFrameEngine,
    LoopbackClient,
    log_in,
)

from dino_autofocus.agents import MockStore
from dino_autofocus.auth import config as auth_config
from dino_autofocus.auth import passwords
from dino_autofocus.server import create_app
from dino_autofocus.server.api import AuthSeat


def pytest_configure(config):
    config.addinivalue_line("markers", "real_scrypt: keep the production scrypt cost")


@pytest.fixture(autouse=True)
def fast_scrypt(request, monkeypatch):
    """As tests/auth/conftest.py: `seat` seeds four accounts per test, and at the production
    cost (n=2**14, ~0.8 s each here) that made every client test spend ~3.4 s in setup and
    tests/server no longer finished in 25 minutes (AF 통합, 2026-10-09). The cost itself is
    tested in tests/auth (real_scrypt); a test here that needs it takes the same marker."""
    if request.node.get_closest_marker("real_scrypt") is None:
        monkeypatch.setattr(passwords, "SCRYPT_N", 2**10)


@pytest.fixture(autouse=True)
def isolated_auth_config(tmp_path, monkeypatch):
    """No test reads the real settings folder or a real admin email."""
    monkeypatch.setenv(auth_config.CONFIG_DIR_ENV, str(tmp_path / "config"))
    monkeypatch.delenv(auth_config.ADMIN_EMAIL_ENV, raising=False)


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def frame_engine() -> FakeFrameEngine:
    return FakeFrameEngine()


@pytest.fixture
def seat(tmp_path) -> AuthSeat:
    s = AuthSeat.from_config(tmp_path / "auth")
    s.accounts.seed(USERS, TEST_PASSWORD)
    return s


@pytest.fixture(scope="session")
def agent_store(tmp_path_factory):
    """One MockStore for the whole run: building one takes a fraction of a second."""
    return MockStore(tmp_path_factory.mktemp("agent-store"))


@pytest.fixture
def make_client(tmp_path, agent_store, seat):
    """`make_client(engine, remote=False, login=OPERATOR, control=False, **create_app_kwargs)`.

    `login` is the seeded account whose cookie the client carries (None: no cookie);
    `control` takes device control for it (local only). No web build unless given."""

    def make(engine: Any, *, remote: bool = False, login: str | None = OPERATOR,
             control: bool = False, **kw) -> LoopbackClient:
        kw.setdefault("web_dist", tmp_path / "no-web-dist")
        kw.setdefault("agent_store", agent_store)
        kw.setdefault("auth", seat)
        app = create_app(engine, engine_name="fake", **kw)
        client = LoopbackClient(app, base_url="http://127.0.0.1:8765",
                                client=REMOTE if remote else LOCAL)
        if login is not None:
            token = log_in(kw["auth"], client, login)
            if control:
                kw["auth"].acquire(token, local=True)
        return client

    return make


@pytest.fixture
def log_in_as(seat):
    """`log_in_as(client, email)` sets that seeded account's login cookie on any TestClient."""
    return lambda client, email: log_in(seat, client, email)
