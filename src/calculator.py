"""Public entry point of the calculation core.

The expression parser lives in :mod:`src.service.expression_parser` because the
back end is organised in layers. This module exposes the same functionality
from ``src/calculator.py`` so the calculation core has an obvious, stable
import path::

    from src.calculator import evaluate, calculate_expression, format_result

Nothing else in the application should import the parser module directly.
"""

from decimal import Decimal

from src.service import calculator as _calculator_service
from src.service import expression_parser as _parser

#: Re-exported so callers can catch evaluation problems without importing the
#: service package themselves.
from src.utils.exceptions import (  # noqa: F401  (re-exported on purpose)
    DivideByZeroError,
    InvalidExpressionError,
    OverflowResultError,
    ValidationError,
)

#: Syntax tree node kinds, useful when inspecting a parsed expression.
NODE_NUMBER = _parser.NODE_NUMBER
NODE_UNARY = _parser.NODE_UNARY
NODE_BINARY = _parser.NODE_BINARY


def normalize(expression: str) -> str:
    """Normalise full width and CJK symbols into ASCII."""
    return _parser.normalize_expression(expression)


def tokenize(expression: str):
    """Tokenize a normalised expression (exposed for tests and teaching)."""
    return _parser.tokenize(normalize(expression))


def parse(expression: str):
    """Parse an expression into a syntax tree without evaluating it."""
    return _parser.parse_expression(expression)


def evaluate(expression: str) -> Decimal:
    """Evaluate an expression and return the exact ``Decimal`` result.

    :raises InvalidExpressionError: the expression violates the grammar
    :raises DivideByZeroError:      the expression divides by zero
    :raises OverflowResultError:    the result is not representable
    """
    return _parser.evaluate_expression(expression)


def format_result(value: Decimal) -> str:
    """Format a ``Decimal`` for display, trimming noise from the output."""
    return _parser.format_decimal(value)


def to_json_number(value: Decimal) -> float:
    """Convert a ``Decimal`` into a JSON serialisable number."""
    return _parser.to_json_number(value)


def calculate_expression(expression: str) -> dict:
    """Evaluate an expression and store it in the calculation history.

    :return: the stored record, for example
        ``{"id": 3, "expression": "(1+2)*3", "result": 9.0,
           "resultText": "9", "createdAt": "2026-10-01 10:20:00"}``
    """
    return _calculator_service.CalculatorService.calculate(expression)


def preview_expression(expression: str) -> dict:
    """Evaluate an expression without storing it."""
    return _calculator_service.CalculatorService.preview(expression)


__all__ = [
    "NODE_BINARY",
    "NODE_NUMBER",
    "NODE_UNARY",
    "calculate_expression",
    "evaluate",
    "format_result",
    "normalize",
    "parse",
    "preview_expression",
    "to_json_number",
    "tokenize",
    "DivideByZeroError",
    "InvalidExpressionError",
    "OverflowResultError",
    "ValidationError",
]
