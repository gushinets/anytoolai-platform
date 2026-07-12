# Task: Windows Quick-Check Maturin Bootstrap

## Brief task description

Fix Windows quick-check failure when LiteLLM requires Maturin during the non-isolated editable
monorepo install.

## Implementation summary

Added `maturin>=1.7,<2` to the canonical quick-check build-tool bootstrap, before the root editable
install. The existing command-level test now verifies that ordering.
