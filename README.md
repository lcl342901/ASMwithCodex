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

## Files

- `index.html`: main UI.
- `styles.css`: layout and visual styling.
- `app.js`: ASM1 model, clarifier model, CSV replay, chart rendering, and UI logic.
- `sample-data.csv`: example CSV that can be uploaded directly.
- `backend/main.py`: FastAPI app and `/api/simulate` route.
- `backend/model.py`: Python ASM1, AAO, RAS/WAS, Takacs clarifier, and CSV replay engine.
- `backend/schemas.py`: API request schema.
- `backend/requirements.txt`: backend Python dependencies.

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

If backend code changes in the project directory, copy the updated `backend/` directory into `/Users/chenglin/aao-simulator-service/` and restart the service.

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
    "outputIntervalHours": 6
  },
  "csvText": "time,Q,COD,NH4,...",
  "csvFileName": "sample-data.csv"
}
```

`params` may include any current frontend parameter. `csvText` is optional. When `csvText` is provided, it is used as a boundary-condition time series, while `params.simulationDays` still controls the total simulation horizon.

The response is compatible with the frontend `lastResult` structure, including:

```text
time, effCod, effNh4, effNo3, effTn, effTss,
anaerobicNo3, anoxicNo3, aerobicNo3,
aerobicDo, aerobicMlss, rasMlss,
boundaries, units, clarifier, mode, sourceName
```

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
- `计算步长`: requested numerical calculation step in hours.
- `结果输出间隔`: chart sampling interval in hours.

For stability, the internal solver caps the actual calculation step. If the requested calculation step is too large,
the simulator uses a smaller internal step while preserving the requested output interval.

## Model Notes

The current implementation uses a Python/FastAPI calculation API that mirrors the original browser JavaScript model.
It uses ASM1-style reaction equations and a simplified Takacs-style layered clarifier. It is useful for teaching,
exploration, and UI/product development.

It is not yet a calibrated engineering-grade simulator.

Important limitations:

- The Python backend is intended to match the current JavaScript RK4/stepper behavior before deeper model refactoring.
- No backend state persistence yet.
- No sensor quality checks beyond basic CSV parsing.
- No formal unit conversion layer.
- Initial conditions are currently fixed in code.
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

## Suggested Next Steps

- Add CSV template download and stricter input validation.
- Add model-state persistence for real-time data.
- Add sensor quality flags and missing-data handling.
- Add calibration/parameter fitting workflow.
- Add export of simulation results as CSV.
- Add benchmark validation against public ASM1/BSM examples.
