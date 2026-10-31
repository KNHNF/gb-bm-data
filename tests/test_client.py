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


def _raises(exc_type, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc_type as e:
        return e
    raise AssertionError(f"expected {exc_type.__name__}")


def test_every_live_only_dataset_raises():
    from gb_bm_data.client import LIVE_ONLY_DATASETS

    assert LIVE_ONLY_DATASETS == {"DATL", "FOU2T14D", "demand/outturn/stream"}
    client = BMRSClient(sleep_seconds=0)
    for name in sorted(LIVE_ONLY_DATASETS):
        _raises(LiveOnlyEndpointError, client.get_forecast, name)


def test_live_only_match_ignores_case_and_slashes():
    client = BMRSClient(sleep_seconds=0)
    for name in ["/demand/outturn/stream", "datl", " FOU2T14D ", "/Demand/Outturn/Stream/"]:
        _raises(LiveOnlyEndpointError, client.get_forecast, name)


def test_unknown_forecast_dataset_is_not_live_only():
    client = BMRSClient(sleep_seconds=0)
    e = _raises(NotImplementedError, client.get_forecast, "SOMETHING_ELSE")
    assert not isinstance(e, LiveOnlyEndpointError)


def test_reversed_date_range_raises_value_error_in_every_client():
    d1, d2 = date(2026, 1, 2), date(2026, 1, 1)
    _raises(ValueError, BMRSClient(sleep_seconds=0).get_system_prices, d1, d2)
    _raises(ValueError, BMRSClient(sleep_seconds=0).get_demand_outturn, d1, d2)
    _raises(ValueError, CarbonIntensityClient(sleep_seconds=0).get_generation_mix, d1, d2)
    _raises(ValueError, NESODataPortalClient(sleep_seconds=0).get_historic_day_ahead_demand_forecast, d1, d2)


def test_demand_outturn_uses_london_settlement_periods_in_bst():
    # 2026-07-01 is BST: 23:00Z on 30 June is local midnight, so period 1 of 1 July.
    rows = [
        {"startTime": "2026-06-30T23:00:00Z", "demand": 1000},
        {"startTime": "2026-06-30T23:25:00Z", "demand": 1100},
        {"startTime": "2026-07-01T22:30:00Z", "demand": 900},
    ]
    client = BMRSClient(sleep_seconds=0)
    captured = {}

    def fake_get_json(url, **kwargs):
        captured.update(kwargs["params"])
        return {"data": rows}

    with patch("gb_bm_data.client.get_json", side_effect=fake_get_json):
        df = client.get_demand_outturn(date(2026, 7, 1), date(2026, 7, 1))
    assert captured["from"] == "2026-06-30T23:00Z"
    assert captured["to"] == "2026-07-01T22:59Z"
    assert list(df["settlementDate"]) == ["2026-07-01", "2026-07-01"]
    assert list(df["settlementPeriod"]) == [1, 48]
    assert list(df["demand_mw"]) == [1050, 900]


def test_demand_outturn_handles_25_hour_clock_change_day():
    # 2026-10-25: clocks go back, the day has 25 hours and 50 periods.
    # Local midnight is 23:00Z on 24 Oct (BST), the day ends at 00:00Z on 26 Oct.
    rows = [
        {"startTime": "2026-10-24T23:00:00Z", "demand": 700},
        {"startTime": "2026-10-25T23:30:00Z", "demand": 800},
    ]
    client = BMRSClient(sleep_seconds=0)
    with patch("gb_bm_data.client.get_json", return_value={"data": rows}):
        df = client.get_demand_outturn(date(2026, 10, 25), date(2026, 10, 25))
    assert list(df["settlementDate"]) == ["2026-10-25", "2026-10-25"]
    assert list(df["settlementPeriod"]) == [1, 50]


def test_generation_mix_uses_london_settlement_periods_in_bst():
    row = {**FAKE_GENERATION_MIX_ROW, "from": "2026-06-30T23:00Z"}
    client = CarbonIntensityClient(sleep_seconds=0)
    with patch("gb_bm_data.carbon_intensity.get_json", return_value={"data": [row]}):
        df = client.get_generation_mix(date(2026, 6, 30), date(2026, 6, 30))
    assert df.iloc[0]["settlementDate"] == "2026-07-01"
    assert df.iloc[0]["settlementPeriod"] == 1


def test_neso_days_ahead_must_be_an_integer():
    client = NESODataPortalClient(sleep_seconds=0)
    with patch("gb_bm_data.neso.get_json", return_value={"result": {"records": []}}) as m:
        _raises(ValueError, client.get_historic_day_ahead_demand_forecast,
                date(2026, 1, 1), date(2026, 1, 1), days_ahead="1 OR 1=1")
        assert not m.called


def _http_error(status):
    import requests

    resp = requests.Response()
    resp.status_code = status
    return requests.HTTPError(f"HTTP {status}", response=resp)


def test_http_client_error_is_not_retried():
    from gb_bm_data import _http
    from gb_bm_data.exceptions import RequestFailedError

    calls = []

    class FakeResp:
        def raise_for_status(self):
            calls.append(1)
            raise _http_error(404)

    with patch("gb_bm_data._http.requests.get", return_value=FakeResp()), \
            patch("gb_bm_data._http.time.sleep") as sleep:
        _raises(RequestFailedError, _http.get_json, "http://x", max_retries=3)
    assert len(calls) == 1
    assert not sleep.called


def test_http_server_error_is_retried_then_raises_retry_exhausted():
    from gb_bm_data import _http
    from gb_bm_data.exceptions import RetryExhaustedError

    calls = []

    class FakeResp:
        def raise_for_status(self):
            calls.append(1)
            raise _http_error(503)

    with patch("gb_bm_data._http.requests.get", return_value=FakeResp()), \
            patch("gb_bm_data._http.time.sleep"):
        _raises(RetryExhaustedError, _http.get_json, "http://x", max_retries=3)
    assert len(calls) == 3


def test_http_rejects_zero_retries():
    from gb_bm_data import _http

    _raises(ValueError, _http.get_json, "http://x", max_retries=0)


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
    print(f"all {len(tests)} tests passed")
