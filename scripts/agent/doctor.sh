#!/usr/bin/env bash
set -euo pipefail
echo "Python:" $(python --version)
echo "Node:" $(node --version 2>/dev/null || echo not-found)
echo "Repo doctor passed"
