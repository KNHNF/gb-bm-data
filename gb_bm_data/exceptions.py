class GBBMDataError(Exception):
    """Base exception for this package."""


class LiveOnlyEndpointError(GBBMDataError):
    """Raised when a date range is requested from a BMRS v2 endpoint that
    ignores historical date parameters and only ever returns recent/live
    data. Confirmed live-only during dissertation data collection (Aug 2026):
    DATL, FOU2T14D forecast endpoints, and /demand/outturn/stream."""


class RetryExhaustedError(GBBMDataError):
    """Raised when all retry attempts for a request have failed."""
