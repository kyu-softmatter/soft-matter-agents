"""The Micro-Manager configuration gate (card 069): what a hardware run may load.

Standard library only, so a test can load it by path and no instrument is
near it. It decides three things and loads nothing itself:

1. The file is the one the person approved. A configuration is a program the
   stand runs on load, so the person's approval is of its sha256, written by
   them under approvals/ and read here, never written (7.1 rule 5). A file
   that is not listed, or whose bytes changed, is refused before anything is
   loaded.
2. The focus direction in it is the one the store says is right. A hash says
   the bytes are the approved bytes; it does not say the direction in them is
   right, so the direction is read from the file and checked, never taken
   from it. See `check_focus_direction`.
3. The System/Startup preset never runs. Loading a configuration applies it,
   and it is a command the file issues. A derived copy without it is written
   into the run's own folder and that copy is what is loaded.

`load` takes the loader as an argument, so a test loads through a fake core on
a non-mock backend and the real one is `devices/micromanager.load_configuration`.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

#: The person's approval of a configuration: a json file under approvals/ with
#: this `artifact` and the file's sha256 under `configuration`. The smallest
#: shape that works (card 069); the schema follows it and does not lead it.
APPROVAL_ARTIFACT = "mm_config_approval"

#: The focus stage the direction is checked for, and the stage the person's
#: tool refuses by name to software (micromanager.NAMED_REFUSALS).
FOCUS_STAGE = "ZDrive"
PFS_STAGE = "PFSOffset"

#: What the rule stands on. The first gives the encoding of FocusDirection in
#: Micro-Manager's own source at the commit matching the installed MMCore
#: 12.5.0 (spec, E3): only the sign of the value counts, and a positive value
#: means increasing position brings objective and sample closer. The second
#: says smaller Z is retracted (E3). Together: increasing Z moves toward the
#: sample, so an agreeing ZDrive value is positive. That derivation is this
#: file's to make and cite, not the store's.
ENCODING_ENTRY = "kb:micromanager_focus_direction_encoding_mmcore_12_5_0"
RETRACT_ENTRY = "kb:z_retract_direction_is_measured"

STARTUP_PREFIX = "ConfigGroup,System,Startup"
_INTEGER = re.compile(r"^[+-]?[0-9]+$")


class ConfigRefused(RuntimeError):
    """The configuration is not loaded, and the reason is a fact, not an opinion."""


class AutoShutterNotVerified(ConfigRefused):
    """The load happened and AutoShutter was not read back as 0, so the run stops.

    Carries the load event: what was loaded is the record even when the run
    does not go on (P1).
    """

    def __init__(self, message: str, event: dict) -> None:
        super().__init__(message)
        self.event = event


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_approvals(approvals_dir: Path) -> list[dict]:
    """Every json card under approvals/. An unreadable one is not an approval."""
    folder = Path(approvals_dir)
    out: list[dict] = []
    if not folder.exists():
        return out
    for path in sorted(folder.glob("*.json")):
        try:
            # utf-8-sig: PowerShell 5.1's Set-Content -Encoding utf8 writes a
            # byte-order mark, and the person writes approvals from there.
            doc = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ConfigRefused(f"{path.name} is not readable JSON: {exc}. "
                                "An unreadable approval is not an approval") from None
        if isinstance(doc, dict):
            doc["__name"] = path.name
            out.append(doc)
    return out


def approval_for(sha256: str, approvals_dir: Path) -> dict | None:
    for doc in read_approvals(approvals_dir):
        if doc.get("artifact") != APPROVAL_ARTIFACT:
            continue
        held = ((doc.get("configuration") or {}).get("sha256") or "").strip().lower()
        if held == sha256:
            return {"id": doc["__name"], "written_by": doc.get("written_by"),
                    "written_at": doc.get("written_at"), "label": doc.get("label")}
    return None


def check_focus_direction(text: str) -> dict:
    """Read the FocusDirection lines and judge them. Refuses; never trusts the file.

    A ZDrive line must be present and its value a positive integer: 0, a
    negative value, a token that is not an integer, an unparseable line, or no
    line at all is refused, with the reason named. No line is refused too: the
    store does not hold what the NikonTi2 adapter reports without one (the
    entry names that gap), and ambiguity stops. More than one ZDrive line is
    refused for the same reason. A line whose label is not the focus stage is
    refused, because Micro-Manager ignores it without a word and a typo there
    would leave the stand on the adapter's unknown default. PFSOffset is the
    other stage a configuration may set; no direction is measured for it, so
    its line is recorded beside the hashes and judged by no one.
    """
    zdrive: list[str] = []
    pfs: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        # A commented-out line needs no test of its own: its first field starts with "#",
        # so it never equals "FocusDirection".
        fields = line.split(",")
        if fields[0].strip() != "FocusDirection":
            continue
        if len(fields) != 3:
            raise ConfigRefused(
                f"line {number} is a FocusDirection line of {len(fields)} tokens, and Micro-Manager "
                f"needs three (FocusDirection,<stage>,<value>): {line!r}. It would fail the load, "
                "and a line nobody can read is not a direction")
        label, value = fields[1].strip(), fields[2].strip()
        if label == FOCUS_STAGE:
            zdrive.append(value)
        elif label == PFS_STAGE:
            pfs.append(value)
        else:
            raise ConfigRefused(
                f"line {number} sets FocusDirection for {label!r}, which is not the configured "
                f"focus stage ({FOCUS_STAGE}). Micro-Manager ignores such a line without a word, so "
                "a typo here would leave the stand on the adapter's unknown default")
    cite = (f"{ENCODING_ENTRY} (only the sign counts; positive means increasing position brings "
            f"objective and sample closer) with {RETRACT_ENTRY} (smaller Z is retracted)")
    if not zdrive:
        raise ConfigRefused(
            f"the file has no FocusDirection line for {FOCUS_STAGE}. The store does not hold what "
            "the NikonTi2 adapter reports without one, and ambiguity stops; the entry that records "
            f"the adapter's default would relax this. The rule stands on {cite}")
    if len(zdrive) > 1:
        raise ConfigRefused(
            f"the file has more than one FocusDirection line for {FOCUS_STAGE} ({len(zdrive)}: "
            f"{zdrive}). Which one Micro-Manager keeps is not on record, and ambiguity stops")
    value = zdrive[0]
    if not _INTEGER.match(value):
        raise ConfigRefused(
            f"FocusDirection for {FOCUS_STAGE} is {value!r}, which is not an integer, and an "
            f"unreadable direction is refused. The rule stands on {cite}")
    number = int(value)
    if number == 0:
        raise ConfigRefused(
            f"FocusDirection for {FOCUS_STAGE} is zero, which Micro-Manager reads as unknown "
            f"direction. The rule stands on {cite}")
    if number < 0:
        raise ConfigRefused(
            f"FocusDirection for {FOCUS_STAGE} is {value}, negative: increasing position moves the "
            f"objective and sample apart, which disagrees with the measured retract direction. "
            f"The rule stands on {cite}")
    out: dict = {FOCUS_STAGE: {"raw": value, "sign": "positive", "checked_against": cite}}
    if pfs:
        sign = "unread"
        if _INTEGER.match(pfs[0]):
            sign = "positive" if int(pfs[0]) > 0 else "negative" if int(pfs[0]) < 0 else "zero"
        out[PFS_STAGE] = {"raw": pfs[0], "sign": sign,
                          "note": f"{PFS_STAGE} is refused by name to software and no direction is "
                                  "measured for it, so this is recorded and judged by no one"}
    else:
        out[PFS_STAGE] = None
    return out


def startup_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.lstrip().startswith(STARTUP_PREFIX)]


def check(cfg_path: Path, approvals_dir: Path) -> dict:
    """Judge a configuration before anything is loaded. Raises ConfigRefused; reads, never writes."""
    path = Path(cfg_path)
    if not path.is_file():
        raise ConfigRefused(f"{path} does not exist, so there is nothing to approve or load")
    data = path.read_bytes()
    digest = _sha256(data)
    approval = approval_for(digest, approvals_dir)
    if approval is None:
        raise ConfigRefused(
            f"{path.name} (sha256 {digest}) is not on the person's approved list: no "
            f"{APPROVAL_ARTIFACT} under {approvals_dir} carries this hash, or the file's bytes "
            "changed after it was approved. Nothing is loaded; the person writes the approval, "
            "this session never does")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ConfigRefused(f"{path.name} is not readable as UTF-8 text ({exc}), so its "
                            "FocusDirection lines cannot be checked") from None
    return {"path": str(path), "sha256": digest, "approval": approval,
            "focus_direction": check_focus_direction(text), "startup_lines": startup_lines(text),
            "_text": text}


def derive(text: str, source_name: str, source_sha256: str) -> tuple[str, list[str]]:
    """The configuration without its System/Startup preset, and the lines removed."""
    kept: list[str] = []
    removed: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(STARTUP_PREFIX):
            removed.append(line.rstrip("\r\n"))
        else:
            kept.append(line)
    header = (f"# DERIVED from {source_name} (sha256 {source_sha256}) by mm_config_gate.py (card 069).\n"
              "# Removed: the System/Startup preset, which is a command the file issues on load.\n"
              "# Nothing else changed.\n")
    return header + "".join(kept), removed


def load(checked: dict, run_folder: Path | None, loader) -> dict:
    """Load a checked configuration through `loader`; return the event the run records.

    `run_folder` is the run's own folder: the derived copy is evidence and
    belongs in the run record, so with no folder (no --write) nothing is
    loaded. Raises AutoShutterNotVerified after the load when AutoShutter was
    not read back as 0, carrying the event.
    """
    if run_folder is None:
        raise ConfigRefused(
            "a hardware load needs the run folder, so --write: the derived copy of the "
            "configuration is evidence and no run record would keep it anywhere else. Nothing is loaded")
    source = Path(checked["path"])
    load_path = source
    derived = None
    if checked["startup_lines"]:
        text, removed = derive(checked["_text"], source.name, checked["sha256"])
        load_path = Path(run_folder) / f"{source.stem}.derived.cfg"
        load_path.write_bytes(text.encode("utf-8"))
        derived = {"path": str(load_path), "sha256": _sha256(load_path.read_bytes()),
                   "removed": removed}
        startup = "removed"
    else:
        startup = "the file has no System/Startup preset, so nothing derived and the original is loaded"
    result = loader(str(load_path)) or {}
    auto = result.get("autoshutter") or {}
    event = {
        "event": "mm_config_loaded",
        "original": {"path": checked["path"], "sha256": checked["sha256"]},
        "approval": checked["approval"],
        "derived": derived,
        "startup_preset": startup,
        "focus_direction": checked["focus_direction"],
        "loaded_path": str(load_path),
        "loaded_sha256": result.get("sha256"),
        "changed_during_load": result.get("changed_during_load"),
        "loaded_devices": list(result.get("loaded_devices") or []),
        "autoshutter": auto,
    }
    if auto.get("verified") is not True:
        raise AutoShutterNotVerified(
            "AutoShutter was not read back as 0 after the load, so every frame would switch the "
            "light on by itself. The run stops here, before the gate or any other call "
            f"(readback: {auto or 'none'})", event)
    return event
