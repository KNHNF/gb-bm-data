# Review result: gb-bm-data

Branch: `cloud/gbbm-data-check-2026-11-01`. Review and tidy only. Nothing published, tagged or made public.

## What I read

All of: `README.md`, `pyproject.toml`, `.gitignore`, `gb_bm_data/*.py` (6 files), `tests/test_client.py`.
Git history: 2 commits. Nothing else in the repo.

## Tests (real output)

Before changes (12 tests, plain-Python runner; pytest is not installed in the sandbox):

```text
$ python tests/test_client.py
all tests passed
```

After changes (23 tests; the runner now discovers every `test_*` function and prints the count):

```text
$ python tests/test_client.py
all 23 tests passed
```

Network: no test makes a network call, every one patches `get_json` or `requests.get`.
A direct probe from the sandbox to the Elexon host returned `http=000` (blocked). So nothing
here was checked against a live API. I also confirmed that 6 of the new tests fail against the
old source (live-only slash form, reversed range, BST periods for BMRS and Carbon Intensity,
SQL integer check, zero retries).

## Live-only routes

Code supports **3**: `DATL`, `FOU2T14D`, `demand/outturn/stream`, all in
`LIVE_ONLY_DATASETS` at `gb_bm_data/client.py:18`, enforced in one place
(`get_forecast`, `client.py:104`), error `LiveOnlyEndpointError`. 4 and 5 are not in the code.
Full table with tests: `docs/LIVE-ONLY-ROUTES.md`.

## What changed

Fixes, each with a test:

1. Settlement periods were computed from UTC. In BST every demand and generation-mix row was
   off by two periods and the date could be wrong near midnight; clock-change days were wrong too.
   Now Europe/London based (`gb_bm_data/_time.py`), and `get_demand_outturn` fetches the local
   settlement day window. This is a behaviour change for summer dates. Winter output is unchanged.
2. Live-only matching was exact string only. `"/demand/outturn/stream"` (the form the old README
   used) or `"datl"` fell through to `NotImplementedError`. Now normalised.
3. A start date after the end date silently returned an empty frame in all four range methods.
   Now `ValueError`.
4. HTTP 4xx (except 429) was retried with sleeps, then reported as "failed after N attempts".
   Now fails at once with the new `RequestFailedError`. `max_retries < 1` previously raised a
   misleading "failed after 0 attempts: None"; now `ValueError`.
5. `days_ahead` was interpolated into SQL unchecked. Now coerced with `int()`.
6. `GBBMDataError`, `RetryExhaustedError`, `RequestFailedError` are exported from the package.
   The README already named the first two as public.
7. Package-wide wording: "BMRS v2" removed from code docstrings and the `pyproject` description,
   because the base URL in the code ends `/v1`. Description no longer says "Typed" (no `py.typed`).

README rewritten (shorter): what it does, install, an offline runnable example
(`examples/offline_example.py`, output checked), live-only section, behaviour notes, a limits
section. Removed because the code does not show it and I could not check it: the ElexonDataPortal
star count and "no mature typed wrapper" claim, "verified live ... 57,918 rows", the claim of use
in two reproduction repos (relative links that cannot work on GitHub), the dated "Done as of"
log, and the "Karan should still do his own read" note (kept in neutral wording). The licence
position paragraphs were condensed, not re-verified.

## Not fixed, on purpose

- Missing `data` or `result.records` key is treated as empty. Raising would be better, but I
  cannot see real error payloads from here, so I documented it under Limits instead.
- `SystemPriceRow` dataclass is unused. Left in place (removing it is an API decision).
- `approx_cost_gbp` formula left as is, labelled approximate.

## Release readiness (not done, not published)

1. Add a `LICENSE` file. `pyproject.toml` says MIT, the repo has none.
2. Run the client once against the live APIs on the laptop and record that (field names,
   `demand` field in `/generation/outturn`, v1 vs v2 base URL, the three live-only claims).
3. Human read of the three data licences (the existing one was by an AI session).
4. Add the attribution strings somewhere users of the data will see them (README has them; consider a returned-frame note).
5. Clean-venv install test: `pip install -e .`, `pip check`, run tests. Not done here.
6. CI (a single workflow running the tests) and `pytest` as an optional dev dependency.
7. Decide public API: `SystemPriceRow`, `get_forecast` always raising, error payload handling.
8. Add a CHANGELOG; `py.typed` marker if "typed" is to be claimed; version bump if the BST change matters to anyone.
9. Check commit history and files for private content before changing visibility (I saw none in tracked files).
10. Repo visibility: the brief says public. I did not check or change it.

## Could not check

- Any live API behaviour, including whether the three routes are truly live-only.
- Whether `/bmrs/api/v1` or `/v2` is current, and whether the endpoint paths and field names are right.
- A clean-venv install (I ran `pip install -e .` in the sandbox Python only; no `pip check`).
- pytest compatibility (not installed). The tests are plain functions and should work.
- The BST fix against real data. It is verified only with synthetic rows.

## Unverified claims still in the repo

- Live-only behaviour (author's observation, August 2026).
- NESO resource id `9847e7bb-...` and column names (`TARGETDATE`, `CP_ST_TIME`) are from the original code and tests only.
- Licence summaries in README.
- The `/generation/outturn` response having a `demand` field (the README says FUELINST; the code does not show it).

## Needs the laptop

Live smoke run of all three clients; confirm base URL and live-only claims; decide on the
licence file and visibility; clean-venv install and `pip check`; read the diff, in particular
the BST change, before merging.
