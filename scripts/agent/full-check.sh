#!/usr/bin/env bash
set -euo pipefail
bash scripts/agent/quick-check.sh
PYTHONPATH=packages/backend/platform-core/src python -m pytest
