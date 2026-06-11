#!/usr/bin/env bash
set -euo pipefail
docker compose -f infra/compose/docker-compose.yml down
