$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $projectRoot "logs"
$pidFile = Join-Path $logDir "bot.pid"
$stderrFile = Join-Path $logDir "runtime.err"

if (-not (Test-Path $pidFile)) {
    Write-Host "Bot is not running."
    if (Test-Path $stderrFile) {
        Write-Host ""
        Write-Host "Last log lines:"
        Get-Content -Tail 15 $stderrFile
    }
    exit 0
}

$pid = Get-Content $pidFile -ErrorAction SilentlyContinue
$process = Get-Process -Id $pid -ErrorAction SilentlyContinue

if ($process) {
    Write-Host "Bot is running. PID: $pid"
    Write-Host "Started: $($process.StartTime)"
} else {
    Write-Host "PID file exists, but process is not running."
    if (Test-Path $stderrFile) {
        Write-Host ""
        Write-Host "Last log lines:"
        Get-Content -Tail 15 $stderrFile
    }
}
