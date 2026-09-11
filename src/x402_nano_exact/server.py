"""Resource-server side of the x402 ``exact`` scheme on ``nano:mainnet`` (V2).

Implements :class:`x402.interfaces.SchemeNetworkServer` so that an
``x402ResourceServer`` can ``register("nano:mainnet", ExactNanoScheme())`` and
delegate verify/settle to a Nano facilitator such as
https://facilitator.pursekeeper.dev. Mirrors ``@x402nano/exact`` (``./server``
export) and follows the structure of ``x402.mechanisms.tvm.exact.server``.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

from x402.schemas import AssetAmount, Network, PaymentRequirements, Price, SupportedKind
from x402.schemas.helpers import parse_money

from .address import normalize_nano_address
from .constants import (
    ASSET_XNO,
    MAX_SUPPLY_XNO,
    RAW_PER_XNO,
    SCHEME_EXACT,
    SEND_BLOCK_WORK_THRESHOLD,
)

MoneyParser = Callable[[str | int | float, str], AssetAmount | None]
"""Same shape as the SDK's own money parsers: ``(decimal_amount, network) -> AssetAmount | None``."""

_RAW_RE = re.compile(r"[1-9]\d*")


def xno_to_raw(amount: str | int | float | Decimal) -> str:
    """Convert an XNO amount to an integer raw string, exactly (1 XNO = 10^30 raw).

    Raises:
        ValueError: If the amount is not a positive finite number, has more than
            30 decimal places (finer than one raw), or is an integer above the
            Nano supply (which means it was a raw amount typed as XNO).
    """
    try:
        value = Decimal(str(amount))
    except InvalidOperation as e:
        raise ValueError(f"invalid XNO amount: {amount!r}") from e
    if not value.is_finite() or value <= 0:
        raise ValueError(f"XNO amount must be positive: {amount!r}")
    if value == value.to_integral_value() and value > MAX_SUPPLY_XNO:
        raise ValueError(
            f"{amount} XNO exceeds the Nano supply; if this is a raw amount pass it as "
            f"{{'amount': '{amount}', 'asset': 'XNO'}}"
        )
    with localcontext() as ctx:
        ctx.prec = 100  # never round: 30 fractional digits plus the integer part must fit
        raw = value * RAW_PER_XNO
    if raw != raw.to_integral_value():
        raise ValueError(f"{amount} XNO has more than 30 decimal places; 1 raw is the smallest unit")
    return str(int(raw))


class ExactNanoScheme:
    """Server implementation of the ``exact`` scheme for Nano (V2).

    Parses prices to raw and adds the work fields the facilitator advertises to
    ``extra``. Does not verify or settle; the SDK delegates that to the
    facilitator client registered for ``nano:mainnet``.

    Attributes:
        scheme: The scheme identifier ("exact").
    """

    scheme = SCHEME_EXACT
    default_asset_transfer_method = "default"
    payment_flows = {
        "default": {"supported": ("authorization",), "default": "authorization"},
    }

    def __init__(self) -> None:
        """Create ExactNanoScheme."""
        self._money_parsers: list[MoneyParser] = []

    def register_money_parser(self, parser: MoneyParser) -> ExactNanoScheme:
        """Register a custom money parser (tried in order before the XNO default).

        Use this to price in fiat: a parser receiving ``"0.01"`` for ``"$0.01"``
        may return an ``AssetAmount`` in raw, or ``None`` to pass.
        """
        self._money_parsers.append(parser)
        return self

    def parse_price(self, price: Price, network: Network) -> AssetAmount:
        """Convert a price to an ``AssetAmount`` in raw.

        * ``AssetAmount``/``{"amount": ..., "asset": "XNO"}``: ``amount`` is raw already.
        * Money (``"0.01"``, ``"0.01 XNO"``, ``0.01``): an XNO amount, converted exactly.
        * ``"$..."``: rejected unless a registered money parser handles it.
        """
        if isinstance(price, dict) and "amount" in price:
            return self._raw_asset_amount(price["amount"], price.get("asset"), price.get("extra"))
        if isinstance(price, AssetAmount):
            return self._raw_asset_amount(price.amount, price.asset, price.extra)

        parsed = parse_money(price)
        decimal_amount = parsed["amount"]
        symbol = parsed.get("symbol")

        for parser in self._money_parsers:
            result = parser(decimal_amount, str(network))
            if result is not None:
                return result

        if isinstance(price, str) and price.lstrip().startswith("$"):
            raise ValueError(
                f"fiat price {price!r} is not supported on {network}; give the amount in XNO "
                "(e.g. '0.01') or register a money parser that converts it"
            )
        if symbol is not None and symbol != ASSET_XNO:
            raise ValueError(f"unsupported asset {symbol!r} on {network}; only {ASSET_XNO} is accepted")

        return AssetAmount(amount=xno_to_raw(decimal_amount), asset=ASSET_XNO, extra={})

    def enhance_payment_requirements(
        self,
        requirements: PaymentRequirements,
        supported_kind: SupportedKind,
        extension_keys: list[str],
    ) -> PaymentRequirements:
        """Normalize asset/payTo/amount and add the facilitator's work fields to ``extra``.

        ``extra.work`` and ``extra.workThreshold`` are copied from the facilitator's
        ``/supported`` entry (falling back to ``"required"`` / the mainnet send
        threshold). Values already present in ``requirements.extra`` win, so a
        seller can override them via ``ResourceConfig.extra``.
        """
        _ = extension_keys
        kind_extra: dict[str, Any] = supported_kind.extra or {}

        asset = requirements.asset or kind_extra.get("asset") or ASSET_XNO
        if str(asset).upper() != ASSET_XNO:
            raise ValueError(f"unsupported asset {asset!r}; only {ASSET_XNO} is accepted")
        requirements.asset = ASSET_XNO

        requirements.pay_to = normalize_nano_address(requirements.pay_to)

        if "." in requirements.amount:
            requirements.amount = xno_to_raw(requirements.amount)
        if not _RAW_RE.fullmatch(requirements.amount):
            raise ValueError(f"amount must be a positive integer string in raw: {requirements.amount!r}")

        extra = dict(requirements.extra or {})
        extra.setdefault("work", kind_extra.get("work", "required"))
        extra.setdefault("workThreshold", kind_extra.get("workThreshold", SEND_BLOCK_WORK_THRESHOLD))
        requirements.extra = extra
        return requirements

    @staticmethod
    def _raw_asset_amount(
        amount: Any, asset: str | None, extra: dict[str, Any] | None
    ) -> AssetAmount:
        if not asset:
            raise ValueError(f"asset is required for AssetAmount prices; use {ASSET_XNO!r}")
        if str(asset).upper() != ASSET_XNO:
            raise ValueError(f"unsupported asset {asset!r}; only {ASSET_XNO} is accepted")
        raw = str(amount)
        if not _RAW_RE.fullmatch(raw):
            raise ValueError(f"AssetAmount.amount must be a positive integer string in raw: {amount!r}")
        return AssetAmount(amount=raw, asset=ASSET_XNO, extra=dict(extra or {}))
