#!/bin/sh
set -e

if [ -n "${ANYTOOLAI_DEPLOYMENT_PROFILE_FINGERPRINT:-}" ]; then
    uv run --project apps/platform-api --no-sync python scripts/agent/validate_configs.py \
        check-deployment-profile-from-manifest \
        --manifest /app/live-profile-manifest.json \
        --expected-fingerprint "$ANYTOOLAI_DEPLOYMENT_PROFILE_FINGERPRINT" \
        --enabled-products "$ANYTOOLAI_ENABLED_PRODUCT_IDS" \
        --unmetered-products "$ANYTOOLAI_UNMETERED_PRODUCT_IDS"
fi

# Migrations run in the dedicated `migrate` compose service (entrypoint override, see
# docker-compose.yml), not here -- platform-api no longer waits on or runs them itself,
# which is what lets it scale to more than one replica safely.
exec uv run --project apps/platform-api --no-sync uvicorn anytoolai_platform_api.main:app --host 0.0.0.0 --port 8000 --no-access-log "$@"
