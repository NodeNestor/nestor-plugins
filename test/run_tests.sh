#!/bin/bash
# Run the full NodeNestor integration test suite.
#
# Prerequisites:
#   - Docker running
#   - All plugin repos cloned as siblings of nestor-plugins:
#     ../claude-rolling-context/
#     ../claude-autofix/
#     ../claude-guardian/
#     ../claude-workflows/
#     ../claude-worktrees/
#     ../claude-autoresearch/
#     ../claude-knowledge-graph/
#   - An upstream API proxy on host port 9212 (or set API_KEY for real API)
#
# Usage:
#   ./run_tests.sh                    # Use mock upstream on :9212
#   API_KEY=sk-ant-... ./run_tests.sh # Use real Anthropic API

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "====================================="
echo " NodeNestor Integration Test Suite"
echo "====================================="
echo ""

# Verify all plugin repos exist
MISSING=""
for repo in claude-rolling-context claude-autofix claude-guardian claude-workflows claude-worktrees claude-autoresearch claude-knowledge-graph; do
    if [ ! -d "../../$repo" ]; then
        MISSING="$MISSING $repo"
    fi
done

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing plugin repos:$MISSING"
    echo "Expected as siblings of nestor-plugins in the same directory."
    exit 1
fi

echo "All plugin repos found."
echo ""

# Build and run
echo "Building test containers..."
docker compose -f docker-compose.test.yml build

echo ""
echo "Running tests..."
docker compose -f docker-compose.test.yml up \
    --abort-on-container-exit \
    --exit-code-from test-runner

# Cleanup
echo ""
echo "Cleaning up..."
docker compose -f docker-compose.test.yml down -v
