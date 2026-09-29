"""Wrapper for the NESO Data Portal's CKAN Datastore API (api.neso.energy).
Datasets are identified by resource_id, not a fixed URL per dataset like
client.py's BMRS endpoints, so this exposes a generic query() plus one
documented convenience method for the historic day-ahead demand forecast:
the historical demand *forecast* BMRS v2 cannot provide (see client.py's
LIVE_ONLY_DATASETS)."""
from __future__ import annotations

import json
import time
from datetime import date

import pandas as pd

from gb_bm_data._http import DEFAULT_BACKOFF_SECONDS, DEFAULT_MAX_RETRIES, get_json

BASE_URL = "https://api.neso.energy/api/3/action"

# NESO's published API guidance caps the Datastore API at 2 requests/minute.
DATASTORE_MIN_INTERVAL_SECONDS = 30.0

# "Historic Day Ahead Demand Forecasts" resource under the
# "1-day-ahead-demand-forecast" dataset: full archive, 2018 to present.
HISTORIC_DAY_AHEAD_DEMAND_FORECAST_RESOURCE_ID = "9847e7bb-986e-49be-8138-717b25933fbb"


class NESODataPortalClient:
    """Generic client for the NESO Data Portal's CKAN Datastore API. Find a
    resource_id via the "API" button on any neso.energy/data-portal dataset
    page, or via resource_search."""

    def __init__(self, base_url: str = BASE_URL,
                 sleep_seconds: float = DATASTORE_MIN_INTERVAL_SECONDS,
                 max_retries: int = DEFAULT_MAX_RETRIES,
                 backoff_seconds: float = DEFAULT_BACKOFF_SECONDS):
        self.base_url = base_url
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def query(self, resource_id: str, sql: str | None = None,
              filters: dict | None = None, limit: int = 32000) -> pd.DataFrame:
        """Runs datastore_search_sql if sql is given (needed for date-range
        WHERE clauses), else datastore_search with optional exact-match
        filters. Sleeps sleep_seconds after the call, honouring NESO's
        2-requests/minute Datastore API guidance if called repeatedly."""
        if sql is not None:
            data = get_json(f"{self.base_url}/datastore_search_sql", params={"sql": sql},
                             max_retries=self.max_retries, backoff_seconds=self.backoff_seconds)
        else:
            params: dict = {"resource_id": resource_id, "limit": limit}
            if filters is not None:
                params["filters"] = json.dumps(filters)
            data = get_json(f"{self.base_url}/datastore_search", params=params,
                             max_retries=self.max_retries, backoff_seconds=self.backoff_seconds)

        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)

        records = data.get("result", {}).get("records", [])
        return pd.DataFrame(records)

    def get_historic_day_ahead_demand_forecast(self, start: date, end: date,
                                                 days_ahead: int = 1) -> pd.DataFrame:
        """Historic day-ahead national demand forecast (TARGETDATE,
        FORECASTDEMAND MW, CARDINALPOINT, DAYSAHEAD), 2018 to present.
        days_ahead=1 selects the 1-day-ahead forecast."""
        sql = (
            f'SELECT * FROM "{HISTORIC_DAY_AHEAD_DEMAND_FORECAST_RESOURCE_ID}" '
            f"WHERE \"TARGETDATE\" >= '{start.isoformat()}' "
            f"AND \"TARGETDATE\" <= '{end.isoformat()}' "
            f"AND \"DAYSAHEAD\" = {days_ahead}"
        )
        df = self.query(HISTORIC_DAY_AHEAD_DEMAND_FORECAST_RESOURCE_ID, sql=sql)
        if df.empty:
            return df
        return df.sort_values(["TARGETDATE", "CP_ST_TIME"]).reset_index(drop=True)
