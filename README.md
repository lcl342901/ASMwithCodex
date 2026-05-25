# ASMwithCodex AAO Simulator

This project is a browser-based AAO/A2O wastewater process simulator prototype.
It is intended as a learning and experimentation platform for ASM1-based process simulation.

## Current Features

- Static frontend that runs directly in the browser.
- AAO process layout with:
  - Influent
  - Anaerobic reactor
  - Anoxic reactor
  - Aerobic reactor
  - Secondary clarifier
  - RAS return sludge
  - WAS waste sludge
  - Effluent
- ASM1-style biological reaction model with 13 components.
- Three CSTR reactors for anaerobic, anoxic, and aerobic zones.
- 10-layer Takacs-style secondary clarifier model.
- RAS/WAS closed-loop sludge handling.
- Editable operating, process, ASM1, influent fractionation, and clarifier parameters.
- CSV historical data upload and replay.
- Interactive charts with hover tooltips.
- Unit-level process curves after clicking a process unit.
- Backend parameter/model validation with returned warnings.
- Model metadata, unit-system, initial-condition, credibility screening, and calibration-preview APIs.
- CSV export for effluent/process results, boundary inputs, and unit-level series.
- JSON export/import for simulation configuration.
- Realtime MVP API with SQLite-backed input, model state, and latest result storage.
- Optional API token protection for online deployment experiments.

## Files

- `index.html`: main UI.
- `styles.css`: layout and visual styling.
- `app.js`: ASM1 model, clarifier model, CSV replay, chart rendering, and UI logic.
- `sample-data.csv`: example CSV that can be uploaded directly.
- `backend/main.py`: FastAPI app and `/api/simulate` route.
- `backend/model.py`: Python ASM1, AAO, RAS/WAS, Takacs clarifier, and CSV replay engine.
- `backend/model_trust.py`: model metadata, unit notes, initial-condition snapshots, credibility screening, and calibration preview helpers.
- `backend/schemas.py`: API request schema.
- `backend/requirements.txt`: backend Python dependencies.
- `docs/PRODUCTION_READINESS.md`: production readiness notes for API token, database, workers, and user/project isolation.

## API Token For Deployment Experiments

Local development does not require authentication by default. If the backend environment variable `ASM_API_TOKEN` is set, every API route except `GET /api/health` requires one of:

```text
Authorization: Bearer <token>
X-API-Key: <token>
```

See `docs/PRODUCTION_READINESS.md` before exposing the service beyond localhost.

## Local AI Analysis Key

The result page can call a backend AI proxy to generate simulation analysis and operating suggestions. The frontend never stores or sends a third-party API key. Configure the key only in the backend runtime environment:

```bash
export DEEPSEEK_API_KEY="..."
```

For local development, you can also create `backend/.env`:

```text
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_API_URL=https://api.deepseek.com/chat/completions
```

`.env` and `backend/.env` are ignored by Git. The status endpoint `GET /api/ai/status` reports only whether a key is configured; it never returns the key.

## How To Run

Start the backend first:

```bash
cd aao-simulator
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Then open `index.html` in a browser. The static frontend calls:

```text
http://127.0.0.1:8000/api/simulate
```

The page still contains the original JavaScript model as a reference path, but the `Run Simulation` button now uses the Python/FastAPI backend.

## Persistent Backend Service

On this Mac, the backend can also run as a user-level `launchd` service. This keeps the API running after the terminal window is closed and starts it again after login.

The service runtime copy is located at:

```text
/Users/chenglin/aao-simulator-service
```

The tracked LaunchAgent template is:

```text
deploy/com.asmwithcodex.backend.plist
```

Installed plist location:

```text
/Users/chenglin/Library/LaunchAgents/com.asmwithcodex.backend.plist
```

Useful commands:

```bash
# Sync project backend code to the persistent service and restart it
./scripts/sync-service.sh

# Start or restart
launchctl kickstart -k gui/501/com.asmwithcodex.backend

# Stop and unload
launchctl bootout gui/501/com.asmwithcodex.backend

# Load again after unloading
launchctl bootstrap gui/501 /Users/chenglin/Library/LaunchAgents/com.asmwithcodex.backend.plist

# Inspect status
launchctl print gui/501/com.asmwithcodex.backend

# Check API health
curl http://127.0.0.1:8000/api/health
```

Logs:

```text
/private/tmp/aao-fastapi.log
/private/tmp/aao-fastapi.err.log
```

If backend code changes in the project directory, run `./scripts/sync-service.sh`. It copies `backend/` into `/Users/chenglin/aao-simulator-service/`, updates dependencies, installs the LaunchAgent plist, restarts the service, and checks `/api/health`.

## API

### `POST /api/simulate`

Request body:

```json
{
  "params": {
    "influentQ": 10000,
    "influentCod": 420,
    "influentNh4": 32,
    "influentNo3": 0.5,
    "influentTss": 220,
    "simulationDays": 20,
    "timeStepHours": 0.5,
    "outputIntervalHours": 6,
    "engineVersion": "v1",
    "solverMethod": "RK4",
    "solverRtol": 0.0001,
    "solverAtol": 0.000001,
    "maxSolverStepHours": 0.05
  },
  "csvText": "time,Q,COD,NH4,...",
  "csvFileName": "sample-data.csv"
}
```

`params` may include any current frontend parameter. `engineVersion` defaults to `v1`; `v2` is available as an experimental API-only path for comparing the new state-vector engine. `csvText` is optional. When `csvText` is provided, it is used as a boundary-condition time series, while `params.simulationDays` still controls the total simulation horizon.

The response is compatible with the frontend `lastResult` structure, including:

```text
time, effCod, effNh4, effNo3, effTn, effTss,
anaerobicNo3, anoxicNo3, aerobicNo3,
aerobicDo, aerobicMlss, rasMlss,
boundaries, units, clarifier, mode, sourceName, engineVersion,
solverMethod, warnings, validation
```

Simulation responses from the engine runner also include `credibility`, a heuristic screening report with `status`, `score`, and review issues. This is not a calibrated compliance check; it is meant to highlight obvious interpretation risks.

Invalid parameters return `400` with a clear message. Suspicious but runnable settings, such as very high clarifier overflow or a requested solver step above the internal cap, return as `warnings` in the normal response.

The frontend uses asynchronous simulation jobs for real progress updates:

```http
POST /api/simulate/jobs
GET  /api/simulate/jobs/{jobId}
GET  /api/simulate/jobs/{jobId}/result
POST /api/simulate/jobs/{jobId}/cancel
```

The job status includes `status`, `progressPercent`, `currentTime`, `totalTime`, `message`, `error`, and partial result fields for progressive chart updates. `POST /api/simulate/jobs/{jobId}/cancel` marks a running job for cooperative cancellation; the model stops at the next progress/output checkpoint. The original synchronous `POST /api/simulate` remains available for API callers that want a blocking request/response flow.

## Model Trust And Calibration APIs

The current model is still a teaching MVP, so the backend exposes a small trust layer to make assumptions and readiness visible:

```http
GET  /api/model/metadata
GET  /api/model/reference-cases
GET  /api/model/reference-cases/{caseId}
POST /api/model/reference-cases/{caseId}/compare
POST /api/model/initial-conditions
POST /api/model/credibility
POST /api/calibration/preview
POST /api/calibration/bsm1/mapping
POST /api/calibration/bsm1/report
GET  /api/calibration/stages
POST /api/calibration/stages/run
POST /api/calibration/optimize
```

- `/api/model/metadata` returns the unit system, ASM1 component list, available metrics, initial-condition keys, recommended calibration parameters, and current assumptions.
- `/api/model/reference-cases` returns the internal default AAO regression case and a BSM1 reference target set from the Lund University/IWA Task Group report.
- `/api/model/reference-cases/{caseId}/compare` compares supplied simulation results against a reference target table. The BSM1 comparison is marked `reference_only` because BSM1 uses two anoxic and three aerobic reactors, while this platform currently uses a three-zone AAO layout.
- `/api/model/initial-conditions` returns the reactor and clarifier initial state generated from the supplied parameters.
- `/api/model/credibility` screens a result object and returns heuristic issues such as missing metrics, horizon mismatch, high effluent TSS, or experimental-engine use.
- `/api/calibration/preview` validates calibration targets, observations, and tunable parameters, and returns the weighted-RMSE setup that a later optimizer will use.
- `/api/calibration/bsm1/mapping` returns a BSM1-to-current-AAO parameter mapping. It approximates BSM1's two anoxic and three aerobic tanks by using a minimal anaerobic selector, `2000 m3` anoxic volume, and `4000 m3` aerobic volume in the current three-zone model.
- `/api/calibration/bsm1/report` runs a BSM1 baseline-vs-target report. It compares baseline effluent metrics with the BSM1 reference targets, runs a short coordinate-search calibration, and returns baseline/optimized/target rows for inspection.
- `/api/calibration/stages` and `/api/calibration/stages/run` expose staged calibration presets for nitrification/NH4, denitrification/TN, COD/BOD, and clarifier/TSS.
- `/api/calibration/optimize` runs a first-pass coordinate-search calibration against supplied observations or, when `useBsm1Mapping` is enabled, the BSM1 reference targets.

Initial conditions can now be supplied as parameters, for example `initialAerobicNh4`, `initialAerobicNo3`, `initialXbh`, `initialXi`, and related `initial*` keys. If `aerobicDo` is provided but `initialAerobicDo` is omitted, the backend keeps the previous behavior by using the aerobic DO setting as the initial aerobic DO.

The built-in BSM1 target set currently stores the 2008 closed-loop dynamic effluent averages: COD 48.2201 gCOD/m3, NH4-N 2.5392 gN/m3, NO3-N 12.4199 gN/m3, TN 16.9245 gN/m3, TSS 13.0038 g/m3, and BOD5 2.7568 g/m3. Source: [Benchmark Simulation Model no. 1 (BSM1), Lund University report LTH-IEA-7229](https://www.iea.lth.se/publications/Reports/LTH-IEA-7229.pdf).

Example calibration request:

```json
{
  "params": {
    "simulationDays": 2,
    "outputIntervalHours": 1
  },
  "observations": [
    { "time": 2, "effNh4": 2.5, "effTss": 13.0 }
  ],
  "tunableParams": ["muA", "kNH"],
  "targets": ["effNh4", "effTss"],
  "maxIterations": 2,
  "stepFraction": 0.1
}
```

The optimizer currently uses a bounded coordinate search. It is intentionally conservative and deterministic so calibration experiments are easy to inspect before introducing heavier optimizers. Optimization responses include `initialObjectiveDetail`, `objectiveDetail`, and `comparisonRows` so the frontend can show observed values, initial predictions, optimized predictions, and residual improvement for each calibration point.

Calibration runs can now be saved into the active project:

```http
GET    /api/projects/{projectId}/calibration-runs
GET    /api/projects/{projectId}/calibration-runs/{runId}
DELETE /api/projects/{projectId}/calibration-runs/{runId}
```

Set `saveRun: true` in `/api/calibration/optimize` to archive the request and result. The frontend includes a compact `校准` workspace that can run a quick NH4 calibration for the active project, upload observation CSV data, and list saved calibration records.

Observation CSV files in the calibration workspace should include a time column (`time`, `day`, `timestamp`, etc.) plus one or more effluent target columns such as `effNh4`, `effCod`, `effNo3`, `effTn`, `effTss`, or `BOD5`. When observation data is loaded, the frontend uses those rows as calibration targets; otherwise it falls back to a built-in NH4 quick-check target.

For a closer BSM1 structural experiment, `POST /api/simulate` also accepts:

```json
{
  "params": {
    "engineVersion": "bsm1",
    "simulationDays": 2,
    "outputIntervalHours": 1
  }
}
```

`engineVersion: "bsm1"` runs a dedicated five-tank layout: two anoxic tanks followed by three aerobic tanks and the existing 10-layer clarifier. It is still experimental, but it avoids collapsing BSM1 into the ordinary three-zone AAO structure.

## Realtime MVP API

The realtime layer stores inputs, model state, and latest step results in SQLite:

```text
backend/realtime.db
```

Available endpoints:

```http
POST /api/realtime/ingest
POST /api/realtime/step
GET  /api/realtime/latest
GET  /api/realtime/history
GET  /api/realtime/sources
GET  /api/realtime/status
POST /api/realtime/reset
POST /api/realtime/mock/start
POST /api/realtime/mock/stop
GET  /api/realtime/mock/status
```

Example realtime step:

```bash
curl -X POST http://127.0.0.1:8000/api/realtime/step \
  -H "Content-Type: application/json" \
  -d '{
    "values": {
      "Q": 10000,
      "COD": 420,
      "NH4": 32,
      "NO3": 0.5,
      "TSS": 220,
      "DO": 2
    },
    "stepHours": 0.5
  }'
```

This MVP uses the current dynamic ASM1 engine and continues from the saved model state on each step. It is intended as a first online/digital-twin prototype, not yet a production historian or SCADA connector.

Realtime operation separates boundary input time from model time:

- `POST /api/realtime/ingest` stores one boundary input row only. It does not advance the model.
- `POST /api/realtime/step` with `values` stores a new boundary row and advances the model once.
- `POST /api/realtime/step` without `values` reuses the latest stored boundary row and advances the model once.
- `stepHours` is the external realtime advance duration. If `stepHours = 0.5`, one realtime step advances the model state by 0.5 hours.
- `inputTimestamp` is the boundary data timestamp. It identifies when the input row came in.
- `modelTimestamp` is the model-state timestamp. It advances by `stepHours` each realtime step, even when the boundary input stays unchanged.

`GET /api/realtime/history?hours=12` returns recent boundary inputs and realtime step results for the active project. The frontend uses it to show the latest 12 hours of input/output tables in the realtime workspace.

Realtime inputs now carry a normalized quality report. The backend stores the raw payload, then derives `quality.status`,
per-field `fieldQuality`, `issues`, and `acceptedValues`. Missing boundaries fall back to current model parameters, and
out-of-range values are clipped to configured parameter limits before the realtime model advances.

`GET /api/realtime/sources` returns the current realtime source registry (`manual`, `mock`, and a disabled external
historian placeholder). `GET /api/realtime/status` returns the latest input/result/state, quality status, record counts,
mock runner state, and simple age/latency fields for operational monitoring.

Mock realtime mode can generate development data every 5 minutes:

```bash
curl -X POST http://127.0.0.1:8000/api/realtime/mock/start
curl http://127.0.0.1:8000/api/realtime/mock/status
curl -X POST http://127.0.0.1:8000/api/realtime/mock/stop
```

Mock data uses the current saved/default model parameters and generates `Q`, `COD`, `NH4`, `NO3`, `TSS`, and `DO` with small periodic variation plus noise. Each mock tick advances the dynamic model by 5 minutes.

## Calculation Logs

The right-side `日志` workspace reads calculation logs from SQLite. Logs include manual simulations, realtime steps, mock runner activity, parameter saves/resets, and failure messages.

Log endpoints:

```http
GET    /api/logs?limit=100
DELETE /api/logs
```

## Export And Configuration

The frontend parameter panel can save the current parameter set to the backend SQLite database and load it again on the next visit.
This is currently a single global configuration, without user accounts.

Configuration endpoints:

```http
GET    /api/config/params
POST   /api/config/params
DELETE /api/config/params
```

## Projects API

The platform layer now has a local multi-project API. This is still single-user SQLite, but it gives each project its own saved parameter configuration and prepares the backend for future user accounts.

```http
GET    /api/projects
POST   /api/projects
GET    /api/projects/default
GET    /api/projects/{projectId}
PATCH  /api/projects/{projectId}
DELETE /api/projects/{projectId}
GET    /api/projects/{projectId}/params
POST   /api/projects/{projectId}/params
DELETE /api/projects/{projectId}/params
GET    /api/projects/{projectId}/csv
POST   /api/projects/{projectId}/csv
DELETE /api/projects/{projectId}/csv
```

The `default` project is created automatically. The older global config endpoints remain available for the current frontend.

The frontend now includes a compact project selector in the parameter panel. Creating or switching a project loads that project's saved parameter set; `保存参数` and `重置默认` operate on the active project.

Project scope now also covers saved CSV boundary data, realtime inputs, realtime model state, realtime results, and calculation logs. Existing endpoints remain backward compatible by using the `default` project when no `projectId` is supplied.

### Ownership And Permissions Plan

The current implementation is still local single-user, but the project model is designed to become multi-user:

- `ownerId` is already stored on each project.
- Anonymous/local mode uses `ownerId = "local"`.
- Future authenticated users should only read and write projects where they are owner or collaborator.
- Project-scoped resources should include parameters, CSV boundary data, realtime inputs, realtime state, realtime results, calculation logs, simulation jobs, simulation result archives, and calibration runs.
- A future `project_members` table should hold `owner`, `editor`, and `viewer` roles.

### Database Migration Plan

SQLite remains the local MVP database. For online deployment, the intended path is PostgreSQL:

- Keep SQLite for local learning/demo mode.
- Introduce schema migrations before production, preferably with Alembic.
- Move the current tables into migration-managed schemas: projects, project parameter configs, project CSV inputs, realtime inputs, realtime state, realtime results, calculation logs, simulation jobs/results, and calibration runs.
- Preserve a one-command export/import path from local SQLite to PostgreSQL for demos that later become hosted projects.
- Add indexes on `project_id`, `created_at`, `timestamp`, and job/status fields before multi-user load.

### Deployment Plan

Recommended online deployment shape:

- Static frontend hosted separately, for example object storage/CDN or a small web server.
- FastAPI backend behind HTTPS, served by Uvicorn/Gunicorn or a container platform.
- PostgreSQL for persistent multi-user data.
- A background worker for long simulation jobs, realtime scheduled ingestion, mock data, and calibration runs.
- Environment variables for database URL, CORS origins, auth provider settings, and runtime limits.
- Centralized logs and health checks for `/api/health`, job failures, realtime ingestion delay, and database connectivity.

The results toolbar supports:

- Export result CSV: effluent, nitrogen, solids, and key operating series.
- Export boundary CSV: all boundary curves used for the run.
- Export unit CSV: all WEST-style unit metrics for all process units.
- Export configuration JSON: current parameters plus optional uploaded CSV text.
- Import configuration JSON: restores parameters and any saved CSV boundary data.

## CSV Input

The CSV file is treated as a boundary-condition time series. It does not determine the simulation horizon.
The simulation duration and calculation step are controlled in the UI under the `运行` tab.

Supported columns include:

```text
time,Q,COD,NH4,NO3,TSS,DO,RAS_Q,IR_Q,WAS_Q
```

Common aliases are also accepted, including:

```text
timestamp, day, flow, Qin, SNH, SNO, ammonium, nitrate,
RAS_Q, rasRatio, IR_Q, internalRecycleRatio, WAS_Q
```

If the requested simulation duration exceeds the CSV time range, the last CSV row is held constant.
Between CSV rows, values are linearly interpolated.

## Time Settings

- `仿真天数`: total simulation horizon.
- `计算步长`: external requested step in hours. In realtime mode, “推进一步” advances the model by this duration unless a specific `stepHours` is supplied.
- `结果输出间隔`: chart sampling interval in hours.
- `解算器方法`: `RK4` is the default for current routine runs. In `engineVersion=v2`, `LSODA`, `BDF`, and `Radau` are also available for API-only comparison.
- `最大耦合步长`: maximum outer coupling step for adaptive solver segments.

For RK4, `计算步长` is not used as one large RK4 integration step. The stable v1 engine caps the internal RK4 substep at `0.0005 d` (about 0.72 minutes). For example, if `计算步长 = 0.5 h`, a realtime “推进一步” advances the model by 0.5 hours, but the backend internally splits that 0.5 hours into many smaller RK4 substeps. This protects numerical stability while keeping the user-facing step aligned with data/update frequency.

Recommended RK4 settings:

- Learning/demo runs: `0.5 h`.
- 5-minute online data: `0.0833 h`.
- Fine online calculation: `0.05 h` to `0.1 h`.
- Avoid very large realtime steps such as `2-6 h` unless intentionally testing slow boundary updates, because boundary changes will be held constant over the whole step.

In the stable v1 engine, adaptive solvers are retained mainly for comparison. In the experimental v2 state-vector engine, `LSODA`, `BDF`, and `Radau` can integrate the full v2 state vector. Early short-horizon benchmarks show close results versus v2-RK4, but adaptive solvers are still slower for the current small Python model, so RK4 remains the default strategy.

## Model Notes

The current implementation uses a Python/FastAPI calculation API that mirrors the original browser JavaScript model.
It uses ASM1-style reaction equations and a simplified Takacs-style layered clarifier. It is useful for teaching,
exploration, and UI/product development.

It is not yet a calibrated engineering-grade simulator.

Important limitations:

- The Python backend is intended to match the current JavaScript RK4/stepper behavior before deeper model refactoring.
- `backend/engine_v2.py` contains the first state-vector scaffold for a future unified solver engine, including an
  experimental continuous RHS for clarifier TSS layers. It is not wired into the public API yet; the production path
  still uses `backend/model.py`.
- Backend persistence currently covers realtime inputs/state/results and one global saved parameter configuration.
- No user accounts or per-user parameter sets yet.
- Realtime input quality checks cover missing values, parse errors, source metadata, and out-of-range clipping, but not full sensor diagnostics.
- No formal unit conversion layer.
- Initial conditions are configurable through backend parameters, but the normal UI does not yet expose them.
- Clarifier solids behavior is simplified and should be validated before engineering use.
- The current ASM1 implementation should be checked against public ASM1/BSM references before open publication or commercial use.

## Development History

Main milestones:

- Initial static AAO simulator frontend.
- Added ASM1 reactor calculations and secondary clarifier.
- Added unit-level process result display.
- Added interactive chart hover values.
- Exposed ASM1, influent fractionation, and clarifier parameters.
- Added CSV historical data replay.
- Changed CSV replay so the UI simulation horizon controls total runtime.
- Added `sample-data.csv`.
- Added FastAPI backend calculation API and migrated the runtime simulation call to Python.
- Added an experimental `engine_v2` state-vector scaffold for future unified ODE solving.
- Added model-trust APIs for metadata, reference-case tracking, initial-condition snapshots, credibility screening, and calibration preview.
- Added BSM1 closed-loop dynamic effluent target set as a reference-only comparison case.
- Added BSM1 three-zone AAO mapping and first-pass coordinate-search calibration optimizer.
- Added experimental BSM1 five-tank simulation layout via `engineVersion: "bsm1"`.
- Added local Projects API with per-project parameter configurations.
- Connected the frontend parameter panel to project selection and per-project parameter save/reset.
- Extended project scope to CSV boundary data, realtime records, realtime state/results, and calculation logs.
- Added ownership, permission, database migration, and deployment plans for the future online platform.
- Added project-scoped calibration run archive, a minimal frontend calibration workspace, observation CSV upload for calibration targets, a BSM1 baseline-vs-target calibration report, staged calibration presets, and before/after residual comparison rows.
- Reworked the frontend information architecture into a desktop workbench with left-side primary navigation for process modeling, simulation configuration, data center, results, model evaluation, calibration center, and system logs.

## Suggested Next Steps

- Productize model credibility in the new Model Evaluation workspace.
- Productize realtime data cleaning in the new Data Center workspace.
- Add richer calibration report export and chart overlays in the Calibration Center.
- Align the BSM1 five-tank layout against official dynamic input files and evaluation windows so the built-in BSM1 targets can become a comparable validation case instead of `reference_only`.
- Implement authentication and project membership enforcement.
- Add project-scoped simulation job/result archive.
