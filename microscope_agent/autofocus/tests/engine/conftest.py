"""Engine test fixtures. FakeBackend lives in `engine_fakes` (T-015d): import it from
there, never from this module. The re-export below keeps in-flight branches working for
one transition."""

from __future__ import annotations

import pytest
from engine_fakes import LABELS, FakeBackend  # noqa: F401 - re-export (T-015d)


@pytest.fixture
def fake() -> FakeBackend:
    return FakeBackend()
