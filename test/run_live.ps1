# Run LIVE integration tests with real Claude Code instance.
# Requires ANTHROPIC_API_KEY to be set.
#
# Usage: $env:ANTHROPIC_API_KEY="sk-ant-..."; .\run_live.ps1
$ErrorActionPreference = "Stop"
$testDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $testDir

if (-not $env:ANTHROPIC_API_KEY) {
    Write-Host "ERROR: ANTHROPIC_API_KEY not set" -ForegroundColor Red
    Write-Host 'Usage: $env:ANTHROPIC_API_KEY="sk-ant-..."; .\run_live.ps1'
    exit 1
}

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host " NodeNestor LIVE Integration Tests"
Write-Host " (Real Claude Code + All Plugins)"
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Key: $($env:ANTHROPIC_API_KEY.Substring(0,12))..."

# Build
Write-Host "`nBuilding containers..." -ForegroundColor Yellow
docker compose -f docker-compose.live.yml build

# Run
Write-Host "`nRunning live tests..." -ForegroundColor Yellow
docker compose -f docker-compose.live.yml up `
    --abort-on-container-exit `
    --exit-code-from live-test

# Cleanup
Write-Host "`nCleaning up..." -ForegroundColor Yellow
docker compose -f docker-compose.live.yml down -v
