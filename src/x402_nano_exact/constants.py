"""Constants for the x402 ``exact`` scheme on ``nano:mainnet``.

Values mirror ``@x402nano/exact`` / ``@x402nano/typescript-common`` and what
https://facilitator.pursekeeper.dev/supported advertises.
"""

SCHEME_EXACT = "exact"
NETWORK_NANO_MAINNET = "nano:mainnet"
ASSET_XNO = "XNO"

RAW_PER_XNO = 10**30
"""1 XNO = 10^30 raw. ``amount`` on the wire is always an integer string in raw."""

SEND_BLOCK_WORK_THRESHOLD = "fffffff800000000"
"""Proof-of-work threshold for send blocks (``SEND_BLOCK_WORK_THRESHOLD`` in
``@x402nano/typescript-common``). Used only as a fallback when the facilitator's
``/supported`` entry does not carry ``extra.workThreshold``."""

MAX_SUPPLY_XNO = 133_248_298
"""Ceiling of the fixed Nano supply. A Money price above this cannot be an XNO
amount, so it is almost certainly a raw amount typed where XNO was expected."""
