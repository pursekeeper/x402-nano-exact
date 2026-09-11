"""Shared fixtures: a fake facilitator client shaped like facilitator.pursekeeper.dev."""

from __future__ import annotations

import pytest
from x402.schemas import (
    PaymentPayload,
    PaymentRequirements,
    SettleResponse,
    SupportedKind,
    SupportedResponse,
    VerifyResponse,
)

PAY_TO = "nano_3mzq6kpu4b56w1afgouwumfc8juriqe3w1t14xf1f3tgc8fn4puepfrjhcfk"
NANO_KIND_EXTRA = {"asset": "XNO", "work": "required", "workThreshold": "fffffff800000000"}


class FakeNanoFacilitator:
    """Sync facilitator client (``FacilitatorClientSync``) that never touches the network.

    ``get_supported`` returns exactly what GET https://facilitator.pursekeeper.dev/supported
    returned on 2026-09-10; ``verify`` records the call and answers a canned response.
    """

    def __init__(self, verify_response: VerifyResponse | None = None) -> None:
        self.verify_calls: list[tuple[PaymentPayload, PaymentRequirements]] = []
        self._verify_response = verify_response or VerifyResponse(is_valid=True, payer=PAY_TO)

    def get_supported(self) -> SupportedResponse:
        return SupportedResponse(
            kinds=[
                SupportedKind(
                    x402_version=2, scheme="exact", network="nano:mainnet", extra=dict(NANO_KIND_EXTRA)
                )
            ],
            extensions=[],
            signers={},
        )

    def verify(self, payload: PaymentPayload, requirements: PaymentRequirements) -> VerifyResponse:
        self.verify_calls.append((payload, requirements))
        return self._verify_response

    def settle(self, payload: PaymentPayload, requirements: PaymentRequirements) -> SettleResponse:
        raise AssertionError("settle must not be called in tests")


@pytest.fixture
def pay_to() -> str:
    return PAY_TO
