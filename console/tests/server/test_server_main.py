from __future__ import annotations

import json
import subprocess
import sys

import numpy as np
import pytest

from sma_console.server.__main__ import BACKENDS, PlaceholderEngine, main, parse_args

COMMON = {"EventOut", "Health", "ApiError",
          "WsEvent", "WsError", "WsFrame", "RefusalDetail",
          "Snapshot", "PermissionOut", "OpSummary", "Lights", "Positions"}
#: retired with dino's engine command path (soft-matter-agents card 077)
RETIRED_PATHS = {"/api/commands", "/api/hardware", "/api/map", "/api/objective",
                 "/api/patterns", "/api/sample", "/api/sessions"}


def test_dump_openapi(tmp_path, capsys):
    out = tmp_path / "openapi.json"
    assert main(["--dump-openapi", str(out)]) == 0
    spec = json.loads(out.read_text(encoding="utf-8"))
    assert {"/api/health", "/api/state", "/api/permissions",
            "/api/shutdown"} <= set(spec["paths"])
    assert not [p for p in spec["paths"] if any(p == r or p.startswith(r + "/")
                                                for r in RETIRED_PATHS)]
    schemas = spec["components"]["schemas"]
    assert set(schemas) >= COMMON
    assert not {"CommandIn", "CommandAccepted", "WsCommand", "WsAccepted"} & set(schemas)
    # WebSocket models refer to the shared ones, not to private copies
    assert schemas["WsEvent"]["properties"]["event"]["$ref"] == "#/components/schemas/EventOut"

    assert main(["--dump-openapi", "-"]) == 0
    assert json.loads(capsys.readouterr().out)["paths"] == spec["paths"]


def test_import_pulls_no_heavy_modules():
    code = (
        "import sys, sma_console.server, sma_console.server.__main__\n"
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


def test_placeholder_engine_moves_nothing_and_takes_no_command():
    eng = PlaceholderEngine(shape=(60, 80))
    assert not hasattr(eng, "submit")  # card 077: no command intake
    before = eng.snapshot()["positions"]
    assert eng.check(["scan_4x"])["scan_4x"]["allowed"] is False
    assert eng.snapshot()["positions"] == before


def test_the_placeholder_is_the_only_backend():
    assert BACKENDS == ("placeholder",)
    assert parse_args([]).backend == "placeholder"
    for engine_backend in ("mock", "mm-demo", "replay", "mm-real"):
        with pytest.raises(SystemExit):
            parse_args(["--backend", engine_backend])
