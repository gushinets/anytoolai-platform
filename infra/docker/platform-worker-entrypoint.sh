#!/bin/sh
set -e

if [ -n "${ANYTOOLAI_DEPLOYMENT_PROFILE_FINGERPRINT:-}" ]; then
    uv run --project apps/platform-worker --no-sync python scripts/agent/validate_configs.py \
        check-deployment-profile-from-manifest \
        --manifest /app/live-profile-manifest.json \
        --expected-fingerprint "$ANYTOOLAI_DEPLOYMENT_PROFILE_FINGERPRINT" \
        --enabled-products "$ANYTOOLAI_ENABLED_PRODUCT_IDS" \
        --unmetered-products "$ANYTOOLAI_UNMETERED_PRODUCT_IDS"
fi

exec uv run --project apps/platform-worker --no-sync anytoolai-platform-worker
