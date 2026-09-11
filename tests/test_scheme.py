"""Offline tests: price parsing, requirement shape via the SDK, and the SDK verify path."""

from __future__ import annotations

import json

import pytest
from x402 import x402ResourceServerSync
from x402.schemas import AssetAmount, PaymentPayload, ResourceConfig, ResourceInfo, VerifyResponse

from x402_nano_exact import ExactNanoScheme, ExactNanoServerScheme, xno_to_raw

from .conftest import NANO_KIND_EXTRA, FakeNanoFacilitator

NETWORK = "nano:mainnet"


def make_server(facilitator: FakeNanoFacilitator | None = None) -> x402ResourceServerSync:
    facilitator = facilitator or FakeNanoFacilitator()
    server = x402ResourceServerSync([facilitator])
    server.register(NETWORK, ExactNanoServerScheme())
    server.initialize()
    return server


# ---------------------------------------------------------------- parse_price


@pytest.mark.parametrize(
    ("price", "raw"),
    [
        ("0.01", "10000000000000000000000000000"),
        ("0.01 XNO", "10000000000000000000000000000"),
        (" 0.01 xno ", "10000000000000000000000000000"),
        ("1", "1000000000000000000000000000000"),
        (1, "1000000000000000000000000000000"),
        (1.5, "1500000000000000000000000000000"),
        ("999999.999999", "999999999999000000000000000000000000"),
        ("0." + "0" * 29 + "1", "1"),
        ({"amount": "123", "asset": "XNO"}, "123"),
        ({"amount": 123, "asset": "xno"}, "123"),
        (AssetAmount(amount="10000000000000000000000000000", asset="XNO"), "10000000000000000000000000000"),
    ],
)
def test_parse_price_to_raw(price, raw):
    result = ExactNanoScheme().parse_price(price, NETWORK)
    assert result == AssetAmount(amount=raw, asset="XNO", extra={})


@pytest.mark.parametrize(
    "price",
    [
        "$0.01",  # fiat: no rate available
        "0.01 USDC",  # other asset
        "0",
        "-1",
        "0." + "0" * 30 + "1",  # finer than one raw
        "100000000000000000000000000",  # raw typed as XNO (JS reference would accept this)
        {"amount": "0.01", "asset": "XNO"},  # AssetAmount must be raw
        {"amount": "1", "asset": "USDC"},
        {"amount": "1"},
        "abc",
    ],
)
def test_parse_price_rejects(price):
    with pytest.raises(ValueError):
        ExactNanoScheme().parse_price(price, NETWORK)


def test_money_parser_chain_can_price_in_fiat():
    scheme = ExactNanoScheme().register_money_parser(
        lambda amount, network: AssetAmount(amount=xno_to_raw(amount) if amount == "2" else "0", asset="XNO")
        if amount == "2"
        else None
    )
    assert scheme.parse_price("$2", NETWORK).amount == xno_to_raw("2")
    assert scheme.parse_price("0.5", NETWORK).amount == xno_to_raw("0.5")  # parser passed, default applied


# ------------------------------------------------- requirements via the SDK


def test_build_payment_requirements_shape(pay_to):
    server = make_server()
    config = ResourceConfig(scheme="exact", network=NETWORK, pay_to=pay_to, price="0.01", max_timeout_seconds=60)
    [req] = server.build_payment_requirements(config)

    assert json.loads(req.model_dump_json(by_alias=True)) == {
        "scheme": "exact",
        "network": "nano:mainnet",
        "asset": "XNO",
        "amount": "10000000000000000000000000000",
        "payTo": pay_to,
        "maxTimeoutSeconds": 60,
        "extra": {"work": "required", "workThreshold": "fffffff800000000"},
    }


def test_requirements_copy_work_fields_from_supported_kind_and_keep_overrides(pay_to):
    server = make_server()
    config = ResourceConfig(
        scheme="exact", network=NETWORK, pay_to=pay_to, price="0.01", extra={"work": "optional", "memo": "x"}
    )
    [req] = server.build_payment_requirements(config)
    assert req.extra == {"work": "optional", "workThreshold": NANO_KIND_EXTRA["workThreshold"], "memo": "x"}
    assert req.max_timeout_seconds == 300  # SDK default when unset


def test_requirements_normalize_xrb_prefix_and_reject_bad_checksum(pay_to):
    server = make_server()
    xrb = "xrb_" + pay_to.removeprefix("nano_")
    [req] = server.build_payment_requirements(ResourceConfig(scheme="exact", network=NETWORK, pay_to=xrb, price="1"))
    assert req.pay_to == pay_to

    bad = pay_to[:-1] + ("1" if pay_to[-1] != "1" else "3")
    with pytest.raises(ValueError, match="Nano address"):
        server.build_payment_requirements(ResourceConfig(scheme="exact", network=NETWORK, pay_to=bad, price="1"))


def test_payment_required_response_json(pay_to):
    server = make_server()
    reqs = server.build_payment_requirements(ResourceConfig(scheme="exact", network=NETWORK, pay_to=pay_to, price="0.01"))
    response = server.create_payment_required_response(
        reqs, ResourceInfo(url="https://example.test/paid", description="Paid", mime_type="application/json")
    )
    body = json.loads(response.model_dump_json(by_alias=True, exclude_none=True))

    assert body["x402Version"] == 2
    assert body["resource"] == {"url": "https://example.test/paid", "description": "Paid", "mimeType": "application/json"}
    assert len(body["accepts"]) == 1
    accept = body["accepts"][0]
    assert accept["network"] == "nano:mainnet" and accept["asset"] == "XNO"
    assert "assetTransferMethod" not in accept["extra"] and "paymentFlow" not in accept["extra"]


def test_facilitator_is_routed_by_network_from_supported():
    fake = FakeNanoFacilitator()
    server = make_server(fake)
    assert server._facilitator_clients_map == {NETWORK: {"exact": fake}}
    assert server.get_supported_kind(2, NETWORK, "exact").extra == NANO_KIND_EXTRA


# ------------------------------------------------------- SDK verify path


def test_verify_payment_delegates_to_facilitator_client(pay_to):
    fake = FakeNanoFacilitator(VerifyResponse(is_valid=False, invalid_reason="invalid_block", payer=""))
    server = make_server(fake)
    [req] = server.build_payment_requirements(ResourceConfig(scheme="exact", network=NETWORK, pay_to=pay_to, price="0.01"))

    payload = PaymentPayload(x402_version=2, accepted=req, payload={"block": {"garbage": True}})
    result = server.verify_payment(payload, req)

    assert result.verify.is_valid is False
    assert result.verify.invalid_reason == "invalid_block"
    assert fake.verify_calls == [(payload, req)]
