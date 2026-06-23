param(
    [switch]$NoCollectLive,
    [string]$RunMode = "live"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtualenv not found: $Python"
}

$ArgsList = @("-m", "onlybtc.cli", "p3-full-audit", "--run-mode", $RunMode)
if ($NoCollectLive) {
    $ArgsList += "--no-collect-live"
}

Push-Location $ProjectRoot
try {
    & $Python @ArgsList
}
finally {
    Pop-Location
}
