# gb-bm-data

Typed Python client for historical GB balancing-mechanism data. It wraps the Elexon BMRS v2 API (system prices, demand outturn), the Carbon Intensity API (generation mix) and the NESO Data Portal (historic day-ahead demand forecast). For the BMRS endpoints that only serve live data it raises an error instead of quietly returning the wrong dates.

It was pulled out of the data-ingestion code for my GB balancing cost forecasting dissertation so it can be reused without the rest of that repo.

**Four BMRS v2 endpoints are live-only and ignore date parameters:** `DATL`, `FOU2T14D`, `/demand/outturn/stream` and `INTOUTHH` (interconnector flows). There is no historical forecast recovery through BMRS v2 for these. Calling them raises `LiveOnlyEndpointError`. The NESO client below covers the demand forecast gap.

## Why it exists

I checked on 15 August 2026 and found no maintained typed wrapper for BMRS v2. The nearest project, [ElexonDataPortal](https://github.com/OSUKED/ElexonDataPortal) (62 stars then), targets the older key-gated v1 tier (`api.bmreports.com`), not the public v2 REST API (`data.elexon.co.uk/bmrs/api/v2`) used here, and does not cover NESO or Carbon Intensity.

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
- `CarbonIntensityClient.get_generation_mix`: wind, solar, gas and nuclear percentages. BMRS v2 has no generation-mix endpoint of its own.
- `NESODataPortalClient`: a generic `query()` over the NESO CKAN Datastore API, plus `get_historic_day_ahead_demand_forecast()` for the 2018 to present archive. Checked live on 15 August 2026 against the resource `9847e7bb-986e-49be-8138-717b25933fbb` (57,918 rows). NESO caps the API at 2 requests a minute.
- `max_retries` and `backoff_seconds` are constructor arguments on the clients.
- Exceptions: `LiveOnlyEndpointError`, `RetryExhaustedError`.

## Test

```bash
python tests/test_client.py
```

The tests mock the HTTP layer, so they need no network and no key. They check parsing, empty ranges, de-duplication of overlapping monthly chunks and the live-only errors. Passing them does not prove the live APIs still behave the same, that needs a manual run.

## Licences and attribution

Read on 15 August 2026. This is my reading of the terms, not legal advice.

- **Carbon Intensity API:** [CC BY 4.0](http://terms.carbonintensity.org.uk/). A thin client library is allowed. The terms bar building something that substantially replaces NESO's own site or app.
- **NESO Data Portal:** [NESO Open Licence](https://www.neso.energy/data-portal/neso-open-licence), permits commercial use, needs the attribution below. Licensed per dataset, and I only checked the demand forecast dataset.
- **Elexon BMRS:** I found no clause against publishing an open-source client. The registered-key terms describe the older v1 tier. This package uses the v2 API that needs no key, so there is no key to bundle. If Elexon adds a key requirement to v2, each user should register their own.

Attribution: carbon intensity data from the [Carbon Intensity API](https://carbonintensity.org.uk/), CC BY 4.0. Demand forecast data: Supported by National Energy SO Open Data.

The code is MIT licensed, see `LICENSE`.

## Status

Version 0.1.0. GitHub only for now, revisit PyPI once the API surface stops changing. Used as the data layer for the reproductions in [gb-energy-forecasting-reproductions](https://github.com/KNHNF/gb-energy-forecasting-reproductions).
