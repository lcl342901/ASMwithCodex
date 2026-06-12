# Engine Testbench Development To-Do

This file tracks the standalone calculation-engine testbench work.
Update it whenever engine interfaces, scenario suites, validation criteria, reports, testbench UI, API contracts, or verification workflows change.

## Development Rule

- Before starting engine-testbench development, check this TODO list first and use it to choose the next scoped task.
- After finishing engine-testbench development, update this TODO list to reflect completed work, changed priorities, and new follow-up items.
- Keep stable setup and usage instructions in `README.md`; keep changing progress details here.
- Keep broader ASM platform work tracked separately in `docs/ASM_PLATFORM_TODO.md`.

## Current Baseline

- Source project: repository root
- Engine package: `backend/engines/`
- Engine evaluation harness: `backend/engine_testing.py`
- Testbench frontend: `frontend/engine-testbench/`
- Broader ASM platform frontend: `frontend/asm-platform/`
- Backend/API URL: `http://127.0.0.1:8000`
- Engine catalog API: `GET /api/engines`
- Engine evaluation API: `POST /api/engines/{engine_id}/evaluate`
- Standalone local file entry: `frontend/engine-testbench/index.html`
- Static-server local URL: `http://127.0.0.1:4175/engine-testbench/index.html`
- Sync command: `./scripts/sync-service.sh`
- Engineering verification:
  - `node --check frontend/engine-testbench/app.js`
  - `python3 -m unittest backend.test_model.ModelTest.test_engine_api_lists_and_evaluates_asm1 backend.test_model.ModelTest.test_asm1_engine_is_registered_and_independently_runnable`
  - `python3 -m backend.engine_testing`

## Developed

### P0 - Engine Boundary

- [x] Added `backend.engines` package with a small calculation-engine interface.
- [x] Added `EngineMetadata` and `EngineRunOptions` as the first engine contract.
- [x] Registered ASM1 v1 as an independently runnable engine.
- [x] Routed the existing v1 simulation path through the engine registry while keeping existing API behavior compatible.

### P1 - ASM1 Evaluation Harness

- [x] Added standalone ASM1 evaluation harness in `backend/engine_testing.py`.
- [x] Added reliability checks for required result keys, finite numeric outputs, matching series lengths, and runnable scenarios.
- [x] Added stability checks for repeatability, RK4 internal-step consistency, and RK4-vs-LSODA short-horizon agreement.
- [x] Added generality coverage across baseline, load, temperature, hydraulics, and oxygen stress axes.
- [x] Added backend tests for engine registration, standalone execution, catalog API, and evaluation API.

### P2 - Standalone Testbench UI

- [x] Added standalone engine-only frontend under `frontend/engine-testbench/`.
- [x] Designed the testbench as a separate desktop engineering workspace, not an embedded ASM platform page.
- [x] Added API base URL input, engine selector, catalog refresh, and run-evaluation controls.
- [x] Added engine asset view, scenario matrix, stability checks, run log, and future-model integration contract.
- [x] Removed the embedded engine-center UI from the broader ASM platform so the testbench remains independent.

## To Develop

### P3 - Evaluation Report Contract

- [x] Define a stable first-pass `EngineEvaluationReport` schema for API, CLI, frontend, and saved reports.
- [x] Add report-level fields: `runId`, `createdAt`, `engine`, `status`, `summary`, `criteria`, `warnings`, and `failures`.
- [x] Add `testLayers` to separate model-kernel, process-engine, and engineering-reference validation status.
- [x] Add scenario result fields: `scenarioId`, `axis`, `paramsDigest`, `durationMs`, `pointCount`, `finalTime`, `summary`, `issues`, and `status`.
- [x] Add stability result fields: `checkId`, `errors`, `maxRelError`, `criteria`, and `status`.
- [x] Add result-contract check details for missing fields, non-finite paths, length mismatches, time-order issues, and negative metric violations.
- [x] Add unit tests that lock the report schema shape so later UI and export work does not drift.
- [ ] Add `baseline` and `candidate` payload summaries to stability checks when report size constraints are clear.

### P4 - Scenario Pack System

- [x] Move ASM1 scenario definitions into a dedicated scenario-pack module, such as `backend/engine_scenarios/asm1.py`.
- [x] Define a reusable first-pass `EngineScenario` contract with ID, title, axis, params, expected ranges, and tags.
- [ ] Expand ASM1 fixed-parameter scenarios beyond the current five: high recycle ratio, low alkalinity, low flow, high TSS, and startup from custom state.
- [x] Add longer-horizon scenarios for 1 d, 5 d, 20 d, and selected stress cases.
- [ ] Add CSV-driven dynamic-boundary scenarios instead of only manual parameter scenarios.
- [ ] Add scenario tags for smoke, regression, stress, reference, long-horizon, and plant-data workflows.

### P5 - Reliability Checks

- [ ] Check required top-level result fields and required nested groups.
- [ ] Check all numeric outputs are finite and report the exact failing path.
- [ ] Check core time-series lengths match `time`.
- [ ] Check time is monotonic and final time matches requested horizon within tolerance.
- [ ] Check core effluent and process metrics are non-negative where physically required.
- [ ] Check output point count is consistent with horizon and output interval.
- [ ] Classify reliability failures by severity: `fail`, `needs_review`, `warning`, and `info`.

### P6 - Stability Checks

- [ ] Add repeatability check for identical input and identical solver settings.
- [ ] Add RK4 internal-step consistency check across coarse and fine requested time steps.
- [ ] Add solver consistency checks for RK4 vs LSODA, and later BDF/Radau when available for the engine path.
- [x] Add explicit long-horizon numerical stability checks for 1 d, 5 d, and 20 d.
- [ ] Add optional 50 d long-horizon stability check with runtime budget controls.
- [ ] Add parameter perturbation stability checks for `muA`, `muH`, `kNH`, `aerobicDo`, and recycle ratios.
- [ ] Add boundary shock stability checks for influent flow, COD, NH4, TSS, and DO setpoint changes.
- [ ] Define default stability thresholds per metric and per scenario type.

### P7 - Engineering Reasonableness Checks

- [ ] Add effluent range checks for COD, NH4, NO3, TN, and TSS.
- [ ] Add reactor state range checks for DO, MLSS, NO3, NH4, and RAS MLSS.
- [ ] Add clarifier sanity checks: top TSS, bottom TSS, effluent TSS, and underflow TSS ordering.
- [ ] Add process-response checks: high NH4 load should affect effluent NH4, low DO should reduce nitrification, and low temperature should reduce reaction rates.
- [ ] Add approximate mass-balance checks for COD, nitrogen, and solids where current model outputs make this practical.
- [ ] Add explicit messages that explain which engineering rule was violated and why it matters.

### P8 - Reference Cases And Benchmarks

- [x] Add the first formal BSM1 reference gate as a `needs_review` scale-only gate until mapping is ready.
- [ ] Convert the current BSM1 placeholder into a pass/fail reference-case object with mapped inputs, target window, metrics, and tolerances.
- [ ] Add support for official or trusted dynamic BSM1 input data when available.
- [ ] Add reference comparison metrics: final relative error, window average error, MAE, RMSE, and MAPE where meaningful.
- [ ] Add support for user-provided plant reference cases with CSV boundaries and observed effluent targets.
- [ ] Add pass/fail gates that prevent labeling ASM1 output as engineering-grade until reference tolerances are met.
- [ ] Add version-to-version comparison for ASM1 v1 vs later engine variants.

### P9 - Reporting And Traceability

- [x] Add JSON export for complete evaluation reports in the standalone testbench.
- [ ] Add CSV export for scenario matrix rows and stability checks.
- [ ] Add Markdown summary export for human review.
- [ ] Include run ID, timestamp, engine metadata, parameter snapshot, scenario pack version, and optional Git commit in every report.
- [ ] Store recent local evaluation runs in browser storage or a backend archive.
- [ ] Add comparison view between two evaluation reports.
- [ ] Add clear report status rules so overall `pass`, `needs_review`, and `fail` are reproducible.

### P10 - Standalone Testbench UI

- [x] Add report export control for JSON.
- [x] Add visible three-layer validation structure for model-kernel, process-engine, and engineering-reference status.
- [ ] Add report export controls for CSV and Markdown.
- [ ] Add scenario-pack selector and scenario filters by axis, tag, and duration.
- [ ] Add detail drawer for a selected scenario showing params, issues, warnings, and final metrics.
- [ ] Add stability-check detail view with per-metric error tables.
- [ ] Add engineering-rule violation panel separate from numeric stability checks.
- [ ] Add reference-case comparison panel.
- [ ] Add explicit connection states for unavailable backend, stale API, and unsupported engine IDs.
- [ ] Add loading indicators and disable repeated evaluation clicks while a run is active.
- [ ] Keep the UI standalone and engine-only; do not reintroduce ASM platform navigation, login, project library, realtime, or calibration UI.

### P11 - Automation And Regression

- [ ] Extend CLI usage for `python3 -m backend.engine_testing --engine asm1 --scenario baseline --output report.json`.
- [ ] Add backend unit tests for report schema, scenario packs, reliability checks, stability checks, and reference-case checks.
- [ ] Add browser smoke test for opening the standalone testbench, refreshing catalog, running evaluation, and verifying scenario rows.
- [ ] Add a lightweight local verify script for the engine testbench workflow.
- [ ] Add deterministic fixtures for CSV boundary scenarios and reference cases.
- [ ] Add runtime budget controls so long-horizon checks can be skipped or run explicitly.

### P12 - Future Engine Extensibility

- [ ] Define a scenario-pack interface separate from the ASM1 implementation.
- [ ] Define a result-contract profile per engine family.
- [ ] Define tolerance profiles per engine family and per scenario axis.
- [ ] Add model-specific component metadata display.
- [ ] Add a placeholder registry entry and disabled UI state for future `ASM2d_NDHA`.
- [ ] Document the minimum steps for adding a new calculation engine.
- [ ] Ensure a new engine only needs implementation, metadata, scenario pack, result contract, and tolerance profile to enter the testbench.

### Next Recommended Tasks

- [x] Stabilize the `EngineEvaluationReport` schema before adding more UI features.
- [x] Move the current ASM1 scenarios into a dedicated scenario-pack module.
- [x] Add JSON export in the standalone testbench.
- [x] Add 1 d / 5 d / 20 d long-horizon stability checks behind an explicit option.
- [x] Add the first formal BSM1 reference-case gate.
- [ ] Expand ASM1 fixed-parameter scenario coverage beyond the current five smoke scenarios.
- [ ] Turn the BSM1 reference gate from scale-only `needs_review` into mapped pass/fail tolerance gates.
- [ ] Add CSV export for scenario matrix rows and stability checks.

## Known Limits

- ASM1 equations are still largely implemented inside `backend/model.py`; the current engine package wraps the existing implementation rather than fully owning the equations.
- The L1 model-kernel layer is declared in reports but still marked `not_implemented`.
- The L3 engineering-reference layer is visible in reports and UI but remains `needs_review` / reference-only.
- Current evaluation scenarios are short-horizon smoke and consistency checks, not engineering-grade validation.
- The standalone UI depends on the backend API for real evaluation results; without a current backend it only shows a local ASM1 contract placeholder.
- There is no persisted report archive yet.
- Future engines such as `ASM2d_NDHA` do not have scenario packs, tolerance gates, or UI-specific metadata yet.
- The testbench is designed primarily as a desktop engineering tool; small-screen support is only a basic layout fallback.

## Update Rule

When engine-testbench work changes:

1. Update the relevant checklist item in this file.
2. Add a new checklist item if the change creates follow-up work.
3. Keep stable setup and usage instructions in `README.md`; keep changing progress details here.
4. Run backend unit tests when engine interfaces, APIs, evaluation logic, or report contracts change.
5. Run frontend syntax/browser checks when `frontend/engine-testbench/` changes.
6. Run `./scripts/sync-service.sh` when the runtime service copy needs to reflect source changes.
7. Check `git status --short` before handing off, so uncommitted engine-testbench changes are visible.
