#!/usr/bin/env bash
set -euo pipefail
mkdir -p docs/generated
echo "# Action Registry" > docs/generated/action-registry.md
for f in configs/kernel/action_definitions/*.yaml; do echo "- $(basename "$f" .yaml)" >> docs/generated/action-registry.md; done
echo "Generated docs refreshed"
