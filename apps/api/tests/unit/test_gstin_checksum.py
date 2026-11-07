import pytest

from app.services.kyc.gstin_checksum import CHARS, check_digit, validate_gstin
from app.services.registry import gstin_registry


def test_every_registry_gstin_passes():
    gstins = list(gstin_registry())
    assert len(gstins) == 3534
    failures = [g for g in gstins if not validate_gstin(g).ok]
    assert failures == []


def test_tampered_check_digit_fails():
    g = next(iter(gstin_registry()))
    wrong = CHARS[(CHARS.index(g[14]) + 1) % 36]
    result = validate_gstin(g[:14] + wrong)
    assert not result.ok
    assert "check digit" in result.reason


def test_single_char_typo_is_caught():
    g = next(iter(gstin_registry()))  # e.g. 32TTNXB7384T1ZW
    typo = g[:7] + ("1" if g[7] != "1" else "2") + g[8:]
    assert not validate_gstin(typo).ok


@pytest.mark.parametrize(
    "gstin, fragment",
    [
        ("", "15 characters"),
        ("32TTNXB7384T1Z", "15 characters"),
        ("3ZTTNXB7384T1ZW", "pattern"),
        ("32TTNXB7384T1YW", "pattern"),  # 14th char must be Z
        ("00TTNXB7384T1ZW", "State code"),
    ],
)
def test_format_errors(gstin, fragment):
    result = validate_gstin(gstin)
    assert not result.ok
    assert fragment in result.reason


def test_known_real_world_style_example():
    # Structure check of the algorithm on a hand-built value.
    body = "27AAPFU0939F1Z"
    assert validate_gstin(body + check_digit(body)).ok
