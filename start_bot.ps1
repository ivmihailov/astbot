$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = "C:\Users\ivmih\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$logDir = Join-Path $projectRoot "logs"
$pidFile = Join-Path $logDir "bot.pid"
$stdoutFile = Join-Path $logDir "runtime.out"
$stderrFile = Join-Path $logDir "runtime.err"

New-Item -ItemType Directory -Force $logDir | Out-Null

if (-not (Test-Path $pythonPath)) {
    throw "Python not found at $pythonPath"
}

if (Test-Path $pidFile) {
    $existingPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($existingPid) {
        $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
        if ($existingProcess) {
            Write-Host "Bot is already running. PID: $existingPid"
            exit 0
        }
    }
}

$process = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList "bot.py" `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $stdoutFile `
    -RedirectStandardError $stderrFile `
    -PassThru

Set-Content -Path $pidFile -Value $process.Id -Encoding ascii

Start-Sleep -Seconds 3

$runningProcess = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
if (-not $runningProcess) {
    Write-Host "Bot failed to start. Check logs:"
    Write-Host "  $stderrFile"
    exit 1
}

Write-Host "Bot started successfully. PID: $($process.Id)"
Write-Host "Logs:"
Write-Host "  $stdoutFile"
Write-Host "  $stderrFile"
