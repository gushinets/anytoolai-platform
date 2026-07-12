# Handoff: Worker Poll Interval Finite Validation

## Status

Implementation complete; focused and baseline validation passes.

## Finding verification

Valid. The previous `poll_interval_seconds <= 0` check allowed `NaN` and positive infinity, which
are invalid inputs for `asyncio.sleep` in the worker polling loop.

## Implemented change

- Imported `math.isfinite` in worker settings.
- Rejected values that are non-finite or non-positive using the existing `ValueError` message.
- Added settings tests for `nan`, `inf`, `-inf`, zero, negative values, and a positive finite value.

## Validation

- Worker settings and boot tests: 14 passed.
- `python scripts/agent/quick_check.py`: 211 passed.
- `python scripts/agent/runner.py quick-check`: 211 passed.
