"""``manifest.json``: every file attached to a session, with size and sha256.

Small files are copied into the session folder (``files/``) and end up in git. Files above
``RecordsConfig.max_tracked_bytes`` go to the session's data folder outside git; the manifest
is then the only thing in git that says they exist and what their content was.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .layout import now_iso, read_json, write_json_atomic

Where = Literal["session", "data"]
_CHUNK = 1 << 20


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ManifestEntry:
    name: str
    where: Where       # "session": inside the session folder (git); "data": data folder
    path: str          # relative, forward slashes: to the session folder or the data root
    size: int
    sha256: str
    added_at: str
    kind: str = ""     # e.g. "frame", "stack", "mosaic"; free text for now


class Manifest:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: list[ManifestEntry] = []
        if self.path.exists():
            self.entries = [ManifestEntry(**e) for e in read_json(self.path)["files"]]

    def save(self) -> None:
        write_json_atomic(self.path, {"files": [asdict(e) for e in self.entries]})

    def names(self) -> set[str]:
        return {e.name for e in self.entries}

    def get(self, name: str) -> ManifestEntry:
        for e in self.entries:
            if e.name == name:
                return e
        raise KeyError(name)


def place_file(src: Path, name: str, session_dir: Path, data_root: Path, session_id: str,
               max_tracked_bytes: int, move: bool = False, kind: str = "") -> ManifestEntry:
    """Copy (or move) `src` to its place and return the manifest entry; hashes the copy."""
    src = Path(src)
    size = src.stat().st_size
    if size > max_tracked_bytes:
        where: Where = "data"
        dest = Path(data_root) / session_id / name
        rel = f"{session_id}/{name}"
    else:
        where = "session"
        dest = Path(session_dir) / "files" / name
        rel = f"files/{name}"
    if dest.exists():
        raise FileExistsError(f"{dest} already exists")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if move:
        shutil.move(str(src), dest)
    else:
        shutil.copy2(src, dest)
    return ManifestEntry(name=name, where=where, path=rel, size=size, sha256=sha256_file(dest),
                         added_at=now_iso(), kind=kind)


def verify(entry: ManifestEntry, session_dir: Path, data_root: Path) -> bool:
    """True when the file is where the entry says and still has the recorded content."""
    base = Path(session_dir) if entry.where == "session" else Path(data_root)
    p = base / entry.path
    return p.is_file() and p.stat().st_size == entry.size and sha256_file(p) == entry.sha256
