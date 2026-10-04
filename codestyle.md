# Code style - 832402226_calculator_backend

## Source of this standard

The rules below are derived from the official Python style guide and its
community accepted extensions:

* **PEP 8 - Style Guide for Python Code** (primary source):
  <https://peps.python.org/pep-0008/>
* **PEP 257 - Docstring Conventions**:
  <https://peps.python.org/pep-0257/>
* **PEP 20 - The Zen of Python** (the design principles behind the layout):
  <https://peps.python.org/pep-0020/>
* **Google Python Style Guide**, used for the docstring sections and for the
  guidance on imports and exceptions:
  <https://google.github.io/styleguide/pyguide.html>
* **The Hitchhiker's Guide to Python - Structuring Your Project**, used for the
  layered directory layout:
  <https://docs.python-guide.org/writing/structure/>

Everything in this document either quotes those sources or records the concrete
conventions this repository follows. Where the tools disagree, PEP 8 wins.

---

## 1. Layout

### 1.1 Indentation and line length

* Indent with **4 spaces**. Never mix tabs and spaces (PEP 8).
* Maximum line length is **100 characters**; docstrings and comments are wrapped
  at 88. Continuation lines are aligned with the opening delimiter or indented
  by 4 extra spaces.

```python
result = history_model.find_all(
    limit=size,
    offset=offset,
)
```

### 1.2 Blank lines

* Two blank lines between top level definitions.
* One blank line between methods inside a class.
* One blank line after the module docstring and after the imports.

### 1.3 Imports

* One import per line, grouped in the order: standard library, third party,
  local application.
* Absolute imports only: `from src.model import database`, never `from . import
  database` across packages. Relative imports are allowed only inside a package
  for its own submodules (used in the `__init__.py` files).
* Never use wildcard imports (`from x import *`).
* Every local import that must follow `sys.path` manipulation carries a
  `# noqa: E402` marker explaining why it is not at the top of the file.

---

## 2. Naming

| Kind | Convention | Example |
| --- | --- | --- |
| Module, package | `lower_snake_case` | `expression_parser.py` |
| Class, exception | `CapWords` | `CalculatorService`, `DivideByZeroError` |
| Function, method | `lower_snake_case` | `evaluate_expression`, `list_history` |
| Variable | `lower_snake_case` | `database_path`, `record_id` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_TOKEN_COUNT`, `API_PREFIX` |
| Private helper | leading underscore | `_to_decimal`, `_parse_power` |

Additional rules:

* Names must be descriptive; single letter names are only acceptable as loop
  indices or in short mathematical helpers.
* A boolean reads like a statement: `is_valid`, `has_frontend`, `database_ok`.
* Modules are named after the concept they hold, not after a layer suffix
  repeated everywhere: `calculator.py`, `history.py`, `database.py`.

---

## 3. Docstrings and comments

* Every module, public class and public function has a docstring (PEP 257).
* The first line is a one line summary ending with a period, in the imperative
  mood. A blank line separates it from the body.
* Sphinx style field markers are used for parameters and return values:

```python
def parse_optional_int(value, default, minimum, maximum, field_name):
    """Parse an optional integer query parameter into the allowed range.

    :param value: the raw query string value, or None
    :param default: value returned when the parameter is absent
    :raises ValidationError: when the value is not an integer or out of range
    """
```

* Comments explain **why**, not what. A comment that repeats the code is
  removed.
* Any non-obvious decision is recorded at the place it matters, for example why
  `tempfile.mkdtemp()` is avoided in the test suite.
* The language of the code base, comments and docs is **English**.

---

## 4. Language features

* Target **Python 3.8+**: no walrus operator in library code, no
  `match` statements, no `X | Y` type unions in annotations.
* Type hints are used on function signatures and on module constants where they
  clarify intent (`def find_all(limit: int, offset: int) -> List[dict]`).
* f-strings are preferred for new code; `%` formatting is kept where a template
  is reused or where it keeps a long message readable.
* Mutable default arguments are forbidden (`def f(items=None)` then
  `items = items or []`).
* Comparison with `None` uses `is` / `is not`.
* Exceptions are raised with a message and re-raised with `from exc` to preserve
  the original traceback.

---

## 5. Exceptions and error handling

* All expected failures derive from `ApiError` in `src/utils/exceptions.py` and
  declare both `status_code` and `code`.
* The service layer raises; the controller layer never builds an error response
  by hand; `middleware/error_handler.py` performs the conversion.
* `except` clauses name the exception types they expect. A bare `except:` is
  forbidden; `except Exception:` is allowed only where a failure must be
  contained, and then it carries a `# noqa: BLE001` marker and a comment.
* Unexpected exceptions are logged with `app.logger.exception(...)` and reported
  as HTTP 500 without leaking a stack trace to the client.

---

## 6. Layering rules

The project is split into controller, service, model, middleware and utils. The
dependencies point strictly downwards:

```
controller  ->  service  ->  model  ->  sqlite3
      \            \          /
       \            \        /
        +---------- utils (exceptions)
middleware  ->  utils (responses)
```

* A controller never touches the database directly.
* A model function never contains business rules and never imports Flask request
  objects.
* `src/utils/__init__.py` deliberately re-exports only the exceptions, so the
  pure algorithm module stays importable without Flask.
* `src/calculator.py` is the documented public entry point of the calculation
  core; other modules import the service layer through it or directly, never
  through a chain of re-exports.

---

## 7. Data and SQL

* All SQL lives in the model layer.
* Parameters are always bound (`?` placeholders); string interpolation of user
  data into SQL is forbidden.
* Column names are listed once in a module constant (`_COLUMNS`) so every query
  returns the same shape.
* The schema uses `IF NOT EXISTS` so that initialisation is idempotent.
* Timestamps are stored as `YYYY-MM-DD HH:MM:SS` local time strings, which stay
  sortable and human readable in the database file.

---

## 8. Tests

* The standard library `unittest` module is used; no extra test runner is
  required.
* Test classes are named `Test<Subject>` and describe a requirement, not an
  implementation detail.
* Every test is independent: it creates its own temporary database in `setUp`
  and removes it in `tearDown`.
* Test names read as a sentence: `test_division_by_zero_returns_400`.
* Assertions compare values, not stringified representations, whenever possible.

---

## 9. Formatting summary

| Item | Rule |
| --- | --- |
| Indentation | 4 spaces |
| Maximum line length | 100 characters |
| Quotes | double quotes for docstrings, single quotes for short literals |
| Trailing whitespace | none |
| File encoding | UTF-8, no BOM |
| Final newline | exactly one |
| Line endings | LF in the repository |
