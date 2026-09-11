# x402 `exact` on `nano:mainnet` for the x402 Python SDK — report

Written 2026-09-10 ~21:00Z. Everything below is on disk under
`/var/lib/gambit/workspace/x402/python-exact/`; nothing was published, posted, pushed or paid.
Line numbers refer to the installed `x402==2.22.0` at `.venv/lib/python3.14/site-packages/x402/`.

## 1. SDK version and server-scheme interface (from the installed source)

- **Version**: PyPI `x402` 2.22.0 (latest; requires Python >=3.10; deps `pydantic`, `nest-asyncio`,
  `typing-extensions`; `httpx` only via extras `x402[httpx]`). Upstream is now
  `github.com/x402-foundation/x402` (`python/x402/pyproject.toml` = 2.22.0);
  `github.com/coinbase/x402` main still shows 2.8.0, i.e. stale.
- **Server scheme type**: `SchemeNetworkServer` is a `typing.Protocol`, not an ABC — duck-typed, no
  base class to import (`interfaces.py:282-363`). Required members:
  - `scheme: str` (`:311`)
  - `default_asset_transfer_method: str` (`:316`; use `"default"` when the scheme has no on-wire ATM)
  - `payment_flows: Mapping[str, PaymentFlowConfig]` (`:324`; `{"default": {"supported": (...), "default": "authorization"}}`)
  - `parse_price(self, price: Price, network: Network) -> AssetAmount` (`:331`)
  - `enhance_payment_requirements(self, requirements: PaymentRequirements, supported_kind: SupportedKind, extensions: list[str]) -> PaymentRequirements` (`:345`)
  - optional `validate_facilitator_support(...)` (`:366-396`), optional hook methods (`:176-247`).
  Protocols are sync-first (`interfaces.py:6`); the same scheme object works with `x402ResourceServer`
  (async) and `x402ResourceServerSync`.
- **Types**: `Network = str`, `Money = str | int | float`, `Price = Money | AssetAmount`
  (`schemas/base.py:12-49`); `AssetAmount(amount: str, asset: str, extra)`; `PaymentRequirements`
  (`schemas/payments.py:33-52`, camelCase aliases via `BaseX402Model`); `ResourceConfig(scheme, pay_to,
  price, network, max_timeout_seconds, extra)` (`schemas/config.py:9-25`); `SupportedKind(x402_version,
  scheme, network, extra)` (`schemas/responses.py:91-104`).
- **`x402ResourceServer.register(network, scheme)`** (`server_base.py:492-509`): stores
  `self._schemes[network][scheme.scheme] = scheme` and collects optional hook methods. Returns self.
- **Facilitator clients per network**: the constructor takes one client or a list
  (`server_base.py:449-458`). `initialize()` (`:596-620`) calls each client's sync `get_supported()`
  and fills `self._facilitator_clients_map[network][scheme] = client` from the returned `kinds`,
  earlier client wins. `verify_payment`/`settle_payment` look the client up by
  `payload.accepted.{network,scheme}` (`:1417`, `:1653`). So OreoMuncher45's description
  (`_facilitator_clients_map`, list of clients, `/supported` routing) is accurate.
- **Requirement building** (`server_base.py:663-722`): `parse_price` -> `PaymentRequirements(...,
  max_timeout_seconds=config.max_timeout_seconds or 300, extra={**asset_amount.extra, **config.extra})`
  -> `enhance_payment_requirements(req, supported_kind, extensions)` -> `resolve_payment_flow` +
  `apply_payment_flow_wire_extra` (`payment_flow.py:84-102`: strips the `"default"` ATM sentinel, adds
  `extra.paymentFlow` only when the flow is not `authorization`).
- **HTTP facilitator client**: `HTTPFacilitatorClient` (async, `http/facilitator_client.py:107`) and
  `HTTPFacilitatorClientSync` (`:334`); config `FacilitatorConfig(url, timeout=30.0, http_client,
  auth_provider, identifier)` dataclass or `{"url": ..., "create_headers": ...}` dict
  (`http/facilitator_client_base.py:133-171`). `get_supported` does a sync GET `{url}/supported`
  (`:203-226`); verify/settle POST `{"x402Version", "paymentPayload", "paymentRequirements"}`
  (`facilitator_client_base.py:195-206`, `facilitator_client.py:280-300`).
- **Non-EVM template**: the Python SDK has no Stellar/XRPL mechanism (only `evm`, `svm`, `tvm`;
  `x402-xrpl`/`x402-algorand` are third-party PyPI packages). I mirrored
  `mechanisms/tvm/exact/server.py:23-130` (`ExactTvmScheme`: class attrs, `register_money_parser`,
  `parse_price` via `schemas.helpers.parse_money`, `enhance_payment_requirements` normalising
  asset/payTo/amount and copying facilitator `supported_kind.extra`), and the `__init__` alias pattern
  `ExactTvmServerScheme` (`tvm/exact/__init__.py`).

## 2. Facilitator contract (what the scheme must emit)

From `api/facilitator.js:61-70,120` and `api/x402.js:29-44,86-91` and the live `/supported`:
`scheme "exact"`, `network "nano:mainnet"`, `asset "XNO"` (compared upper-cased), `payTo` a valid
`nano_`/`xrb_` address, `amount` matching `/^[1-9]\d*$/` in raw (1 XNO = 10^30 raw). Unknown `extra`
keys are ignored; `maxTimeoutSeconds` is not validated (settle waits at most 30 s). `/supported`
advertises `extra: {asset: "XNO", work: "required", workThreshold: "fffffff800000000"}`.

JS reference (`x402/exact/src/typescript/server/scheme.ts:71-171`): `scheme='exact'`,
`defaultAssetTransferMethod='default'`, `paymentFlows={default:{supported:['authorization']}}`;
`parsePrice` treats strings matching `/^\d*\.\d+$/` as XNO and everything else as raw
(`typescript-common` `STRING_DECIMAL`); `enhancePaymentRequirements` is a no-op.

## 3. What was built

```
src/x402_nano_exact/
  constants.py   SCHEME_EXACT, NETWORK_NANO_MAINNET, ASSET_XNO, RAW_PER_XNO, SEND_BLOCK_WORK_THRESHOLD
  address.py     normalize_nano_address / is_nano_address (base32 + blake2b checksum, stdlib only)
  server.py      ExactNanoScheme (SchemeNetworkServer), xno_to_raw (Decimal, exact, no rounding)
  __init__.py    re-exports; ExactNanoServerScheme = ExactNanoScheme (SDK naming)
tests/           conftest.py (FakeNanoFacilitator), test_scheme.py (28 offline), test_live_facilitator.py (2 live)
examples/fastapi_server.py   Base + nano:mainnet, two HTTPFacilitatorClients, payment_middleware
README.md, pyproject.toml (dist name x402-nano-exact, dep x402>=2.22.0)
```

`ExactNanoScheme`: `scheme="exact"`, `default_asset_transfer_method="default"`,
`payment_flows={"default": {"supported": ("authorization",), "default": "authorization"}}` (as JS).
`parse_price` accepts `"0.01"`, `0.01`, `"0.01 XNO"` (SDK `parse_money`), `{"amount": raw, "asset":
"XNO"}` and `AssetAmount` (raw as-is), runs registered money parsers first (SDK pattern), rejects `$`
prices, other assets, zero/negative, >30 decimals and integer amounts above the Nano supply.
`enhance_payment_requirements` forces `asset="XNO"`, checksum-validates and `nano_`-normalises
`payTo`, converts a stray decimal amount, and `setdefault`s `extra.work` / `extra.workThreshold` from
`supported_kind.extra` (fallbacks `"required"` / `fffffff800000000`) so `ResourceConfig.extra` wins.

Resulting `accepts` entry for `price="0.01"`:
`{"scheme":"exact","network":"nano:mainnet","asset":"XNO","amount":"10000000000000000000000000000",
"payTo":"nano_...","maxTimeoutSeconds":60,"extra":{"work":"required","workThreshold":"fffffff800000000"}}`.

## 4. Running the tests

`python3 -m venv` lacked ensurepip on this box, so: `python3 -m venv --without-pip .venv &&
python3 -m pip --python .venv/bin/python install x402 pytest httpx fastapi`. Then from the package dir:

- `.venv/bin/python -m pytest` -> **28 passed, 2 skipped** (pytest picks up `src/` via `pyproject.toml`).
  Covers price parsing, SDK-built requirements/402 JSON shape, facilitator routing via `/supported`,
  and `x402ResourceServerSync.verify_payment` delegating to a fake client returning `invalid_block`.
- `X402_NANO_LIVE=1 .venv/bin/python -m pytest tests/test_live_facilitator.py` -> **2 passed**.

## 5. Live check (20:54:56Z, no settle, no payment)

Real `HTTPFacilitatorClientSync` and async `HTTPFacilitatorClient` against
`https://facilitator.pursekeeper.dev`: `get_supported()` lists `(2, "exact", "nano:mainnet")` with the
expected `extra`; `verify()` with `payload.block = {"type":"state","account":..., "signature":"not-hex"}`
returns `isValid=false, invalidReason="invalid_block"` on both clients. Additionally a FastAPI
`payment_middleware` app with a `nano:mainnet` route (TestClient): unpaid GET -> 402 with a
`PAYMENT-REQUIRED` header decoding to exactly the entry above; a malformed `PAYMENT-SIGNATURE` -> 402
whose `PAYMENT-REQUIRED.error` is `"invalid_block"` (JSON body `{}`, the SDK default).

## 6. Name research (checked 2026-09-10; nothing registered)

| name | PyPI | npm | GitHub repos with that name | reads as squatting x402nano? |
| --- | --- | --- | --- | --- |
| `x402nano` | free (404) | free | org `x402nano` + `Bobjonesgood/x402nano` | yes — it is the org's name |
| `x402nano-exact` | free | free (`@x402nano/exact` is scoped) | `x402nano/exact` (name match) | yes unless published by/with the org |
| `x402-nano-exact` | free | free | none | no; fits PyPI's `x402-<chain>` pattern (`x402-algorand`, `x402-xrpl`, `x402-solana` exist) and is scheme-scoped |
| `x402-nano` | free | free | unrelated hits (`nano-x402-client`, `x402.Nano`) | no, but over-claims (implies client + facilitator) |
| `nano-x402-exact` | free | free | none | no; unusual word order |

**Recommendation**: offer the code to the x402nano org first as a sibling repo (e.g.
`x402nano/exact-python`), published as dist **`x402nano-exact`** with import path **`x402nano.exact`**
(PEP 420 namespace package `x402nano`; `from x402nano.exact import ExactNanoServerScheme`, and
`x402nano.exact.server.ExactNanoScheme` mirroring the JS `@x402nano/exact/server`). If the org declines
or is slow, publish independently as **`x402-nano-exact`** with import **`x402_nano_exact`** — which is
what is on disk now, precisely so it does not presume the org's name. Switching is `git mv
src/x402_nano_exact src/x402nano/exact` plus the `packages` line in `pyproject.toml`.

## 7. Open questions / things I guessed

1. **Integer Money = XNO, not raw.** The JS package reads `"1"` as 1 raw; the SDK's `Money` convention
   is human units, so here `"1"` is 1 XNO and raw must be passed as `AssetAmount`. Integer amounts above
   the supply are rejected with a hint instead of silently guessed. Worth agreeing with x402nano.
2. `"$0.01"` is rejected (JS produces an invalid amount). A fiat rate hook is available via
   `register_money_parser`, same shape as the SDK's.
3. `extra.work`/`extra.workThreshold` are added per the brief; the facilitator ignores requirement
   `extra`, and the JS server emits `extra: {}`. Harmless and informative to clients; overridable.
4. Only the `authorization` flow is declared (as JS). `upfront` could be added later.
5. `maxTimeoutSeconds` is left to the caller (SDK default 300). Because `/settle` can wait 30 s and
   `FacilitatorConfig.timeout` defaults to 30 s, README/example use `timeout=45.0`.
6. Browser paywall: the SDK serves its EVM HTML paywall for any non-`solana:` network
   (`http/x402_http_server_base.py:1293-1315`), so a nano-only route shows an EVM wallet page to
   browsers. JSON clients are unaffected; a `PaywallProvider` could fix it later.
7. No `validate_facilitator_support` hook (could assert `kind.extra.asset == "XNO"` at `initialize()`).
8. `pip install -e .` with the hatchling backend was not exercised (no backend in the venv); tests run
   through pytest's `pythonpath`.
9. Interface drift: the seller's description omitted `default_asset_transfer_method`/`payment_flows`,
   which the SDK now requires; otherwise their account matched the source.
