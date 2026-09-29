"""Unit tests with mocked HTTP, no real network calls."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gb_bm_data.carbon_intensity import CarbonIntensityClient
from gb_bm_data.client import BMRSClient
from gb_bm_data._settlement import to_settlement
from gb_bm_data.exceptions import LiveOnlyEndpointError, RetryExhaustedError
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

FAKE_DEMAND_OUTTURN_ROWS = [
    {"startTime": "2026-01-01T00:05:00Z", "demand": 1000},
    {"startTime": "2026-01-01T00:25:00Z", "demand": 1100},
    {"startTime": "2026-01-01T00:30:00Z", "demand": 1200},
]

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


def test_get_demand_outturn_aggregates_five_minute_values_to_settlement_periods():
    client = BMRSClient(sleep_seconds=0)
    with patch("gb_bm_data.client.get_json", return_value={"data": FAKE_DEMAND_OUTTURN_ROWS}):
        df = client.get_demand_outturn(date(2026, 1, 1), date(2026, 1, 1))
    assert list(df["settlementPeriod"]) == [1, 2]
    assert list(df["demand_mw"]) == [1050, 1200]


def test_get_interconnector_flows_raises_live_only():
    client = BMRSClient(sleep_seconds=0)
    try:
        client.get_interconnector_flows(date(2026, 1, 1), date(2026, 1, 1))
        assert False, "expected LiveOnlyEndpointError"
    except LiveOnlyEndpointError:
        pass


def test_get_nonbm_stor_parses_rows():
    client = BMRSClient(sleep_seconds=0)
    fake_row = {"dataset": "NONBM", "settlementDate": "2026-01-01", "settlementPeriod": 1, "volume": 5.2}
    with patch("gb_bm_data.client.get_json", return_value={"data": [fake_row]}):
        df = client.get_nonbm_stor(date(2026, 1, 1), date(2026, 1, 1))
    assert len(df) == 1
    assert df.iloc[0]["volume"] == 5.2


def test_get_nonbm_stor_empty_range_returns_empty_frame():
    client = BMRSClient(sleep_seconds=0)
    with patch("gb_bm_data.client.get_json", return_value={"data": []}):
        df = client.get_nonbm_stor(date(2026, 1, 1), date(2026, 1, 1))
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


def _settle(*utc):
    s = pd.Series(pd.to_datetime(list(utc), utc=True))
    d, p = to_settlement(s)
    return list(zip(d, p))


def test_settlement_winter_day_starts_at_midnight_utc():
    assert _settle("2026-01-15T00:00Z", "2026-01-15T23:30Z") == [("2026-01-15", 1), ("2026-01-15", 48)]


def test_settlement_summer_day_starts_at_23_00_utc_the_day_before():
    assert _settle("2026-06-30T23:00Z", "2026-07-01T22:30Z") == [("2026-07-01", 1), ("2026-07-01", 48)]


def test_settlement_clock_forward_day_has_46_periods():
    assert _settle("2026-03-29T00:00Z", "2026-03-29T22:30Z", "2026-03-29T23:00Z") == [
        ("2026-03-29", 1), ("2026-03-29", 46), ("2026-03-30", 1)]


def test_settlement_clock_back_day_has_50_periods():
    assert _settle("2025-10-25T23:00Z", "2025-10-26T23:30Z") == [("2025-10-26", 1), ("2025-10-26", 50)]


BST_DEMAND_ROWS = [
    {"startTime": "2026-06-30T23:05:00Z", "demand": 1000},
    {"startTime": "2026-06-30T23:25:00Z", "demand": 1100},
    {"startTime": "2026-06-30T23:30:00Z", "demand": 1200},
    {"startTime": "2026-06-30T12:00:00Z", "demand": 9999},
]


def test_demand_outturn_uses_official_periods_in_summer_and_drops_other_dates():
    client = BMRSClient(sleep_seconds=0)
    with patch("gb_bm_data.client.get_json", return_value={"data": BST_DEMAND_ROWS}):
        df = client.get_demand_outturn(date(2026, 7, 1), date(2026, 7, 1))
    assert list(df["settlementDate"]) == ["2026-07-01", "2026-07-01"]
    assert list(df["settlementPeriod"]) == [1, 2]
    assert list(df["demand_mw"]) == [1050, 1200]


def test_demand_outturn_utc_index_keeps_the_older_numbering():
    client = BMRSClient(sleep_seconds=0)
    with patch("gb_bm_data.client.get_json", return_value={"data": BST_DEMAND_ROWS[:3]}):
        df = client.get_demand_outturn(date(2026, 7, 1), date(2026, 7, 1), utc_index=True)
    assert list(df["settlementPeriod"]) == [47, 48]
    assert list(df["settlementDate"]) == ["2026-07-01", "2026-07-01"]


def test_generation_mix_uses_official_periods_in_summer():
    row = dict(FAKE_GENERATION_MIX_ROW, **{"from": "2026-06-30T23:00Z", "to": "2026-06-30T23:30Z"})
    client = CarbonIntensityClient(sleep_seconds=0)
    with patch("gb_bm_data.carbon_intensity.get_json", return_value={"data": [row]}):
        df = client.get_generation_mix(date(2026, 7, 1), date(2026, 7, 1))
        legacy = client.get_generation_mix(date(2026, 7, 1), date(2026, 7, 1), utc_index=True)
    assert (df.iloc[0]["settlementDate"], df.iloc[0]["settlementPeriod"]) == ("2026-07-01", 1)
    assert (legacy.iloc[0]["settlementDate"], legacy.iloc[0]["settlementPeriod"]) == ("2026-06-30", 47)


def test_client_error_is_not_retried():
    resp = Mock()
    resp.raise_for_status.side_effect = requests.HTTPError(response=Mock(status_code=404))
    with patch("gb_bm_data._http.requests.get", return_value=resp) as fake_get:
        try:
            BMRSClient(sleep_seconds=0).get_system_prices(date(2026, 1, 1), date(2026, 1, 1))
            assert False, "expected RetryExhaustedError"
        except RetryExhaustedError as e:
            assert "HTTP 404" in str(e)
    assert fake_get.call_count == 1


if __name__ == "__main__":
    test_get_system_prices_computes_approx_cost()
    test_get_system_prices_empty_range_returns_empty_frame()
    test_get_demand_outturn_aggregates_five_minute_values_to_settlement_periods()
    test_get_interconnector_flows_raises_live_only()
    test_get_nonbm_stor_parses_rows()
    test_get_nonbm_stor_empty_range_returns_empty_frame()
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
