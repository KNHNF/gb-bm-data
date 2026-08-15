"""Unit tests with mocked HTTP, no real network calls."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gb_bm_data.carbon_intensity import CarbonIntensityClient
from gb_bm_data.client import BMRSClient
from gb_bm_data.exceptions import LiveOnlyEndpointError
from gb_bm_data.neso import HISTORIC_DAY_AHEAD_DEMAND_FORECAST_RESOURCE_ID, NESODataPortalClient

FAKE_PRICE_ROW = {
    "settlementDate": "2026-01-01",
    "settlementPeriod": 1,
    "systemBuyPrice": 80.0,
    "systemSellPrice": 60.0,
    "netImbalanceVolume": 120.0,
    "totalAcceptedOfferVolume": 50.0,
    "totalAcceptedBidVolume": -30.0,
}

FAKE_DEMAND_FORECAST_RECORD = {
    "_id": 1,
    "DAYSAHEAD": 1,
    "TARGETDATE": "2026-01-01",
    "FORECASTDEMAND": 25269,
    "CARDINALPOINT": "2A",
    "CP_TYPE": "P",
    "CP_ST_TIME": 930,
    "CP_END_TIME": 1030,
    "F_Point": "DM",
    "FORECAST_TIMESTAMP": "2025-12-31T08:46:43",
}

FAKE_GENERATION_MIX_ROW = {
    "from": "2026-01-01T00:00Z",
    "to": "2026-01-01T00:30Z",
    "generationmix": [
        {"fuel": "wind", "perc": 30.5},
        {"fuel": "solar", "perc": 0.0},
        {"fuel": "gas", "perc": 40.2},
        {"fuel": "nuclear", "perc": 15.1},
        {"fuel": "imports", "perc": 5.0},
    ],
}


def test_get_system_prices_computes_approx_cost():
    client = BMRSClient(sleep_seconds=0)
    with patch("gb_bm_data.client.get_json", return_value={"data": [FAKE_PRICE_ROW]}):
        df = client.get_system_prices(date(2026, 1, 1), date(2026, 1, 1))
    assert len(df) == 1
    expected = 50.0 * 80.0 + 30.0 * 60.0
    assert df.iloc[0]["approx_cost_gbp"] == expected


def test_get_system_prices_empty_range_returns_empty_frame():
    client = BMRSClient(sleep_seconds=0)
    with patch("gb_bm_data.client.get_json", return_value={"data": []}):
        df = client.get_system_prices(date(2026, 1, 1), date(2026, 1, 1))
    assert df.empty


def test_live_only_endpoint_raises():
    client = BMRSClient(sleep_seconds=0)
    try:
        client.get_forecast("FOU2T14D")
        assert False, "expected LiveOnlyEndpointError"
    except LiveOnlyEndpointError:
        pass


def test_get_generation_mix_parses_fuel_percentages():
    client = CarbonIntensityClient(sleep_seconds=0)
    with patch("gb_bm_data.carbon_intensity.get_json", return_value={"data": [FAKE_GENERATION_MIX_ROW]}):
        df = client.get_generation_mix(date(2026, 1, 1), date(2026, 1, 1))
    assert len(df) == 1
    row = df.iloc[0]
    assert row["settlementDate"] == "2026-01-01"
    assert row["settlementPeriod"] == 1
    assert row["wind_pct"] == 30.5
    assert row["gas_pct"] == 40.2
    assert row["nuclear_pct"] == 15.1
    assert row["imports_pct"] == 5.0


def test_get_generation_mix_empty_range_returns_empty_frame():
    client = CarbonIntensityClient(sleep_seconds=0)
    with patch("gb_bm_data.carbon_intensity.get_json", return_value={"data": []}):
        df = client.get_generation_mix(date(2026, 1, 1), date(2026, 1, 1))
    assert df.empty


def test_get_generation_mix_deduplicates_overlapping_chunks():
    client = CarbonIntensityClient(sleep_seconds=0)
    dup_rows = [FAKE_GENERATION_MIX_ROW, FAKE_GENERATION_MIX_ROW]
    with patch("gb_bm_data.carbon_intensity.get_json", return_value={"data": dup_rows}):
        df = client.get_generation_mix(date(2026, 1, 1), date(2026, 1, 1))
    assert len(df) == 1


def test_neso_query_uses_sql_endpoint_when_sql_given():
    client = NESODataPortalClient(sleep_seconds=0)
    captured = {}

    def fake_get_json(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return {"result": {"records": [FAKE_DEMAND_FORECAST_RECORD]}}

    with patch("gb_bm_data.neso.get_json", side_effect=fake_get_json):
        df = client.query(HISTORIC_DAY_AHEAD_DEMAND_FORECAST_RESOURCE_ID, sql="SELECT 1")
    assert captured["url"].endswith("datastore_search_sql")
    assert len(df) == 1


def test_neso_query_uses_search_endpoint_and_filters_when_no_sql():
    client = NESODataPortalClient(sleep_seconds=0)
    captured = {}

    def fake_get_json(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return {"result": {"records": []}}

    with patch("gb_bm_data.neso.get_json", side_effect=fake_get_json):
        client.query("some-resource-id", filters={"DAYSAHEAD": 1})
    assert captured["url"].endswith("datastore_search")
    assert captured["params"]["resource_id"] == "some-resource-id"
    assert '"DAYSAHEAD": 1' in captured["params"]["filters"]


def test_get_historic_day_ahead_demand_forecast_parses_and_sorts():
    client = NESODataPortalClient(sleep_seconds=0)
    rows = [
        {**FAKE_DEMAND_FORECAST_RECORD, "CP_ST_TIME": 1030},
        {**FAKE_DEMAND_FORECAST_RECORD, "CP_ST_TIME": 30},
    ]
    with patch("gb_bm_data.neso.get_json", return_value={"result": {"records": rows}}):
        df = client.get_historic_day_ahead_demand_forecast(date(2026, 1, 1), date(2026, 1, 1))
    assert list(df["CP_ST_TIME"]) == [30, 1030]
    assert df.iloc[0]["FORECASTDEMAND"] == 25269


def test_get_historic_day_ahead_demand_forecast_empty_range_returns_empty_frame():
    client = NESODataPortalClient(sleep_seconds=0)
    with patch("gb_bm_data.neso.get_json", return_value={"result": {"records": []}}):
        df = client.get_historic_day_ahead_demand_forecast(date(2026, 1, 1), date(2026, 1, 1))
    assert df.empty


def test_retry_params_pass_through_to_http_layer():
    client = BMRSClient(sleep_seconds=0, max_retries=5, backoff_seconds=2.0)
    captured = {}

    def fake_get_json(url, **kwargs):
        captured.update(kwargs)
        return {"data": [FAKE_PRICE_ROW]}

    with patch("gb_bm_data.client.get_json", side_effect=fake_get_json):
        client.get_system_prices(date(2026, 1, 1), date(2026, 1, 1))
    assert captured["max_retries"] == 5
    assert captured["backoff_seconds"] == 2.0


if __name__ == "__main__":
    test_get_system_prices_computes_approx_cost()
    test_get_system_prices_empty_range_returns_empty_frame()
    test_live_only_endpoint_raises()
    test_get_generation_mix_parses_fuel_percentages()
    test_get_generation_mix_empty_range_returns_empty_frame()
    test_get_generation_mix_deduplicates_overlapping_chunks()
    test_neso_query_uses_sql_endpoint_when_sql_given()
    test_neso_query_uses_search_endpoint_and_filters_when_no_sql()
    test_get_historic_day_ahead_demand_forecast_parses_and_sorts()
    test_get_historic_day_ahead_demand_forecast_empty_range_returns_empty_frame()
    test_retry_params_pass_through_to_http_layer()
    print("all tests passed")
