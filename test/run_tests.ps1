# Run the full NodeNestor integration test suite (Windows)
$ErrorActionPreference = "Stop"
$testDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $testDir

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host " NodeNestor Integration Test Suite"
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Verify all plugin repos exist
$repos = @(
    "claude-rolling-context", "claude-autofix", "claude-guardian",
    "claude-workflows", "claude-worktrees", "claude-autoresearch",
    "claude-knowledge-graph"
)
$missing = @()
foreach ($repo in $repos) {
    if (-not (Test-Path "../../$repo")) {
        $missing += $repo
    }
}
if ($missing.Count -gt 0) {
    Write-Host "ERROR: Missing repos: $($missing -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "All plugin repos found."

# Build and run
Write-Host "`nBuilding test containers..." -ForegroundColor Yellow
docker compose -f docker-compose.test.yml build

Write-Host "`nRunning tests..." -ForegroundColor Yellow
docker compose -f docker-compose.test.yml up `
    --abort-on-container-exit `
    --exit-code-from test-runner

# Cleanup
Write-Host "`nCleaning up..." -ForegroundColor Yellow
docker compose -f docker-compose.test.yml down -v
