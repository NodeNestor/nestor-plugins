#!/bin/bash
# Run LIVE integration tests with real Claude Code instance.
#
# Requires ANTHROPIC_API_KEY to be set.
# Routes through rolling-context proxy automatically.
#
# Usage:
#   ANTHROPIC_API_KEY=sk-ant-... ./run_live.sh
#
# Or export it:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   ./run_live.sh

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    echo "Usage: ANTHROPIC_API_KEY=sk-ant-... ./run_live.sh"
    exit 1
fi

echo "====================================="
echo " NodeNestor LIVE Integration Tests"
echo " (Real Claude Code + All Plugins)"
echo "====================================="
echo ""
echo "API Key: ${ANTHROPIC_API_KEY:0:12}..."
echo ""

# Build
echo "Building containers..."
docker compose -f docker-compose.live.yml build

# Run
echo ""
echo "Running live tests..."
docker compose -f docker-compose.live.yml up \
    --abort-on-container-exit \
    --exit-code-from live-test

# Cleanup
echo ""
echo "Cleaning up..."
docker compose -f docker-compose.live.yml down -v
