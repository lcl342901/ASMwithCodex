import math
import asyncio
import os
import time
import unittest
from pathlib import Path
from backend.engine_compare import compare_engines
from backend.engine_runner import normalize_engine_version, simulate_with_engine
from backend.main import calibration_bsm1_mapping_endpoint, calibration_bsm1_report_endpoint, calibration_optimize_endpoint, calibration_preview_endpoint, calibration_stage_run_endpoint, calibration_stages_endpoint, cancel_simulation_job_endpoint, clear_project_csv_endpoint, configured_api_token, create_project_endpoint, default_project_endpoint, delete_project_calibration_run_endpoint, get_project_calibration_run_endpoint, get_project_csv_endpoint, get_project_params_endpoint, get_project_periodic_calibration_endpoint, create_simulation_job_endpoint, get_simulation_job_endpoint, get_simulation_job_result_endpoint, list_project_calibration_runs_endpoint, list_projects_endpoint, model_credibility_endpoint, model_initial_conditions_endpoint, model_metadata_endpoint, model_reference_case_compare_endpoint, model_reference_case_endpoint, model_reference_cases_endpoint, realtime_sources_endpoint, realtime_status_endpoint, request_api_token, reset_project_params_endpoint, run_project_periodic_calibration_endpoint, save_project_csv_endpoint, save_project_params_endpoint, save_project_periodic_calibration_endpoint, simulate_endpoint
from backend.model import DEFAULT_PARAMS, csv_values_at, normalize_csv_records, simulate, SimulationContext, sanitize_params
from backend.schemas import Bsm1CalibrationReportRequest, Bsm1MappingRequest, CalibrationOptimizeRequest, CalibrationPreviewRequest, CalibrationStageRunRequest, InitialConditionRequest, ModelCredibilityRequest, ParamConfigRequest, PeriodicCalibrationRunRequest, PeriodicCalibrationScheduleRequest, ProjectCsvRequest, ProjectRequest, ReferenceComparisonRequest, SimulationRequest
from backend.solver_benchmark import benchmark_v2_solvers, project_long_horizon_durations, step_consistency_report
from backend.engine_v2 import clarifier_layer_rhs, continuous_step, hybrid_step, initial_vector_state, pack_state, run_vector_simulation_v2, unpack_state, vector_snapshot
from backend import realtime
from backend.calibration import historical_replay_report


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


def rk4_params(**overrides):
    return {**DEFAULT_PARAMS, "solverMethod": "RK4", **overrides}


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
        params = rk4_params(simulationDays=1, outputIntervalHours=12, timeStepHours=1)
        result = simulate(params=params)

        self.assertTrue(REQUIRED_KEYS.issubset(result.keys()))
        self.assertEqual(result["mode"], "manual")
        self.assertGreater(len(result["time"]), 1)
        self.assertIn("warningCount", result["validation"])
        assert_finite_tree(self, result)

    def test_manual_simulation_reports_partial_results(self):
        partial_lengths = []

        def capture_partial(result):
            partial_lengths.append(len(result["time"]))

        result = simulate(
            params=rk4_params(simulationDays=0.05, outputIntervalHours=0.24, timeStepHours=0.5),
            partial_result_callback=capture_partial,
        )

        self.assertGreaterEqual(len(partial_lengths), 2)
        self.assertEqual(partial_lengths[-1], len(result["time"]))
        self.assertEqual(partial_lengths, sorted(partial_lengths))

    def test_csv_simulation_uses_requested_simulation_horizon(self):
        csv_text = Path("frontend/asm-platform/sample-data.csv").read_text(encoding="utf-8")
        params = rk4_params(simulationDays=50, outputIntervalHours=24, timeStepHours=1)

        result = simulate(params=params, csv_text=csv_text, csv_file_name="sample-data.csv")

        self.assertEqual(result["mode"], "csv")
        self.assertEqual(result["sourceName"], "sample-data.csv")
        self.assertAlmostEqual(result["time"][-1], 50, places=4)
        self.assertTrue(any("CSV 数据到" in warning for warning in result["warnings"]))

    def test_csv_holds_last_boundary_after_range(self):
        ctx = SimulationContext(params=rk4_params(timeStepHours=1))
        records = normalize_csv_records("time,Q,COD\n0,100,300\n1,200,500\n", ctx)
        cursor = {"index": 0}

        values = csv_values_at(records, 10, cursor)

        self.assertEqual(values["influentQ"], 200)
        self.assertEqual(values["influentCod"], 500)

    def test_invalid_parameter_raises_clear_error(self):
        params = rk4_params(influentQ=0)

        with self.assertRaisesRegex(ValueError, "influentQ"):
            simulate(params=params)

    def test_unusual_but_runnable_parameter_returns_warning(self):
        params = rk4_params(simulationDays=1, timeStepHours=2)

        result = simulate(params=params)

        self.assertGreater(result["validation"]["warningCount"], 0)
        self.assertTrue(any("内部求解器上限" in warning for warning in result["warnings"]))

    def test_large_requested_steps_use_same_internal_solver_step(self):
        base = rk4_params(simulationDays=2, outputIntervalHours=12)
        coarse = simulate(params={**base, "timeStepHours": 0.5})
        fine = simulate(params={**base, "timeStepHours": 0.04167})

        self.assertAlmostEqual(coarse["time"][-1], 2, places=8)
        self.assertAlmostEqual(fine["time"][-1], 2, places=8)
        self.assertAlmostEqual(coarse["effNh4"][-1], fine["effNh4"][-1], places=8)
        self.assertAlmostEqual(coarse["effCod"][-1], fine["effCod"][-1], places=8)

    def test_initial_condition_params_are_configurable(self):
        params = rk4_params(initialAnaerobicNh4=18, initialAerobicNo3=7, initialXbh=1800)
        ctx = SimulationContext(params=sanitize_params(params))
        state = ctx.create_simulation_state()

        self.assertEqual(state["anaerobic"][4], 18)
        self.assertEqual(state["aerobic"][3], 7)
        self.assertEqual(state["anoxic"][9], 1800)

    def test_model_metadata_and_reference_cases_are_available(self):
        metadata = model_metadata_endpoint()
        cases = model_reference_cases_endpoint()

        self.assertEqual(metadata["status"], "teaching_mvp_not_engineering_grade")
        self.assertIn("unitSystem", metadata)
        self.assertTrue(any(component["id"] == "S_NH" for component in metadata["asm1Components"]))
        self.assertTrue(any(case["id"] == "bsm1_alignment_placeholder" for case in cases["cases"]))

        bsm = model_reference_case_endpoint("bsm1_alignment_placeholder")
        self.assertEqual(bsm["status"], "needs_mapping")
        self.assertEqual(bsm["plant"]["averageDryWeatherFlowM3D"], 18446)
        self.assertAlmostEqual(bsm["targets"]["effNh4"]["value"], 2.5392)

    def test_reference_case_comparison_reports_errors(self):
        result = simulate_with_engine(rk4_params(simulationDays=0.05, outputIntervalHours=1))
        comparison = model_reference_case_compare_endpoint(
            "bsm1_alignment_placeholder",
            ReferenceComparisonRequest(result=result),
        )

        self.assertEqual(comparison["caseStatus"], "needs_mapping")
        self.assertEqual(comparison["comparisonStatus"], "reference_only")
        self.assertTrue(any(row["metric"] == "effNh4" for row in comparison["rows"]))
        assert_finite_tree(self, comparison)

    def test_optional_api_token_middleware(self):
        previous = os.environ.get("ASM_API_TOKEN")
        os.environ["ASM_API_TOKEN"] = "test-token"
        try:
            self.assertEqual(configured_api_token(), "test-token")

            class FakeRequest:
                def __init__(self, headers):
                    self.headers = headers

            self.assertEqual(request_api_token(FakeRequest({"authorization": "Bearer test-token"})), "test-token")
            self.assertEqual(request_api_token(FakeRequest({"x-api-key": "test-token"})), "test-token")
            self.assertEqual(request_api_token(FakeRequest({})), "")
        finally:
            if previous is None:
                os.environ.pop("ASM_API_TOKEN", None)
            else:
                os.environ["ASM_API_TOKEN"] = previous

    def test_initial_condition_endpoint_returns_state_snapshot(self):
        snapshot = model_initial_conditions_endpoint(
            InitialConditionRequest(params=rk4_params(initialAerobicNh4=3, initialXbh=1500))
        )

        self.assertEqual(snapshot["reactors"]["aerobic"][4], 3)
        self.assertEqual(snapshot["reactors"]["anaerobic"][9], 1500)
        self.assertIn("aerobic", snapshot["summary"])
        assert_finite_tree(self, snapshot)

    def test_simulation_api_attaches_credibility_report(self):
        result = simulate_with_engine(rk4_params(simulationDays=0.05, outputIntervalHours=1))

        self.assertIn("credibility", result)
        self.assertIn(result["credibility"]["status"], {"ok", "caution", "needs_review", "invalid"})
        self.assertGreaterEqual(result["credibility"]["score"], 0)
        self.assertLessEqual(result["credibility"]["score"], 100)

    def test_credibility_endpoint_flags_missing_metrics(self):
        report = model_credibility_endpoint(
            ModelCredibilityRequest(result={"time": [0, 1], "effCod": [1]}, params=rk4_params(simulationDays=1))
        )

        self.assertEqual(report["status"], "invalid")
        self.assertTrue(any(issue["code"] == "missing_metric" for issue in report["issues"]))

    def test_calibration_preview_reports_targets_and_tunables(self):
        preview = calibration_preview_endpoint(
            CalibrationPreviewRequest(
                params=rk4_params(),
                observations=[{"time": 1, "effNh4": 2.5, "effTss": 12}],
                tunableParams=["muA", "kNH"],
                targets=["effNh4", "effTss"],
            )
        )

        self.assertEqual(preview["status"], "ready")
        self.assertEqual(preview["usableObservationCount"], 1)
        self.assertEqual([item["key"] for item in preview["tunableParams"]], ["muA", "kNH"])

    def test_bsm1_mapping_endpoint_returns_three_zone_params(self):
        mapping = calibration_bsm1_mapping_endpoint(
            Bsm1MappingRequest(params={"simulationDays": 0.05, "outputIntervalHours": 1})
        )

        self.assertEqual(mapping["caseId"], "bsm1_alignment_placeholder")
        self.assertEqual(mapping["mapping"], "three_zone_aao_approximation")
        self.assertEqual(mapping["params"]["anoxicVolume"], 2000)
        self.assertEqual(mapping["params"]["aerobicVolume"], 4000)
        self.assertEqual(mapping["params"]["simulationDays"], 0.05)

    def test_bsm1_calibration_report_compares_baseline_and_optimized(self):
        report = calibration_bsm1_report_endpoint(
            Bsm1CalibrationReportRequest(
                params={"simulationDays": 0.02, "outputIntervalHours": 1},
                maxIterations=1,
                stepFraction=0.1,
            )
        )

        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["layout"], "bsm1_5tank")
        self.assertIn("baselineObjective", report)
        self.assertIn("optimizedObjective", report)
        self.assertTrue(report["rows"])
        self.assertTrue(any(row["metric"] == "effNh4" for row in report["rows"]))

    def test_calibration_stage_run_uses_stage_targets_and_tunables(self):
        stages = calibration_stages_endpoint()["stages"]
        self.assertTrue(any(stage["id"] == "nitrification" for stage in stages))

        payload = calibration_stage_run_endpoint(
            CalibrationStageRunRequest(
                stageId="nitrification",
                params={"simulationDays": 0.02, "outputIntervalHours": 1},
                observations=[{"time": 0.02, "effNh4": 2.5}],
                maxIterations=1,
                stepFraction=0.1,
            )
        )

        self.assertEqual(payload["stage"]["id"], "nitrification")
        self.assertEqual(payload["result"]["targets"], ["effNh4"])
        self.assertIn("muA", payload["result"]["tunableParams"])

    def test_calibration_optimizer_improves_or_matches_objective(self):
        baseline_params = rk4_params(simulationDays=0.03, outputIntervalHours=1, timeStepHours=0.5)
        reference = simulate_with_engine({**baseline_params, "muA": 0.8})
        observation = {"time": reference["time"][-1], "effNh4": reference["effNh4"][-1]}

        optimized = calibration_optimize_endpoint(
            CalibrationOptimizeRequest(
                params={**baseline_params, "muA": 0.3},
                observations=[observation],
                tunableParams=["muA"],
                targets=["effNh4"],
                maxIterations=1,
                stepFraction=0.5,
            )
        )

        self.assertEqual(optimized["status"], "completed")
        self.assertLessEqual(optimized["bestObjective"], optimized["initialObjective"])
        self.assertEqual(optimized["tunableParams"], ["muA"])
        self.assertGreater(len(optimized["history"]), 1)
        self.assertIn("initialObjectiveDetail", optimized)
        self.assertTrue(optimized["comparisonRows"])
        self.assertEqual(optimized["comparisonRows"][0]["metric"], "effNh4")

    def test_calibration_optimizer_can_use_bsm1_layout(self):
        optimized = calibration_optimize_endpoint(
            CalibrationOptimizeRequest(
                params={"simulationDays": 0.02, "outputIntervalHours": 1},
                observations=[{"time": 0.02, "effNh4": 2.5}],
                tunableParams=["muA"],
                targets=["effNh4"],
                maxIterations=1,
                stepFraction=0.1,
                useBsm1Layout=True,
            )
        )

        self.assertEqual(optimized["status"], "completed")
        self.assertEqual(optimized["mapping"], "bsm1_5tank")
        self.assertLessEqual(optimized["bestObjective"], optimized["initialObjective"])

    def test_calibration_optimizer_can_save_project_run(self):
        project = create_project_endpoint(ProjectRequest(name="Calibration archive"))
        optimized = calibration_optimize_endpoint(
            CalibrationOptimizeRequest(
                projectId=project["id"],
                name="NH4 calibration",
                saveRun=True,
                params={"simulationDays": 0.02, "outputIntervalHours": 1},
                observations=[{"time": 0.02, "effNh4": 2.5}],
                tunableParams=["muA"],
                targets=["effNh4"],
                maxIterations=1,
                stepFraction=0.1,
            )
        )
        saved = optimized["savedRun"]
        listed = list_project_calibration_runs_endpoint(project["id"])
        detail = get_project_calibration_run_endpoint(project["id"], saved["id"])

        self.assertEqual(saved["projectId"], project["id"])
        self.assertEqual(listed["runs"][0]["id"], saved["id"])
        self.assertEqual(detail["name"], "NH4 calibration")
        self.assertEqual(detail["request"]["projectId"], project["id"])
        self.assertEqual(detail["result"]["bestObjective"], optimized["bestObjective"])

        deleted = delete_project_calibration_run_endpoint(project["id"], saved["id"])
        self.assertEqual(deleted["deleted"], 1)
        self.assertEqual(list_project_calibration_runs_endpoint(project["id"])["runs"], [])

    def test_periodic_calibration_schedule_runs_and_archives_result(self):
        project = create_project_endpoint(ProjectRequest(name="Periodic calibration"))
        saved_schedule = save_project_periodic_calibration_endpoint(
            project["id"],
            PeriodicCalibrationScheduleRequest(
                name="Daily NH4 check",
                enabled=True,
                cadence="daily",
                dataWindowHours=24,
                stageId="nitrification",
                targets=["effNh4"],
                tunableParams=["muA"],
                maxIterations=1,
                stepFraction=0.05,
                useProjectCsv=False,
            ),
        )

        result = run_project_periodic_calibration_endpoint(
            project["id"],
            PeriodicCalibrationRunRequest(
                observations=[{"time": 0.02, "effNh4": 2.5}],
                applyBestParams=False,
            ),
        )
        schedule = get_project_periodic_calibration_endpoint(project["id"])
        runs = list_project_calibration_runs_endpoint(project["id"])

        self.assertTrue(saved_schedule["config"]["enabled"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["observationSource"], "request")
        self.assertEqual(schedule["lastRunId"], result["savedRun"]["id"])
        self.assertEqual(runs["runs"][0]["id"], result["savedRun"]["id"])
        self.assertEqual(runs["runs"][0]["method"], "coordinate_search")

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

    def test_realtime_step_without_values_reuses_latest_input_and_advances_model_time(self):
        input_record = realtime.ingest_input("2026-05-18T00:00:00+00:00", {"Q": 10000, "COD": 420}, {"source": "unit-test"})
        first = realtime.realtime_step(step_hours=1)
        second = realtime.realtime_step(step_hours=1)

        self.assertEqual(realtime.realtime_counts()["inputs"], 1)
        self.assertEqual(realtime.realtime_counts()["results"], 2)
        self.assertEqual(first["result"]["inputId"], input_record["id"])
        self.assertEqual(second["result"]["inputId"], input_record["id"])
        self.assertEqual(first["result"]["inputTimestamp"], input_record["timestamp"])
        self.assertEqual(second["result"]["inputTimestamp"], input_record["timestamp"])
        self.assertEqual(first["result"]["modelTimestamp"], "2026-05-18T01:00:00+00:00")
        self.assertEqual(second["result"]["modelTimestamp"], "2026-05-18T02:00:00+00:00")
        self.assertFalse(second["result"]["createdNewInput"])

    def test_realtime_history_returns_recent_inputs_and_results(self):
        realtime.realtime_step(values={"Q": 10000, "COD": 420}, step_hours=5 / 60)
        history = realtime.realtime_history(hours=12)

        self.assertEqual(len(history["inputs"]), 1)
        self.assertEqual(len(history["results"]), 1)
        self.assertEqual(history["results"][0]["inputId"], history["inputs"][0]["id"])
        self.assertIn("effCod", history["results"][0]["result"])

    def test_realtime_trust_compares_observations_to_results(self):
        step = realtime.realtime_step(values={"Q": 10000, "COD": 420, "NH4": 32, "NO3": 0.5, "TSS": 220}, step_hours=0.5)
        model_time = step["result"]["modelTimestamp"]
        predicted_nh4 = step["result"]["effNh4"]

        observation = realtime.insert_observation(model_time, {"NH4": predicted_nh4 + 0.4}, "unit-test")
        trust = realtime.realtime_trust(hours=12)

        self.assertEqual(observation["projectId"], "default")
        self.assertEqual(trust["observationCount"], 1)
        self.assertEqual(trust["matchedCount"], 1)
        nh4_summary = next(row for row in trust["metrics"] if row["metric"] == "effNh4")
        self.assertEqual(nh4_summary["count"], 1)
        self.assertAlmostEqual(nh4_summary["mae"], 0.4)

    def test_mock_observation_feeds_realtime_trust_trend(self):
        realtime.realtime_step(values={"Q": 10000, "COD": 300, "NH4": 25, "NO3": 0.5, "TSS": 160}, step_hours=0.5)

        observation = realtime.generate_mock_observation(noise_fraction=0)
        trust = realtime.realtime_trust(hours=12)

        self.assertEqual(observation["source"], "mock-lab")
        self.assertEqual(trust["matchedCount"], 1)
        self.assertGreaterEqual(len(trust["trend"]), 1)
        self.assertGreaterEqual(len(trust["suggestions"]), 1)

    def test_state_correction_suggests_and_applies_bias(self):
        step = realtime.realtime_step(values={"Q": 10000, "COD": 420, "NH4": 32, "NO3": 0.5, "TSS": 220, "DO": 2}, step_hours=0.5)
        model_time = step["result"]["modelTimestamp"]
        predicted_nh4 = step["result"]["effNh4"]
        realtime.insert_observation(model_time, {"NH4": predicted_nh4 + 2.0}, "unit-test")

        suggestion = realtime.suggest_state_corrections("default", hours=12)
        nh4 = next(item for item in suggestion["suggestions"] if item["metric"] == "effNh4")
        self.assertGreater(nh4["bias"], 0)

        applied = realtime.apply_suggested_state_corrections("default", hours=12)
        self.assertGreaterEqual(applied["appliedCount"], 1)
        corrected = realtime.realtime_step(step_hours=0.5)
        correction = corrected["result"].get("stateCorrection", {})

        self.assertTrue(correction.get("applied"))
        self.assertTrue(any(item["metric"] == "effNh4" for item in correction["corrections"]))

        cleared = realtime.clear_state_corrections("default")
        self.assertEqual(cleared["enabledCount"], 0)

    def test_forecast_alignment_prevents_large_tn_jump_from_latest_result(self):
        points = [
            {"metrics": {"TN": {"low": 1.4, "median": 1.7, "high": 1.9, "risk": "ok"}}},
            {"metrics": {"TN": {"low": 1.5, "median": 1.8, "high": 2.0, "risk": "ok"}}},
        ]
        aligned = realtime._align_forecast_metrics_to_current(points, {"result": {"effTn": 7.7}})

        self.assertAlmostEqual(aligned[0]["metrics"]["TN"]["median"], 7.7)
        self.assertTrue(aligned[0]["metrics"]["TN"]["alignment"]["applied"])
        self.assertGreater(aligned[1]["metrics"]["TN"]["median"], 7.7)

    def test_realtime_forecast_uses_saved_state_without_advancing_realtime_state(self):
        step = realtime.realtime_step(values={"Q": 10000, "COD": 420, "NH4": 32, "NO3": 0.5, "TSS": 220}, step_hours=0.5)
        before = realtime.latest()["state"]["timestamp"]

        forecast = realtime.realtime_forecast(horizon_hours=8, step_hours=1, history_hours=24)
        after = realtime.latest()["state"]["timestamp"]

        self.assertEqual(before, after)
        self.assertEqual(forecast["status"], "ready")
        self.assertEqual(len(forecast["points"]), 8)
        self.assertEqual(forecast["sourceResultId"], step["resultId"])
        self.assertIn("NH4", forecast["points"][0]["metrics"])
        self.assertEqual(forecast["points"][0]["metrics"]["TP"]["risk"], "unavailable")

    def test_realtime_ingest_enriches_quality_report(self):
        record = realtime.ingest_input(
            None,
            {"Q": 10000, "COD": "bad", "NH4": 32},
            {"source": "unit-test"},
        )

        self.assertEqual(record["quality"]["source"], "unit-test")
        self.assertEqual(record["quality"]["status"], "warning")
        self.assertIn("acceptedValues", record["quality"])
        self.assertTrue(any(issue["code"] == "parse_error" for issue in record["quality"]["issues"]))
        self.assertTrue(any(issue["code"] == "missing_value" for issue in record["quality"]["issues"]))

    def test_realtime_point_configs_default_mapping(self):
        configs = realtime.list_point_configs("default")

        self.assertEqual(configs["projectId"], "default")
        self.assertEqual(len(configs["points"]), 6)
        self.assertEqual(configs["points"][0]["pointId"], "IN_Q")
        self.assertEqual(configs["points"][0]["modelKey"], "influentQ")
        self.assertTrue(all(point["enabled"] for point in configs["points"]))

    def test_realtime_quality_report_includes_point_scores(self):
        record = realtime.ingest_input(
            None,
            {"Q": -10, "COD": 420, "NH4": 32, "NO3": 0.5, "TSS": 220, "DO": 2},
            {"source": "unit-test"},
        )

        q_field = record["quality"]["fieldQuality"]["influentQ"]
        self.assertEqual(q_field["pointId"], "IN_Q")
        self.assertEqual(q_field["pointName"], "进水流量")
        self.assertLess(q_field["score"], 100)
        self.assertEqual(record["quality"]["pointConfigs"][0]["modelKey"], "influentQ")

    def test_realtime_quality_score_summary_returns_current_and_trend(self):
        realtime.ingest_input(
            None,
            {"Q": 10000, "COD": 420, "NH4": 32, "NO3": 0.5, "TSS": 220, "DO": 2},
            {"source": "unit-test"},
        )

        summary = realtime.realtime_quality_score("default", hours=12)

        self.assertEqual(summary["projectId"], "default")
        self.assertEqual(summary["current"]["score"], 100.0)
        self.assertEqual(summary["current"]["scoreLabel"], "可信")
        self.assertEqual(len(summary["current"]["pointScores"]), 6)
        self.assertGreaterEqual(summary["rolling"]["recordCount"], 1)
        self.assertTrue(summary["rolling"]["trend"])

    def test_historical_replay_report_compares_observations(self):
        csv_text = Path("frontend/asm-platform/sample-data.csv").read_text()
        report = historical_replay_report(
            params={**DEFAULT_PARAMS, "simulationDays": 2, "outputIntervalHours": 6},
            csv_text=csv_text,
            csv_file_name="sample-data.csv",
            observations=[
                {"time": 1, "effNh4": 2.5, "effTn": 15},
                {"time": 2, "effNh4": 2.7, "effTn": 14.5},
            ],
            targets=["effNh4", "effTn"],
        )

        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["method"], "historical_replay")
        self.assertEqual(report["observationCount"], 2)
        self.assertEqual(report["matchedCount"], 4)
        self.assertEqual({row["metric"] for row in report["metrics"]}, {"effNh4", "effTn"})
        self.assertTrue(report["suggestions"])

    def test_realtime_cleaning_rules_can_disable_checks(self):
        realtime.save_cleaning_settings("default", ["missing_fill"])
        record = realtime.ingest_input(
            None,
            {"Q": -10, "COD": "bad", "NH4": 32},
            {"source": "unit-test"},
        )

        self.assertEqual(record["quality"]["acceptedValues"]["influentQ"], -10)
        self.assertFalse(any(issue["code"] == "parse_error" for issue in record["quality"]["issues"]))
        self.assertFalse(any(issue["code"] == "out_of_range_clipped" for issue in record["quality"]["issues"]))
        self.assertTrue(any(issue["code"] == "missing_value" for issue in record["quality"]["issues"]))

    def test_realtime_step_clips_out_of_range_values(self):
        step = realtime.realtime_step(
            values={"Q": -10, "COD": 420, "NH4": 32, "NO3": 0.5, "TSS": 220, "DO": 99},
            quality={"source": "unit-test"},
            step_hours=5 / 60,
        )

        quality = step["input"]["quality"]
        self.assertEqual(quality["status"], "warning")
        self.assertEqual(quality["acceptedValues"]["influentQ"], 1)
        self.assertEqual(quality["acceptedValues"]["aerobicDo"], 10)
        self.assertTrue(any(issue["code"] == "out_of_range_clipped" for issue in quality["issues"]))
        self.assertIn("quality", step["result"])

    def test_realtime_sources_and_status_monitor(self):
        sources = realtime_sources_endpoint()
        self.assertTrue(any(source["id"] == "manual" for source in sources["sources"]))
        self.assertTrue(any(source["id"] == "mock" for source in sources["sources"]))

        step = realtime.realtime_step(
            values={"Q": 10000, "COD": 420, "NH4": 32, "NO3": 0.5, "TSS": 220, "DO": 2},
            quality={"source": "external-test"},
            step_hours=5 / 60,
        )
        status = realtime_status_endpoint()

        self.assertIn(status["status"], {"ready", "mock_running"})
        self.assertEqual(status["qualityStatus"], "ok")
        self.assertEqual(status["latestInput"]["id"], step["input"]["id"])
        self.assertEqual(status["latestResult"]["id"], step["resultId"])
        self.assertEqual(status["counts"]["inputs"], 1)
        self.assertEqual(status["counts"]["results"], 1)
        self.assertGreaterEqual(status["scheduler"]["lastInputAgeSeconds"], 0)
        self.assertEqual(status["latestInput"]["quality"]["sourceInfo"]["kind"], "external")

    def test_realtime_records_are_project_scoped(self):
        project = create_project_endpoint(ProjectRequest(name="Realtime scope"))
        default_step = realtime.realtime_step(values={"Q": 10000, "COD": 420}, step_hours=5 / 60)
        project_step = realtime.realtime_step(
            values={"Q": 12000, "COD": 500},
            quality={"source": "unit-test"},
            step_hours=5 / 60,
            project_id=project["id"],
        )

        default_latest = realtime.latest()
        project_latest = realtime.latest(project["id"])

        self.assertEqual(default_latest["projectId"], "default")
        self.assertEqual(project_latest["projectId"], project["id"])
        self.assertEqual(default_latest["result"]["id"], default_step["resultId"])
        self.assertEqual(project_latest["result"]["id"], project_step["resultId"])
        self.assertEqual(realtime.realtime_counts()["results"], 1)
        self.assertEqual(realtime.realtime_counts(project["id"])["results"], 1)

        realtime.clear_calculation_logs()
        log = realtime.insert_calculation_log("unit", "success", "project log", project_id=project["id"])
        self.assertEqual(log["projectId"], project["id"])
        self.assertEqual(realtime.list_calculation_logs(project_id=project["id"])["logs"][0]["id"], log["id"])
        self.assertEqual(realtime.list_calculation_logs()["logs"], [])

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

    def test_project_api_creates_default_and_isolates_params(self):
        default_project = default_project_endpoint()
        listed = list_projects_endpoint()

        self.assertEqual(default_project["id"], "default")
        self.assertTrue(any(project["id"] == "default" for project in listed["projects"]))

        project = create_project_endpoint(ProjectRequest(name="Calibration study", description="Unit test"))
        saved_default = save_project_params_endpoint(
            "default",
            ParamConfigRequest(params={**DEFAULT_PARAMS, "simulationDays": 11}),
        )
        saved_project = save_project_params_endpoint(
            project["id"],
            ParamConfigRequest(params={**DEFAULT_PARAMS, "simulationDays": 22}),
        )

        self.assertEqual(saved_default["params"]["simulationDays"], 11)
        self.assertEqual(saved_project["params"]["simulationDays"], 22)
        self.assertEqual(get_project_params_endpoint("default")["params"]["simulationDays"], 11)
        self.assertEqual(get_project_params_endpoint(project["id"])["params"]["simulationDays"], 22)

        reset = reset_project_params_endpoint(project["id"])
        self.assertEqual(reset["source"], "default")
        self.assertEqual(get_project_params_endpoint(project["id"])["params"]["simulationDays"], DEFAULT_PARAMS["simulationDays"])

    def test_project_csv_is_scoped_and_clearable(self):
        project = create_project_endpoint(ProjectRequest(name="CSV scope"))
        saved = save_project_csv_endpoint(
            project["id"],
            ProjectCsvRequest(csvFileName="unit.csv", csvText="time,Q,COD\n0,10000,420\n"),
        )
        default_csv = get_project_csv_endpoint("default")
        loaded = get_project_csv_endpoint(project["id"])

        self.assertEqual(saved["csvFileName"], "unit.csv")
        self.assertEqual(default_csv["source"], "none")
        self.assertEqual(loaded["source"], "database")
        self.assertIn("COD", loaded["csvText"])

        cleared = clear_project_csv_endpoint(project["id"])
        self.assertEqual(cleared["status"], "cleared")
        self.assertEqual(get_project_csv_endpoint(project["id"])["source"], "none")

    def test_default_solver_is_rk4(self):
        result = simulate(params={**DEFAULT_PARAMS, "simulationDays": 0.1, "outputIntervalHours": 6, "timeStepHours": 0.5})

        self.assertEqual(result["solverMethod"], "RK4")

    def test_lsoda_simulation_returns_finite_values(self):
        result = simulate(params={**DEFAULT_PARAMS, "solverMethod": "LSODA", "simulationDays": 0.25, "outputIntervalHours": 6, "timeStepHours": 0.5})

        self.assertEqual(result["solverMethod"], "LSODA")
        self.assertEqual(result["mode"], "manual")
        self.assertAlmostEqual(result["time"][-1], 0.25)
        assert_finite_tree(self, result)

    def test_lsoda_step_consistency_when_coupling_step_matches(self):
        base = {**DEFAULT_PARAMS, "solverMethod": "LSODA", "simulationDays": 0.25, "outputIntervalHours": 6, "maxSolverStepHours": 0.04167}
        coarse = simulate(params={**base, "timeStepHours": 0.5})
        fine = simulate(params={**base, "timeStepHours": 0.04167})

        self.assertAlmostEqual(coarse["effNh4"][-1], fine["effNh4"][-1], places=5)

    def test_invalid_solver_method_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "solverMethod"):
            simulate(params={**DEFAULT_PARAMS, "solverMethod": "VODE", "simulationDays": 0.1})

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
            params=rk4_params(simulationDays=1, timeStepHours=0.5, outputIntervalHours=12),
            progress_callback=lambda current, total: progress.append((current, total)),
        )

        self.assertGreaterEqual(len(progress), 2)
        self.assertEqual(progress[0], (0, 1))
        self.assertAlmostEqual(progress[-1][0], 1)
        self.assertAlmostEqual(progress[-1][1], 1)
        self.assertAlmostEqual(result["time"][-1], 1)

    def test_engine_v2_state_vector_round_trips_current_state(self):
        ctx = SimulationContext(params=rk4_params())
        state = ctx.create_simulation_state()
        layout, vector = initial_vector_state(ctx)
        unpacked = unpack_state(vector, layout)

        self.assertEqual(layout.size, 13 * 4 + int(DEFAULT_PARAMS["clarifierLayers"]))
        self.assertEqual(vector, pack_state(unpacked, layout))
        self.assertEqual(unpacked["anaerobic"], state["anaerobic"])
        self.assertEqual(unpacked["clarifierLayers"], state["clarifierLayers"])

    def test_engine_v2_hybrid_step_returns_finite_vector_and_split(self):
        ctx = SimulationContext(params=rk4_params())
        layout, vector = initial_vector_state(ctx)
        influent = ctx.influent_vector()

        next_vector, split = hybrid_step(ctx, vector, influent, layout, 0.0005)
        snapshot = vector_snapshot(ctx, next_vector, layout)

        self.assertEqual(len(next_vector), layout.size)
        self.assertIn("eff", split)
        assert_finite_tree(self, next_vector)
        assert_finite_tree(self, snapshot)
        self.assertNotEqual(vector, next_vector)

    def test_engine_v2_clarifier_rhs_matches_discrete_takacs_derivative(self):
        ctx = SimulationContext(params=rk4_params())
        state = ctx.create_simulation_state()
        layers = state["clarifierLayers"]
        inlet = state["aerobic"]
        dt = 1e-6
        q = ctx.params["influentQ"]
        ras_q = q * ctx.params["rasRatio"]
        was_q = min(ctx.params["wasQ"], q * 0.8)
        capture = min(max(ctx.params["captureEfficiency"] / 100, 0.8), 0.9995)

        rhs = clarifier_layer_rhs(ctx, layers, inlet)
        discrete = ctx.takacs_clarifier_step(layers, inlet, q + ras_q, ras_q, was_q, dt, capture)

        for index, derivative in enumerate(rhs):
            self.assertAlmostEqual(layers[index] + derivative * dt, discrete["layers"][index], places=8)

    def test_engine_v2_continuous_step_returns_finite_vector_and_split(self):
        ctx = SimulationContext(params=rk4_params())
        layout, vector = initial_vector_state(ctx)
        influent = ctx.influent_vector()

        next_vector, split = continuous_step(ctx, vector, influent, layout, 0.0005)
        snapshot = vector_snapshot(ctx, next_vector, layout)

        self.assertEqual(len(next_vector), layout.size)
        self.assertIn("under", split)
        assert_finite_tree(self, next_vector)
        assert_finite_tree(self, snapshot)
        self.assertNotEqual(vector, next_vector)

    def test_engine_v2_manual_run_returns_frontend_shape(self):
        ctx = SimulationContext(params=rk4_params(simulationDays=0.1, timeStepHours=0.5, outputIntervalHours=2))

        result = run_vector_simulation_v2(ctx)

        self.assertTrue(REQUIRED_KEYS.issubset(result.keys()))
        self.assertEqual(result["engineVersion"], "v2")
        self.assertEqual(result["mode"], "manual")
        self.assertAlmostEqual(result["time"][-1], 0.1)
        self.assertGreater(len(result["time"]), 1)
        assert_finite_tree(self, result)

    def test_engine_v2_csv_run_uses_requested_horizon(self):
        csv_text = Path("frontend/asm-platform/sample-data.csv").read_text(encoding="utf-8")
        ctx = SimulationContext(params=rk4_params(simulationDays=0.2, timeStepHours=0.5, outputIntervalHours=2), source_name="sample-data.csv")
        records = normalize_csv_records(csv_text, ctx)

        result = run_vector_simulation_v2(ctx, records)

        self.assertEqual(result["engineVersion"], "v2")
        self.assertEqual(result["mode"], "csv")
        self.assertEqual(result["sourceName"], "sample-data.csv")
        self.assertAlmostEqual(result["time"][-1], 0.2)
        assert_finite_tree(self, result)

    def test_engine_v2_reports_progress_callback(self):
        progress = []
        ctx = SimulationContext(
            params=rk4_params(simulationDays=0.1, timeStepHours=0.5, outputIntervalHours=2),
            progress_callback=lambda current, total: progress.append((current, total)),
        )

        run_vector_simulation_v2(ctx)

        self.assertGreaterEqual(len(progress), 2)
        self.assertEqual(progress[0], (0, 0.1))
        self.assertAlmostEqual(progress[-1][0], 0.1)
        self.assertAlmostEqual(progress[-1][1], 0.1)

    def test_engine_compare_manual_returns_error_tables(self):
        comparison = compare_engines(rk4_params(simulationDays=0.1, timeStepHours=0.5, outputIntervalHours=2))

        self.assertEqual(comparison["engineComparison"], "v1_vs_v2")
        self.assertEqual(comparison["mode"], "manual")
        self.assertAlmostEqual(comparison["time"]["v1Final"], 0.1)
        self.assertAlmostEqual(comparison["time"]["v2Final"], 0.1)
        self.assertEqual([row["metric"] for row in comparison["effluentErrors"]], ["effCod", "effNh4", "effNo3", "effTn", "effTss"])
        self.assertEqual([row["metric"] for row in comparison["clarifierErrors"]], ["topTss", "middleTss", "bottomTss", "effluentTss", "underflowTss"])
        self.assertIn(comparison["apiReadiness"]["status"], {"candidate", "needs_review"})
        self.assertIn("v1", comparison["results"])
        self.assertIn("v2", comparison["results"])
        assert_finite_tree(self, comparison)

    def test_engine_compare_csv_returns_error_tables(self):
        csv_text = Path("frontend/asm-platform/sample-data.csv").read_text(encoding="utf-8")
        comparison = compare_engines(
            rk4_params(simulationDays=0.2, timeStepHours=0.5, outputIntervalHours=2),
            csv_text=csv_text,
            csv_file_name="sample-data.csv",
        )

        self.assertEqual(comparison["mode"], "csv")
        self.assertEqual(comparison["sourceName"], "sample-data.csv")
        self.assertAlmostEqual(comparison["time"]["v1Final"], 0.2)
        self.assertAlmostEqual(comparison["time"]["v2Final"], 0.2)
        self.assertGreater(len(comparison["effluentErrors"]), 0)
        self.assertGreater(len(comparison["clarifierErrors"]), 0)
        assert_finite_tree(self, comparison)

    def test_engine_runner_defaults_to_v1_and_accepts_v2(self):
        v1 = simulate_with_engine(rk4_params(simulationDays=0.05, timeStepHours=0.5, outputIntervalHours=1))
        v2 = simulate_with_engine(rk4_params(engineVersion="v2", simulationDays=0.05, timeStepHours=0.5, outputIntervalHours=1))

        self.assertEqual(v1["engineVersion"], "v1")
        self.assertEqual(v2["engineVersion"], "v2")
        self.assertEqual(normalize_engine_version({"engineVersion": "2"}), "v2")
        assert_finite_tree(self, v1)
        assert_finite_tree(self, v2)

    def test_engine_runner_accepts_bsm1_layout(self):
        result = simulate_with_engine(
            rk4_params(engineVersion="bsm1", simulationDays=0.03, timeStepHours=0.5, outputIntervalHours=1)
        )

        self.assertEqual(result["engineVersion"], "bsm1")
        self.assertEqual(result["layout"]["id"], "bsm1_5tank")
        self.assertEqual(result["layout"]["tankOrder"], ["anoxic1", "anoxic2", "aerobic1", "aerobic2", "aerobic3"])
        self.assertIn("bsm1Units", result)
        self.assertAlmostEqual(result["time"][-1], 0.03)
        assert_finite_tree(self, result)

    def test_engine_runner_rejects_unknown_engine_version(self):
        with self.assertRaisesRegex(ValueError, "engineVersion"):
            simulate_with_engine(rk4_params(engineVersion="v3", simulationDays=0.05))

    def test_v2_accepts_adaptive_solvers_while_v1_rejects_them(self):
        for solver in ["LSODA", "BDF", "RADAU"]:
            result = simulate_with_engine(
                rk4_params(
                    engineVersion="v2",
                    solverMethod=solver,
                    simulationDays=0.02,
                    timeStepHours=0.5,
                    outputIntervalHours=1,
                    maxSolverStepHours=0.05,
                )
            )

            self.assertEqual(result["engineVersion"], "v2")
            self.assertEqual(result["solverMethod"], solver)
            self.assertAlmostEqual(result["time"][-1], 0.02)
            assert_finite_tree(self, result)

        with self.assertRaisesRegex(ValueError, "solverMethod"):
            simulate_with_engine(rk4_params(solverMethod="BDF", simulationDays=0.02))

    def test_v2_solver_benchmark_returns_timing_and_recommendation(self):
        report = benchmark_v2_solvers(
            rk4_params(timeStepHours=0.5, outputIntervalHours=1, maxSolverStepHours=0.05),
            solvers=["RK4", "LSODA"],
            horizons=[0.02],
        )

        self.assertEqual(report["engineVersion"], "v2")
        self.assertEqual(report["solvers"], ["RK4", "LSODA"])
        self.assertEqual(report["horizons"], [0.02])
        self.assertEqual(len(report["runs"]), 2)
        self.assertIn("defaultSolver", report["recommendation"])
        for run in report["runs"]:
            self.assertGreaterEqual(run["durationMs"], 0)
            self.assertEqual(run["finalTime"], 0.02)
            self.assertGreater(len(run["errorsVsRk4"]), 0)
        assert_finite_tree(self, report)

    def test_v2_long_horizon_projection_report(self):
        benchmark = benchmark_v2_solvers(
            rk4_params(timeStepHours=0.5, outputIntervalHours=1, maxSolverStepHours=0.05),
            solvers=["RK4"],
            horizons=[0.02],
        )
        projection = project_long_horizon_durations(benchmark, target_horizons=[20, 50, 100])

        self.assertEqual(projection["type"], "duration_projection")
        self.assertEqual(projection["targetHorizons"], [20, 50, 100])
        self.assertEqual(len(projection["projections"]), 3)
        self.assertTrue(all(row["projectionMethod"] == "linear_by_simulation_days" for row in projection["projections"]))
        assert_finite_tree(self, projection)

    def test_v2_step_consistency_report(self):
        report = step_consistency_report(
            rk4_params(outputIntervalHours=1, maxSolverStepHours=0.05),
            solver="RK4",
            time_steps_hours=[0.5, 0.04167],
            horizon_days=0.05,
        )

        self.assertEqual(report["engineVersion"], "v2")
        self.assertEqual(report["solverMethod"], "RK4")
        self.assertEqual(report["timeStepsHours"], [0.5, 0.04167])
        self.assertIn(report["status"], {"consistent", "needs_review"})
        self.assertEqual(len(report["runs"]), 2)
        assert_finite_tree(self, report)

    def test_simulate_api_accepts_v2_engine_version(self):
        result = simulate_endpoint(
            SimulationRequest(params=rk4_params(engineVersion="v2", simulationDays=0.05, timeStepHours=0.5, outputIntervalHours=1))
        )

        self.assertEqual(result["engineVersion"], "v2")
        self.assertEqual(result["mode"], "manual")
        self.assertAlmostEqual(result["time"][-1], 0.05)

    def test_simulate_api_reuses_project_final_state(self):
        params = rk4_params(simulationDays=0.02, timeStepHours=0.5, outputIntervalHours=0.24)
        first = simulate_endpoint(SimulationRequest(projectId="stateful-project", params=params))
        second = simulate_endpoint(SimulationRequest(projectId="stateful-project", params=params))

        self.assertIn("finalState", first)
        self.assertFalse(first["statePersistence"]["usedPreviousState"])
        self.assertTrue(first["statePersistence"]["savedFinalState"])
        self.assertTrue(second["statePersistence"]["usedPreviousState"])
        self.assertTrue(second["statePersistence"]["savedFinalState"])
        self.assertAlmostEqual(second["units"]["aerobic"]["NH4"][0], first["units"]["aerobic"]["NH4"][-1], places=6)

    def test_simulation_job_api_records_v2_engine_version(self):
        job = create_simulation_job_endpoint(
            SimulationRequest(params=rk4_params(engineVersion="v2", simulationDays=0.05, timeStepHours=0.5, outputIntervalHours=1))
        )

        self.assertEqual(job["engineVersion"], "v2")
        job_id = job["jobId"]

        final_job = job
        for _ in range(50):
            final_job = get_simulation_job_endpoint(job_id)
            if final_job["status"] in {"success", "failed"}:
                break
            time.sleep(0.05)

        self.assertEqual(final_job["status"], "success")
        self.assertEqual(get_simulation_job_result_endpoint(job_id)["engineVersion"], "v2")

    def test_simulation_job_can_be_cancelled(self):
        job = create_simulation_job_endpoint(
            SimulationRequest(params=rk4_params(simulationDays=10, timeStepHours=0.5, outputIntervalHours=0.5))
        )
        cancel = cancel_simulation_job_endpoint(job["jobId"])
        self.assertTrue(cancel["cancelRequested"])

        final_job = cancel
        for _ in range(80):
            final_job = get_simulation_job_endpoint(job["jobId"])
            if final_job["status"] in {"cancelled", "success", "failed"}:
                break
            time.sleep(0.05)

        self.assertEqual(final_job["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
