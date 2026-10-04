"""Unit tests for expression parsing and evaluation.

Run them with::

    python -m unittest discover -s tests -v

Only the standard library ``unittest`` module is required; pytest is not needed.
"""

import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.service import expression_parser                       # noqa: E402
from src.utils.exceptions import (                               # noqa: E402
    DivideByZeroError,
    InvalidExpressionError,
    OverflowResultError,
    ValidationError,
)


def calculate(expression: str) -> str:
    """Helper returning the formatted result of an expression."""
    value = expression_parser.evaluate_expression(expression)
    return expression_parser.format_decimal(value)


class TestBasicCalculation(unittest.TestCase):
    """The four basic operators."""

    def test_addition(self):
        self.assertEqual(calculate("12+8"), "20")

    def test_subtraction(self):
        self.assertEqual(calculate("12-8"), "4")

    def test_multiplication(self):
        self.assertEqual(calculate("6*7"), "42")

    def test_division(self):
        self.assertEqual(calculate("20/4"), "5")

    def test_division_with_remainder(self):
        self.assertEqual(calculate("7/2"), "3.5")

    def test_spaces_are_ignored(self):
        self.assertEqual(calculate("  12   +   8  "), "20")


class TestCompoundExpression(unittest.TestCase):
    """Compound expressions: precedence, parentheses and unary signs."""

    def test_operator_precedence(self):
        self.assertEqual(calculate("1+2*3"), "7")

    def test_parentheses(self):
        self.assertEqual(calculate("(1+2)*3"), "9")

    def test_division_then_addition(self):
        self.assertEqual(calculate("10/2+7"), "12")

    def test_subtraction_and_multiplication(self):
        self.assertEqual(calculate("8-3*2"), "2")

    def test_unary_minus_prefix(self):
        self.assertEqual(calculate("-5+8"), "3")

    def test_multiply_by_negative_number(self):
        self.assertEqual(calculate("3*-2"), "-6")

    def test_nested_parentheses(self):
        self.assertEqual(calculate("((2+3)*(4-1))/5"), "3")

    def test_double_negative(self):
        self.assertEqual(calculate("3--2"), "5")

    def test_unary_plus(self):
        self.assertEqual(calculate("+7-+2"), "5")

    def test_parenthesised_negative(self):
        self.assertEqual(calculate("2*(-3+5)"), "4")


class TestDecimalNumbers(unittest.TestCase):
    """Decimal input, without binary floating point error."""

    def test_decimal_addition_is_exact(self):
        # Binary floating point yields 0.30000000000000004; decimal yields 0.3.
        self.assertEqual(calculate("0.1+0.2"), "0.3")

    def test_decimal_multiplication(self):
        self.assertEqual(calculate("1.5*2"), "3")

    def test_leading_dot(self):
        self.assertEqual(calculate(".5+.5"), "1")

    def test_trailing_dot(self):
        self.assertEqual(calculate("2.+3."), "5")

    def test_repeating_decimal_is_rounded_for_display(self):
        # 1/3 = 0.333..., displayed with at most 10 decimal places.
        self.assertEqual(calculate("1/3"), "0.3333333333")

    def test_negative_zero_is_normalised(self):
        self.assertEqual(calculate("0-0"), "0")


class TestPowerOperator(unittest.TestCase):
    """Optional feature: the power operator ^ (right associative)."""

    def test_simple_power(self):
        self.assertEqual(calculate("2^10"), "1024")

    def test_power_is_right_associative(self):
        # 2^3^2 = 2^(3^2) = 2^9 = 512
        self.assertEqual(calculate("2^3^2"), "512")

    def test_power_binds_tighter_than_unary_minus(self):
        # -2^2 = -(2^2) = -4, matching mathematical convention.
        self.assertEqual(calculate("-2^2"), "-4")

    def test_negative_exponent(self):
        self.assertEqual(calculate("2^-3"), "0.125")

    def test_fractional_exponent(self):
        self.assertEqual(calculate("9^0.5"), "3")

    def test_zero_power_zero(self):
        self.assertEqual(calculate("0^0"), "1")


class TestInputNormalisation(unittest.TestCase):
    """Full width and CJK symbols are normalised automatically."""

    def test_full_width_operators(self):
        self.assertEqual(calculate("１２＋８"), "20")

    def test_chinese_multiplication_sign(self):
        self.assertEqual(calculate("6×7"), "42")

    def test_chinese_division_sign(self):
        self.assertEqual(calculate("20÷4"), "5")

    def test_full_width_parentheses(self):
        self.assertEqual(calculate("（1＋2）×3"), "9")


class TestErrorHandling(unittest.TestCase):
    """Illegal expressions and division by zero must be rejected."""

    def test_division_by_zero(self):
        with self.assertRaises(DivideByZeroError):
            calculate("1/0")

    def test_division_by_zero_inside_expression(self):
        with self.assertRaises(DivideByZeroError):
            calculate("(1+2)/(3-3)")

    def test_zero_to_negative_power(self):
        with self.assertRaises(DivideByZeroError):
            calculate("0^-1")

    def test_missing_operand(self):
        with self.assertRaises(InvalidExpressionError):
            calculate("1+")

    def test_unclosed_parenthesis(self):
        with self.assertRaises(InvalidExpressionError):
            calculate("(1+2")

    def test_extra_closing_parenthesis(self):
        with self.assertRaises(InvalidExpressionError):
            calculate("1+2)")

    def test_empty_parentheses(self):
        with self.assertRaises(InvalidExpressionError):
            calculate("()")

    def test_two_numbers_without_operator(self):
        with self.assertRaises(InvalidExpressionError):
            calculate("1 2")

    def test_illegal_character(self):
        with self.assertRaises(InvalidExpressionError):
            calculate("1+abc")

    def test_script_injection_is_rejected(self):
        # Because eval is never used, such input is simply an illegal character.
        with self.assertRaises(InvalidExpressionError):
            calculate("__import__('os').system('whoami')")

    def test_empty_expression(self):
        with self.assertRaises(ValidationError):
            calculate("")

    def test_blank_expression(self):
        with self.assertRaises(ValidationError):
            calculate("     ")

    def test_double_operator(self):
        with self.assertRaises(InvalidExpressionError):
            calculate("1+*2")

    def test_multiple_decimal_points(self):
        with self.assertRaises(InvalidExpressionError):
            calculate("1.2.3")

    def test_power_exponent_limit(self):
        with self.assertRaises(OverflowResultError):
            calculate("9^999999")

    def test_negative_base_fractional_power(self):
        with self.assertRaises(InvalidExpressionError):
            calculate("(-8)^0.5")


class TestParserInternals(unittest.TestCase):
    """Syntax tree shape, showing the parse-then-evaluate two step design."""

    def test_ast_shape_for_precedence(self):
        # In 1+2*3 the multiplication must sit deeper in the tree.
        node = expression_parser.parse_expression("1+2*3")
        self.assertEqual(node[0], expression_parser.NODE_BINARY)
        self.assertEqual(node[1], "+")
        self.assertEqual(node[2], (expression_parser.NODE_NUMBER, Decimal(1)))
        self.assertEqual(node[3][0], expression_parser.NODE_BINARY)
        self.assertEqual(node[3][1], "*")

    def test_ast_shape_for_unary(self):
        node = expression_parser.parse_expression("-5")
        self.assertEqual(node, (expression_parser.NODE_UNARY, "-",
                                (expression_parser.NODE_NUMBER, Decimal(5))))

    def test_tokenize_counts(self):
        tokens = expression_parser.tokenize("1+2*3")
        self.assertEqual([token.kind for token in tokens],
                         ["NUMBER", "OPERATOR", "NUMBER", "OPERATOR", "NUMBER"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
