import math
import unittest
from pathlib import Path

from backend.model import DEFAULT_PARAMS, csv_values_at, normalize_csv_records, simulate, SimulationContext
from backend import realtime


REQUIRED_KEYS = {
    "time",
    "effCod",
    "effNh4",
    "effNo3",
    "effTn",
    "effTss",
    "anaerobicNo3",
    "anoxicNo3",
    "aerobicNo3",
    "aerobicDo",
    "aerobicMlss",
    "rasMlss",
    "boundaries",
    "units",
    "clarifier",
    "mode",
    "sourceName",
    "warnings",
    "validation",
}


def assert_finite_tree(test_case: unittest.TestCase, value):
    if isinstance(value, dict):
        for child in value.values():
            assert_finite_tree(test_case, child)
    elif isinstance(value, list):
        for child in value:
            assert_finite_tree(test_case, child)
    elif isinstance(value, (int, float)):
        test_case.assertTrue(math.isfinite(value))


class ModelTest(unittest.TestCase):
    def setUp(self):
        realtime.DB_PATH = Path("/private/tmp/aao-realtime-test.db")
        if realtime.DB_PATH.exists():
            realtime.DB_PATH.unlink()

    def tearDown(self):
        if realtime.DB_PATH.exists():
            realtime.DB_PATH.unlink()

    def test_manual_simulation_returns_frontend_shape_and_finite_values(self):
        params = {**DEFAULT_PARAMS, "simulationDays": 1, "outputIntervalHours": 12, "timeStepHours": 1}
        result = simulate(params=params)

        self.assertTrue(REQUIRED_KEYS.issubset(result.keys()))
        self.assertEqual(result["mode"], "manual")
        self.assertGreater(len(result["time"]), 1)
        self.assertIn("warningCount", result["validation"])
        assert_finite_tree(self, result)

    def test_csv_simulation_uses_requested_simulation_horizon(self):
        csv_text = Path("sample-data.csv").read_text(encoding="utf-8")
        params = {**DEFAULT_PARAMS, "simulationDays": 50, "outputIntervalHours": 24, "timeStepHours": 1}

        result = simulate(params=params, csv_text=csv_text, csv_file_name="sample-data.csv")

        self.assertEqual(result["mode"], "csv")
        self.assertEqual(result["sourceName"], "sample-data.csv")
        self.assertAlmostEqual(result["time"][-1], 50, places=4)
        self.assertTrue(any("CSV 数据到" in warning for warning in result["warnings"]))

    def test_csv_holds_last_boundary_after_range(self):
        ctx = SimulationContext(params={**DEFAULT_PARAMS, "timeStepHours": 1})
        records = normalize_csv_records("time,Q,COD\n0,100,300\n1,200,500\n", ctx)
        cursor = {"index": 0}

        values = csv_values_at(records, 10, cursor)

        self.assertEqual(values["influentQ"], 200)
        self.assertEqual(values["influentCod"], 500)

    def test_invalid_parameter_raises_clear_error(self):
        params = {**DEFAULT_PARAMS, "influentQ": 0}

        with self.assertRaisesRegex(ValueError, "influentQ"):
            simulate(params=params)

    def test_unusual_but_runnable_parameter_returns_warning(self):
        params = {**DEFAULT_PARAMS, "simulationDays": 1, "timeStepHours": 2}

        result = simulate(params=params)

        self.assertGreater(result["validation"]["warningCount"], 0)
        self.assertTrue(any("内部求解器上限" in warning for warning in result["warnings"]))

    def test_realtime_step_persists_latest_result(self):
        step = realtime.realtime_step(values={"Q": 10000, "COD": 420, "NH4": 32, "NO3": 0.5, "TSS": 220}, step_hours=0.5)
        latest = realtime.latest()

        self.assertEqual(step["result"]["mode"], "realtime")
        self.assertIsNotNone(latest["result"])
        self.assertEqual(latest["result"]["id"], step["resultId"])
        self.assertIn("effCod", latest["result"]["result"])

    def test_realtime_reset_clears_state(self):
        realtime.realtime_step(values={"Q": 10000}, step_hours=0.5)
        realtime.reset()

        latest = realtime.latest()

        self.assertIsNone(latest["input"])
        self.assertIsNone(latest["state"])
        self.assertIsNone(latest["result"])


if __name__ == "__main__":
    unittest.main()
