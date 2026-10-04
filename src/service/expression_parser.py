"""Safe mathematical expression parsing and evaluation.

This module holds the core algorithm of the calculator. It **never** uses
``eval`` or ``exec``; instead it implements the classic three step pipeline:
lexical analysis, recursive descent parsing, and evaluation of the syntax tree.

--------------------------------------------------------------------------
Grammar (EBNF)
--------------------------------------------------------------------------
::

    expression -> term (("+" | "-") term)*
    term       -> unary (("*" | "/") unary)*
    unary      -> ("+" | "-") unary | power
    power      -> primary ("^" unary)?
    primary    -> NUMBER | "(" expression ")"

* Operator precedence follows from the layering of the grammar:
  ``+ -``  <  ``* /``  <  unary ``+ -``  <  ``^``  <  ``( )``.
* ``^`` is right associative and its right hand side is a ``unary``, so
  ``2^3^2`` means ``2^(3^2)`` = 512 and ``2^-3`` = 0.125.
* Unary minus binds looser than ``^``, so ``-2^2`` means ``-(2^2)`` = -4,
  which matches mathematical convention.

--------------------------------------------------------------------------
Syntax tree representation
--------------------------------------------------------------------------
::

    ("number", Decimal)                 # literal
    ("unary",  op, operand)             # op in {"+", "-"}
    ("binary", op, left, right)         # op in {"+", "-", "*", "/", "^"}

--------------------------------------------------------------------------
Numeric precision
--------------------------------------------------------------------------
Arithmetic uses :mod:`decimal` instead of binary floating point, which removes
representation error:

    >>> 0.1 + 0.2                          # binary float: 0.30000000000000004
    >>> Decimal("0.1") + Decimal("0.2")    # decimal: 0.3
"""

import re
from collections import namedtuple
from decimal import (
    Decimal,
    DecimalException,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    ROUND_HALF_UP,
    localcontext,
)

from src.config import Config
from src.utils.exceptions import (
    DivideByZeroError,
    InvalidExpressionError,
    OverflowResultError,
    ValidationError,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

#: Syntax tree node kinds.
NODE_NUMBER = "number"
NODE_UNARY = "unary"
NODE_BINARY = "binary"

#: Token kinds.
TOKEN_NUMBER = "NUMBER"
TOKEN_OPERATOR = "OPERATOR"
TOKEN_LPAREN = "LPAREN"
TOKEN_RPAREN = "RPAREN"

#: Supported binary and unary operators.
BINARY_OPERATORS = ("+", "-", "*", "/", "^")
ADDITIVE_OPERATORS = ("+", "-")
MULTIPLICATIVE_OPERATORS = ("*", "/")
SIGN_OPERATORS = ("+", "-")

#: Largest number of digits allowed in a single literal.
MAX_NUMBER_DIGITS = 30

#: A lexical token: kind, literal text, and its offset in the input.
Token = namedtuple("Token", "kind value position")

#: Number literal: ``12`` / ``12.5`` / ``12.`` / ``.5``
_NUMBER_PATTERN = re.compile(r"\d+\.?\d*|\.\d+")

#: Full width or CJK input symbols mapped to their ASCII equivalents, so typing
#: with a Chinese IME still produces a valid expression.
_NORMALIZE_TABLE = str.maketrans({
    "（": "(", "）": ")",
    "［": "(", "］": ")",
    "【": "(", "】": ")",
    "＋": "+", "－": "-", "−": "-", "—": "-", "–": "-", "ー": "-",
    "×": "*", "✕": "*", "✖": "*", "＊": "*", "·": "*", "⋅": "*",
    "÷": "/", "／": "/",
    "＾": "^", "︿": "^",
    "．": ".", "。": ".",
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
    "　": " ",
})


# --------------------------------------------------------------------------- #
# Step 1: normalisation
# --------------------------------------------------------------------------- #

def normalize_expression(raw: str) -> str:
    """Translate full width and CJK symbols into plain ASCII."""
    return raw.translate(_NORMALIZE_TABLE)


# --------------------------------------------------------------------------- #
# Step 2: lexical analysis
# --------------------------------------------------------------------------- #

def tokenize(text: str):
    """Split a normalised expression into a list of tokens.

    :raises InvalidExpressionError: on an unsupported character or too many tokens
    """
    tokens = []
    index = 0
    length = len(text)

    while index < length:
        char = text[index]

        # Whitespace is not significant.
        if char == " ":
            index += 1
            continue

        # Operators.
        if char in "+-*/^":
            tokens.append(Token(TOKEN_OPERATOR, char, index))
            index += 1
            continue

        # Parentheses.
        if char == "(":
            tokens.append(Token(TOKEN_LPAREN, char, index))
            index += 1
            continue
        if char == ")":
            tokens.append(Token(TOKEN_RPAREN, char, index))
            index += 1
            continue

        # Numbers.
        if char in "0123456789.":
            match = _NUMBER_PATTERN.match(text, index)
            if match is None:
                raise InvalidExpressionError(
                    "The decimal point at position %d is misplaced" % (index + 1)
                )
            literal = match.group(0)
            if literal.endswith("."):
                literal = literal[:-1]
            tokens.append(Token(TOKEN_NUMBER, literal, index))
            index = match.end()
            continue

        # Anything else is rejected: no percent sign, letters or function calls.
        raise InvalidExpressionError(
            "Unsupported character '%s' at position %d; only digits, "
            "+ - * / ^, the decimal point and parentheses are allowed"
            % (char, index + 1)
        )

    if len(tokens) > Config.MAX_TOKEN_COUNT:
        raise InvalidExpressionError(
            "The expression is too complex: at most %d tokens are allowed"
            % Config.MAX_TOKEN_COUNT
        )

    return tokens


# --------------------------------------------------------------------------- #
# Step 3: parsing (recursive descent)
# --------------------------------------------------------------------------- #

def _to_decimal(token: Token) -> Decimal:
    """Convert a number token into a ``Decimal``, enforcing the digit limit."""
    literal = token.value
    if len(literal.replace(".", "")) > MAX_NUMBER_DIGITS:
        raise InvalidExpressionError(
            "The number '%s' has too many digits; at most %d are supported"
            % (literal, MAX_NUMBER_DIGITS)
        )
    try:
        return Decimal(literal)
    except (InvalidOperation, DecimalException) as exc:  # pragma: no cover - regex guards this
        raise InvalidExpressionError("Unrecognised number '%s'" % literal) from exc


class _Parser:
    """Recursive descent parser turning a token list into a syntax tree."""

    def __init__(self, tokens, source: str):
        self._tokens = tokens
        self._source = source
        self._index = 0

    # ---------------------------- helpers ---------------------------- #

    @property
    def _current(self):
        """The token under the cursor, or ``None`` at the end of the input."""
        if self._index < len(self._tokens):
            return self._tokens[self._index]
        return None

    def _advance(self):
        token = self._current
        self._index += 1
        return token

    def _at_end(self) -> bool:
        return self._index >= len(self._tokens)

    def _syntax_error(self, message: str, token=None) -> InvalidExpressionError:
        """Build a syntax error that carries the offending position."""
        if token is None and not self._at_end():
            token = self._current
        if token is None:
            return InvalidExpressionError("%s (the expression ends unexpectedly)" % message)
        return InvalidExpressionError("%s (position %d)" % (message, token.position + 1))

    # ---------------------------- grammar rules ---------------------------- #

    def parse(self):
        """Parse ``expression`` and make sure no input is left over."""
        node = self._parse_expression()
        if not self._at_end():
            token = self._current
            raise self._syntax_error(
                "Missing operator before '%s'" % token.value, token
            )
        return node

    def _parse_expression(self):
        """expression -> term (("+" | "-") term)*"""
        node = self._parse_term()
        while True:
            token = self._current
            if token is None or token.kind != TOKEN_OPERATOR:
                return node
            if token.value not in ADDITIVE_OPERATORS:
                return node
            self._advance()
            right = self._parse_term()
            node = (NODE_BINARY, token.value, node, right)

    def _parse_term(self):
        """term -> unary (("*" | "/") unary)*"""
        node = self._parse_unary()
        while True:
            token = self._current
            if token is None or token.kind != TOKEN_OPERATOR:
                return node
            if token.value not in MULTIPLICATIVE_OPERATORS:
                return node
            self._advance()
            right = self._parse_unary()
            node = (NODE_BINARY, token.value, node, right)

    def _parse_unary(self):
        """unary -> ("+" | "-") unary | power"""
        token = self._current
        if (
            token is not None
            and token.kind == TOKEN_OPERATOR
            and token.value in SIGN_OPERATORS
        ):
            self._advance()
            operand = self._parse_unary()
            return (NODE_UNARY, token.value, operand)
        return self._parse_power()

    def _parse_power(self):
        """power -> primary ("^" unary)?   (right associative)"""
        base = self._parse_primary()
        token = self._current
        if token is not None and token.kind == TOKEN_OPERATOR and token.value == "^":
            self._advance()
            # Reusing `unary` on the right allows both 2^3^2 and 2^-3.
            exponent = self._parse_unary()
            return (NODE_BINARY, "^", base, exponent)
        return base

    def _parse_primary(self):
        """primary -> NUMBER | "(" expression ")" """
        token = self._current

        if token is None:
            raise self._syntax_error("Incomplete expression: a number or '(' is required")

        if token.kind == TOKEN_NUMBER:
            self._advance()
            return (NODE_NUMBER, _to_decimal(token))

        if token.kind == TOKEN_LPAREN:
            self._advance()
            node = self._parse_expression()
            closing = self._current
            if closing is None:
                raise self._syntax_error("'(' has no matching ')'", token)
            if closing.kind != TOKEN_RPAREN:
                raise self._syntax_error("Expected ')' here", closing)
            self._advance()
            return node

        if token.kind == TOKEN_RPAREN:
            raise self._syntax_error("')' has no operand before it", token)

        raise self._syntax_error("'%s' is misplaced" % token.value, token)


def parse_expression(expression: str):
    """Parse an expression and return its syntax tree (no evaluation yet)."""
    normalized = normalize_expression(expression)
    tokens = tokenize(normalized)
    if not tokens:
        raise ValidationError("The expression must not be empty")
    return _Parser(tokens, normalized).parse()


# --------------------------------------------------------------------------- #
# Step 4: evaluation of the syntax tree
# --------------------------------------------------------------------------- #

def _guard_finite(value: Decimal) -> Decimal:
    """Reject infinity, NaN, and values beyond the configured magnitude."""
    if not value.is_finite():
        raise OverflowResultError("The result is not a finite number")
    if value != 0 and value.adjusted() > Config.MAX_DECIMAL_ADJUSTED_EXPONENT:
        raise OverflowResultError(
            "The result is too large; the absolute value must stay below 1E+%d"
            % Config.MAX_DECIMAL_ADJUSTED_EXPONENT
        )
    return value


def _power(base: Decimal, exponent: Decimal) -> Decimal:
    """Evaluate ``base ** exponent`` including all edge cases."""
    # By convention 0^0 = 1, matching Python and common calculators.
    if base == 0 and exponent == 0:
        return Decimal(1)

    # A negative power of zero is a division by zero.
    if base == 0 and exponent < 0:
        raise DivideByZeroError("Zero cannot be raised to a negative power")

    if exponent == exponent.to_integral_value():
        integral_exponent = int(exponent)
        if abs(integral_exponent) > Config.MAX_POWER_EXPONENT:
            raise OverflowResultError(
                "The absolute value of the exponent must not exceed %d"
                % Config.MAX_POWER_EXPONENT
            )
        try:
            return base ** integral_exponent
        except (InvalidOperation, Overflow, DivisionByZero) as exc:
            raise OverflowResultError("The power operation overflowed") from exc

    # Fractional powers require a positive base.
    if base < 0:
        raise InvalidExpressionError(
            "A negative number cannot be raised to a fractional power"
        )

    try:
        return base ** exponent
    except (InvalidOperation, Overflow, DivisionByZero) as exc:
        raise OverflowResultError("The power operation overflowed") from exc


def _apply_binary(operator: str, left: Decimal, right: Decimal) -> Decimal:
    """Apply one binary operator."""
    if operator == "+":
        return _guard_finite(left + right)
    if operator == "-":
        return _guard_finite(left - right)
    if operator == "*":
        return _guard_finite(left * right)
    if operator == "/":
        if right == 0:
            raise DivideByZeroError("Division by zero is not allowed")
        return _guard_finite(left / right)
    if operator == "^":
        return _guard_finite(_power(left, right))
    # The grammar makes this unreachable.
    raise InvalidExpressionError("Unsupported operator '%s'" % operator)  # pragma: no cover


def evaluate(node) -> Decimal:
    """Recursively evaluate a syntax tree."""
    tag = node[0]

    if tag == NODE_NUMBER:
        return node[1]

    if tag == NODE_UNARY:
        _, operator, operand = node
        value = evaluate(operand)
        return value if operator == "+" else -value

    if tag == NODE_BINARY:
        _, operator, left_node, right_node = node
        # Evaluate both sides first so that the evaluation order matches the
        # written order and a zero divisor is reported reliably.
        left = evaluate(left_node)
        right = evaluate(right_node)
        return _apply_binary(operator, left, right)

    raise InvalidExpressionError("Invalid syntax tree node: %s" % tag)  # pragma: no cover


def evaluate_expression(expression: str) -> Decimal:
    """Parse and evaluate an expression, returning a ``Decimal``."""
    node = parse_expression(expression)
    with localcontext() as context:
        context.prec = Config.DECIMAL_PRECISION
        try:
            return +evaluate(node)  # unary + rounds the result to the context precision
        except (InvalidOperation, DivisionByZero, Overflow) as exc:
            raise OverflowResultError("Evaluation failed: %s" % exc) from exc


# --------------------------------------------------------------------------- #
# Step 5: result formatting
# --------------------------------------------------------------------------- #

def format_decimal(value: Decimal) -> str:
    """Format a ``Decimal`` for display.

    * trailing zeros are removed: ``5.00`` becomes ``5``
    * long fractions are rounded half up to ``MAX_DISPLAY_DECIMAL_PLACES``
    * very large or very small values switch to scientific notation
    """
    if value == 0:
        return "0"

    adjusted = value.adjusted()
    if adjusted >= 16 or adjusted <= -7:
        return _format_scientific(value)

    text = format(value, "f")

    if "." not in text:
        return text

    integer_part, _, decimal_part = text.partition(".")
    decimal_part = decimal_part.rstrip("0")

    if len(decimal_part) > Config.MAX_DISPLAY_DECIMAL_PLACES:
        quantizer = Decimal(1).scaleb(-Config.MAX_DISPLAY_DECIMAL_PLACES)
        # quantize() raises InvalidOperation when the value has more significant
        # digits than the current context allows, so widen the precision for the
        # rounding step. Without this, lowering CALC_DECIMAL_PRECISION would turn
        # a formatting detail into an HTTP 500.
        with localcontext() as context:
            context.prec = (
                len(value.as_tuple().digits)
                + Config.MAX_DISPLAY_DECIMAL_PLACES
                + 2
            )
            rounded = value.quantize(quantizer, rounding=ROUND_HALF_UP)
        text = format(rounded, "f")
        integer_part, _, decimal_part = text.partition(".")
        decimal_part = decimal_part.rstrip("0")

    return integer_part + "." + decimal_part if decimal_part else integer_part


def _format_scientific(value: Decimal) -> str:
    """Render values such as ``1.5E+20`` or ``2.5E-8``."""
    text = format(value.normalize(), "E")
    mantissa, _, exponent = text.partition("E")
    exponent_value = int(exponent)
    return "%sE%s%d" % (mantissa, "+" if exponent_value >= 0 else "-", abs(exponent_value))


def to_json_number(value: Decimal) -> float:
    """Convert a ``Decimal`` into a JSON serialisable number.

    The string form produced by :func:`format_decimal` is what the UI displays,
    so large or high precision results are never truncated by JSON.
    """
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise OverflowResultError("The result exceeds the representable range") from exc

    if number != number or number in (float("inf"), float("-inf")):
        raise OverflowResultError("The result exceeds the representable range")

    # Normalise -0.0 to 0.0.
    return 0.0 if number == 0 else number
