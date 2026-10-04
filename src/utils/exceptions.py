"""Business exception hierarchy.

Design notes:
    * Every *expected* failure derives from :class:`ApiError` and carries both an
      HTTP status code and a machine readable error code.
    * ``middleware/error_handler.py`` converts any :class:`ApiError` into the
      standard JSON error body, so controllers never build error responses by
      hand.
    * Unexpected exceptions (for example a broken database) become HTTP 500
      without leaking a stack trace to the client.
"""


class ApiError(Exception):
    """Base class for all business exceptions."""

    #: Default HTTP status code.
    status_code = 400
    #: Default machine readable error code, used by the front-end to branch.
    code = "BAD_REQUEST"

    def __init__(self, message: str, code: str = None, status_code: int = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self) -> dict:
        """Render the exception as the unified error body."""
        return {
            "success": False,
            "code": self.code,
            "message": self.message,
        }


class ValidationError(ApiError):
    """A request parameter is missing, of the wrong type, or out of range."""

    status_code = 400
    code = "VALIDATION_ERROR"


class InvalidExpressionError(ApiError):
    """The expression contains an illegal character or violates the grammar."""

    status_code = 400
    code = "INVALID_EXPRESSION"


class DivideByZeroError(ApiError):
    """A division (or a negative power of zero) has a zero divisor."""

    status_code = 400
    code = "DIVIDE_BY_ZERO"


class OverflowResultError(ApiError):
    """The result is not a finite number, or exceeds the configured limits."""

    status_code = 400
    code = "RESULT_OVERFLOW"


class NotFoundError(ApiError):
    """The requested resource does not exist, for example an unknown history id."""

    status_code = 404
    code = "NOT_FOUND"


class DatabaseError(ApiError):
    """A database read or write failed."""

    status_code = 500
    code = "DATABASE_ERROR"
