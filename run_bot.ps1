$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = "C:\Users\ivmih\AppData\Local\Python\pythoncore-3.14-64\python.exe"

if (-not (Test-Path $pythonPath)) {
    throw "Python not found at $pythonPath"
}

Set-Location $projectRoot
& $pythonPath "bot.py"
