import math
import unittest
from pathlib import Path

from backend.model import DEFAULT_PARAMS, csv_values_at, normalize_csv_records, simulate, SimulationContext


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
    def test_manual_simulation_returns_frontend_shape_and_finite_values(self):
        params = {**DEFAULT_PARAMS, "simulationDays": 1, "outputIntervalHours": 12, "timeStepHours": 1}
        result = simulate(params=params)

        self.assertTrue(REQUIRED_KEYS.issubset(result.keys()))
        self.assertEqual(result["mode"], "manual")
        self.assertGreater(len(result["time"]), 1)
        assert_finite_tree(self, result)

    def test_csv_simulation_uses_requested_simulation_horizon(self):
        csv_text = Path("sample-data.csv").read_text(encoding="utf-8")
        params = {**DEFAULT_PARAMS, "simulationDays": 50, "outputIntervalHours": 24, "timeStepHours": 1}

        result = simulate(params=params, csv_text=csv_text, csv_file_name="sample-data.csv")

        self.assertEqual(result["mode"], "csv")
        self.assertEqual(result["sourceName"], "sample-data.csv")
        self.assertAlmostEqual(result["time"][-1], 50, places=4)

    def test_csv_holds_last_boundary_after_range(self):
        ctx = SimulationContext(params={**DEFAULT_PARAMS, "timeStepHours": 1})
        records = normalize_csv_records("time,Q,COD\n0,100,300\n1,200,500\n", ctx)
        cursor = {"index": 0}

        values = csv_values_at(records, 10, cursor)

        self.assertEqual(values["influentQ"], 200)
        self.assertEqual(values["influentCod"], 500)


if __name__ == "__main__":
    unittest.main()
