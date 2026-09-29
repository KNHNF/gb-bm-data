class GBBMDataError(Exception):
    """Base exception for this package."""


class LiveOnlyEndpointError(GBBMDataError):
    """Raised when historical data is requested from a BMRS endpoint that
    ignores date parameters and only returns recent data: DATL, FOU2T14D,
    /demand/outturn/stream and the interconnector outturn endpoint."""


class RetryExhaustedError(GBBMDataError):
    """Raised when all retry attempts for a request have failed."""
