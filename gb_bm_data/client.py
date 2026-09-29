"""Client for the Elexon BMRS (Insights) API, historical GB balancing-mechanism
data only. Live-only endpoints (forecasts, streaming demand) raise
LiveOnlyEndpointError rather than silently returning wrong data, see
exceptions.py for the confirmed list."""
from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd

from gb_bm_data._http import DEFAULT_BACKOFF_SECONDS, DEFAULT_MAX_RETRIES, get_json
from gb_bm_data.exceptions import LiveOnlyEndpointError

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"

LIVE_ONLY_DATASETS = {"DATL", "FOU2T14D", "demand/outturn/stream", "INTOUTHH"}


class BMRSClient:
    """Historical GB balancing-mechanism data. Dates are inclusive.
    Rate-limits itself with a small sleep between calls by default; pass
    sleep_seconds=0 to disable (e.g. in tests with mocked requests)."""

    def __init__(self, base_url: str = BASE_URL, sleep_seconds: float = 0.5,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 backoff_seconds: float = DEFAULT_BACKOFF_SECONDS):
        self.base_url = base_url
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def get_system_prices(self, start: date, end: date) -> pd.DataFrame:
        """DISEBSP dataset: system buy/sell price, net imbalance volume,
        accepted offer/bid volumes per settlement period. Adds
        approx_cost_gbp = offer_vol * SBP + |bid_vol| * SSP."""
        rows: list[dict] = []
        current = start
        while current <= end:
            url = f"{self.base_url}/balancing/settlement/system-prices/{current.isoformat()}"
            data = get_json(url, params={"format": "json"}, max_retries=self.max_retries,
                             backoff_seconds=self.backoff_seconds).get("data", [])
            rows.extend(data)
            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)
            current += timedelta(days=1)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["approx_cost_gbp"] = (
            df["totalAcceptedOfferVolume"] * df["systemBuyPrice"]
            + df["totalAcceptedBidVolume"].abs() * df["systemSellPrice"]
        )
        return df

    def get_demand_outturn(self, start: date, end: date) -> pd.DataFrame:
        """FUELINST via /generation/outturn: 5-min system demand, averaged into
        half-hours. settlementPeriod here is a UTC half-hour index (1 starts at
        00:00 UTC), not the official settlement period. The two match in winter
        but differ by two periods during British Summer Time. Historical day-ahead demand
        forecasts are not available via BMRS; lagged actual demand is the
        standard substitute for a demand feature, document this in methodology
        if used that way."""
        rows: list[dict] = []
        current = start
        while current <= end:
            url = f"{self.base_url}/generation/outturn"
            data = get_json(url, params={
                "from": f"{current.isoformat()}T00:00Z",
                "to": f"{current.isoformat()}T23:59Z",
                "format": "json",
            }, max_retries=self.max_retries, backoff_seconds=self.backoff_seconds).get("data", [])
            rows.extend(self._aggregate_to_settlement_period(data, current))
            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)
            current += timedelta(days=1)

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        return df.sort_values(["settlementDate", "settlementPeriod"]).reset_index(drop=True)

    def get_interconnector_flows(self, *_args, **_kwargs):
        """Always raises. INTOUTHH (/generation/outturn/interconnectors) ignores the
        from and to parameters and returns only the latest few days. Tested on
        2017-03-01 and it still returned recent data, so this fails loudly."""
        raise LiveOnlyEndpointError(
            "INTOUTHH ('/generation/outturn/interconnectors') is live-only in BMRS "
            "and ignores historical from and to parameters."
        )

    def get_nonbm_stor(self, start: date, end: date) -> pd.DataFrame:
        """Non-BM Short Term Operating Reserve volumes from /balancing/nonbm/stor.
        The endpoint and its parameters work, but every window I tried returned
        an empty list, including recent dates and a day in 2024. I have not found
        out whether STOR events are that rare or the query is wrong, so an empty
        frame means no rows came back, nothing more."""
        rows: list[dict] = []
        current = start
        while current <= end:
            url = f"{self.base_url}/balancing/nonbm/stor"
            data = get_json(url, params={
                "from": current.isoformat(),
                "to": current.isoformat(),
                "format": "json",
            }, max_retries=self.max_retries, backoff_seconds=self.backoff_seconds).get("data", [])
            rows.extend(data)
            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)
            current += timedelta(days=1)

        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    def get_forecast(self, dataset: str, *_args, **_kwargs):
        """Always raises for the live-only datasets (DATL, FOU2T14D,
        demand/outturn/stream, INTOUTHH). They ignore historical dates, so there
        is no way to recover past forecasts from BMRS."""
        if dataset in LIVE_ONLY_DATASETS:
            raise LiveOnlyEndpointError(
                f"{dataset!r} is live-only in BMRS, so no historical data is available."
            )
        raise NotImplementedError(f"get_forecast for {dataset!r} is not implemented yet")

    @staticmethod
    def _aggregate_to_settlement_period(rows: list[dict], d: date) -> list[dict]:
        if not rows:
            return []
        df = pd.DataFrame(rows)
        df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
        minutes = df["startTime"].dt.hour * 60 + df["startTime"].dt.minute
        df["settlementPeriod"] = (minutes // 30) + 1
        df["settlementDate"] = str(d)
        agg = (
            df.groupby(["settlementDate", "settlementPeriod"])["demand"]
            .mean()
            .round(0)
            .astype(int)
            .reset_index()
            .rename(columns={"demand": "demand_mw"})
        )
        return agg.to_dict("records")
