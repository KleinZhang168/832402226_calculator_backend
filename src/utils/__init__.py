"""Shared utilities: business exceptions and unified response bodies.

Layering note
-------------
The two modules in this package have very different dependencies:

* :mod:`src.utils.exceptions` is **pure Python** and only uses the standard
  library, so any layer may import it, including the expression parser;
* :mod:`src.utils.responses` depends on Flask's ``jsonify`` and therefore
  belongs to the web layer; only controllers and middleware need it.

Only the exceptions are re-exported here on purpose. Importing the responses
module as well would pull Flask into every import of this package and stop the
pure algorithm module from being tested in an environment without Flask.

Modules that need response helpers import them explicitly::

    from src.utils.responses import success_response, error_response
"""

from .exceptions import (
    ApiError,
    DatabaseError,
    DivideByZeroError,
    InvalidExpressionError,
    NotFoundError,
    OverflowResultError,
    ValidationError,
)

__all__ = [
    "ApiError",
    "DatabaseError",
    "DivideByZeroError",
    "InvalidExpressionError",
    "NotFoundError",
    "OverflowResultError",
    "ValidationError",
]
