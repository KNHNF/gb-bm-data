# gb-bm-data

Python client for historical GB electricity data from three public APIs:

- Elexon BMRS: system prices and demand outturn (`BMRSClient`).
- Carbon Intensity API: generation mix as a percentage by fuel (`CarbonIntensityClient`).
- NESO Data Portal (CKAN Datastore): a generic query method, plus the historic
  day-ahead demand forecast (`NESODataPortalClient`).

It was extracted from data-ingestion code written for a GB balancing-mechanism
cost forecasting dissertation. Results are pandas DataFrames. Dates are inclusive.

Status: version 0.1.0, not published to PyPI. Not yet checked against the live
APIs in this review (see Limits).

## Install

From a clone of this repository (Python 3.10 or later; installs `requests` and `pandas`):

```bash
pip install -e .
```

## Example (runs offline, no API key)

The HTTP layer is replaced by a fake, so this needs no network:

```bash
python examples/offline_example.py
```

Expected output:

```text
  settlementDate  settlementPeriod  approx_cost_gbp
0     2026-01-01                 1           5800.0
LiveOnlyEndpointError: 'FOU2T14D' is live-only in the BMRS API, no historical data is available. Confirmed during GB BM dissertation data collection, Aug 2026.
```

Against the real APIs the same calls look like this (needs network):

```python
from datetime import date
from gb_bm_data import BMRSClient

client = BMRSClient()
prices = client.get_system_prices(date(2026, 1, 1), date(2026, 1, 7))
demand = client.get_demand_outturn(date(2026, 1, 1), date(2026, 1, 7))
```

## Live-only endpoints

`BMRSClient.get_forecast(name)` raises `LiveOnlyEndpointError` for three names,
`DATL`, `FOU2T14D` and `demand/outturn/stream`, instead of returning data. The
author reported during data collection (August 2026) that these ignore
historical date parameters. That observation is not re-tested here. Any other
name raises `NotImplementedError`. Exact locations and tests are in
[docs/LIVE-ONLY-ROUTES.md](docs/LIVE-ONLY-ROUTES.md).

## Modules

- `gb_bm_data.client.BMRSClient`: `get_system_prices` (adds an
  `approx_cost_gbp` column), `get_demand_outturn` (5-minute values from
  `/generation/outturn` averaged into 30-minute settlement periods),
  `get_forecast` (always raises).
- `gb_bm_data.carbon_intensity.CarbonIntensityClient.get_generation_mix`:
  wind, solar, gas, nuclear and imports percentages, fetched in 30-day chunks.
- `gb_bm_data.neso.NESODataPortalClient`: `query()` and
  `get_historic_day_ahead_demand_forecast()`.
- `gb_bm_data.exceptions`: `GBBMDataError` (base), `LiveOnlyEndpointError`,
  `RetryExhaustedError` (all retries failed), `RequestFailedError` (HTTP 4xx
  other than 429, not retried).

Behaviour that is easy to miss:

- A start date after the end date raises `ValueError`.
- Settlement dates and periods use Europe/London time. A BST day starts at
  23:00 UTC the previous evening, and clock-change days have 46 or 50 periods.
- Requests are retried on network errors, HTTP 5xx and 429, with linear backoff.
  `max_retries` and `backoff_seconds` are constructor arguments.
- Each client sleeps between calls (BMRS 0.5 s, Carbon Intensity 1 s, NESO 30 s).
  Pass `sleep_seconds=0` to disable, for example with mocks.

## Limits

- The test suite is mocked. No test calls a real API, so response field names
  and endpoint behaviour are as the code assumes, not as verified here.
- The base URL in `client.py` ends in `/bmrs/api/v1`. Earlier versions of this
  README called it v2. Check the current Elexon documentation before relying on it.
- `approx_cost_gbp` is `offer volume * system buy price + abs(bid volume) * system
  sell price`. It is an approximation, not a settlement cost.
- Missing fuels in the Carbon Intensity response are filled with 0.0, so a
  missing fuel and a true zero look the same.
- A response without the expected `data` or `result.records` key is treated as
  empty, not as an error.
- `BMRSClient.get_forecast` only protects the three names above. Other endpoints
  are not classed as historical or live-only.
- Calls are sequential, one request per day (BMRS) or per 30 days (Carbon
  Intensity). Long ranges are slow by design.
- The `SystemPriceRow` dataclass in `client.py` is not used by any method.

## Tests

```bash
python tests/test_client.py
```

No network and no API key needed. `pytest tests/` also works if pytest is installed.

## Licences and attribution

Data licences were read once, on 2026-08-15, by an AI session. That is not
legal advice and not a substitute for the maintainer's own read before release.

- Carbon intensity data: [Carbon Intensity API](https://carbonintensity.org.uk/),
  licensed under [CC BY 4.0](http://terms.carbonintensity.org.uk/).
- NESO demand forecast data: Supported by National Energy SO Open Data
  ([NESO Open Licence](https://www.neso.energy/data-portal/neso-open-licence)).
  Each NESO dataset is licensed individually.
- Elexon BMRS: no key is sent by this client. If Elexon starts requiring a key,
  never bundle one in this repository.

The package declares `license = MIT` in `pyproject.toml`. There is no `LICENSE`
file yet (see RESULT.md).
