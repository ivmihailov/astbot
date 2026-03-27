$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path (Join-Path $projectRoot "logs") "bot.pid"

if (-not (Test-Path $pidFile)) {
    Write-Host "PID file not found. Bot may already be stopped."
    exit 0
}

$pid = Get-Content $pidFile -ErrorAction SilentlyContinue
if (-not $pid) {
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    Write-Host "PID file was empty. Removed it."
    exit 0
}

$process = Get-Process -Id $pid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $pid -Force
    Write-Host "Bot stopped. PID: $pid"
} else {
    Write-Host "Process $pid was not running."
}

Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
