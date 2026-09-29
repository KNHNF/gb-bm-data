# gb-bm-data

Python client for historical GB balancing-mechanism data. It wraps the current Elexon BMRS (Insights) API (system prices, demand outturn), the Carbon Intensity API (generation mix) and the NESO Data Portal (historic day-ahead demand forecast). For the BMRS endpoints that only serve live data it raises an error instead of quietly returning the wrong dates.

It was pulled out of the data-ingestion code for my GB balancing cost forecasting dissertation so it can be reused without the rest of that repo.

**Four BMRS endpoints are live-only and ignore date parameters:** `DATL`, `FOU2T14D`, `/demand/outturn/stream` and `INTOUTHH` (interconnector flows). There is no historical forecast recovery through BMRS for these. Calling them raises `LiveOnlyEndpointError`. The NESO client below covers the demand forecast gap.

## Why it exists

I checked on 15 August 2026 and found no maintained typed wrapper for BMRS. The nearest project, [ElexonDataPortal](https://github.com/OSUKED/ElexonDataPortal) (62 stars then), targets the older key-gated legacy API (`api.bmreports.com`), not the current one (`data.elexon.co.uk/bmrs/api/v1`) used here, and does not cover NESO or Carbon Intensity.

## Install

```bash
pip install git+https://github.com/KNHNF/gb-bm-data
```

or from a clone, `pip install -e .`. Python 3.10 or later, needs `requests` and `pandas`. No API key is needed for any of the three sources.

## Use

```python
from datetime import date
from gb_bm_data import BMRSClient

client = BMRSClient()
prices = client.get_system_prices(date(2026, 1, 1), date(2026, 1, 7))
demand = client.get_demand_outturn(date(2026, 1, 1), date(2026, 1, 7))

client.get_forecast("FOU2T14D")  # raises LiveOnlyEndpointError
```

## What is in it

- `BMRSClient.get_system_prices`: DISEBSP system prices with an `approx_cost_gbp` column I compute from them.
- `BMRSClient.get_demand_outturn`: FUELINST via `/generation/outturn`, aggregated from 5-minute data to 30-minute settlement periods.
- `BMRSClient.get_nonbm_stor`: non-BM Short Term Operating Reserve volumes. **It returned an empty frame for every window I tried**, recent and 2024. I have not confirmed whether STOR events are that rare or the query needs changing, so treat an empty frame as "no rows returned", not proof nothing happened.
- `CarbonIntensityClient.get_generation_mix`: wind, solar, gas and nuclear percentages. BMRS has no generation-mix endpoint of its own.
- `NESODataPortalClient`: a generic `query()` over the NESO CKAN Datastore API, plus `get_historic_day_ahead_demand_forecast()` for the 2018 to present archive. Checked live on 15 August 2026 against the resource `9847e7bb-986e-49be-8138-717b25933fbb` (57,918 rows). NESO caps the API at 2 requests a minute.
- `max_retries` and `backoff_seconds` are constructor arguments on the clients.
- Exceptions: `LiveOnlyEndpointError`, `RetryExhaustedError`.

## Test

```bash
python tests/test_client.py
```

The tests mock the HTTP layer, so they need no network and no key. They check parsing, empty ranges, de-duplication of overlapping monthly chunks, settlement period numbering (winter, summer and both clock-change days), that client errors are not retried, and the live-only errors. Passing them does not prove the live APIs still behave the same, that needs a manual run.

## Settlement periods

`get_system_prices`, `get_demand_outturn` and `get_generation_mix` all return the official `settlementDate` and `settlementPeriod`, so they join directly. A settlement day starts at local midnight, so period 1 begins at 23:00 UTC the day before during British Summer Time, and clock-change days have 46 or 50 periods. I checked this against the live API on 1 July 2026 (48 periods) and 29 March 2026 (46 periods): the keys from all three methods matched exactly.

Version 0.1.0 numbered demand and generation-mix periods from 00:00 UTC instead, which is two periods behind in summer and puts some rows on the wrong date. Pass `utc_index=True` to `get_demand_outturn` or `get_generation_mix` to get that older numbering back, for example to reproduce a dataset built with 0.1.0.

## Known limits

- The clients return pandas DataFrames with the columns the APIs use. The type hints cover the method signatures, not the columns.
- Tests use mocked HTTP only. The settlement period behaviour has unit tests, including the clock-change days.

## Licences and attribution

Read on 15 August 2026. This is my reading of the terms, not legal advice.

- **Carbon Intensity API:** [CC BY 4.0](http://terms.carbonintensity.org.uk/). A thin client library is allowed. The terms bar building something that substantially replaces NESO's own site or app.
- **NESO Data Portal:** [NESO Open Licence](https://www.neso.energy/data-portal/neso-open-licence), permits commercial use, needs the attribution below. Licensed per dataset, and I only checked the demand forecast dataset.
- **Elexon BMRS:** I found no clause against publishing an open-source client. The registered-key terms describe the older legacy tier. This package uses the current API, which needs no key, so there is no key to bundle. If Elexon adds a key requirement, each user should register their own.

Attribution: carbon intensity data from the [Carbon Intensity API](https://carbonintensity.org.uk/), CC BY 4.0. Demand forecast data: Supported by National Energy SO Open Data.

The code is MIT licensed, see `LICENSE`.

## Status

Version 0.2.0. GitHub only for now, revisit PyPI once the API surface stops changing. Used as the data layer for the reproductions in [gb-energy-forecasting-reproductions](https://github.com/KNHNF/gb-energy-forecasting-reproductions).
