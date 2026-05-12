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

## How To Run

Open `index.html` in a browser.

No build step or package installation is currently required.

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

The current implementation is a frontend prototype. It uses ASM1-style reaction equations and a simplified
Takacs-style layered clarifier. It is useful for teaching, exploration, and UI/product development.

It is not yet a calibrated engineering-grade simulator.

Important limitations:

- The solver is implemented in browser JavaScript.
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

## Suggested Next Steps

- Move the model engine into a Python/FastAPI backend.
- Add CSV template download and stricter input validation.
- Add model-state persistence for real-time data.
- Add sensor quality flags and missing-data handling.
- Add calibration/parameter fitting workflow.
- Add export of simulation results as CSV.
- Add benchmark validation against public ASM1/BSM examples.
