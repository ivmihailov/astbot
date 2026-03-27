$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

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

Set-Location $projectRoot
$python = Get-PythonCommand -ProjectRoot $projectRoot -ScriptName "bot.py"
Write-Host "Using Python: $($python.Description)"
& $python.FilePath @($python.Arguments)
