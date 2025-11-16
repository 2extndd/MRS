"""
Exception classes for pyMercariAPI
"""


class MercariAPIError(Exception):
    """Base exception for Mercari API errors"""
    pass


class MercariConnectionError(MercariAPIError):
    """Raised when connection to Mercari fails"""
    pass


class MercariRateLimitError(MercariAPIError):
    """Raised when rate limit is exceeded"""
    pass


class MercariParseError(MercariAPIError):
    """Raised when parsing Mercari response fails"""
    pass


class MercariItemNotFoundError(MercariAPIError):
    """Raised when item is not found"""
    pass
