#!/usr/bin/env bash
set -euo pipefail
echo "Kernel smoke placeholder: runtime implementation will be added in MVP-A slices."
PYTHONPATH=packages/backend/platform-core/src python -m pytest tests/e2e -q
