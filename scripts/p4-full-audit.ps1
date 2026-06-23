param(
    [switch]$NoCollectLive,
    [string]$RunMode = "live",
    [string]$RuntimeMode = "mock",
    [string]$ArticleRuntimeMode = "mock"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Python virtualenv not found: $Python"
}

$ArgsList = @(
    "-m",
    "onlybtc.cli",
    "p4-full-audit",
    "--run-mode",
    $RunMode,
    "--runtime-mode",
    $RuntimeMode,
    "--article-runtime-mode",
    $ArticleRuntimeMode
)
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
