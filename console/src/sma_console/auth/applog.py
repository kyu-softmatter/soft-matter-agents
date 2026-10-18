"""The app log: server activity and errors, one file per day, old days removed (X4).

Files are ``app-YYYY-MM-DD.log`` in ``<settings folder>/logs``. That folder is kept apart from
the records folder (experiment data) on purpose: app logs are thrown away after
``retention_days``, records never are. ``DailyFileHandler`` switches file at midnight (local
time) and prunes then; ``prune`` can also be called on start-up.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

from . import config

RETENTION_DAYS = 30
LOGGER_NAME = "dino_autofocus"
_NAME = re.compile(r"^app-(\d{4}-\d{2}-\d{2})\.log$")
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def log_dir(directory: str | os.PathLike[str] | None = None) -> Path:
    return config.config_dir(directory) / config.APP_LOG_DIR


def file_for(directory: Path, day: date) -> Path:
    return directory / f"app-{day.isoformat()}.log"


def prune(directory: str | os.PathLike[str], retention_days: int, today: date) -> list[Path]:
    """Delete ``app-*.log`` files more than ``retention_days`` old. Other files are untouched."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    oldest = today - timedelta(days=retention_days)
    removed = []
    for path in directory.iterdir():
        m = _NAME.match(path.name)
        if m and path.is_file() and date.fromisoformat(m.group(1)) < oldest:
            path.unlink()
            removed.append(path)
    return sorted(removed)


class DailyFileHandler(logging.Handler):
    """Writes each record to the file of its own day; prunes when the day changes."""

    def __init__(
        self,
        directory: str | os.PathLike[str],
        *,
        retention_days: int = RETENTION_DAYS,
        today: Callable[[], date] = date.today,
    ) -> None:
        super().__init__()
        self.directory = Path(directory)
        self.retention_days = retention_days
        self._today = today
        self._day: date | None = None
        self._stream = None
        self._io_lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            with self._io_lock:
                day = self._today()
                if day != self._day:
                    self._open(day)
                self._stream.write(msg + "\n")
                self._stream.flush()
        except Exception:
            self.handleError(record)

    def _open(self, day: date) -> None:
        if self._stream is not None:
            self._stream.close()
        self.directory.mkdir(parents=True, exist_ok=True)
        # held open across records until the day changes or the handler closes
        self._stream = open(file_for(self.directory, day), "a", encoding="utf-8")  # noqa: SIM115
        self._day = day
        prune(self.directory, self.retention_days, day)

    def close(self) -> None:
        with self._io_lock:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
                self._day = None
        super().close()


def setup(
    directory: str | os.PathLike[str] | None = None,
    *,
    retention_days: int = RETENTION_DAYS,
    level: int = logging.INFO,
    today: Callable[[], date] = date.today,
) -> DailyFileHandler:
    """Attach a daily handler to the ``dino_autofocus`` logger and prune old files now."""
    path = Path(directory) if directory is not None else log_dir()
    handler = DailyFileHandler(path, retention_days=retention_days, today=today)
    handler.setFormatter(logging.Formatter(FORMAT))
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.addHandler(handler)
    prune(path, retention_days, today())
    return handler
