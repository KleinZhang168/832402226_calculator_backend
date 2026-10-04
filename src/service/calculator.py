"""Calculator business service.

Responsibilities (the back end owns validation, parsing, evaluation, error
handling and persistence):

    1. validate the ``expression`` parameter sent by the client;
    2. delegate parsing and evaluation to ``expression_parser``;
    3. format the result;
    4. store successful calculations in the database;
    5. hand the complete record back to the controller layer.
"""

import datetime
from typing import Optional

from src.config import Config
from src.model import history_model
from src.service import expression_parser
from src.utils.exceptions import ValidationError


def current_time_text() -> str:
    """Current local time formatted as ``YYYY-MM-DD HH:MM:SS``."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def validate_expression(raw) -> str:
    """Validate and normalise the expression submitted by the client.

    :raises ValidationError: when the value is missing, not a string, empty or too long
    """
    if raw is None:
        raise ValidationError("The request body must contain an 'expression' field")
    if not isinstance(raw, str):
        raise ValidationError("'expression' must be a string")
    text = raw.strip()
    if not text:
        raise ValidationError("The expression must not be empty")
    if len(text) > Config.MAX_EXPRESSION_LENGTH:
        raise ValidationError(
            "The expression must not be longer than %d characters"
            % Config.MAX_EXPRESSION_LENGTH
        )
    return text


class CalculatorService:
    """The core business entry point of the back end."""

    @staticmethod
    def calculate(raw_expression) -> dict:
        """Validate, evaluate, persist and return the stored record.

        :param raw_expression: the raw expression sent by the client
        :return: a record such as
            ``{"id": 1, "expression": "12+8", "result": 20.0,
               "resultText": "20", "createdAt": "2026-10-01 10:20:00"}``
        """
        expression = validate_expression(raw_expression)

        # The whole computation happens on the server.
        value = expression_parser.evaluate_expression(expression)
        result_text = expression_parser.format_decimal(value)
        result_number = expression_parser.to_json_number(value)

        # Only successful calculations enter the history.
        return history_model.insert(
            expression=expression,
            result=result_number,
            result_text=result_text,
            created_at=current_time_text(),
        )

    @staticmethod
    def preview(raw_expression) -> dict:
        """Evaluate without storing, used for the live preview in the UI.

        Even though nothing is stored, the evaluation still happens on the
        server, so the front-end cannot produce a result on its own.
        """
        expression = validate_expression(raw_expression)
        value = expression_parser.evaluate_expression(expression)
        return {
            "expression": expression,
            "result": expression_parser.to_json_number(value),
            "resultText": expression_parser.format_decimal(value),
        }


def parse_optional_int(value: Optional[str], default: int, minimum: int, maximum: int,
                       field_name: str) -> int:
    """Parse an optional integer query parameter into the allowed range."""
    if value is None or str(value).strip() == "":
        return default
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValidationError("%s must be an integer" % field_name) from exc
    if parsed < minimum or parsed > maximum:
        raise ValidationError(
            "%s must be between %d and %d" % (field_name, minimum, maximum)
        )
    return parsed
