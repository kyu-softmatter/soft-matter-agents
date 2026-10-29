"""Card 023, part 1: the person's light-path file is kept as a reference and nothing uses it.

The two files in docs/light-path/ are the look the person named for the drawing. They are
data: kept byte for byte, so their hashes on disk and in the commit are the ones the card
names, and nothing in the console's code or in its build refers to them.
"""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

CONSOLE = Path(__file__).resolve().parents[1]
REPO = CONSOLE.parent
FOLDER = CONSOLE / "docs" / "light-path"

SHA256 = {
    "Main.dc.html": "15995359d4c8a4d7510447d1bf5055cde899d76ee70574fe0f3c21480e7506e9",
    "canvas.json": "eab0c3c01541b47d8e30156b22e5b0ccbe7d9c6d6a7b8afa7ecc5a60bd71c138",
}
SIZE = {"Main.dc.html": 79719, "canvas.json": 334}

GIT = shutil.which("git")


def _git(*args) -> str:
    done = subprocess.run([GIT, *args], cwd=REPO, capture_output=True, text=True, check=True)
    return done.stdout.strip()


@pytest.mark.parametrize("name", sorted(SHA256))
def test_each_copied_file_is_the_one_the_card_names(name):
    data = (FOLDER / name).read_bytes()
    assert len(data) == SIZE[name]
    assert hashlib.sha256(data).hexdigest() == SHA256[name]


def test_the_folder_holds_the_two_files_and_the_two_notes_and_nothing_else():
    assert sorted(p.name for p in FOLDER.iterdir()) == [
        ".gitattributes", "Main.dc.html", "README.md", "canvas.json"]


@pytest.mark.skipif(GIT is None, reason="git is not on the path")
@pytest.mark.parametrize("name", sorted(SHA256))
def test_git_keeps_each_file_as_it_is_on_checkout(name):
    """No end-of-line conversion: the committed blob is the bytes on disk, on any computer."""
    rel = (FOLDER / name).relative_to(REPO).as_posix()
    assert _git("check-attr", "text", "--", rel).endswith(": text: unset")
    as_committed = _git("hash-object", f"--path={rel}", str(FOLDER / name))
    as_on_disk = _git("hash-object", "--no-filters", str(FOLDER / name))
    assert as_committed == as_on_disk


def test_the_gitattributes_holds_one_text_line_for_each_file_and_no_other_rule():
    lines = [ln.strip() for ln in (FOLDER / ".gitattributes").read_text(encoding="utf-8").splitlines()]
    rules = [ln for ln in lines if ln and not ln.startswith("#")]
    assert sorted(rules) == ["Main.dc.html -text", "canvas.json -text"]


def test_the_readme_names_both_hashes_the_person_s_decision_and_the_superseded_export():
    text = (FOLDER / "README.md").read_text(encoding="utf-8")
    for digest in SHA256.values():
        assert digest in text
    assert "18ca4a68" in text
    assert "5cdcbc49ba6d27f23cd3ec566fc1d40bdfd1f1525359c54092601a5a07f44254" in text
    assert "superseded" in text
    assert "reference mockup" in text


def _text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".css", ".html", ".json", ".md"}:
            yield path


@pytest.mark.parametrize("tree", [CONSOLE / "src", CONSOLE / "web" / "src"], ids=["src", "web-src"])
def test_no_source_file_names_the_folder(tree):
    assert tree.is_dir()
    named = [p.relative_to(CONSOLE).as_posix() for p in _text_files(tree)
             if "docs/light-path" in p.read_text(encoding="utf-8", errors="replace")
             or "docs\\light-path" in p.read_text(encoding="utf-8", errors="replace")]
    assert named == []


def test_the_build_output_holds_nothing_from_the_folder():
    dist = CONSOLE / "web" / "dist"
    if not dist.is_dir():
        pytest.skip("the web build has not been made here")
    held = SHA256.values()
    found = [p.relative_to(dist).as_posix() for p in dist.rglob("*")
             if p.is_file() and (p.name in SHA256 or hashlib.sha256(p.read_bytes()).hexdigest() in held)]
    assert found == []
