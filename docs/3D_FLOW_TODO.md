# 3D Flow Development To-Do

This file tracks the 3D process-view work for the AAO / wastewater treatment prototype.
Update it whenever a 3D feature, data mapping, scene module, workflow page, or deployment script changes.

## Current Baseline

- Source project: repository root
- Runtime service copy: local runtime service directory
- Main 3D page: `frontend/3d-process/wwtp-3d.html`
- Underground process page: `frontend/3d-process/underground-line-3d.html`
- ASM platform frontend: `frontend/asm-platform/`
- Sync command: `./scripts/sync-service.sh`
- Engineering verification: `./scripts/verify-p7.sh`

## Developed

### P0 - Prototype Baseline

- [x] Chose the lightweight Web 3D route: Three.js + glTF/GLB-ready asset layer + custom process data layer.
- [x] Created a standalone AAO wastewater treatment plant 3D prototype page.
- [x] Built a programmatic 3D scene for AAO tanks, secondary clarifier, pipes, sludge layers, aeration, and labels.
- [x] Added free orbit camera controls.
- [x] Added preset views for overview, AAO, clarifier, return lines, and blower room.
- [x] Added object picking so selected units show process status in the side panel.

### P1 - Visual Process Expression

- [x] Added transparent mode for easier internal process inspection.
- [x] Added clipping mode to inspect water level, sludge layer, and pipe relationships.
- [x] Added animated main-flow particles.
- [x] Added sludge layer visual expression.
- [x] Added aeration bubbles and blower-load visual feedback.
- [x] Added layer controls for map, flow, sludge, aeration, pipes, buildings, and labels.
- [x] Added OpenStreetMap tile ground plane for prototype context, with attribution and a map toggle.

### P2 - Process State Data

- [x] Added unified process-state structure for DO, MLSS, NH4-N, NO3-N, COD, flow, RAS, WAS, and internal recycle.
- [x] Added scenario buttons: stable operation, high load, and aeration shortage.
- [x] Mapped process state to water color, sludge thickness, aeration density, particle speed, warning labels, and side-panel values.
- [x] Split visual threshold and legend configuration into `wwtp-visual-config.js`.
- [x] Split simulation result mapping into `wwtp-simulation-mapping.js`.
- [x] Added field-mapping quality reporting so missing simulation fields are visible instead of silently hidden.

### P3 - Process Logic Corrections

- [x] Corrected external sludge return: RAS now returns from the secondary clarifier to the anaerobic inlet.
- [x] Added internal recycle line from the aerobic outlet to the anoxic inlet.
- [x] Added separate click targets and status panels for RAS and internal recycle.
- [x] Adjusted return-line preset view to show both recycle paths.

### P4 - Performance And Structure

- [x] Skipped flow and aeration animation updates when those layers are hidden.
- [x] Cached blower rotor references instead of scanning the full scene every frame.
- [x] Split animation logic into `wwtp-animation.js`.
- [x] Split pipe and particle construction helpers into `wwtp-scene-utils.js`.
- [x] Reduced `wwtp-3d.html` by moving mapping, configuration, animation, and utility logic into modules.
- [x] Added visible runtime optimization status in the 3D page.
- [x] Moved the ASM platform and 3D process view into separate frontend subdirectories: `frontend/asm-platform/` and `frontend/3d-process/`.

### P5 - Additional Process View

- [x] Created `underground-line-3d.html` as a separate underground plant / one-line process-flow page.
- [x] Included main process units, biological lanes, secondary clarifier lanes, high-density clarification cells, denitrification filter groups, flow arrows, and upper grating.
- [x] Kept this page separate from the AAO page to avoid overwriting the main prototype.

### P7 - Engineering Baseline

- [x] Updated `scripts/sync-service.sh` to sync complete frontend static resources, including `asm-platform/` and `3d-process/`.
- [x] Added `scripts/verify-p7.sh` for frontend module checks, backend tests, service-file checks, and local service health checks.
- [x] Updated `README.md` with 3D module and P7 verification notes.
- [x] Updated `docs/PRODUCTION_READINESS.md` with engineering baseline notes.
- [x] Added a login-page entry link from the ASM platform to the 3D process display.
- [x] Added consistent 3D page navigation for returning to the ASM platform and switching process views.
- [x] Verified `./scripts/sync-service.sh`.
- [x] Verified `./scripts/verify-p7.sh`.
- [x] Verified backend test suite: 73 tests passed.
- [x] Verified frontend service and backend health check.
- [x] Migrated source work from OneDrive path to the local project path.

## To Develop

### P5 - Productization

- [ ] Connect `underground-line-3d.html` to the same state, time-axis, and indicator system used by `wwtp-3d.html`.
- [ ] Add multi-process-line switching between AAO view, underground line view, and future process views.
- [x] Add a consistent navigation model across all 3D pages.
- [ ] Add more explicit scenario / timeline controls for demo and review use.
- [ ] Add alarm event display and process-risk summary.

### P6 - Real Simulation Integration

- [ ] Replace static scenario data with real backend simulation results where available.
- [ ] Define the final backend-to-3D data contract.
- [ ] Map real time-series output to 3D timeline frames.
- [ ] Validate data mapping for DO, MLSS, NH4-N, NO3-N, COD, Q, RAS, WAS, and internal recycle.
- [ ] Add test fixtures for representative backend simulation results.
- [ ] Add checks for incomplete or inconsistent simulation output.

### P7 - 3D Model / BIM-Like Assets

- [ ] Select or create a lightweight GLB model for the plant layout.
- [ ] Keep the model low-poly and web-friendly.
- [ ] Name model parts with stable IDs for tanks, pipes, equipment, buildings, and process units.
- [ ] Load the GLB model in Three.js.
- [ ] Replace selected programmatic geometry with model assets.
- [ ] Preserve process-state binding after model replacement.
- [ ] Add model loading performance checks.

### P8 - Maintainability

- [ ] Continue splitting `frontend/3d-process/wwtp-3d.html` into scene-builder modules for tanks, pipes, buildings, labels, map, and UI wiring.
- [ ] Add small module-level tests for simulation mapping and visual threshold rules.
- [ ] Add a documented update checklist for new 3D features.
- [ ] Decide whether to keep standalone HTML modules or move the 3D prototype into the main frontend app structure.

## Known Limits

- The current AAO scene is still mostly programmatic geometry, not a real BIM / GLB model.
- The current process data is mostly simulated scenario data, not fully wired to real backend time-series output.
- OSM tiles are acceptable for prototype use, but production should use a compliant map provider or self-hosted tiles.
- Browser visual QA was limited in the previous session because the in-app browser could not access the local service URL reliably.
- `westpy` was copied locally without its `.git` directory because the OneDrive Git metadata had permission / extended-attribute issues.

## Update Rule

When a 3D feature changes:

1. Update the relevant checklist item in this file.
2. Add a new checklist item if the change creates follow-up work.
3. Run `./scripts/verify-p7.sh` when the change affects runtime files, sync behavior, frontend modules, backend integration, or documentation.
4. Run `./scripts/sync-service.sh` when the runtime service copy needs to reflect source changes.
5. Check `git status --short` before handing off, so uncommitted 3D changes are visible.
