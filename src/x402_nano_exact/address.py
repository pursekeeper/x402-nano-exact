"""Nano address validation (``nano_``/``xrb_`` prefix, base32 body, blake2b checksum).

Pure Python; ``hashlib.blake2b`` is in the standard library.
"""

from __future__ import annotations

import hashlib
import re

_ALPHABET = "13456789abcdefghijkmnopqrstuwxyz"
_ADDRESS_RE = re.compile(r"(?:nano|xrb)_([13][13456789abcdefghijkmnopqrstuwxyz]{59})")


def normalize_nano_address(address: str) -> str:
    """Validate ``address`` (including its checksum) and return it with the ``nano_`` prefix.

    Raises:
        ValueError: If the address is malformed or its checksum does not match.
    """
    match = _ADDRESS_RE.fullmatch(str(address).strip())
    if match is None or not _checksum_ok(match.group(1)):
        raise ValueError(f"not a valid Nano address: {address!r}")
    return "nano_" + match.group(1)


def is_nano_address(address: str) -> bool:
    """Return True if ``address`` is a well-formed Nano address with a valid checksum."""
    try:
        normalize_nano_address(address)
    except ValueError:
        return False
    return True


def _checksum_ok(body: str) -> bool:
    """Check the 8-char checksum of a 60-char address body against its 32-byte public key."""
    bits = 0
    for char in body[:52]:
        bits = (bits << 5) | _ALPHABET.index(char)
    if bits >> 256:  # the first char encodes 4 padding bits that must be zero
        return False
    public_key = bits.to_bytes(32, "big")
    digest = hashlib.blake2b(public_key, digest_size=5).digest()[::-1]
    check = int.from_bytes(digest, "big")
    encoded = "".join(_ALPHABET[(check >> (5 * i)) & 31] for i in range(7, -1, -1))
    return encoded == body[52:]
