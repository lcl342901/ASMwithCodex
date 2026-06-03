# ASM Platform Development To-Do

This file tracks the ASM learning and simulation platform work.
Update it whenever the ASM frontend, backend simulation engine, realtime workflow, calibration workflow, project model, data handling, or deployment baseline changes.

## Development Rule

- Before starting ASM platform development, check this TODO list first and use it to choose the next scoped task.
- After finishing ASM platform development, update this TODO list to reflect completed work, changed priorities, and any new follow-up items.
- Keep 3D process-display work tracked separately in `docs/3D_FLOW_TODO.md`.

## Current Baseline

- Source project: `/Users/chenglin/Projects/WEST model/Modelica2023TH/aao-simulator`
- ASM frontend: `frontend/asm-platform/`
- Backend API: `backend/`
- Runtime service copy: `/Users/chenglin/aao-simulator-service`
- Main ASM service URL: `http://127.0.0.1:4173/asm-platform/index.html`
- Backend health URL: `http://127.0.0.1:8000/api/health`
- Sync command: `./scripts/sync-service.sh`
- Engineering verification: `./scripts/verify-p7.sh`

## Developed

### P0 - Browser Learning Platform Baseline

- [x] Built browser-based AAO / A2O wastewater process simulator prototype.
- [x] Added static ASM platform frontend under `frontend/asm-platform/`.
- [x] Added AAO process layout: influent, anaerobic reactor, anoxic reactor, aerobic reactor, secondary clarifier, RAS, WAS, and effluent.
- [x] Added editable operating, process, ASM1, influent fractionation, and clarifier parameters.
- [x] Added CSV historical boundary upload and replay.
- [x] Added interactive charts and unit-level process curves.
- [x] Added CSV export for effluent, process results, boundary inputs, and unit-level series.
- [x] Added JSON export/import for simulation configuration.

### P1 - Simulation Engine

- [x] Implemented ASM1-style biological reaction model with 13 components.
- [x] Implemented three CSTR reactors for anaerobic, anoxic, and aerobic zones.
- [x] Implemented 10-layer Takacs-style secondary clarifier model.
- [x] Implemented RAS / WAS closed-loop sludge handling.
- [x] Added Python/FastAPI backend simulation path.
- [x] Kept the original frontend JavaScript model as a reference path.
- [x] Added solver controls including engine version, method, tolerance, and max step.
- [x] Added backend parameter and model validation with warnings.
- [x] Added backend unit test coverage for core model behavior.

### P2 - Model Trust And Calibration

- [x] Added model metadata API.
- [x] Added unit-system notes, ASM1 component list, available metrics, and initial-condition snapshots.
- [x] Added credibility screening API for obvious interpretation risks.
- [x] Added calibration preview API.
- [x] Added BSM1-to-current-AAO mapping.
- [x] Added BSM1 baseline-vs-target report.
- [x] Added staged calibration presets for nitrification/NH4, denitrification/TN, COD/BOD, and clarifier/TSS.
- [x] Added first-pass coordinate-search calibration optimizer.
- [x] Added project-scoped calibration run archive.
- [x] Added observation CSV upload for calibration targets.
- [x] Added periodic calibration plan API and manual run path.

### P3 - Realtime MVP

- [x] Added SQLite-backed realtime input, model state, latest result, and history storage.
- [x] Added realtime API endpoints for ingest, step, latest, history, reset, status, mock start/stop, and mock status.
- [x] Added realtime observations and trust comparison.
- [x] Added realtime state/output bias correction workflow.
- [x] Added realtime source registry and point configuration API.
- [x] Added realtime input quality checks and quality score.
- [x] Added realtime forecast workflow based on recent boundary trends.
- [x] Added calculation logs for simulations, realtime steps, mock runner activity, parameter operations, and failures.

### P4 - Project And Data Management

- [x] Added local multi-project API.
- [x] Added per-project parameter configuration save/reset.
- [x] Added project-scoped CSV boundary data.
- [x] Extended project scope to realtime inputs, realtime state, realtime results, calculation logs, simulation jobs/results, and calibration runs.
- [x] Added compact project selector in the frontend parameter panel.
- [x] Kept existing endpoints backward compatible through the `default` project.

### P5 - Frontend Workbench

- [x] Reworked frontend information architecture into a desktop workbench.
- [x] Added login / environment selection flow for realtime simulation, simulation lab, and model management.
- [x] Added workspaces for process modeling, simulation configuration, data center, results, model evaluation, calibration, system settings, and logs.
- [x] Added realtime operation views for online data, trust, state correction, and status workflows.
- [x] Added compact calibration workspace.
- [x] Added visual polish and scenario-management UI concepts in `design-concepts/`.

### P7 - Engineering Baseline

- [x] Added `scripts/sync-service.sh` to sync backend and frontend into `/Users/chenglin/aao-simulator-service`.
- [x] Added `scripts/verify-p7.sh` to run frontend syntax checks, backend tests, service-copy checks, and health checks.
- [x] Updated sync logic to preserve the `frontend/asm-platform/` and `frontend/3d-process/` boundaries.
- [x] Verified backend test suite: 73 tests passed.
- [x] Verified backend health and frontend service availability.
- [x] Updated production readiness notes.
- [x] Added a login-page entry link from the ASM platform to the 3D process display.

## To Develop

### P6 - Product Boundaries And Navigation

- [ ] Clarify how ASM platform navigation links to the 3D process display.
- [x] Add an explicit login-page entry point to the related 3D visualization.
- [ ] Add an explicit entry point from ASM simulation results to the related 3D visualization.
- [ ] Define which ASM result payload fields are required by the 3D process view.
- [ ] Add user-facing labels that separate teaching simulation, realtime decision support, and 3D process display.

### P7 - Real Data And Integration

- [ ] Replace development mock realtime data with a real plant data adapter.
- [ ] Define historian / SCADA import contract.
- [ ] Store raw values, cleaned values, quality issues, and source metadata together.
- [ ] Add import validation for real plant CSV or historian exports.
- [ ] Add a stable backend endpoint for 3D-friendly simulation time-series output.

### P8 - Production Readiness

- [ ] Enable API token in any non-local deployment.
- [ ] Restrict CORS for public deployment.
- [ ] Move from SQLite to PostgreSQL for shared online usage.
- [ ] Add Alembic migrations before production schema changes.
- [ ] Move long simulations, realtime polling, mock generation, and calibration runs into a worker process.
- [ ] Add real user accounts and project membership roles.
- [ ] Add backup/restore flow for project data.

### P9 - Testing And Maintainability

- [ ] Add frontend regression checks for key workbench flows.
- [ ] Add API tests for project, realtime, calibration, and forecast workflows.
- [ ] Add fixtures for CSV replay, realtime observations, calibration observations, and forecast inputs.
- [ ] Split the large ASM frontend script into smaller modules if feature work continues.
- [ ] Keep README focused on stable usage and keep this file as the ASM platform development ledger.

## Known Limits

- The platform is still a local teaching MVP, not a certified engineering product.
- SQLite is acceptable for local demos but not enough for shared online operation.
- There are no real user accounts or project-member permissions yet.
- Mock realtime data is for product demonstration and development only.
- Calibration and credibility outputs are decision-support / teaching aids, not validated compliance reports.
- The ASM frontend is still concentrated in a large `frontend/asm-platform/app.js` file.

## Update Rule

When an ASM platform feature changes:

1. Update the relevant checklist item in this file.
2. Add a new checklist item if the change creates follow-up work.
3. Keep stable setup and usage instructions in `README.md`; keep changing progress details here.
4. Run `./scripts/verify-p7.sh` when the change affects backend logic, frontend runtime files, data files, sync behavior, or documentation.
5. Run `./scripts/sync-service.sh` when the runtime service copy needs to reflect source changes.
6. Check `git status --short` before handing off, so uncommitted platform changes are visible.
