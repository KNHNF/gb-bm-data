"""Typed client for the Elexon BMRS v2 API, historical GB balancing-mechanism
data only. Live-only endpoints (forecasts, streaming demand) raise
LiveOnlyEndpointError rather than silently returning wrong data, see
exceptions.py for the confirmed list."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from gb_bm_data._http import DEFAULT_BACKOFF_SECONDS, DEFAULT_MAX_RETRIES, get_json
from gb_bm_data.exceptions import LiveOnlyEndpointError

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"

LIVE_ONLY_DATASETS = {"DATL", "FOU2T14D", "demand/outturn/stream", "INTOUTHH"}


@dataclass
class SystemPriceRow:
    settlement_date: str
    settlement_period: int
    system_buy_price: float
    system_sell_price: float
    net_imbalance_volume: float
    total_accepted_offer_volume: float
    total_accepted_bid_volume: float
    approx_cost_gbp: float


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
        import time

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
        """FUELINST via /generation/outturn: 5-min system demand, aggregated
        to 30-min settlement periods by mean. Historical day-ahead demand
        forecasts are not available via BMRS v2; lagged actual demand is the
        standard substitute for a demand feature, document this in methodology
        if used that way."""
        import time

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
        """INTOUTHH via /generation/outturn/interconnectors. Deliberately
        raises. First implemented 2026-09-12 on the mistaken belief (a
        misread WebFetch test result) that this endpoint honours historical
        from/to parameters. Directly retested the same day with a clean
        single-day request (2017-03-01): the endpoint returned only the
        three most recent live days (confirmed against real system dates),
        completely ignoring the requested historical range, same failure
        mode as DATL, FOU2T14D and demand/outturn/stream. Fails loud instead
        of silently returning today's data mislabelled as a historical year,
        which is what the first version of this method did."""
        raise LiveOnlyEndpointError(
            "INTOUTHH ('/generation/outturn/interconnectors') is live-only in BMRS v2, "
            "ignores historical from/to parameters entirely. Confirmed by direct retest "
            "2026-09-12, after an earlier implementation of this method incorrectly "
            "treated it as historical based on a misread test result."
        )

    def get_nonbm_stor(self, start: date, end: date) -> pd.DataFrame:
        """NONBM dataset via /balancing/nonbm/stor: non-BM Short Term Operating
        Reserve volumes. Confirmed live 2026-09-12: the endpoint and its from/to
        parameters work and return the standard {metadata, data} shape, but the
        data array was empty for every window tried against real dates, both
        recent (Aug 2026) and a spot-check day in 2024. Whether that means STOR
        events are genuinely rare/sparse in this dataset or something about the
        query needs adjusting has not been confirmed; treat an empty frame from
        this method as "no rows returned", not as proof STOR never happened in
        that window."""
        import time

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
        """Deliberately raises. Confirmed during dissertation collection
        (Aug 2026) that DATL, FOU2T14D and the demand/outturn/stream
        endpoints ignore historical date parameters and only return
        live/recent data, there is no historical forecast recovery via
        BMRS v2. Do not silently fetch garbage, fail loud instead."""
        if dataset in LIVE_ONLY_DATASETS:
            raise LiveOnlyEndpointError(
                f"{dataset!r} is live-only in BMRS v2, no historical data is available. "
                "Confirmed during GB BM dissertation data collection, Aug 2026."
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
