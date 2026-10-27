"""Read each device's report of itself under the configuration the person approved (card 092).

    python microscope_runtime/src/read_devices.py --run-id run-YYYYMMDD-NNN --mm-config <file.cfg>

A preparatory run (operator.run_device_reading): it loads the approved configuration, reads, and
writes nothing to the stand. On hardware it needs the person at the microscope and the hardware
visit asked through the intake seat; nothing here asks for either, and nothing here is run by a
session without that. The record is runs/<run_id>/, written, and printed as one line per device.
A refusal exits 2 and says why, before anything is loaded.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


op = _load("_operator_for_read_devices", _HERE / "operator.py")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="read each device's report of itself (card 092)")
    parser.add_argument("--run-id", required=True, help="runs/<run_id>/ is created and never overwritten (P9)")
    parser.add_argument("--mm-config", required=True, type=Path,
                        help="a Micro-Manager configuration file the person approved by sha256 under approvals/")
    parser.add_argument("--backend", default="hardware",
                        help="hardware; the mock loads no configuration and is refused")
    parser.add_argument("--runs-root", type=Path, default=None,
                        help="where runs/<run_id>/ is written (default: this folder's runs/)")
    args = parser.parse_args(argv)
    try:
        record = op.run_device_reading(args.run_id, runs_root=args.runs_root or op.AGENT / "runs", backend=args.backend,
                                       mm_config=args.mm_config)
    except op.Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"run {record['run_id']}: {record['ended']}, configuration sha256 "
          f"{record['approved_commands']['sha256']}")
    for event in record["events"]:
        if event["event"] == "device_report":
            if not event["loaded"]:
                print(f"  {event['label']}: not loaded")
                continue
            unread = [p["property"] for p in event["properties"] if "unread" in p]
            print(f"  {event['label']}: {len(event['properties'])} read-only properties"
                  + (f", unread: {unread}" if unread else ""))
        elif event["event"] == "device_reading_failed":
            print(f"  FAILED: {event['error']}")
    return 0 if record["ended"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
