"""T-009i: the server starts the real engine. `build()` opens the backend and makes the runner,
records, login and app without listening, so these tests hold no port and open no window."""

from __future__ import annotations

from pathlib import Path

import pytest

from dino_autofocus.engine.backends.mock import MockBackend
from dino_autofocus.engine.operations import sample_ops
from dino_autofocus.engine.runner import OPERATIONS, Runner
from dino_autofocus.engine.sample import SAMPLES_ROOT
from dino_autofocus.records.layout import DEFAULT_DATA_ROOT, DEFAULT_RECORDS_ROOT
from dino_autofocus.server import __main__ as launcher


def args_for(tmp_path: Path, *extra: str):
    return launcher.parse_args(["--config-dir", str(tmp_path / "config"),
                                "--web-dist", str(tmp_path / "no-web-dist"), *extra])


@pytest.fixture
def built(tmp_path):
    made = []

    def make(*extra: str):
        b = launcher.build(args_for(tmp_path, "--records-root", str(tmp_path / "records"),
                                    *extra))
        made.append(b)
        return b

    yield make
    for b in made:
        b.close("test teardown")


def test_mock_is_the_default_and_builds_the_real_runner(built, tmp_path):
    assert launcher.parse_args([]).backend == "mock"
    b = built()
    assert isinstance(b.engine, Runner) and isinstance(b.backend, MockBackend)
    ops = set(b.engine.snapshot()["operations"])
    assert set(OPERATIONS.names()) <= ops  # every registered operation
    assert {"hardware_scan", "hardware_confirm"} <= ops  # the hardware provider
    assert set(sample_ops.OPS) <= ops
    assert b.app.state.hardware is not None and b.app.state.committer is not None
    assert Path(b.app.state.records.config.records_root) == tmp_path / "records"
    assert b.engine.sample_seat.samples_root == tmp_path / "records-samples"
    assert b.roots == (tmp_path / "records", tmp_path / "records-data",
                       tmp_path / "records-samples")


def test_close_stops_the_engine_then_closes_the_backend_once(built, monkeypatch):
    b = built()
    order = []
    monkeypatch.setattr(b.app.state.stop_engine, "_engine", _Spy(b.engine, order))
    real_close = b.backend.close
    monkeypatch.setattr(b.backend, "close", lambda: (order.append("backend"), real_close()))
    b.close("test")
    b.close("again")
    assert order == ["engine", "backend"]


class _Spy:
    def __init__(self, engine, order):
        self._engine, self._order = engine, order

    def shutdown(self, reason):
        self._order.append("engine")
        return self._engine.shutdown(reason)


def test_simulated_backends_default_to_the_mock_folders():
    real = launcher.record_roots(None, bench=True)
    mock = launcher.record_roots(None, bench=False)
    assert real[:2] == (DEFAULT_RECORDS_ROOT, DEFAULT_DATA_ROOT)
    assert mock[0] == DEFAULT_RECORDS_ROOT.with_name(DEFAULT_RECORDS_ROOT.name + "-mock")
    assert mock[1] == DEFAULT_DATA_ROOT.with_name(DEFAULT_DATA_ROOT.name + "-mock")
    assert all(m != r for m, r in zip(mock, real, strict=True))


REAL_SAMPLES = Path(SAMPLES_ROOT)


@pytest.mark.parametrize(("root", "real"), [
    (DEFAULT_RECORDS_ROOT, "records"),  # the real records folder itself
    (DEFAULT_RECORDS_ROOT / "sub", "records"),  # inside it
    (Path(str(DEFAULT_RECORDS_ROOT).upper()) / "x", "records"),  # Windows: any case
    (DEFAULT_DATA_ROOT, "data"),  # the real data folder as the records root
    (DEFAULT_DATA_ROOT / "x", "data"),
    (REAL_SAMPLES / "x", "samples"),
    (DEFAULT_RECORDS_ROOT.parent, "records"),  # a folder that holds the real ones
], ids=["records", "inside-records", "case", "data", "inside-data", "inside-samples",
        "parent"])
def test_simulated_backend_never_writes_into_the_real_tree(root, real):
    with pytest.raises(SystemExit, match=f"overlaps the real {real} folder"):
        launcher.record_roots(root, bench=False)


def test_real_folders_stay_for_the_bench_and_others_are_fine(tmp_path):
    assert launcher.record_roots(DEFAULT_RECORDS_ROOT, bench=True)[0] == DEFAULT_RECORDS_ROOT
    assert launcher.record_roots(DEFAULT_RECORDS_ROOT / "sub", bench=True)[0] == \
        DEFAULT_RECORDS_ROOT / "sub"
    other = tmp_path / "rec"
    assert launcher.record_roots(other, bench=False) == (
        other, tmp_path / "rec-data", tmp_path / "rec-samples")
    beside = DEFAULT_RECORDS_ROOT.with_name("records-elsewhere")  # a sibling, not inside
    assert launcher.record_roots(beside, bench=False)[0] == beside


def test_failed_start_up_stops_the_runner_before_closing_the_backend(tmp_path, monkeypatch):
    order = []
    monkeypatch.setattr(Runner, "shutdown",
                        lambda self, reason="", timeout=15.0: order.append("runner"))
    monkeypatch.setattr(MockBackend, "close", lambda self: order.append("backend"))

    def broken_app(*a, **kw):
        raise RuntimeError("create_app broke")

    monkeypatch.setattr(launcher, "create_app", broken_app)
    with pytest.raises(RuntimeError, match="create_app broke"):
        launcher.build(args_for(tmp_path, "--records-root", str(tmp_path / "records")))
    assert order == ["runner", "backend"]


def test_mock_build_refuses_the_real_records_root(tmp_path):
    with pytest.raises(SystemExit, match="real records folder"):
        launcher.build(args_for(tmp_path, "--records-root", str(DEFAULT_RECORDS_ROOT)))


@pytest.mark.parametrize(("backend", "message"), [
    ("nope", "unknown backend 'nope'; choose one of mock, mm-demo, replay, mm-real"),
])
def test_backends_that_do_not_exist_exit_with_the_reason(backend, message, tmp_path):
    with pytest.raises(SystemExit, match=message):
        launcher.build(args_for(tmp_path, "--backend", backend))


def test_mm_real_without_the_stand_fails_cleanly_and_never_falls_back(tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(MockBackend, "open", lambda self: opened.append(self))
    missing = tmp_path / "no-such.cfg"
    with pytest.raises(SystemExit) as e:
        launcher.build(args_for(tmp_path, "--backend", "mm-real", "--mm-config", str(missing)))
    text = str(e.value)
    assert "'mm-real' cannot open on this PC" in text and "no other backend" in text
    assert opened == []  # the mock was never opened in its place


def test_main_serves_the_built_engine_and_closes_it(tmp_path, monkeypatch):
    seen = {}

    def fake_serve(b, *, port, remote_view):
        seen["built"], seen["port"] = b, port
        assert isinstance(b.engine, Runner)

    monkeypatch.setattr(launcher, "serve", fake_serve)
    monkeypatch.setattr(launcher.atexit, "register", lambda *a, **kw: None)
    argv = ["--config-dir", str(tmp_path / "config"), "--records-root", str(tmp_path / "rec"),
            "--web-dist", str(tmp_path / "no-web-dist"), "--port", "8799"]
    assert launcher.main(argv) == 0
    assert seen["port"] == 8799
    state = seen["built"].app.state
    # the sessions router (T-106) needs both: no 503 no_records on the real server
    assert Path(state.records.config.records_root) == tmp_path / "rec"
    assert type(state.records).__name__ in ("GitFolderStore", "FolderStore")
    assert state.committer is not None and state.committer.store is state.records
    assert state.stop_engine.done  # the engine was stopped on the way out
