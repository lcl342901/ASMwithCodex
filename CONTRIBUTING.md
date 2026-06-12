# Contributing

Thank you for your interest in this wastewater-process simulation and engine-validation project.

The project is still early, so the most useful contributions are focused, reproducible improvements to model reliability, test coverage, documentation, and validation data.

## Project Scope

This repository currently contains two related workspaces:

- `frontend/asm-platform/`: interactive AAO/ASM learning and simulation UI.
- `frontend/engine-testbench/`: standalone calculation-engine validation UI.

The engine testbench separates three validation layers:

1. Model-kernel tests for ASM reaction equations and state-vector behavior.
2. Process-engine tests for AAO + ASM1 + clarifier + recycle boundary conditions.
3. Engineering-reference validation against BSM1, measured data, or historical plant cases.

## Development Setup

Install backend dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Start the backend:

```bash
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open the standalone engine testbench:

```text
frontend/engine-testbench/index.html
```

Or serve the frontend locally:

```bash
python3 -m http.server 4175 --bind 127.0.0.1 --directory frontend
```

Then open:

```text
http://127.0.0.1:4175/engine-testbench/index.html
```

## Useful Checks

Run backend tests:

```bash
python3 -m unittest backend.test_model
```

Run the standalone engine evaluation report:

```bash
python3 -m backend.engine_testing
```

Check frontend JavaScript syntax:

```bash
node --check frontend/engine-testbench/app.js
node --check frontend/asm-platform/app.js
```

## Contribution Guidelines

- Keep changes focused and tied to a clear validation or usability improvement.
- Do not label a model result as engineering-grade unless the relevant reference case and tolerance gate are documented.
- Prefer scenario packs and explicit test fixtures over ad hoc parameter changes.
- When changing engine behavior, update or add tests in `backend/test_model.py`.
- When changing the engine testbench, update `docs/ENGINE_TESTBENCH_TODO.md`.
- Keep private plant data, credentials, and environment files out of the repository.

## Good First Issues

- Add ASM1 model-kernel unit tests for reaction-rate behavior.
- Add process-boundary scenarios for high recycle, low alkalinity, low flow, high TSS, and startup conditions.
- Add CSV export for engine evaluation reports.
- Add Markdown report export for human review.
- Add BSM1 mapping notes and first pass/fail tolerance gates.
