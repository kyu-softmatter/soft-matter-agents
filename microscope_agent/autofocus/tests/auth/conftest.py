import json
from pathlib import Path

import pytest

from dino_autofocus.auth import AccountStore, AuditLog, DeviceControl, LoginSessions, passwords
from dino_autofocus.auth import config as auth_config

FIXTURES = Path(__file__).parent / "fixtures"
#: the one password every seeded fake user gets (a test value, not a real credential)
SEED_PASSWORD = "seed-pass-1234"


class Clock:
    """Hand-driven time in seconds."""

    def __init__(self, t: float = 1_800_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """No test reads the real settings folder or a real admin email."""
    monkeypatch.setenv(auth_config.CONFIG_DIR_ENV, str(tmp_path / "config"))
    monkeypatch.delenv(auth_config.ADMIN_EMAIL_ENV, raising=False)
    return tmp_path / "config"


@pytest.fixture
def audit(tmp_path):
    return AuditLog(tmp_path / "config" / "audit.jsonl")


@pytest.fixture
def store(tmp_path, audit):
    return AccountStore(tmp_path / "config" / "accounts.json", audit=audit)


@pytest.fixture
def seeded(store):
    users = json.loads((FIXTURES / "users.json").read_text(encoding="utf-8"))["users"]
    store.seed(users, SEED_PASSWORD)
    return store


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def logins(seeded, audit, clock):
    return LoginSessions(seeded, audit=audit, idle_lock_s=600, max_age_s=3600, clock=clock)


@pytest.fixture
def control(logins, audit, clock):
    return DeviceControl(logins, audit=audit, clock=clock)


@pytest.fixture
def login(logins):
    def _login(email: str) -> str:
        result = logins.login(email, SEED_PASSWORD)
        assert result.ok, result.outcome
        return result.token

    return _login


@pytest.fixture
def seed_password():
    return SEED_PASSWORD


def pytest_configure(config):
    config.addinivalue_line("markers", "real_scrypt: keep the production scrypt cost")


@pytest.fixture(autouse=True)
def fast_scrypt(request, monkeypatch):
    """scrypt at the production cost takes ~1 s here; tests use a cheaper n."""
    if request.node.get_closest_marker("real_scrypt") is None:
        monkeypatch.setattr(passwords, "SCRYPT_N", 2**10)
