#!/usr/bin/env bash
set -euo pipefail
python scripts/agent/validate_configs.py
python scripts/agent/validate_architecture.py
PYTHONPATH=packages/backend/platform-core/src python -m pytest tests/architecture
