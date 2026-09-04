# gb-bm-data

Typed Python client for historical GB balancing-mechanism data: the Elexon
BMRS v2 API (system prices, demand outturn) and the Carbon Intensity API
(generation mix). Extracted from data-ingestion code originally written for
a GB BM cost forecasting dissertation (2026), packaged standalone so it is
reusable without the rest of that repo.

## Why this exists

BMRS v2 has no mature typed wrapper yet. Checked 2026-08-15: the only real
prior art, [ElexonDataPortal](https://github.com/OSUKED/ElexonDataPortal)
(62 stars), targets the legacy key-gated v1 tier (`api.bmreports.com`,
stream codes like `B1610`), not the public v2 REST API
(`data.elexon.co.uk/bmrs/api/v2`) this package wraps, and doesn't touch
NESO or Carbon Intensity at all. This package also documents, as code (not
just a paragraph in a methodology section), which BMRS v2 endpoints are
historical and which are live-only:

```python
from datetime import date
from gb_bm_data import BMRSClient

client = BMRSClient()
prices = client.get_system_prices(date(2026, 1, 1), date(2026, 1, 7))
demand = client.get_demand_outturn(date(2026, 1, 1), date(2026, 1, 7))

client.get_forecast("FOU2T14D")  # raises LiveOnlyEndpointError, not silently wrong data
```

## Install

```bash
pip install -e .
```

## What's confirmed live-only (raises `LiveOnlyEndpointError`)

Confirmed during real dissertation data collection, August 2026: `DATL`,
`FOU2T14D` forecast datasets, and `/demand/outturn/stream` all ignore
historical date parameters and only return recent/live data. There is no
historical forecast recovery through BMRS v2 for these. Use lagged actual
values as a documented substitute feature instead of pretending a forecast
exists.

## Modules

- `gb_bm_data.client.BMRSClient`: system prices (DISEBSP, includes an
  `approx_cost_gbp` computed column), demand outturn (FUELINST via
  `/generation/outturn`, aggregated 5-min to 30-min settlement periods).
- `gb_bm_data.carbon_intensity.CarbonIntensityClient`: generation mix
  (wind/solar/gas/nuclear %) from the separate, unrelated, no-auth Carbon
  Intensity API. BMRS v2 has no LOLP or wind-mix endpoint of its own.
- `gb_bm_data.neso.NESODataPortalClient`: generic query() over the NESO
  Data Portal's CKAN Datastore API (api.neso.energy), plus a convenience
  method `get_historic_day_ahead_demand_forecast()` covering 2018 to
  present. This is the historical demand *forecast* BMRS v2 cannot provide
  (see `LIVE_ONLY_DATASETS` in `client.py`); the dissertation had to fall
  back to lagged actual demand for that reason, this endpoint removes that
  limitation for future use.
- `gb_bm_data.exceptions`: `LiveOnlyEndpointError`, `RetryExhaustedError`.

## Test

```bash
python tests/test_client.py
```

All tests mock the HTTP layer, no real network calls, no API key needed to
run the test suite.

## Status

Skeleton extracted 2026-08-14 from `gb-bm-forecasting/src/01-03`. Release
plan (decided 2026-08-15): GitHub-only for now, `pip install
git+https://github.com/KNHNF/gb-bm-data`; revisit PyPI once the API
surface settles.

## GitHub release checklist

This package is not published until Karan approves the release.

1. Run `python tests/test_client.py` from a clean virtual environment.
2. Confirm `pip install -e .` and `pip check` succeed.
3. Review the public README and licence attribution below.
4. Create the GitHub remote, push the reviewed commit, then install with:

```bash
pip install git+https://github.com/KNHNF/gb-bm-data
```

Used since as the data layer for two independent paper reproductions:
[lucas-2020-reproduction](../lucas-2020-reproduction) and a Bunn/Ganesh &
Bunn/Deng reproduction set, both under `public-projects`.

Done as of 2026-08-14:
- Generation-mix tests added (`tests/test_client.py`): fuel-percentage
  parsing, empty-range handling, dedup of overlapping monthly chunks.
- `max_retries` and `backoff_seconds` exposed as constructor arguments on
  both `BMRSClient` and `CarbonIntensityClient`, threaded through to the
  shared `_http.get_json` retry wrapper (previously only configurable by
  editing `_http.py`'s module-level defaults).

Done as of 2026-08-15:
- `gb_bm_data.neso.NESODataPortalClient` added: generic `query()` over
  the CKAN Datastore API plus `get_historic_day_ahead_demand_forecast()`,
  verified live against `api.neso.energy` (resource
  `9847e7bb-986e-49be-8138-717b25933fbb`, 57,918 rows, 2018 to present).
  Four new mocked tests in `tests/test_client.py`.
- Licence/ToS read for all three APIs (see "Licence position" below).
  Read directly by this session, not a substitute for the human sign-off
  a public release still needs, see caveat below.

## Licence position (read 2026-08-15, not a substitute for your own read before release)

- **Carbon Intensity API**: [CC BY 4.0](http://terms.carbonintensity.org.uk/).
  Commercial and non-commercial use allowed. Cannot sell/lease/sublicense
  the API itself, and cannot build something that "substantially replaces
  the core user experience" of NESO's own site/app/API, a thin typed
  client library is neither. Prior art exists (e.g. a .NET wrapper for the
  same API is already public on GitHub), so this pattern is established.
  Attribution recommended per CC BY 4.0, not yet added to this repo.
- **NESO Data Portal**: [NESO Open Licence](https://www.neso.energy/data-portal/neso-open-licence),
  OGL-compatible, worldwide/royalty-free/perpetual, explicitly permits
  commercial use and inclusion in your own product. Requires the
  attribution string `"Supported by National Energy SO Open Data"`, not
  yet added to this repo. Each dataset is licensed individually, this
  applies to the demand-forecast dataset checked, not verified per-dataset
  for future additions.
- **Elexon BMRS API**: no clause found that prohibits building or publicly
  distributing an open-source client library. The important constraint is
  different: the licence terms on elexon.co.uk describe a registered
  account and API key from elexonportal.co.uk, "revocable, non-transferable,
  non-sublicensable". Confirmed 2026-08-15 (see ElexonDataPortal comparison
  above) that this applies to the legacy `api.bmreports.com` tier: this
  package instead calls `data.elexon.co.uk/bmrs/api/v2`, the newer public
  Developer API, which requires no key at all, so there is no key to
  accidentally bundle. If Elexon ever gates v2 behind a key, treat the same
  rule as would apply to the legacy tier: never bundle one, document that
  each user registers their own.

None of the above is legal advice, and this was read by an AI session, not
a solicitor. Karan should still do his own read before a public PyPI
release, this section exists to make that read faster, not replace it.

## Attribution

Required by the licences above, both credited here rather than only in
code comments:

- Carbon intensity data: [Carbon Intensity API](https://carbonintensity.org.uk/),
  licensed under [CC BY 4.0](http://terms.carbonintensity.org.uk/).
- Demand forecast data: Supported by National Energy SO Open Data.
