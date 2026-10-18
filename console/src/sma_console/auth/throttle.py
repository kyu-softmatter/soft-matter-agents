"""Attempt limits for login and unlock (public-release audit S2).

Wrong passwords are counted per **account** (the email as typed, normalized, whether or not it
exists, so a lockout says nothing about which emails have accounts) and per **client** (the
socket address). Too many inside the window locks that key for `lockout_s`; while any key of a
request is locked the request is refused before the password is checked, so a locked guesser
costs no scrypt either. A right password clears the account's count (not the client's: one
client trying many accounts stays counted).

PROVISIONAL numbers (not tuned): 5 wrong per account, 20 per client, in 15 min; 15 min lockout.
State is in memory: a server restart clears it. Keys are capped in length and stale ones are
dropped, so guesses with made-up emails cannot grow it without bound. The check and the count
are two steps: a burst of parallel requests can pass a few more than the limit (bounded by the
server's worker threads).
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

ACCOUNT_LIMIT = 5
CLIENT_LIMIT = 20
WINDOW_S = 15 * 60
LOCKOUT_S = 15 * 60
MAX_KEY = 320  # characters of an account key (the longest valid email)
PRUNE_AT = 5000  # keys kept before stale ones are dropped


@dataclass
class _Count:
    failures: list[float] = field(default_factory=list)
    locked_until: float = 0.0


class AttemptLimiter:
    def __init__(self, *, account_limit: int = ACCOUNT_LIMIT, client_limit: int = CLIENT_LIMIT,
                 window_s: float = WINDOW_S, lockout_s: float = LOCKOUT_S,
                 clock: Callable[[], float] = time.time) -> None:
        self.limits = {"account": account_limit, "client": client_limit}
        self.window_s, self.lockout_s, self._clock = window_s, lockout_s, clock
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, str], _Count] = {}

    @staticmethod
    def keys(account: str | None, client: str | None) -> list[tuple[str, str]]:
        out = []
        if account:
            out.append(("account", account.strip().lower()[:MAX_KEY]))
        if client:
            out.append(("client", client))
        return out

    def retry_after(self, keys: Iterable[tuple[str, str]]) -> int | None:
        """Seconds until every key is free again, or None if none is locked now."""
        now = self._clock()
        with self._lock:
            waits = [c.locked_until - now for k in keys
                     if (c := self._counts.get(k)) is not None and c.locked_until > now]
        return math.ceil(max(waits)) if waits else None

    def failed(self, keys: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
        """Count a wrong password; returns the keys that this failure locked."""
        now = self._clock()
        locked = []
        with self._lock:
            if len(self._counts) > PRUNE_AT:
                self._prune(now)
            for k in keys:
                c = self._counts.setdefault(k, _Count())
                c.failures = [t for t in c.failures if now - t < self.window_s]
                c.failures.append(now)
                if len(c.failures) >= self.limits[k[0]] and c.locked_until <= now:
                    c.locked_until = now + self.lockout_s
                    c.failures = []
                    locked.append(k)
        return locked

    def _prune(self, now: float) -> None:
        """Drop keys that are neither locked nor holding a failure inside the window."""
        for k in [k for k, c in self._counts.items() if c.locked_until <= now
                  and not any(now - t < self.window_s for t in c.failures)]:
            del self._counts[k]

    def succeeded(self, account: str | None) -> None:
        if account:
            with self._lock:
                self._counts.pop(("account", account.strip().lower()[:MAX_KEY]), None)
