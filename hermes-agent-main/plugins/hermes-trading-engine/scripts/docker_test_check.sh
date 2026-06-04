#!/usr/bin/env bash
# Verify Docker test visibility for the Hermes Trading Engine.
#
# Confirms that the test suite is present and runnable inside the container with
# no manual `pip install` (pytest ships via requirements-dev.txt; tests/ is
# copied to /app/tests in the Dockerfile). PAPER-ONLY: runs tests + the existing
# status command; it never changes trading flags or places any order.
#
# Usage:
#   bash scripts/docker_test_check.sh [service]   # default service: hermes-training
#
# Run AFTER:  docker compose up --build
set -euo pipefail

SERVICE="${1:-hermes-training}"
DC=(docker compose exec -T "$SERVICE")

echo "==> Service: $SERVICE"

echo "==> 1/7 /app/tests exists in the container"
"${DC[@]}" test -d /app/tests && echo "    OK: /app/tests present"

echo "==> 2/7 pytest importable without manual install"
"${DC[@]}" python -m pytest --version

echo "==> 3/7 Full suite: python -m pytest"
"${DC[@]}" python -m pytest

for kw in chainlink btc_pulse news bregman; do
  echo "==> Targeted: python -m pytest tests -k \"$kw\""
  "${DC[@]}" python -m pytest tests -k "$kw"
done

echo "==> 7/7 Status command still works (paper-only, unchanged)"
"${DC[@]}" python scripts/polymarket_training_status.py

echo "==> All Docker test-visibility checks passed."
