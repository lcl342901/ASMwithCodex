import math
import asyncio
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
        try:
            asyncio.run(realtime.stop_mock())
        except RuntimeError:
            pass
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

    def test_large_requested_steps_use_same_internal_solver_step(self):
        base = {**DEFAULT_PARAMS, "simulationDays": 2, "outputIntervalHours": 12}
        coarse = simulate(params={**base, "timeStepHours": 0.5})
        fine = simulate(params={**base, "timeStepHours": 0.04167})

        self.assertAlmostEqual(coarse["time"][-1], 2, places=8)
        self.assertAlmostEqual(fine["time"][-1], 2, places=8)
        self.assertAlmostEqual(coarse["effNh4"][-1], fine["effNh4"][-1], places=8)
        self.assertAlmostEqual(coarse["effCod"][-1], fine["effCod"][-1], places=8)

    def test_realtime_step_persists_latest_result(self):
        step = realtime.realtime_step(values={"Q": 10000, "COD": 420, "NH4": 32, "NO3": 0.5, "TSS": 220}, step_hours=0.5)
        latest = realtime.latest()

        self.assertEqual(step["result"]["mode"], "realtime")
        self.assertIsNotNone(latest["result"])
        self.assertEqual(latest["result"]["id"], step["resultId"])
        self.assertIn("effCod", latest["result"]["result"])

    def test_realtime_step_records_full_requested_step_hours(self):
        realtime.realtime_step(values={"Q": 10000}, step_hours=5 / 60)
        latest = realtime.latest()

        self.assertAlmostEqual(latest["result"]["stepHours"], 5 / 60)

    def test_realtime_reset_clears_state(self):
        realtime.realtime_step(values={"Q": 10000}, step_hours=0.5)
        realtime.reset()

        latest = realtime.latest()

        self.assertIsNone(latest["input"])
        self.assertIsNone(latest["state"])
        self.assertIsNone(latest["result"])

    def test_mock_values_are_complete_and_finite(self):
        values = realtime.generate_mock_values(run_count=0)

        self.assertEqual(set(values.keys()), {"Q", "COD", "NH4", "NO3", "TSS", "DO"})
        for value in values.values():
            self.assertTrue(math.isfinite(value))

    def test_mock_run_writes_input_result_and_state(self):
        result = realtime.run_mock_once()
        latest = realtime.latest()

        self.assertEqual(result["resultId"], latest["result"]["id"])
        self.assertEqual(latest["input"]["quality"]["source"], "mock")
        self.assertIsNotNone(latest["state"])

    def test_mock_start_stop_status(self):
        status = asyncio.run(realtime.start_mock(interval_seconds=300))
        self.assertTrue(status["running"])
        self.assertEqual(status["intervalSeconds"], 300)

        status = asyncio.run(realtime.stop_mock())
        self.assertFalse(status["running"])

    def test_param_config_save_load_and_reset(self):
        saved = realtime.save_params_config({**DEFAULT_PARAMS, "simulationDays": 33, "influentCod": 510})
        loaded = realtime.get_saved_params()

        self.assertEqual(saved["source"], "database")
        self.assertEqual(loaded["source"], "database")
        self.assertEqual(loaded["params"]["simulationDays"], 33)
        self.assertEqual(loaded["params"]["influentCod"], 510)

        reset = realtime.reset_params_config()
        loaded_after_reset = realtime.get_saved_params()

        self.assertEqual(reset["source"], "default")
        self.assertEqual(loaded_after_reset["source"], "default")
        self.assertEqual(loaded_after_reset["params"]["simulationDays"], DEFAULT_PARAMS["simulationDays"])

    def test_calculation_logs_save_list_and_clear(self):
        created = realtime.insert_calculation_log(
            "simulate",
            "failed",
            "test failure",
            {"reason": "unit-test"},
            12.5,
        )
        listed = realtime.list_calculation_logs()

        self.assertEqual(listed["logs"][0]["id"], created["id"])
        self.assertEqual(listed["logs"][0]["status"], "failed")
        self.assertEqual(listed["logs"][0]["detail"]["reason"], "unit-test")

        cleared = realtime.clear_calculation_logs()
        listed_after_clear = realtime.list_calculation_logs()

        self.assertEqual(cleared["deleted"], 1)
        self.assertEqual(listed_after_clear["logs"], [])

    def test_simulation_reports_progress_callback(self):
        progress = []

        result = simulate(
            params={**DEFAULT_PARAMS, "simulationDays": 1, "timeStepHours": 0.5, "outputIntervalHours": 12},
            progress_callback=lambda current, total: progress.append((current, total)),
        )

        self.assertGreaterEqual(len(progress), 2)
        self.assertEqual(progress[0], (0, 1))
        self.assertAlmostEqual(progress[-1][0], 1)
        self.assertAlmostEqual(progress[-1][1], 1)
        self.assertAlmostEqual(result["time"][-1], 1)


if __name__ == "__main__":
    unittest.main()
