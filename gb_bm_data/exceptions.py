class GBBMDataError(Exception):
    """Base exception for this package."""


class LiveOnlyEndpointError(GBBMDataError):
    """Raised when a date range is requested from a BMRS endpoint that
    ignores historical date parameters and only ever returns recent/live
    data. Confirmed live-only during dissertation data collection (Aug 2026):
    DATL, FOU2T14D forecast endpoints, and /demand/outturn/stream."""


class RetryExhaustedError(GBBMDataError):
    """Raised when all retry attempts for a request have failed."""


class RequestFailedError(GBBMDataError):
    """Raised when the server rejects a request with a client error (HTTP 4xx
    other than 429). These are not retried because repeating the same request
    cannot succeed."""
