"""x402 ``exact`` scheme on ``nano:mainnet`` for the x402 Python SDK (resource-server side).

Usage::

    from x402 import x402ResourceServer
    from x402.http import FacilitatorConfig, HTTPFacilitatorClient
    from x402_nano_exact import ExactNanoServerScheme

    nano_facilitator = HTTPFacilitatorClient(FacilitatorConfig(url="https://facilitator.pursekeeper.dev"))
    server = x402ResourceServer([nano_facilitator])
    server.register("nano:mainnet", ExactNanoServerScheme())
"""

from .address import is_nano_address, normalize_nano_address
from .constants import (
    ASSET_XNO,
    NETWORK_NANO_MAINNET,
    RAW_PER_XNO,
    SCHEME_EXACT,
    SEND_BLOCK_WORK_THRESHOLD,
)
from .server import ExactNanoScheme, xno_to_raw

ExactNanoServerScheme = ExactNanoScheme
"""SDK-style alias (cf. ``x402.mechanisms.tvm.exact.ExactTvmServerScheme``)."""

__all__ = [
    "ASSET_XNO",
    "NETWORK_NANO_MAINNET",
    "RAW_PER_XNO",
    "SCHEME_EXACT",
    "SEND_BLOCK_WORK_THRESHOLD",
    "ExactNanoScheme",
    "ExactNanoServerScheme",
    "is_nano_address",
    "normalize_nano_address",
    "xno_to_raw",
]
