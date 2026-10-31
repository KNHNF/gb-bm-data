# Live-only routes, as shown by the code

Source of truth: the code on this branch. Nothing here is inferred from notes,
the README history or memory. Whether these routes really are live-only on the
Elexon side was not tested (the sandbox blocks Elexon), only what the client does.

## Count the code supports: 3

`LIVE_ONLY_DATASETS` in `gb_bm_data/client.py:18` holds exactly three names.
There is one enforcement point: `BMRSClient.get_forecast`
(`gb_bm_data/client.py:104`, check at line 110, raise at line 111).

| # | Name | Defined | Error raised | Test |
|---|------|---------|--------------|------|
| 1 | `DATL` | `client.py:18` | `LiveOnlyEndpointError` (`exceptions.py:5`) | `test_every_live_only_dataset_raises`, `test_live_only_match_ignores_case_and_slashes` |
| 2 | `FOU2T14D` | `client.py:18` | `LiveOnlyEndpointError` | `test_live_only_endpoint_raises` (original), `test_every_live_only_dataset_raises`, `test_live_only_match_ignores_case_and_slashes` |
| 3 | `demand/outturn/stream` | `client.py:18` | `LiveOnlyEndpointError` | `test_every_live_only_dataset_raises`, `test_live_only_match_ignores_case_and_slashes` (leading and trailing slash forms) |

All tests are in `tests/test_client.py`. Before this review only `FOU2T14D`
had a test. `DATL` and `demand/outturn/stream` were untested.

## What "live-only" means in the code

- `get_forecast(dataset, *args, **kwargs)` takes no dates. It ignores all extra
  arguments and raises for the three names. It never makes an HTTP call. So the
  client does not "return wrong dates" for these routes at all: it refuses.
- Matching is now case-insensitive and ignores surrounding spaces and slashes
  (`"/demand/outturn/stream"`, `"datl"`). Before this review it was an exact
  string match, so the slash form that the old README used would have fallen
  through to `NotImplementedError`. Fixed, with a test.
- Any other name raises `NotImplementedError` (`client.py:115`), which is not a
  `LiveOnlyEndpointError`. Test: `test_unknown_forecast_dataset_is_not_live_only`.

## Not live-only in the code

- `get_system_prices` and `get_demand_outturn` take dates and call the API.
  `get_demand_outturn` uses `/generation/outturn`, not
  `demand/outturn/stream`.
- `NESODataPortalClient.get_historic_day_ahead_demand_forecast` is a historic
  route (`neso.py`). `neso.py:6` refers to `LIVE_ONLY_DATASETS` in a docstring only.
- Counts of 4 or 5 live-only routes: not in the code.

## Where the three names are also written down (documentation, not enforcement)

- `gb_bm_data/exceptions.py`, docstring of `LiveOnlyEndpointError`
- `gb_bm_data/client.py`, module docstring and `get_forecast` docstring
- `README.md`, "Live-only endpoints"
