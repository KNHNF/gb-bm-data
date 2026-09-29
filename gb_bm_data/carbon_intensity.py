"""Wrapper for the (unrelated-org, public, no-auth) Carbon Intensity API,
used here for historical GB generation mix (wind/solar/gas/nuclear %) since
BMRS does not expose an LOLP or wind-mix endpoint directly."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import pandas as pd

from gb_bm_data._http import DEFAULT_BACKOFF_SECONDS, DEFAULT_MAX_RETRIES, get_json

BASE_URL = "https://api.carbonintensity.org.uk/generation"
CHUNK_DAYS = 30


class CarbonIntensityClient:
    def __init__(self, base_url: str = BASE_URL, sleep_seconds: float = 1.0,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 backoff_seconds: float = DEFAULT_BACKOFF_SECONDS):
        self.base_url = base_url
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def get_generation_mix(self, start: date, end: date) -> pd.DataFrame:
        """Fuel-type generation as % of mix per half-hour, chunked 30 days per
        call. settlementPeriod is a UTC half-hour index, not the official
        settlement period, so it is two periods behind during British Summer Time."""
        rows: list[dict] = []
        current = start
        while current <= end:
            chunk_end = min(current + timedelta(days=CHUNK_DAYS - 1), end)
            url = f"{self.base_url}/{current.isoformat()}T00:00Z/{chunk_end.isoformat()}T23:30Z"
            data = get_json(url, headers={"Accept": "application/json"}, max_retries=self.max_retries,
                             backoff_seconds=self.backoff_seconds).get("data", [])
            rows.extend(r for r in (self._parse_row(row) for row in data) if r is not None)
            if self.sleep_seconds:
                time.sleep(self.sleep_seconds)
            current += timedelta(days=CHUNK_DAYS)

        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df = df.drop_duplicates(subset=["settlementDate", "settlementPeriod"])
        return df.sort_values(["settlementDate", "settlementPeriod"]).reset_index(drop=True)

    @staticmethod
    def _parse_row(row: dict) -> dict | None:
        from_str = row.get("from", "")
        if not from_str:
            return None
        dt = datetime.fromisoformat(from_str.replace("Z", "+00:00"))
        minutes = dt.hour * 60 + dt.minute
        sp = (minutes // 30) + 1
        mix = {item["fuel"]: item["perc"] for item in row.get("generationmix", [])}
        return {
            "settlementDate": str(dt.date()),
            "settlementPeriod": sp,
            "wind_pct": mix.get("wind", 0.0),
            "solar_pct": mix.get("solar", 0.0),
            "gas_pct": mix.get("gas", 0.0),
            "nuclear_pct": mix.get("nuclear", 0.0),
            "imports_pct": mix.get("imports", 0.0),
        }
