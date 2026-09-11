"""FastAPI seller accepting USDC on Base *and* XNO on nano:mainnet with the x402 Python SDK.

Run:  pip install "x402[fastapi,httpx]" x402-nano-exact
      uvicorn fastapi_server:app --port 4021
"""

from fastapi import FastAPI
from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.middleware.fastapi import payment_middleware
from x402.mechanisms.evm.exact import ExactEvmServerScheme

from x402_nano_exact import ExactNanoServerScheme

# One facilitator client per facilitator. x402ResourceServer accepts a list and,
# on initialize(), maps each (network, scheme) from that client's /supported to it.
# Needs `pip install 'x402[evm,httpx,fastapi]'` (the EVM extra is not part of this package's
# dependencies). The Base facilitator must advertise eip155:8453 in /supported;
# https://x402.org/facilitator serves Base Sepolia (eip155:84532) only, so put the
# facilitator your USDC rail already uses here.
base_facilitator = HTTPFacilitatorClient(FacilitatorConfig(url="https://<the facilitator your Base rail uses>"))
nano_facilitator = HTTPFacilitatorClient(
    # /settle waits for confirmation up to 30 s; give the HTTP client more than the 30 s default.
    FacilitatorConfig(url="https://facilitator.pursekeeper.dev", timeout=45.0)
)

server = x402ResourceServer([base_facilitator, nano_facilitator])
server.register("eip155:8453", ExactEvmServerScheme())  # what you already do for Base
server.register("nano:mainnet", ExactNanoServerScheme())  # this package

routes = {
    "GET /api/weather": {
        "accepts": [
            {"scheme": "exact", "network": "eip155:8453", "price": "$0.01", "payTo": "0xYourBaseAddress"},
            {
                "scheme": "exact",
                "network": "nano:mainnet",
                "price": "0.01",  # XNO; the scheme converts to raw (10^28)
                "payTo": "nano_3mzq6kpu4b56w1afgouwumfc8juriqe3w1t14xf1f3tgc8fn4puepfrjhcfk",
                "maxTimeoutSeconds": 60,
            },
        ],
        "description": "Weather for the next hour",
        "mimeType": "application/json",
    }
}

app = FastAPI()
app.middleware("http")(payment_middleware(routes, server))


@app.get("/api/weather")
def weather():
    return {"forecast": "sunny", "unit": "celsius"}
