"""Where the auth files live, and where the first admin's email comes from.

Account files, the audit log and the app log live in a **settings folder outside the
repository** (docs/PLAN.md 5절 "사용자와 로그인"): ``%LOCALAPPDATA%\\dino-autofocus`` on Windows,
``$XDG_DATA_HOME/dino-autofocus`` (default ``~/.local/share``) elsewhere. ``DINO_AF_CONFIG_DIR``
or an explicit argument overrides it.

The admin email is **never written in code, tests, docs or git** (the repository goes public at
integration). It is read from the ``DINO_AF_ADMIN_EMAIL`` environment variable or from
``settings.json`` in the settings folder (``{"admin_email": "..."}``). When neither is set the
app needs its first-run setup step; ``admin_email`` returns None and callers say so.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_DIR_NAME = "dino-autofocus"
CONFIG_DIR_ENV = "DINO_AF_CONFIG_DIR"
ADMIN_EMAIL_ENV = "DINO_AF_ADMIN_EMAIL"
SETTINGS_FILE = "settings.json"

ACCOUNTS_FILE = "accounts.json"
AUDIT_FILE = "audit.jsonl"
APP_LOG_DIR = "logs"


def config_dir(override: str | os.PathLike[str] | None = None) -> Path:
    """The settings folder. Not created here; the stores create it when they first write."""
    if override is not None:
        return Path(override)
    env = os.environ.get(CONFIG_DIR_ENV)
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME


def admin_email(directory: str | os.PathLike[str] | None = None) -> str | None:
    """The configured first-admin email (environment first, then settings.json), or None."""
    env = os.environ.get(ADMIN_EMAIL_ENV, "").strip()
    if env:
        return env
    path = config_dir(directory) / SETTINGS_FILE
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8")).get("admin_email")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
