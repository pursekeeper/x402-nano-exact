# x402-nano-exact

Resource-server side of the x402 v2 **`exact`** scheme on **`nano:mainnet`** for the
official [x402 Python SDK](https://pypi.org/project/x402/) (`x402 >= 2.22`).
It is the Python counterpart of the JS package
[`@x402nano/exact`](https://github.com/x402nano/exact) (`./server` export): it
parses prices into raw and builds the `accepts` entry; verification and
settlement are delegated by the SDK to a Nano facilitator such as
[facilitator.pursekeeper.dev](https://facilitator.pursekeeper.dev).

Pure Python; the only dependency is `x402` itself (`x402[httpx]` for the HTTP
facilitator client).

## Quick start

```python
from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402_nano_exact import ExactNanoServerScheme

base_facilitator = HTTPFacilitatorClient(FacilitatorConfig(url="https://x402.org/facilitator"))
nano_facilitator = HTTPFacilitatorClient(FacilitatorConfig(url="https://facilitator.pursekeeper.dev", timeout=45.0))

server = x402ResourceServer([base_facilitator, nano_facilitator])
server.register("eip155:8453", ExactEvmServerScheme())
server.register("nano:mainnet", ExactNanoServerScheme())
server.initialize()  # fetches /supported from each facilitator and routes nano:mainnet to the Nano one
```

Then use the server exactly as for any other network. A route accepting both:

```python
routes = {
    "GET /api/weather": {
        "accepts": [
            {"scheme": "exact", "network": "eip155:8453", "price": "$0.01", "payTo": "0x..."},
            {"scheme": "exact", "network": "nano:mainnet", "price": "0.01", "payTo": "nano_...", "maxTimeoutSeconds": 60},
        ]
    }
}
```

See `examples/fastapi_server.py` for the full FastAPI middleware version.

## What goes on the wire

`price: "0.01"` on `nano:mainnet` produces this `accepts` entry (1 XNO = 10^30 raw):

```json
{"scheme": "exact", "network": "nano:mainnet", "asset": "XNO",
 "amount": "10000000000000000000000000000", "payTo": "nano_...", "maxTimeoutSeconds": 60,
 "extra": {"work": "required", "workThreshold": "fffffff800000000"}}
```

`extra.work` / `extra.workThreshold` are copied from the facilitator's `/supported`
entry; values you set in `extra` yourself take precedence.

## Prices

| form | meaning |
| --- | --- |
| `"0.01"`, `0.01`, `"0.01 XNO"` | XNO, converted exactly to raw |
| `{"amount": "10000000000000000000000000000", "asset": "XNO"}` / `AssetAmount(...)` | already raw |
| `"$0.01"` | rejected unless you `register_money_parser(...)` a fiat converter |

Rejected: zero/negative, more than 30 decimal places, other assets, and integer
amounts above the Nano supply (a raw amount typed as XNO — pass it as `AssetAmount`).
Note the JS `@x402nano/exact` reads integer strings as raw; here Money is always XNO,
matching the SDK's convention for `Money`.

`payTo` is checksum-validated at requirement build time; `xrb_` is normalized to `nano_`.

## Notes

- Payment flow is `authorization` only: verify before the handler, settle after it
  (the buyer is never charged for a failed request). Same as the JS package.
- The facilitator's `/settle` waits for block confirmation for up to 30 s; set
  `FacilitatorConfig(timeout=45.0)` so the SDK's HTTP client does not give up first.
- `maxTimeoutSeconds` defaults to the SDK's 300 if you do not set it; 60 is customary.

## Pitfalls seen in the first integrations

Reported by the first two sellers who wired this in (2026-09-11), with credit:

- **Import the right module.** The package is `x402_nano_exact`, not `x402nano`. One seller wrapped the
  registration in a broad `except` and a wrong module name turned into "Nano rail silently disabled on
  every boot", which looks identical to "not enabled". Let the import fail loudly, or log the exception.
  (OreoMuncher45)
- **Module-level names are evaluated before your feature flag.** A `NANO_ADDRESS` default referenced at
  import time, before the `NANO_ENABLED` check, raised `NameError` on startup and would have taken a
  40-endpoint API down with it. Declare the payout address at module scope or read it inside the flag.
  (OreoMuncher45)
- **Two networks, two facilitators, both must answer `/supported`.** Running without the Base facilitator
  key silently fell back to the x402.org testnet facilitator, which does not serve `eip155:8453`; every
  EVM route then failed `RouteConfigurationError` and nothing about it pointed at Nano. Check each
  facilitator's `/supported` for its own network before blaming the new scheme. (OreoMuncher45)
- **Price is integer XNO, not raw and not `"$0.01"`.** `Money` follows the SDK convention; a string
  dollar price is rejected on purpose rather than converted at a guessed rate. (Kept after review by
  OreoMuncher45; open an issue if you disagree.)
- **Free hosting sleeps.** A seller on Render Free takes about a minute to wake; fetch a health route
  with a long timeout first, then get a fresh 402 before building the block, since `maxTimeoutSeconds`
  starts at the quote. (Reeyen Patel, github.com/Reeyenn/nano-csv-service, the first live seller on
  this scheme; settled through facilitator.pursekeeper.dev on 2026-09-11.)

## Tests

```
pip install -e ".[dev]"
pytest                    # offline: SDK-built 402 shape and verify path with a fake facilitator
X402_NANO_LIVE=1 pytest   # plus one live /supported + malformed /verify against facilitator.pursekeeper.dev
```
