# Handoff: Windows Quick-Check Maturin Bootstrap

## Status

Complete and validated on Windows.

## Root cause

Quick-check uses `uv pip install --no-build-isolation -e .`. With build isolation disabled,
LiteLLM's Maturin build backend must already be importable in the managed quick-check environment.
It was not installed before the editable root install.

## Implemented change

- Added `maturin>=1.7,<2` to `ROOT_BUILD_REQUIREMENTS` in
  `scripts/agent/quick_check.py`.
- Updated the existing bootstrap command test to require Maturin in the first tool-install command.
- No runtime dependency, LiteLLM version, CI workflow, or application code changed.

## Validation

- `tests/test_quick_check.py`: 6 passed.
- `python scripts/agent/quick_check.py`: 203 passed.
- `python scripts/agent/runner.py quick-check`: 203 passed.
- The managed environment installed `maturin==1.14.1` before the root editable install.

## Notes for the next bot

Keep Maturin in the quick-check bootstrap while the root editable install uses
`--no-build-isolation` and LiteLLM requires it on Windows. Removing non-isolated builds would be a
separate harness decision and should be validated across platforms.
