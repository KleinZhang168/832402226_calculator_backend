"""HTTP layer tests, driving the application through Flask's test client.

Run them with::

    python -m unittest discover -s tests -v

Every test case creates its own temporary directory and SQLite file under
``tests/.tmp/`` and removes it afterwards, so cases cannot influence each other
and the real database in ``data/`` is never touched.
"""

import json
import os
import shutil
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.app import create_app          # noqa: E402
from src.config import Config           # noqa: E402

JSON_HEADERS = {"Content-Type": "application/json"}

#: Temporary directory for the tests (see make_temp_dir for the rationale).
TESTS_TMP_DIR = Path(__file__).resolve().parent / ".tmp"


def make_temp_dir() -> str:
    """Create a unique temporary directory under ``tests/.tmp/``.

    ``tempfile.mkdtemp()`` is deliberately avoided: on Windows it creates a
    directory with mode 0700, and in some restricted environments sqlite3 then
    fails to create the database file with "unable to open database file",
    which would break every API test during setUp. A plain ``mkdir`` inside the
    project directory avoids that and keeps the artefacts visible.
    """
    TESTS_TMP_DIR.mkdir(parents=True, exist_ok=True)
    for index in range(1, 100000):
        candidate = TESTS_TMP_DIR / ("case_%d_%d" % (os.getpid(), index))
        try:
            candidate.mkdir()
            return str(candidate)
        except FileExistsError:
            continue
    raise RuntimeError("Could not create a temporary directory under %s" % TESTS_TMP_DIR)


def build_test_config(database_path: str):
    """Build a config class pointing at a temporary database."""

    class TestConfig(Config):
        TESTING = True
        DEBUG = False
        DATABASE_PATH = database_path
        CORS_ALLOW_ORIGIN = "*"

    return TestConfig


class CalculatorApiTestCase(unittest.TestCase):
    """Shared base class: one fresh temporary database per test case."""

    def setUp(self):
        self.temp_dir = make_temp_dir()
        self.database_path = str(Path(self.temp_dir) / "test_calculator.db")
        self.app = create_app(build_test_config(self.database_path))
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def post_calculate(self, expression):
        return self.client.post(
            "/api/calculate",
            data=json.dumps({"expression": expression}),
            headers=JSON_HEADERS,
        )

    def get_history(self, query=""):
        return self.client.get("/api/history" + query)

    def body(self, response):
        return json.loads(response.data.decode("utf-8"))


class TestHealthApi(CalculatorApiTestCase):
    """Health check endpoint."""

    def test_health_returns_ok(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = self.body(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["database"], "ok")
        self.assertEqual(payload["historyCount"], 0)

    def test_index_lists_endpoints(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        payload = self.body(response)
        self.assertTrue(payload["success"])
        self.assertTrue(any("/api/calculate" in item for item in payload["endpoints"]))


class TestCalculateApi(CalculatorApiTestCase):
    """POST /api/calculate"""

    def test_basic_addition(self):
        response = self.post_calculate("12+8")
        self.assertEqual(response.status_code, 200)
        payload = self.body(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["expression"], "12+8")
        self.assertEqual(payload["result"], 20)
        self.assertEqual(payload["resultText"], "20")

    def test_compound_expression(self):
        payload = self.body(self.post_calculate("(1+2)*3"))
        self.assertEqual(payload["result"], 9)

    def test_precedence(self):
        payload = self.body(self.post_calculate("1+2*3"))
        self.assertEqual(payload["result"], 7)

    def test_unary_minus(self):
        payload = self.body(self.post_calculate("-5+8"))
        self.assertEqual(payload["result"], 3)

    def test_multiply_negative(self):
        payload = self.body(self.post_calculate("3*-2"))
        self.assertEqual(payload["result"], -6)

    def test_decimal_result(self):
        payload = self.body(self.post_calculate("0.1+0.2"))
        self.assertEqual(payload["resultText"], "0.3")

    def test_response_contains_record_metadata(self):
        payload = self.body(self.post_calculate("1+1"))
        self.assertIn("id", payload)
        self.assertIn("createdAt", payload)
        self.assertEqual(len(payload["createdAt"]), 19)  # YYYY-MM-DD HH:MM:SS

    def test_division_by_zero_returns_400(self):
        response = self.post_calculate("1/0")
        self.assertEqual(response.status_code, 400)
        payload = self.body(response)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["code"], "DIVIDE_BY_ZERO")
        self.assertIn("zero", payload["message"].lower())

    def test_invalid_expression_returns_400(self):
        response = self.post_calculate("1+*2")
        self.assertEqual(response.status_code, 400)
        payload = self.body(response)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["code"], "INVALID_EXPRESSION")

    def test_missing_expression_field_returns_400(self):
        response = self.client.post(
            "/api/calculate", data=json.dumps({}), headers=JSON_HEADERS
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["code"], "VALIDATION_ERROR")

    def test_expression_wrong_type_returns_400(self):
        response = self.client.post(
            "/api/calculate", data=json.dumps({"expression": 123}), headers=JSON_HEADERS
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_expression_returns_400(self):
        response = self.post_calculate("   ")
        self.assertEqual(response.status_code, 400)

    def test_too_long_expression_returns_400(self):
        response = self.post_calculate("1+" * 200 + "1")
        self.assertEqual(response.status_code, 400)

    def test_failed_calculation_is_not_stored(self):
        self.post_calculate("1/0")
        self.post_calculate("1+*2")
        payload = self.body(self.get_history())
        self.assertEqual(payload["total"], 0)

    def test_preview_endpoint_does_not_store(self):
        response = self.client.post(
            "/api/calculate/preview",
            data=json.dumps({"expression": "2*21"}),
            headers=JSON_HEADERS,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.body(response)["result"], 42)
        self.assertEqual(self.body(self.get_history())["total"], 0)


class TestHistoryApi(CalculatorApiTestCase):
    """GET /api/history, DELETE /api/history/{id}, DELETE /api/history"""

    def seed(self, expressions):
        """Calculate several expressions to build up history."""
        for expression in expressions:
            self.post_calculate(expression)

    def test_history_is_empty_at_start(self):
        payload = self.body(self.get_history())
        self.assertTrue(payload["success"])
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["list"], [])

    def test_history_returns_stored_records(self):
        self.seed(["1+2", "5*8", "(2+3)*4"])
        payload = self.body(self.get_history())
        self.assertEqual(payload["total"], 3)
        # Sorted by id descending, newest first.
        self.assertEqual(
            [item["expression"] for item in payload["list"]],
            ["(2+3)*4", "5*8", "1+2"],
        )

    def test_history_record_fields(self):
        self.seed(["1+2"])
        record = self.body(self.get_history())["list"][0]
        self.assertEqual(
            sorted(record.keys()),
            ["createdAt", "expression", "id", "result", "resultText"],
        )
        self.assertEqual(record["result"], 3)
        self.assertEqual(record["resultText"], "3")

    def test_history_pagination(self):
        self.seed(["1+1", "2+2", "3+3", "4+4", "5+5"])
        first_page = self.body(self.get_history("?page=1&pageSize=2"))
        self.assertEqual(first_page["total"], 5)
        self.assertEqual(len(first_page["list"]), 2)
        second_page = self.body(self.get_history("?page=2&pageSize=2"))
        self.assertEqual(len(second_page["list"]), 2)
        # No record may appear on both pages.
        self.assertFalse(
            {item["id"] for item in first_page["list"]}
            & {item["id"] for item in second_page["list"]}
        )

    def test_history_invalid_page_size_returns_400(self):
        self.assertEqual(self.get_history("?pageSize=0").status_code, 400)
        self.assertEqual(self.get_history("?pageSize=abc").status_code, 400)

    def test_delete_single_record(self):
        self.seed(["1+1", "2+2"])
        target_id = self.body(self.get_history())["list"][0]["id"]

        response = self.client.delete("/api/history/%d" % target_id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.body(response)["success"])

        remaining = self.body(self.get_history())
        self.assertEqual(remaining["total"], 1)
        self.assertNotIn(target_id, [item["id"] for item in remaining["list"]])

    def test_delete_missing_record_returns_404(self):
        response = self.client.delete("/api/history/999999")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.body(response)["code"], "NOT_FOUND")

    def test_delete_invalid_id_returns_400(self):
        self.assertEqual(self.client.delete("/api/history/abc").status_code, 400)
        self.assertEqual(self.client.delete("/api/history/0").status_code, 400)

    def test_clear_all_history(self):
        self.seed(["1+1", "2+2", "3+3"])
        response = self.client.delete("/api/history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.body(response)["deleted"], 3)
        self.assertEqual(self.body(self.get_history())["total"], 0)


class TestPersistence(CalculatorApiTestCase):
    """Restarting the back end or reloading the front-end must not lose history."""

    def test_history_survives_app_restart(self):
        self.seed_and_check()

        # Simulate a restart: drop the old application, build a new one on the
        # same database file.
        restarted_app = create_app(build_test_config(self.database_path))
        restarted_client = restarted_app.test_client()

        payload = json.loads(restarted_client.get("/api/history").data.decode("utf-8"))
        self.assertEqual(payload["total"], 2)
        self.assertEqual(
            [item["expression"] for item in payload["list"]], ["8-3*2", "1+2"]
        )

    def seed_and_check(self):
        self.post_calculate("1+2")
        self.post_calculate("8-3*2")
        self.assertEqual(self.body(self.get_history())["total"], 2)


class TestErrorResponses(CalculatorApiTestCase):
    """Every failure uses the same structure: success=false plus a message."""

    def test_unknown_route_returns_404_json(self):
        response = self.client.get("/api/not-exist")
        self.assertEqual(response.status_code, 404)
        payload = self.body(response)
        self.assertFalse(payload["success"])
        self.assertIn("message", payload)

    def test_wrong_method_returns_405_json(self):
        response = self.client.get("/api/calculate")
        self.assertEqual(response.status_code, 405)
        self.assertFalse(self.body(response)["success"])

    def test_cors_headers_present(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")


if __name__ == "__main__":
    unittest.main(verbosity=2)
