"""Runs with no network and no API key: the HTTP layer is replaced by a fake.

    python examples/offline_example.py
"""
from datetime import date
from unittest.mock import patch

from gb_bm_data import BMRSClient, LiveOnlyEndpointError

FAKE_PRICE_ROW = {
    "settlementDate": "2026-01-01",
    "settlementPeriod": 1,
    "systemBuyPrice": 80.0,
    "systemSellPrice": 60.0,
    "netImbalanceVolume": 120.0,
    "totalAcceptedOfferVolume": 50.0,
    "totalAcceptedBidVolume": -30.0,
}

client = BMRSClient(sleep_seconds=0)
with patch("gb_bm_data.client.get_json", return_value={"data": [FAKE_PRICE_ROW]}):
    prices = client.get_system_prices(date(2026, 1, 1), date(2026, 1, 1))
print(prices[["settlementDate", "settlementPeriod", "approx_cost_gbp"]])

try:
    client.get_forecast("FOU2T14D")
except LiveOnlyEndpointError as e:
    print("LiveOnlyEndpointError:", e)
