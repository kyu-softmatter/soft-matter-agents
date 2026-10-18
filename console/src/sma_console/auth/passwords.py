"""Password hashing with the standard library's ``hashlib.scrypt``.

The stored form is one string, ``scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>``, so the salt and
the cost parameters travel with the hash and can be raised later without breaking old
accounts. The plain password is never stored, logged or returned. Comparison uses
``hmac.compare_digest``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

SCHEME = "scrypt"

#: Cost parameters for new hashes (audit S11): OWASP's n=2**14, r=8, p=5, which matches its
#: n=2**17, p=1 in work but keeps memory at 16 MiB per check (the login limiter bounds how many
#: run at once, but a burst still runs one per worker thread). About 1 s per check on the desktop
#: (2026-10-02). Was p=1 until then; such hashes still verify and are upgraded at the next login.
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 5
SALT_BYTES = 16
HASH_BYTES = 32

MIN_PASSWORD_LENGTH = 8


class PasswordPolicyError(ValueError):
    """The password does not meet the minimum rules."""


def check_policy(password: str) -> None:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters"
        )


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    # maxmem must cover 128 * n * r bytes; OpenSSL's default (32 MiB) is too tight at n=2**15
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen,
        maxmem=256 * n * r + 1024 * 1024,
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    """Hash a new password (after the policy check) with a fresh random salt."""
    check_policy(password)
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P, HASH_BYTES)
    return f"{SCHEME}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def dummy_verify(password: str) -> bool:
    """Spend what a real check costs and return False (for an unknown login email)."""
    _scrypt(password, bytes(SALT_BYTES), SCRYPT_N, SCRYPT_R, SCRYPT_P, HASH_BYTES)
    return False


def needs_rehash(stored: str) -> bool:
    """True when ``stored`` was made with other cost parameters than new hashes get."""
    try:
        scheme, n, r, p, _, _ = stored.split("$")
        return (scheme, int(n), int(r), int(p)) != (SCHEME, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    except (ValueError, AttributeError):
        return True


def verify_password(password: str, stored: str) -> bool:
    """True when ``password`` matches ``stored``. A malformed ``stored`` never matches."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != SCHEME:
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
        digest = _scrypt(password, salt, int(n), int(r), int(p), len(expected))
    except (ValueError, TypeError, AttributeError):
        return False
    return hmac.compare_digest(digest, expected)
