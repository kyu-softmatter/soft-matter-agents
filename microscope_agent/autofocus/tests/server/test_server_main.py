from __future__ import annotations

import json
import subprocess
import sys

import numpy as np

from dino_autofocus.server.__main__ import PlaceholderEngine, main, simulated_extras
from dino_autofocus.server.schemas import Command

COMMON = {"CommandIn", "CommandAccepted", "EventOut", "Health", "ApiError",
          "WsEvent", "WsCommand", "WsAccepted", "WsError", "WsFrame", "RefusalDetail",
          "Snapshot", "PermissionOut", "OpSummary", "Lights", "Positions"}


def test_dump_openapi(tmp_path, capsys):
    out = tmp_path / "openapi.json"
    assert main(["--dump-openapi", str(out)]) == 0
    spec = json.loads(out.read_text(encoding="utf-8"))
    assert {"/api/health", "/api/state", "/api/commands", "/api/permissions",
            "/api/shutdown"} <= set(spec["paths"])
    schemas = spec["components"]["schemas"]
    assert set(schemas) >= COMMON
    assert schemas["CommandIn"]["properties"]["kind"]["enum"][:2] == ["start", "abort"]
    # WebSocket models refer to the shared ones, not to private copies
    assert schemas["WsEvent"]["properties"]["event"]["$ref"] == "#/components/schemas/EventOut"

    assert main(["--dump-openapi", "-"]) == 0
    assert json.loads(capsys.readouterr().out)["paths"] == spec["paths"]


def test_import_pulls_no_heavy_modules():
    code = (
        "import sys, dino_autofocus.server, dino_autofocus.server.__main__\n"
        "heavy = {'torch', 'pymmcore', 'pymmcore_plus', 'tkinter', 'PySide6', 'PyQt5', 'PyQt6'}\n"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in heavy)\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_placeholder_engine_has_two_cameras_that_share_some_blobs():
    eng = PlaceholderEngine(shape=(600, 800))  # blobs are sigma 40 px: a small frame saturates
    t = 12.3
    blue, red = (eng._picture(t, eng.CAMERAS[c]) for c in ("Kinetix_blue", "Kinetix_red"))
    assert blue.shape == red.shape == (600, 800) and blue.dtype == red.dtype == np.uint16
    assert not np.array_equal(blue, red)
    assert sorted(eng.CAMERAS) == ["Kinetix_blue", "Kinetix_red"]


def test_placeholder_engine_moves_nothing():
    eng = PlaceholderEngine(shape=(60, 80))
    seen = []
    unsubscribe = eng.subscribe(seen.append)
    try:
        op_id = eng.submit(Command(kind="start", op="status"))
        assert [e.kind for e in seen if e.op_id == op_id] == ["started", "finished"]
        before = eng.snapshot()["positions"]
        eng.submit(Command(kind="lights_off"))
        assert eng.snapshot()["positions"] == before
    finally:
        unsubscribe()


def test_simulated_backends_get_mock_tweezers_and_piezo_and_only_the_mock_a_stream():
    from dino_autofocus.engine.backends.mock import MockBackend

    mock = MockBackend(seed=1)
    mock.open()
    tw, piezo, stream = simulated_extras("mock", mock, bench=False)
    assert tw.info().kind == "mock" and piezo.info().bench is False
    assert stream is not None and not stream.running()
    tw, piezo, stream = simulated_extras("mm-demo", mock, bench=False)
    assert tw is not None and piezo is not None and stream is None
    assert simulated_extras("mm-real", mock, bench=True) == (None, None, None)
