$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $projectRoot "logs"
$pidFile = Join-Path $logDir "bot.pid"
$stdoutFile = Join-Path $logDir "runtime.out"
$stderrFile = Join-Path $logDir "runtime.err"

function Get-PythonCommand {
    param(
        [string]$ProjectRoot,
        [string]$ScriptName
    )

    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return @{
            FilePath = $venvPython
            Arguments = @($ScriptName)
            Description = $venvPython
        }
    }

    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCommand -and $pyCommand.Source) {
        return @{
            FilePath = $pyCommand.Source
            Arguments = @("-3", $ScriptName)
            Description = "$($pyCommand.Source) -3"
        }
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (
        $pythonCommand -and
        $pythonCommand.Source -and
        $pythonCommand.Source -notmatch "WindowsApps\\python(.exe)?$"
    ) {
        return @{
            FilePath = $pythonCommand.Source
            Arguments = @($ScriptName)
            Description = $pythonCommand.Source
        }
    }

    throw "Python не найден. Установите Python 3.11+ или создайте .venv в корне проекта."
}

New-Item -ItemType Directory -Force $logDir | Out-Null

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

$python = Get-PythonCommand -ProjectRoot $projectRoot -ScriptName "bot.py"

$process = Start-Process `
    -FilePath $python.FilePath `
    -ArgumentList $python.Arguments `
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
Write-Host "Using Python: $($python.Description)"
Write-Host "Logs:"
Write-Host "  $stdoutFile"
Write-Host "  $stderrFile"
