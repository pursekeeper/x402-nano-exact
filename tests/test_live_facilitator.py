"""One live check against https://facilitator.pursekeeper.dev (no settle, no payment).

Runs only with ``X402_NANO_LIVE=1``: ``supported()`` must list exact/nano:mainnet and
``verify()`` with a deliberately malformed payload must answer ``invalid_block``.
"""

from __future__ import annotations

import asyncio
import os

import pytest
from x402 import x402ResourceServer, x402ResourceServerSync
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, HTTPFacilitatorClientSync
from x402.schemas import PaymentPayload, ResourceConfig

from x402_nano_exact import ExactNanoServerScheme

from .conftest import PAY_TO

FACILITATOR_URL = os.environ.get("X402_NANO_FACILITATOR", "https://facilitator.pursekeeper.dev")
pytestmark = pytest.mark.skipif(os.environ.get("X402_NANO_LIVE") != "1", reason="set X402_NANO_LIVE=1")

MALFORMED_PAYLOAD = {"block": {"type": "state", "account": PAY_TO, "signature": "not-hex"}}


def test_live_supported_and_malformed_verify_sync():
    client = HTTPFacilitatorClientSync(FacilitatorConfig(url=FACILITATOR_URL))
    supported = client.get_supported()
    kinds = [(k.x402_version, k.scheme, k.network) for k in supported.kinds]
    assert (2, "exact", "nano:mainnet") in kinds

    server = x402ResourceServerSync([client])
    server.register("nano:mainnet", ExactNanoServerScheme())
    server.initialize()
    [req] = server.build_payment_requirements(
        ResourceConfig(scheme="exact", network="nano:mainnet", pay_to=PAY_TO, price="0.01", max_timeout_seconds=60)
    )
    assert req.extra["workThreshold"] == supported.kinds[0].extra["workThreshold"]

    result = server.verify_payment(PaymentPayload(x402_version=2, accepted=req, payload=MALFORMED_PAYLOAD), req)
    assert result.verify.is_valid is False
    assert result.verify.invalid_reason == "invalid_block"


def test_live_malformed_verify_async():
    async def run():
        async with HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL)) as client:
            server = x402ResourceServer([client])
            server.register("nano:mainnet", ExactNanoServerScheme())
            server.initialize()
            [req] = server.build_payment_requirements(
                ResourceConfig(scheme="exact", network="nano:mainnet", pay_to=PAY_TO, price="0.01")
            )
            return await server.verify_payment(PaymentPayload(x402_version=2, accepted=req, payload=MALFORMED_PAYLOAD), req)

    result = asyncio.run(run())
    assert result.verify.is_valid is False
    assert result.verify.invalid_reason == "invalid_block"
