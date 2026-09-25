#!/bin/sh
set -e

if [ -n "${ANYTOOLAI_DEPLOYMENT_PROFILE_FINGERPRINT:-}" ]; then
    uv run --project apps/platform-worker --no-sync python scripts/agent/validate_configs.py \
        check-deployment-profile-from-manifest \
        --manifest /app/live-profile-manifest.json \
        --expected-fingerprint "$ANYTOOLAI_DEPLOYMENT_PROFILE_FINGERPRINT" \
        --enabled-products "$ANYTOOLAI_ENABLED_PRODUCT_IDS" \
        --unmetered-products "$ANYTOOLAI_UNMETERED_PRODUCT_IDS"
    if [ -z "${ANYTOOLAI_DEPLOYMENT_ACTIVATION_NAME:-}" ] || \
       [ -z "${ANYTOOLAI_DEPLOYMENT_ACTIVATION_MARKER:-}" ]; then
        echo "live worker activation marker is required" >&2
        exit 1
    fi
    while [ "$(cat "$ANYTOOLAI_DEPLOYMENT_ACTIVATION_MARKER" 2>/dev/null || true)" != \
            "$ANYTOOLAI_DEPLOYMENT_ACTIVATION_NAME" ]; do
        sleep 1
    done
fi

exec uv run --project apps/platform-worker --no-sync anytoolai-platform-worker
