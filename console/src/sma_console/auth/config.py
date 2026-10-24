"""Where the auth files live, and where the first administrator's login comes from.

Account files, the audit log and the app log live in a **settings folder outside the
repository** (docs/PLAN.md §5 "Users and login"): ``%LOCALAPPDATA%\\dino-autofocus`` on Windows,
``$XDG_DATA_HOME/dino-autofocus`` (default ``~/.local/share``) elsewhere. ``DINO_AF_CONFIG_DIR``
or an explicit argument overrides it.

The first administrator's **login** is a plain id (never an email, console card 009). It is
``admin_login`` in ``settings.json`` in that folder (``{"admin_login": "..."}``) and defaults to
``softmatter`` when the key is absent. It is a name and not a credential: no password comes with
the console, and the person types the administrator's password at the first start. The old
``admin_email`` setting and its environment variable are no longer read.

``person_login`` (console card 011) names the login that is the person's own, for the screen only:
the Sign button shows to that login and to no other, and to nobody while the key is absent.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_DIR_NAME = "dino-autofocus"
CONFIG_DIR_ENV = "DINO_AF_CONFIG_DIR"
SETTINGS_FILE = "settings.json"
#: the login the person named for the administrator (I-20261022-office-04)
DEFAULT_ADMIN_LOGIN = "softmatter"

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


def admin_login(directory: str | os.PathLike[str] | None = None) -> str:
    """The first administrator's login: ``admin_login`` in settings.json, else ``softmatter``.

    The value is returned as written (trimmed). Whether it is a plain id is the account store's
    check, made where the account is created, so a bad setting is refused with its reason there.
    """
    path = config_dir(directory) / SETTINGS_FILE
    if path.is_file():
        value = json.loads(path.read_text(encoding="utf-8")).get("admin_login")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return DEFAULT_ADMIN_LOGIN


def person_login(directory: str | os.PathLike[str] | None = None) -> str | None:
    """The login the console's settings name as the person's own, or None.

    ``person_login`` in settings.json (console card 011). It decides only what the screen offers:
    who sees the Sign button. The runtime decides from the person's own file beside the safety
    policy, never from this (plan.md 6.1). Whether the value is a plain id is the account store's
    check; absent or blank is None, and then no login is the person.
    """
    path = config_dir(directory) / SETTINGS_FILE
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8")).get("person_login")
    return value.strip() if isinstance(value, str) and value.strip() else None
