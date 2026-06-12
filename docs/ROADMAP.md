# Roadmap

This roadmap describes the open-source direction for the AAO/ASM simulator and engine testbench.

## Project Goal

Build a reusable, transparent validation framework for wastewater-treatment calculation engines.

The current implementation focuses on an AAO-ASM1 process engine. Future work should allow additional engines such as ASM2d and ASM2d_NDHA to plug into the same contract, scenario-pack, and validation-report workflow.

## Validation Layers

### L1 - Model-Kernel Tests

Status: planned.

Purpose: test the ASM reaction kernel without process-layout assumptions.

Scope:

- reaction-rate equations
- state-vector shape and units
- stoichiometric consistency
- mass-balance checks where practical
- finite numeric behavior
- solver-independent small fixtures

Out of scope:

- reactor volumes
- AAO layout
- clarifier behavior
- RAS/WAS loops
- plant-level operating strategy

### L2 - Process-Engine Tests

Status: first implementation active.

Purpose: test whether a complete process simulation engine can run reliably under defined boundary conditions.

Current scope:

- AAO anaerobic/anoxic/aerobic CSTR zones
- ASM1-style biological reactions
- Takacs-style secondary clarifier
- RAS/WAS sludge handling
- influent and process parameter scenarios
- reliability, stability, and generality checks

Near-term additions:

- explicit HRT/SRT/recycle-ratio fixtures
- long-horizon runtime budgets
- CSV-driven dynamic influent scenarios
- process-response checks for expected qualitative behavior
- richer report exports

### L3 - Engineering-Reference Validation

Status: reference-only.

Purpose: compare engine outputs with trusted reference cases or observed plant data.

Planned scope:

- BSM1 mapping and tolerance bands
- reference-window averaging rules
- measured plant-data case format
- historical project-data regression cases
- version-to-version engine comparisons

This layer is the only layer that should support claims about engineering reasonableness.

## Suggested Release Plan

### v0.1.0 - Open-Source Baseline

- Public repository with MIT license.
- Clear README, contribution guide, and roadmap.
- Standalone engine testbench for AAO-ASM1.
- JSON engine evaluation report with three validation layers.
- Process-engine reliability and stability checks.

### v0.2.0 - Kernel Test Extraction

- Extract ASM1 reaction-kernel fixtures.
- Add model-kernel tests for state-vector behavior and reaction-rate sanity.
- Document unit conventions and state-variable names.
- Add model-kernel report section to the testbench.

### v0.3.0 - Scenario Expansion

- Add high recycle, low alkalinity, low flow, high TSS, and startup scenarios.
- Add CSV dynamic-boundary scenarios.
- Add scenario tags and filters in the UI.
- Add CSV and Markdown report exports.

### v0.4.0 - Engineering Reference Gates

- Convert the BSM1 placeholder gate into a mapped reference case.
- Add tolerance bands and averaging windows.
- Add comparison metrics such as MAE, RMSE, and MAPE where meaningful.
- Add plant-data reference case format.

### v0.5.0 - Future Engine Extension

- Add documented adapter path for ASM2d or ASM2d_NDHA.
- Add engine-family-specific result contracts.
- Add tolerance profiles per engine family and scenario axis.
- Add disabled/future registry states for engines under development.

## Open Questions

- Which license is best long term if the project later includes benchmark data or third-party reference cases?
- Which BSM1 data source and mapping assumptions should be considered authoritative?
- How should plant-data privacy be handled for user-provided reference cases?
- Which engineering thresholds should be defaults versus user-configurable policies?
