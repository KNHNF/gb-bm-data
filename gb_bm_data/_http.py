"""Shared retry/backoff wrapper. Internal module, not part of the public API."""
from __future__ import annotations

import time

import requests

from gb_bm_data.exceptions import RetryExhaustedError

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 1.0


def get_json(url: str, params: dict | None = None, headers: dict | None = None,
             timeout: int = 30, max_retries: int = DEFAULT_MAX_RETRIES,
             backoff_seconds: float = DEFAULT_BACKOFF_SECONDS) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and 400 <= status < 500 and status != 429:
                raise RetryExhaustedError(f"GET {url} failed with HTTP {status}, not retried") from e
            last_error = e
            if attempt < max_retries:
                time.sleep(backoff_seconds * attempt)
        except requests.RequestException as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(backoff_seconds * attempt)
    raise RetryExhaustedError(f"GET {url} failed after {max_retries} attempts: {last_error}")
