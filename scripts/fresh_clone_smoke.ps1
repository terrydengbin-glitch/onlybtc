param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$SmokeDataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("onlybtc-smoke-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $SmokeDataDir | Out-Null
$env:ONLYBTC_DATA_DIR = $SmokeDataDir
$env:PYTHONUTF8 = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Remove-PipAuditAvHotspotCache {
    $CycloneDxPycache = Join-Path $RepoRoot ".venv\Lib\site-packages\cyclonedx\model\__pycache__"
    if (-not (Test-Path -LiteralPath $CycloneDxPycache)) {
        return
    }
    Get-ChildItem -LiteralPath $CycloneDxPycache -Filter "vulnerability*.pyc" -File |
        Remove-Item -Force
}

if ($SkipInstall) {
    $Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $Python)) {
        $Python = "python"
    }
} else {
    $VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        python -m venv .venv
    }
    $Python = $VenvPython
    Invoke-External "Upgrade pip" { & $Python -m pip install --upgrade pip }
    Invoke-External "Install backend" { & $Python -m pip install -e ".\backend[dev]" }
}

Remove-PipAuditAvHotspotCache

Invoke-External "Ruff contract gate" {
    & $Python -m ruff check `
        backend\src\onlybtc\core\settings_contract.py `
        backend\src\onlybtc\core\glassnode_entitlement.py `
        backend\tests\test_settings_contract.py `
        backend\tests\test_glassnode_entitlement.py `
        scripts\generate_glassnode_entitlement_report.py
}

Invoke-External "Pytest contract gate" {
    & $Python -m pytest `
        backend\tests\test_settings_contract.py `
        backend\tests\test_glassnode_entitlement.py `
        -q
}

Invoke-External "Audit backend dependencies" { & $Python -B -m pip_audit --skip-editable }

Push-Location frontend
try {
    $HasNodeModules = Test-Path -LiteralPath "node_modules"
    if ((-not $SkipInstall) -and (-not $HasNodeModules)) {
        Invoke-External "Install frontend" { npm ci }
    }
    Invoke-External "Build frontend" { npm run build }
    Invoke-External "Audit frontend dependencies" { npm audit --audit-level=high }
} finally {
    Pop-Location
}

Write-Host "Fresh clone smoke passed. Temporary data dir: $SmokeDataDir"
