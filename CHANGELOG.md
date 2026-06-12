# Changelog

All notable changes to this project will be documented in this file.

This project uses early `0.x` releases while the engine contract and validation layers are still stabilizing.

## Unreleased

### Added

- Standalone `AAO-ASM1 Process Engine` testbench under `frontend/engine-testbench/`.
- Calculation-engine package and registry under `backend/engines/`.
- Engine scenario-pack scaffolding under `backend/engine_scenarios/`.
- Engine evaluation report with three validation layers:
  - model-kernel tests
  - process-engine tests
  - engineering-reference validation
- JSON export for engine evaluation reports.
- BSM1 reference gate in `reference-only` mode.
- Open-source project materials:
  - MIT license
  - contribution guide
  - roadmap
  - Codex for Open Source application notes
  - GitHub issue templates

### Changed

- The broader ASM platform no longer embeds the engine-testbench UI.
- The engine-testbench UI now clearly distinguishes ASM1 model-kernel work from AAO-ASM1 process-engine validation.

### Known Limits

- ASM1 model-kernel tests are not implemented yet.
- BSM1 validation is not pass/fail yet.
- Future ASM2d and ASM2d_NDHA engines are roadmap items.
