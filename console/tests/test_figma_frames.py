"""Card 027: a place for the frames exported from the person's Figma design, that nothing serves.

docs/figma/ holds screen images kept byte for byte as the console's look, listed in frames.json.
The folder is data: no source file names it, the web build holds nothing from it, and no link
to a Figma file is written in it. The checks below are helpers that return a list of problems,
so the real tree is asserted to have none and synthetic folders (built in a test's own temporary
directory, with a tiny PNG generated there and not a Figma export) are asserted to have the one
each check exists to find.
"""

import datetime
import hashlib
import json
import re
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

CONSOLE = Path(__file__).resolve().parents[1]
REPO = CONSOLE.parent
FOLDER = CONSOLE / "docs" / "figma"
TASKS = CONSOLE / "tasks"

DECISIONS = ("93ab0a9a", "f35e2c97")
PNG_SIGNATURE = bytes.fromhex("89504e470d0a1a0a")
KEYS = {"file", "bytes", "sha256", "card", "read"}
FIXED_FILES = {".gitattributes", "README.md", "frames.json"}
NAME_FORM = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*\.png$")
SHA_FORM = re.compile(r"^[0-9a-f]{64}$")
CARD_FORM = re.compile(r"^[0-9]{3}$")
DATE_FORM = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
# a slash, or one or more backslashes (a path written inside a string literal doubles each one)
NAMES_FOLDER = re.compile(r"docs(/|\\+)figma")
NO_FRAME_SENTENCE ="No frame is filed yet."
LINK_WORD = "figma" + ".com"

GIT = shutil.which("git")


def _git(*args) -> str:
    done = subprocess.run([GIT, *args], cwd=REPO, capture_output=True, text=True, check=True)
    return done.stdout.strip()


def _tiny_png() -> bytes:
    """A valid one-pixel PNG, made here; never a Figma export."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (PNG_SIGNATURE + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b""))


def _load(folder: Path):
    return json.loads((folder / "frames.json").read_text(encoding="utf-8"))


def _entries(data) -> list:
    if isinstance(data, dict) and isinstance(data.get("frames"), list):
        return [e for e in data["frames"] if isinstance(e, dict)]
    return []


# --- the checks: each returns the problems it finds, and an empty list when there are none ---

def list_problems(data, tasks: Path) -> list:
    if not isinstance(data, dict) or set(data) != {"frames"}:
        return ["frames.json must be an object whose only key is 'frames'"]
    if not isinstance(data["frames"], list):
        return ["'frames' must be a list"]
    found = []
    for i, entry in enumerate(data["frames"]):
        where = f"entry {i}"
        if not isinstance(entry, dict) or set(entry) != KEYS:
            found.append(f"{where}: keys must be exactly {sorted(KEYS)}")
            continue
        if not (isinstance(entry["file"], str) and NAME_FORM.match(entry["file"])):
            found.append(f"{where}: file must be lower-case ASCII words joined by hyphens, ending .png")
        if not (isinstance(entry["bytes"], int) and not isinstance(entry["bytes"], bool) and entry["bytes"] > 0):
            found.append(f"{where}: bytes must be a positive integer")
        if not (isinstance(entry["sha256"], str) and SHA_FORM.match(entry["sha256"])):
            found.append(f"{where}: sha256 must be 64 lower-case hex digits")
        card = entry["card"]
        if not (isinstance(card, str) and CARD_FORM.match(card)):
            found.append(f"{where}: card must be a three-digit string")
        elif not list(tasks.glob(f"{card}-*.md")):
            found.append(f"{where}: card {card} names no console/tasks/{card}-*.md")
        read = entry["read"]
        try:
            if not (isinstance(read, str) and DATE_FORM.match(read)):
                raise ValueError
            datetime.date.fromisoformat(read)
        except ValueError:
            found.append(f"{where}: read must be a YYYY-MM-DD date")
    for key in ("file", "sha256"):
        values = [e.get(key) for e in _entries(data)]
        repeated = sorted({v for v in values if values.count(v) > 1}, key=str)
        if repeated:
            found.append(f"{key} repeats: {repeated}")
    return found


def file_problems(data, folder: Path) -> list:
    found = []
    for entry in _entries(data):
        name = entry.get("file")
        path = folder / name if isinstance(name, str) else None
        if path is None or not path.is_file():
            found.append(f"{name}: no such file in the folder")
            continue
        blob = path.read_bytes()
        if len(blob) != entry.get("bytes"):
            found.append(f"{name}: {len(blob)} bytes on disk, {entry.get('bytes')} listed")
        if hashlib.sha256(blob).hexdigest() != entry.get("sha256"):
            found.append(f"{name}: sha256 on disk is not the one listed")
        if not blob.startswith(PNG_SIGNATURE):
            found.append(f"{name}: does not begin with the PNG signature")
    return found


def folder_problems(data, folder: Path) -> list:
    found = []
    held = {p.name for p in folder.iterdir()}
    for p in folder.iterdir():
        if p.is_dir():
            found.append(f"{p.name}: a subfolder")
    listed = {e.get("file") for e in _entries(data)}
    for name in sorted(held - FIXED_FILES - listed):
        found.append(f"{name}: in the folder and not listed")
    for name in sorted(FIXED_FILES - held):
        found.append(f"{name}: missing from the folder")
    return found


def attributes_problems(folder: Path) -> list:
    lines = [ln.strip() for ln in (folder / ".gitattributes").read_text(encoding="utf-8").splitlines()]
    rules = [ln for ln in lines if ln and not ln.startswith("#")]
    comments = [ln for ln in lines if ln.startswith("#")]
    found = []
    if rules != ["*.png binary"]:
        found.append(f"rules must be exactly ['*.png binary'], not {rules}")
    if not comments:
        found.append("the rule must carry a comment saying why")
    return found


def readme_problems(data, folder: Path) -> list:
    text = (folder / "README.md").read_text(encoding="utf-8")
    found = [f"README does not name decision {d}" for d in DECISIONS if d not in text]
    entries = _entries(data)
    for entry in entries:
        for key in ("file", "sha256"):
            if str(entry.get(key)) not in text:
                found.append(f"README does not name {key} {entry.get(key)}")
    if entries and NO_FRAME_SENTENCE in text:
        found.append("README still says no frame is filed")
    if not entries and NO_FRAME_SENTENCE not in text:
        found.append("README must say 'No frame is filed yet.' while the list is empty")
    return found


def link_problems(folder: Path) -> list:
    found = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() != ".png":
            if LINK_WORD in path.read_text(encoding="utf-8", errors="replace").lower():
                found.append(f"{path.name}: contains a link to a Figma file")
    return found


def naming_problems(tree: Path) -> list:
    found = []
    for path in sorted(tree.rglob("*")):
        if path.is_file():
            text = path.read_bytes().decode("utf-8", errors="replace")
            if NAMES_FOLDER.search(text):
                found.append(path.relative_to(tree).as_posix())
    return found


def dist_problems(dist: Path, data, folder: Path) -> list:
    digests = {e.get("sha256") for e in _entries(data)}
    names = {p.name for p in folder.iterdir()} | {p.name.lower() for p in folder.iterdir()}
    found = []
    for path in sorted(dist.rglob("*")):
        if path.is_file() and (path.name in names or path.name.lower() in names
                               or hashlib.sha256(path.read_bytes()).hexdigest() in digests):
            found.append(path.relative_to(dist).as_posix())
    return found


# --- the real tree ---

def test_frames_json_parses_and_its_list_is_well_formed():
    assert list_problems(_load(FOLDER), TASKS) == []


def test_each_listed_file_is_a_png_of_the_listed_size_and_sha256():
    assert file_problems(_load(FOLDER), FOLDER) == []


def test_the_folder_holds_the_three_fixed_files_and_the_listed_frames_and_nothing_else():
    assert folder_problems(_load(FOLDER), FOLDER) == []


def test_the_gitattributes_holds_the_one_binary_rule_and_a_comment():
    assert attributes_problems(FOLDER) == []


@pytest.mark.skipif(GIT is None, reason="git is not on the path")
def test_git_keeps_a_png_in_the_folder_as_it_is_on_checkout():
    """No end-of-line conversion: the committed blob is the bytes on disk, on any computer."""
    probe = (FOLDER / "any-frame.png").relative_to(REPO).as_posix()
    assert _git("check-attr", "text", "--", probe).endswith(": text: unset")
    for entry in _entries(_load(FOLDER)):
        path = FOLDER / entry["file"]
        rel = path.relative_to(REPO).as_posix()
        assert _git("check-attr", "text", "--", rel).endswith(": text: unset")
        assert _git("hash-object", f"--path={rel}", str(path)) == _git("hash-object", "--no-filters", str(path))


def test_the_readme_names_every_listed_sha256_and_both_decisions():
    assert readme_problems(_load(FOLDER), FOLDER) == []


def test_no_text_file_in_the_folder_links_to_a_figma_file():
    assert link_problems(FOLDER) == []


@pytest.mark.parametrize("tree", [CONSOLE / "src", CONSOLE / "web" / "src"], ids=["src", "web-src"])
def test_no_source_file_names_the_folder(tree):
    assert tree.is_dir()
    assert naming_problems(tree) == []


def test_the_build_output_holds_nothing_from_the_folder():
    dist = CONSOLE / "web" / "dist"
    if not dist.is_dir():
        pytest.skip("the web build has not been made here")
    assert dist_problems(dist, _load(FOLDER), FOLDER) == []


# --- the checks themselves, each shown to find what it exists to find ---

def _synthetic(tmp_path: Path, **change) -> tuple:
    """A folder with one tiny PNG, listed correctly, and a tasks folder holding card 027."""
    folder, tasks = tmp_path / "figma", tmp_path / "tasks"
    folder.mkdir(parents=True)
    tasks.mkdir(parents=True)
    (tasks / "027-a-place.md").write_text("card", encoding="utf-8")
    blob = _tiny_png()
    (folder / "tiny-frame.png").write_bytes(blob)
    (folder / ".gitattributes").write_text("# why\n*.png binary\n", encoding="utf-8")
    (folder / "README.md").write_text("93ab0a9a f35e2c97 tiny-frame.png " + hashlib.sha256(blob).hexdigest(),
                                      encoding="utf-8")
    entry = {"file": "tiny-frame.png", "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
             "card": "027", "read": "2026-11-04"}
    entry.update(change)
    data = {"frames": [entry]}
    (folder / "frames.json").write_text(json.dumps(data), encoding="utf-8")
    return folder, tasks, data


def test_a_correctly_listed_tiny_png_has_no_problem(tmp_path):
    folder, tasks, data = _synthetic(tmp_path)
    assert list_problems(data, tasks) == []
    assert file_problems(data, folder) == []
    assert folder_problems(data, folder) == []
    assert attributes_problems(folder) == []
    assert readme_problems(data, folder) == []
    assert link_problems(folder) == []


@pytest.mark.parametrize("change", [
    {"extra": 1},
    {"card": "999"},
    {"card": 27},
    {"file": "Tiny_Frame.png"},
    {"file": "tiny-frame.svg"},
    {"bytes": 0},
    {"bytes": True},
    {"sha256": "ABC"},
    {"read": "2026-13-45"},
    {"read": "4 November 2026"},
], ids=["sixth-key", "card-names-no-task", "card-not-a-string", "name-form", "not-png-name",
        "zero-bytes", "bool-bytes", "short-sha", "impossible-date", "date-form"])
def test_a_malformed_entry_is_found(tmp_path, change):
    folder, tasks, data = _synthetic(tmp_path)
    data["frames"][0].update(change)
    assert list_problems(data, tasks) != []


def test_a_missing_key_a_repeated_file_and_a_repeated_sha256_are_found(tmp_path):
    folder, tasks, data = _synthetic(tmp_path)
    entry = data["frames"][0]
    short = {k: v for k, v in entry.items() if k != "read"}
    assert list_problems({"frames": [short]}, tasks) != []
    assert list_problems({"frames": [entry, dict(entry)]}, tasks) != []
    assert list_problems({"frames": [entry], "other": 1}, tasks) != []
    assert list_problems({"frames": "no"}, tasks) != []


def test_a_wrong_size_or_a_wrong_sha256_is_found(tmp_path):
    folder, tasks, data = _synthetic(tmp_path)
    data["frames"][0]["bytes"] += 1
    assert file_problems(data, folder) != []
    folder, tasks, data = _synthetic(tmp_path / "again")
    data["frames"][0]["sha256"] = "0" * 64
    assert file_problems(data, folder) != []


def test_a_listed_file_that_is_not_a_png_or_is_missing_is_found(tmp_path):
    folder, tasks, data = _synthetic(tmp_path)
    (folder / "tiny-frame.png").write_bytes(b"<svg></svg>")
    assert any("PNG signature" in p for p in file_problems(data, folder))
    (folder / "tiny-frame.png").unlink()
    assert file_problems(data, folder) != []


def test_a_file_that_is_not_listed_and_a_subfolder_are_found(tmp_path):
    folder, tasks, data = _synthetic(tmp_path)
    (folder / "stray.png").write_bytes(_tiny_png())
    assert any("stray.png" in p for p in folder_problems(data, folder))
    (folder / "stray.png").unlink()
    (folder / "sub").mkdir()
    assert any("subfolder" in p for p in folder_problems(data, folder))


def test_a_changed_rule_or_a_missing_comment_in_the_gitattributes_is_found(tmp_path):
    folder, tasks, data = _synthetic(tmp_path)
    (folder / ".gitattributes").write_text("# why\n*.png binary\n*.svg binary\n", encoding="utf-8")
    assert attributes_problems(folder) != []
    (folder / ".gitattributes").write_text("*.png binary\n", encoding="utf-8")
    assert attributes_problems(folder) != []


def test_a_readme_that_misses_a_decision_or_a_digest_is_found(tmp_path):
    folder, tasks, data = _synthetic(tmp_path)
    (folder / "README.md").write_text("93ab0a9a tiny-frame.png", encoding="utf-8")
    assert readme_problems(data, folder) != []
    (folder / "README.md").write_text("93ab0a9a f35e2c97 tiny-frame.png", encoding="utf-8")
    assert readme_problems(data, folder) != []
    assert readme_problems({"frames": []}, folder) != []


def test_a_figma_link_in_the_readme_is_found(tmp_path):
    folder, tasks, data = _synthetic(tmp_path)
    (folder / "README.md").write_text("see https://www." + LINK_WORD + "/design/x", encoding="utf-8")
    assert link_problems(folder) != []


def test_a_source_file_naming_the_folder_is_found(tmp_path):
    tree = tmp_path / "src"
    tree.mkdir()
    (tree / "a.ts").write_text("import x from '../docs/figma/x'", encoding="utf-8")
    (tree / "b.ts").write_text("'..\\docs\\figma\\x'", encoding="utf-8")
    # a backslash path inside a TS or Python string literal is written with two backslashes,
    # so that is the text on disk; built with chr so no editor or shell halves it
    two = chr(92) * 2
    (tree / "d.ts").write_text(f"'..{two}docs{two}figma{two}x'", encoding="utf-8")
    (tree / "c.ts").write_text("nothing", encoding="utf-8")
    assert naming_problems(tree) == ["a.ts", "b.ts", "d.ts"]


def test_a_build_file_with_a_listed_digest_or_a_name_from_the_folder_is_found(tmp_path):
    folder, tasks, data = _synthetic(tmp_path)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "unrelated.js").write_text("x", encoding="utf-8")
    assert dist_problems(dist, data, folder) == []
    (dist / "renamed.bin").write_bytes((folder / "tiny-frame.png").read_bytes())
    assert dist_problems(dist, data, folder) == ["renamed.bin"]
    (dist / "renamed.bin").unlink()
    (dist / "tiny-frame.png").write_bytes(b"other")
    assert dist_problems(dist, data, folder) == ["tiny-frame.png"]
    (dist / "tiny-frame.png").unlink()
    (dist / "frames.json").write_text("{}", encoding="utf-8")
    assert dist_problems(dist, data, folder) == ["frames.json"]
