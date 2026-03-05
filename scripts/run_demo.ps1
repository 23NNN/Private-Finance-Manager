$ErrorActionPreference = "Stop"

# Repo-Root ist eine Ebene über scripts\
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

$DemoDir = Join-Path $RepoRoot "demo_data"
$LogDir  = Join-Path $DemoDir "logs"

New-Item -ItemType Directory -Force -Path $DemoDir, $LogDir | Out-Null

# Zusätzlich als ENV setzen (falls App/Settings ENV bevorzugt)
$env:FINANZMANAGER_DATA_DIR = $DemoDir
$env:FINANZMANAGER_LOG_DIR  = $LogDir

function Invoke-Python {
    param([string[]]$Args)

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Args
        return
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Args
        return
    }
    throw "Python nicht gefunden (py oder python)."
}

Write-Host ""
Write-Host "=== Demo-Daten erzeugen (Mini) ==="
Invoke-Python @("scripts/build_demo_data.py", "--data-dir", $DemoDir, "--mini")

Write-Host ""
Write-Host "=== App starten ==="
Invoke-Python @("app.py", "--data-dir", $DemoDir, "--log-dir", $LogDir)
