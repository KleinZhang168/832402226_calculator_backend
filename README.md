# 832402226_calculator_backend

> A front-end / back-end separated calculator - **back-end service**
> Student ID: 832402226 | Stack: Python 3 + Flask + SQLite

This repository is the server side of the project. It owns validation,
expression parsing, evaluation, error handling and data persistence, and exposes
them as a JSON API. It contains no user interface code.

The companion client lives in the repository **832402226_calculator_frontend**.

---

## 1. Project introduction

The service provides six endpoints:

| Purpose | Method | Path |
| --- | --- | --- |
| Health check | GET | `/api/health` |
| Evaluate an expression and store it | POST | `/api/calculate` |
| Evaluate an expression without storing it | POST | `/api/calculate/preview` |
| List the calculation history (paged) | GET | `/api/history` |
| Count the stored records | GET | `/api/history/count` |
| Delete one record | DELETE | `/api/history/{id}` |
| Clear the whole history (optional feature) | DELETE | `/api/history` |

The core algorithm in `src/service/expression_parser.py` is a hand written
**lexer + recursive descent parser + tree evaluator**. It never calls `eval` or
`exec`, so a submitted expression cannot execute arbitrary code.

---

## 2. Technology stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Language | Python 3.8+ | Standard library only for parsing, maths and SQLite |
| Web framework | Flask 2.2+ | Lightweight, blueprint based routing |
| Database | SQLite 3 | Single file, ships with Python, nothing to install |
| Data access | `sqlite3` with hand written DAO | No ORM: the SQL and the schema stay readable |
| Expression parser | Custom recursive descent parser | See section 10 |
| Tests | `unittest` from the standard library | No pytest needed |
| CORS | Custom middleware | One dependency less |
| Production server | gunicorn (optional) | Used on Linux cloud hosts |

**The only third party package is Flask.**

---

## 3. Directory structure

```
832402226_calculator_backend/
├── src/
│   ├── app.py                       # application factory: blueprints, middleware, database
│   ├── calculator.py                # public entry point of the calculation core
│   ├── config.py                    # central configuration, overridable by environment
│   ├── controller/                  # controller layer: parse requests, wrap responses
│   │   ├── calculate_controller.py  # POST /api/calculate, /api/calculate/preview
│   │   ├── history_controller.py    # GET /api/history, DELETE /api/history[/{id}]
│   │   └── system_controller.py     # GET /api/health
│   ├── service/                     # service layer: business rules
│   │   ├── calculator.py            # validate -> parse -> evaluate -> store
│   │   ├── expression_parser.py     # the core algorithm (no eval)
│   │   └── history.py               # list / delete / clear history
│   ├── model/                       # model layer: database only
│   │   ├── database.py              # connection management and schema
│   │   └── history_model.py         # CRUD for calculation_history
│   ├── middleware/                  # CORS and centralised error handling
│   └── utils/                       # business exceptions, unified response bodies
├── scripts/init_db.py               # database initialisation helper
├── tests/                           # 81 unit tests
├── data/                            # SQLite file location (created at runtime)
├── run.py                           # development entry point
├── requirements.txt
├── .env.example
├── README.md
└── codestyle.md
```

Call chain:

```
HTTP request
   -> controller/   parse the request, wrap the response (no business rules)
   -> service/      validate, evaluate, orchestrate persistence
   -> model/        SQL statements and connection handling
   -> SQLite
```

---

## 4. Runtime environment

| Item | Requirement |
| --- | --- |
| Operating system | Windows, macOS or Linux |
| Python | **3.8 or newer** (3.10+ recommended) |
| Dependencies | Flask only (see `requirements.txt`) |
| Database | None to install: SQLite ships with Python |
| Port | 5000 by default, changeable with `CALC_PORT` |

Check the interpreter:

```bash
python --version
```

---

## 5. Installation

```bash
# 1. Enter the project directory
cd 832402226_calculator_backend

# 2. (Recommended) create and activate a virtual environment
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
# .venv\Scripts\activate.bat
# macOS / Linux:
# source .venv/bin/activate

# 3. Install dependencies
python -m pip install -r requirements.txt
```

> If `Activate.ps1` is blocked by the execution policy, either use the CMD
> script shown above or skip activation entirely and call the interpreter
> directly: `.venv\Scripts\python run.py`.

---

## 6. Configuration

All settings live in `src/config.py` and every one of them can be overridden by
an environment variable, so no code change is needed between machines. The full
list is in `.env.example`.

| Variable | Default | Description |
| --- | --- | --- |
| `CALC_HOST` | `0.0.0.0` | Bind address; `0.0.0.0` also accepts LAN traffic |
| `CALC_PORT` | `5000` | Listening port |
| `PORT` | - | Port injected by a cloud platform, used when `CALC_PORT` is unset |
| `CALC_DEBUG` | `false` | Debug mode; must stay `false` in public |
| `CALC_DB_PATH` | `data/calculator.db` | SQLite file path |
| `CALC_FRONTEND_DIR` | - | Optional static front-end directory (same origin hosting) |
| `CALC_MAX_EXPRESSION_LENGTH` | `200` | Maximum expression length in characters |
| `CALC_MAX_TOKEN_COUNT` | `500` | Maximum number of tokens |
| `CALC_DECIMAL_PRECISION` | `28` | Decimal precision used while evaluating |
| `CALC_MAX_DISPLAY_DP` | `10` | Maximum decimal places in the displayed result |
| `CALC_MAX_POWER_EXPONENT` | `1000` | Absolute limit of a power exponent |
| `CALC_DEFAULT_PAGE_SIZE` | `20` | Default page size of the history endpoint |
| `CALC_MAX_PAGE_SIZE` | `100` | Maximum accepted `pageSize` |
| `CALC_CORS_ORIGIN` | `*` | Allowed cross origin source |

Temporary override in PowerShell (current window only):

```powershell
$env:CALC_PORT = "8080"
python run.py
```

---

## 7. Database initialisation

No manual database setup is required. The first start creates
`data/calculator.db`, the `calculation_history` table and its index, using
`CREATE TABLE IF NOT EXISTS`, so existing data is never destroyed.

To initialise explicitly, or to load sample rows before a demonstration:

```bash
# Create the schema (safe to repeat)
python scripts/init_db.py

# Delete the old file and recreate the schema (clears the history)
python scripts/init_db.py --reset

# Create the schema and insert 3 sample rows
python scripts/init_db.py --demo
```

The script prints the resulting table layout:

```
[schema] calculation_history
  column       type     pk     description
  ------------------------------------------------------------
  id           INTEGER  yes    auto increment primary key
  expression   TEXT     no     the expression submitted by the client
  result       REAL     no     numeric result
  result_text  TEXT     no     result formatted for display
  created_at   TEXT     no     calculation time YYYY-MM-DD HH:MM:SS
```

The `result` column stores the numeric value, while `result_text` stores the
formatted string. Clients should display `resultText`, because JSON numbers
cannot represent very large or very precise values exactly.

---

## 8. Startup

```bash
python run.py
```

Expected output:

```
====================================================================
  832402226 Calculator Backend
====================================================================
  Listening : http://0.0.0.0:5000
  Database  : .../832402226_calculator_backend/data/calculator.db
  Health    : GET http://127.0.0.1:5000/api/health
  Endpoints : GET http://127.0.0.1:5000/
====================================================================
 * Running on http://127.0.0.1:5000
```

Open <http://127.0.0.1:5000/> for the endpoint list and
<http://127.0.0.1:5000/api/health> to confirm that the service and the database
are healthy.

Quick manual check (PowerShell):

```powershell
# Evaluate an expression; the record is stored in the database
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/calculate -Method Post `
  -ContentType 'application/json' -Body '{"expression":"(1+2)*3"}'

# List the history
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/history

# Delete record 1
Invoke-RestMethod -Uri http://127.0.0.1:5000/api/history/1 -Method Delete
```

With curl:

```bash
curl -X POST http://127.0.0.1:5000/api/calculate \
     -H "Content-Type: application/json" \
     -d '{"expression":"(1+2)*3"}'
```

Response:

```json
{
  "success": true,
  "id": 1,
  "expression": "(1+2)*3",
  "result": 9,
  "resultText": "9",
  "createdAt": "2026-10-01 10:20:00"
}
```

---

## 9. API description

### 9.1 Response format

Success:

```json
{ "success": true, "expression": "(1+2)*3", "result": 9 }
```

Failure:

```json
{ "success": false, "code": "INVALID_EXPRESSION", "message": "Unsupported character 'a' at position 3" }
```

`code` is an extension of the required `{success, message}` shape; a client that
only reads `success` and `message` works unchanged.

### 9.2 Endpoints

| Method | Path | Body / query | Success | Notes |
| --- | --- | --- | --- | --- |
| GET | `/api/health` | - | 200 | `database: ok`, `historyCount`, `databasePath` |
| POST | `/api/calculate` | `{"expression": "(1+2)*3"}` | 200 | Stores the record, returns `id` and `createdAt` |
| POST | `/api/calculate/preview` | `{"expression": "(1+2)*3"}` | 200 | Evaluates only, nothing is stored |
| GET | `/api/history` | `?page=1&pageSize=20` | 200 | `total`, `page`, `pageSize`, `list[]`, newest first |
| GET | `/api/history/count` | - | 200 | `total` only |
| DELETE | `/api/history/{id}` | - | 200 | 404 when the id does not exist |
| DELETE | `/api/history` | - | 200 | Clears everything, returns `deleted` |

### 9.3 Status codes and error codes

| HTTP | When | Example `code` |
| --- | --- | --- |
| 200 OK | The request succeeded | - |
| 400 Bad Request | Validation or expression problem | `VALIDATION_ERROR`, `INVALID_EXPRESSION`, `DIVIDE_BY_ZERO`, `RESULT_OVERFLOW` |
| 404 Not Found | Unknown endpoint or unknown history id | `NOT_FOUND` |
| 405 Method Not Allowed | Wrong HTTP method for the path | `METHOD_NOT_ALLOWED` |
| 500 Internal Server Error | Unexpected failure; no stack trace is returned | `INTERNAL_ERROR`, `DATABASE_ERROR` |

### 9.4 Verified behaviour

| Input | HTTP | Result |
| --- | --- | --- |
| `(1+2)*3` | 200 | `resultText: "9"` |
| `0.1+0.2` | 200 | `"0.3"` (decimal arithmetic, no binary rounding error) |
| `7/2` | 200 | `"3.5"` |
| `1/3` | 200 | `"0.3333333333"`; `result` is a 16 digit float, so display `resultText` |
| `2^3^2` | 200 | `"512"` (`^` is right associative) |
| `-2^2` | 200 | `"-4"` (power binds tighter than the unary minus) |
| `2^-3` | 200 | `"0.125"` |
| `0^0` | 200 | `"1"` |
| `1000000*1000000` | 200 | `"1000000000000"` |
| `1/0` | 400 | `DIVIDE_BY_ZERO` |
| `1+abc` | 400 | `INVALID_EXPRESSION` with the offending position |
| `(1+2` | 400 | `INVALID_EXPRESSION`, unbalanced parenthesis |
| `9^999999` | 400 | `RESULT_OVERFLOW`, exponent limit |
| Longer than 200 characters | 400 | `VALIDATION_ERROR` |
| `?pageSize=0`, `=abc`, `=999` | 400 | `VALIDATION_ERROR` |
| `?page=99` beyond the last page | 200 | `list: []`, which is not an error |
| Unknown route | 404 | `NOT_FOUND` JSON |
| Wrong method | 405 | `METHOD_NOT_ALLOWED` JSON |

Note that `expression` in the response is the normalised form: submitting `6×7`
stores `6*7`, so clients should render the expression returned by the server.

---

## 10. How the front end connects

1. Start this service (`python run.py`) and confirm
   <http://127.0.0.1:5000/api/health> returns `"database": "ok"`.
2. Start the front-end project (see its README). The client decides which base
   URL to use on its own:

   | Front-end opened from | Base URL used | Configuration needed |
   | --- | --- | --- |
   | `http://127.0.0.1:8080` | `http://127.0.0.1:5000` | none |
   | `http://127.0.0.1:5000` (same origin) | relative `/api/...` | none |
   | A phone on the LAN | `http://<your-lan-ip>:5000` | none |
   | A public deployment | relative `/api/...` | none |

3. Allow port 5000 through the firewall when a phone has to reach this machine.
4. Verify from the phone browser: `http://<your-lan-ip>:5000/api/health`.

**Optional same origin hosting.** If a copy of the front-end is placed in
`src/web/` (or `CALC_FRONTEND_DIR` points at it), this service also serves the
pages, so a single URL covers both the UI and the API and the browser issues no
cross origin request at all. This is the mode used by the free cloud deployment
described in the front-end README.

---

## 11. Running the tests

```bash
python -m unittest discover -s tests -v
```

Expected result:

```
Ran 81 tests in ~1s

OK
```

Coverage:

* **Expression parser (51 cases)**: arithmetic, precedence, nested parentheses,
  unary signs, decimals, powers, full width normalisation, division by zero,
  malformed input, over-long input, and script injection strings such as
  `__import__('os')...` being rejected.
* **HTTP API (30 cases)**: response structure, status codes, pagination,
  deleting a missing id returning 404, and failed calculations not being stored.
* **Persistence**: history survives a simulated restart of the application.

The tests create temporary databases under `tests/.tmp/` and delete them
afterwards; `data/calculator.db` is never modified.

---

## 12. Core algorithm

### 12.1 Why not `eval`

The assignment forbids executing user input with `eval` or `exec`, and even a
character whitelist around `eval` leaves the door open to function calls,
attribute access and comprehensions. This project therefore implements the
parser itself: every accepted character belongs to one of three token kinds -
number, operator or parenthesis.

### 12.2 Five steps

```
1. normalise   full width and CJK symbols -> ASCII
2. tokenize    string -> [NUMBER 1] [OPERATOR +] [NUMBER 2] ...
3. parse       recursive descent -> syntax tree (nothing is computed yet)
4. evaluate    post-order traversal using decimal.Decimal
5. format      trim trailing zeros, round long fractions, use scientific notation
```

### 12.3 Grammar

```
expression -> term (("+" | "-") term)*
term       -> unary (("*" | "/") unary)*
unary      -> ("+" | "-") unary | power
power      -> primary ("^" unary)?
primary    -> NUMBER | "(" expression ")"
```

Operator precedence comes from the layering of the grammar instead of a
precedence table, and `^` is right associative because its right hand side is a
`unary`.

### 12.4 Decimal arithmetic

```
binary float:  0.1 + 0.2 = 0.30000000000000004
decimal:       0.1 + 0.2 = 0.3                 <- this project
```

Results are rounded half up to at most 10 decimal places for display, so `1/3`
is shown as `0.3333333333` rather than a long binary tail.

### 12.5 Error handling

| Situation | Error code | HTTP |
| --- | --- | --- |
| Missing, empty, wrong type or too long input | `VALIDATION_ERROR` | 400 |
| Illegal character, unbalanced parenthesis, missing operand | `INVALID_EXPRESSION` | 400 |
| Division by zero, `0^-1` | `DIVIDE_BY_ZERO` | 400 |
| Result overflow, exponent too large, fractional power of a negative base | `RESULT_OVERFLOW` / `INVALID_EXPRESSION` | 400 |
| Deleting an unknown history id | `NOT_FOUND` | 404 |
| Database read or write failure | `DATABASE_ERROR` | 500 |
| Anything unexpected | `INTERNAL_ERROR` | 500 |

---

## 13. Frequently asked questions

**`python` is not recognised.** Python is not installed or not on `PATH`.
Install it from python.org and tick *Add Python to PATH*.

**`ModuleNotFoundError: No module named 'flask'`.** Dependencies are missing:
run `python -m pip install -r requirements.txt`.

**Port 5000 is already in use.** Start on another port with
`$env:CALC_PORT="5001"; python run.py` and point the front-end at it.

**A phone cannot reach the service.** Check that both devices are on the same
network, that the front-end uses the machine's LAN IP (not `127.0.0.1`), and
that the firewall allows port 5000.

**Is the history lost when the service restarts?** No. Records live in the
SQLite file; only `scripts/init_db.py --reset` or `DELETE /api/history` removes
them.
