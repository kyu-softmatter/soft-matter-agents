"""scrypt round trip, wrong passwords, policy, and a stored form that never holds the password."""

import pytest

from dino_autofocus.auth import PasswordPolicyError, hash_password, passwords, verify_password


def test_round_trip_and_wrong_password():
    stored = hash_password("correct horse")
    assert verify_password("correct horse", stored)
    assert not verify_password("correct hors", stored)
    assert not verify_password("Correct horse", stored)


def test_stored_form_carries_salt_and_parameters_not_the_password():
    a, b = hash_password("correct horse"), hash_password("correct horse")
    assert a != b  # fresh salt each time
    scheme, n, r, p, salt, digest = a.split("$")
    assert (scheme, int(n)) == ("scrypt", passwords.SCRYPT_N) and salt and digest
    assert "correct horse" not in a


def test_old_parameters_still_verify():
    import base64
    import hashlib

    salt = b"0123456789abcdef"
    digest = hashlib.scrypt(b"older pass", salt=salt, n=2**10, r=8, p=1, dklen=32)
    b64 = base64.b64encode
    stored = f"scrypt$1024$8$1${b64(salt).decode()}${b64(digest).decode()}"
    assert verify_password("older pass", stored)


@pytest.mark.parametrize("stored", ["", "plain", "md5$1$2$3$4$5", "scrypt$x$8$1$AA==$AA==",
                                    "scrypt$1024$8$1$!!$AA=="])
def test_malformed_stored_value_never_matches(stored):
    assert not verify_password("anything", stored)


def test_short_password_is_refused():
    with pytest.raises(PasswordPolicyError):
        hash_password("short")



@pytest.mark.real_scrypt
def test_production_cost():
    assert (passwords.SCRYPT_N, passwords.SCRYPT_R, passwords.SCRYPT_P) == (2**14, 8, 5)
    assert hash_password("correct horse").split("$")[1] == str(2**14)


def test_needs_rehash_only_for_other_parameters():
    assert not passwords.needs_rehash(hash_password("correct horse"))
    n, r = passwords.SCRYPT_N, passwords.SCRYPT_R
    assert passwords.needs_rehash(f"scrypt${n}${r}$1$AA==$AA==")
    assert passwords.needs_rehash("not a hash")
