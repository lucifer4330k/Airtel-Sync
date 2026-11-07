"""GSTIN structure and checksum validation.

Layout: SS PPPPPPPPPP E Z C
  SS  state code (01-38, plus 97 other territory, 99 centre jurisdiction)
  P   embedded PAN (5 letters, 4 digits, 1 letter); its 4th char is the entity
      type. The case data always uses X (not a real type) -- we accept it.
  E   entity number for the PAN in that state (1-9, A-Z)
  Z   literal 'Z'
  C   check character (mod-36 Luhn-style)
"""

import re
from dataclasses import dataclass

CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_FORMAT = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_VALID_STATE_CODES = {f"{i:02d}" for i in range(1, 39)} | {"97", "99"}
# Real PAN entity types + X used throughout the synthetic dataset.
_PAN_ENTITY_TYPES = set("PCHFATBLJGX")


def check_digit(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        product = CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return CHARS[(36 - total % 36) % 36]


@dataclass(frozen=True)
class GstinResult:
    ok: bool
    reason: str


def validate_gstin(gstin: str) -> GstinResult:
    g = (gstin or "").strip().upper()
    if len(g) != 15:
        return GstinResult(False, f"GSTIN must be 15 characters, got {len(g)}")
    if not _FORMAT.match(g):
        return GstinResult(False, "GSTIN does not follow the 15-character GST pattern")
    if g[:2] not in _VALID_STATE_CODES:
        return GstinResult(False, f"State code {g[:2]} is not a valid GST state code")
    if g[5] not in _PAN_ENTITY_TYPES:
        return GstinResult(False, f"PAN entity type '{g[5]}' is not recognised")
    expected = check_digit(g[:14])
    if g[14] != expected:
        return GstinResult(False, "GSTIN check digit is wrong (possible typo or tampering)")
    return GstinResult(True, "GSTIN format and checksum are valid")
