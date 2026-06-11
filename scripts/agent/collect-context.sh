#!/usr/bin/env bash
set -euo pipefail
echo "## git status"
git status --short || true
echo "## recent files"
find . -maxdepth 3 -type f | sort | head -200
