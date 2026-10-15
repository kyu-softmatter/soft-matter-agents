"""Origin headers of the flat files under microscope_agent/ (integration workplan D-03).

Every flat src and test file there starts with three comment lines that say where its body
comes from and what the body is:

    # origin: dino-autofocus, public since 2026-10-03:
    #   https://github.com/kyu-softmatter/dino-autofocus/blob/<commit>/<path>
    # body-sha256: <hex>

``<commit>`` is the commit in which this body first appeared, so the URL resolves to a file
whose body is byte-for-byte this one; ``<path>`` is the file's path in that commit; and
``body-sha256`` is the SHA-256 of everything after the header with line endings normalised to
LF (the two repositories' checkouts differ in nothing else). A body edit therefore takes two
commits -- the body, then the header that names it -- and ``tests/test_sma_shape.py`` fails
in between. Whoever holds a copy (soft-matter-agents after the copy card, or anyone) can check
the commit and the hash without trusting either repository's history.

Mirrors (workplan D-06, decision OD-3): a file soft-matter-agents has copied is the original
there, and dino keeps it as a pinned read-only mirror. Its header names soft-matter-agents
and the commit there that holds the body:

    # origin: soft-matter-agents, the original since 2026-10-05; dino-autofocus mirrors it:
    #   https://github.com/kyu-softmatter/soft-matter-agents/blob/<commit>/<path>
    # body-sha256: <hex>

``MIRRORED`` lists those files and ``SMA_MIRROR_COMMIT`` the commit they follow. A change to
a mirrored file is made in soft-matter-agents first, by card; dino then takes the new body
and re-points the header with ``--mirror <sha>``.

Command line: ``python -m dino_autofocus.flat_origin --check`` lists what is wrong;
``--commit <sha>`` (re)writes the headers of dino's own files naming that dino commit;
``--mirror <sha>`` (re)writes the mirrored files' headers naming that soft-matter-agents
commit. Both keep each file's line-ending style.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ORIGIN = "dino-autofocus"
PUBLIC_SINCE = "2026-10-03"
BLOB_URL = "https://github.com/kyu-softmatter/dino-autofocus/blob/{commit}/{path}"
SMA = "soft-matter-agents"
SMA_NOTE = "the original since 2026-10-05; dino-autofocus mirrors it"
SMA_BLOB_URL = "https://github.com/kyu-softmatter/soft-matter-agents/blob/{commit}/{path}"
#: The soft-matter-agents commit the mirrored files follow (card 059's copy, G-06).
SMA_MIRROR_COMMIT = "f2c56dcfc018b23ff784dc2ac06e150db499f556"
#: Files soft-matter-agents holds the original of; dino's copies are a read-only mirror.
MIRRORED = frozenset({
    "microscope_agent/src/focus_classical.py",
    "microscope_agent/src/focus_verdict.py",
    "microscope_agent/src/focus_search.py",
    "microscope_agent/tests/test_focus_core.py",
    "microscope_agent/tests/test_focus_contract.py",
    "microscope_agent/tests/test_focus_search.py",
})
FLAT_DIRS = ("microscope_agent/src", "microscope_agent/tests")

HEADER_RE = re.compile(
    r"\A# origin: (?:dino-autofocus, public since (?P<since>\d{4}-\d{2}-\d{2})"
    r"|soft-matter-agents, (?P<note>[^\n]+)):\n"
    r"#   https://github\.com/kyu-softmatter/(?P<repo>dino-autofocus|soft-matter-agents)"
    r"/blob/(?P<commit>[0-9a-f]{40})/"
    r"(?P<path>microscope_agent/(?:src|tests)/[A-Za-z0-9_./-]+\.py)\n"
    r"# body-sha256: (?P<sha>[0-9a-f]{64})\n"
)


@dataclass(frozen=True)
class Header:
    commit: str
    path: str  # repository-relative, posix
    body_sha256: str
    public_since: str = PUBLIC_SINCE
    origin: str = ORIGIN  # "dino-autofocus" or "soft-matter-agents"

    def render(self) -> str:
        if self.origin == SMA:
            url = SMA_BLOB_URL.format(commit=self.commit, path=self.path)
            return (f"# origin: {SMA}, {SMA_NOTE}:\n#   {url}\n"
                    f"# body-sha256: {self.body_sha256}\n")
        url = BLOB_URL.format(commit=self.commit, path=self.path)
        return (f"# origin: {ORIGIN}, public since {self.public_since}:\n#   {url}\n"
                f"# body-sha256: {self.body_sha256}\n")


def normalise(text: str) -> str:
    return text.replace("\r\n", "\n")


def body_sha256(body: str) -> str:
    return hashlib.sha256(normalise(body).encode("utf-8")).hexdigest()


def split(text: str) -> tuple[Header | None, str]:
    """(header, body) of a file's text; header is None when the file has none."""
    text = normalise(text)
    m = HEADER_RE.match(text)
    if m is None:
        return None, text
    if m["repo"] == SMA:
        return Header(m["commit"], m["path"], m["sha"], origin=SMA), text[m.end():]
    return Header(m["commit"], m["path"], m["sha"], m["since"]), text[m.end():]


def flat_files(repo: Path) -> list[Path]:
    out = []
    for folder in FLAT_DIRS:
        out += [p for p in (repo / folder).rglob("*.py") if "__pycache__" not in p.parts]
    return sorted(out)


def check(repo: Path) -> list[str]:
    """Every flat file has a header naming its own path and the hash of its body."""
    problems = []
    for p in flat_files(repo):
        rel = p.relative_to(repo).as_posix()
        header, body = split(p.read_text(encoding="utf-8"))
        if header is None:
            problems.append(f"{rel}: no origin header")
            continue
        if header.path != rel:
            problems.append(f"{rel}: header names {header.path}")
        want = SMA if rel in MIRRORED else ORIGIN
        if header.origin != want:
            problems.append(f"{rel}: header names {header.origin} as origin; it should name "
                            f"{want}" + (" (a mirrored file)" if rel in MIRRORED else ""))
        elif rel in MIRRORED and header.commit != SMA_MIRROR_COMMIT:
            problems.append(f"{rel}: mirror header names {header.commit[:12]}, not "
                            f"SMA_MIRROR_COMMIT {SMA_MIRROR_COMMIT[:12]}")
        if header.body_sha256 != body_sha256(body):
            problems.append(f"{rel}: body changed since the header was written "
                            f"(run `python -m dino_autofocus.flat_origin --commit <sha>` "
                            f"with the commit that holds this body)")
    return problems


def rewrite(repo: Path, commit: str, *, mirror: bool = False) -> list[Path]:
    """Write (or replace) headers so they name `commit` and the current body: dino's own
    files with a dino commit, or (``mirror=True``) the mirrored files with the
    soft-matter-agents commit that holds their bodies."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError(f"need the full 40-hex commit, got {commit!r}")
    written = []
    for p in flat_files(repo):
        rel = p.relative_to(repo).as_posix()
        if (rel in MIRRORED) != mirror:
            continue
        raw = p.read_bytes()
        crlf = b"\r\n" in raw
        _, body = split(raw.decode("utf-8"))
        header = Header(commit, rel, body_sha256(body), origin=SMA if mirror else ORIGIN)
        text = header.render() + body
        p.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
        written.append(p)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="list header problems, exit 1 if any")
    g.add_argument("--commit", help="rewrite dino's own headers naming this 40-hex dino commit")
    g.add_argument("--mirror", help="rewrite the mirrored files' headers naming this 40-hex "
                   "soft-matter-agents commit")
    a = ap.parse_args(argv)
    if a.check:
        problems = check(a.repo)
        print("\n".join(problems) if problems else "origin headers: ok")
        return 1 if problems else 0
    written = rewrite(a.repo, a.mirror, mirror=True) if a.mirror else rewrite(a.repo, a.commit)
    for p in written:
        print("header:", p.relative_to(a.repo).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
