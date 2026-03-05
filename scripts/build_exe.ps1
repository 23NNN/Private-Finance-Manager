$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Resolve-PythonCommand {
    <#
    Returns a hashtable:
      @{ FilePath = "...\python.exe"; PreArgs = @() }
    or for py launcher:
      @{ FilePath = "py"; PreArgs = @("-3") }
    #>

    # 1) If a venv is activated, use it
    if ($env:VIRTUAL_ENV) {
        $p = Join-Path $env:VIRTUAL_ENV "Scripts\python.exe"
        if (Test-Path $p) {
            return @{ FilePath = (Resolve-Path $p).Path; PreArgs = @() }
        }
    }

    # 2) Prefer repo-local venv if present
    $localVenv = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path $localVenv) {
        return @{ FilePath = (Resolve-Path $localVenv).Path; PreArgs = @() }
    }

    # 3) Fall back to py launcher, then python
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ FilePath = "py"; PreArgs = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ FilePath = "python"; PreArgs = @() }
    }

    throw "Python nicht gefunden. Nutze ein venv (.venv) oder installiere Python."
}

function Write-ColoredLine {
    param([Parameter(Mandatory=$true)][string]$Line)

    if ($Line -match "^(?i).*ERROR:|Traceback") {
        Write-Host $Line -ForegroundColor Red
    }
    elseif ($Line -match "^(?i).*WARNING:") {
        Write-Host $Line -ForegroundColor Yellow
    }
    else {
        Write-Host $Line
    }
}

function Invoke-Process {
    param(
        [Parameter(Mandatory=$true)][string]$FilePath,
        [Parameter(Mandatory=$true)][string[]]$ArgumentList
    )

    $cmdLine = $FilePath + " " + ($ArgumentList -join " ")
    Write-Host ("-> " + $cmdLine)

    $stdoutFile = Join-Path $env:TEMP ("fm_build_stdout_" + [Guid]::NewGuid().ToString("N") + ".log")
    $stderrFile = Join-Path $env:TEMP ("fm_build_stderr_" + [Guid]::NewGuid().ToString("N") + ".log")

    try {
        $p = Start-Process `
            -FilePath $FilePath `
            -ArgumentList $ArgumentList `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutFile `
            -RedirectStandardError $stderrFile

        if (Test-Path $stdoutFile) {
            Get-Content $stdoutFile | ForEach-Object { Write-ColoredLine -Line ([string]$_) }
        }

        if (Test-Path $stderrFile) {
            # stderr wird in PowerShell oft als "Fehlerstream" behandelt -> hier explizit nur ausgeben, ohne Stop.
            Get-Content $stderrFile | ForEach-Object { Write-ColoredLine -Line ([string]$_) }
        }

        return [int]$p.ExitCode
    }
    finally {
        Remove-Item -Force -ErrorAction SilentlyContinue $stdoutFile, $stderrFile | Out-Null
    }
}

Write-Host ""
Write-Host "== Clean build/dist =="
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue ".\build", ".\dist"

Write-Host ""
Write-Host "== PyInstaller =="

$py = Resolve-PythonCommand
$args = @($py.PreArgs + @("-m", "PyInstaller", "scripts\finanzmanager.spec"))

$rc = Invoke-Process -FilePath $py.FilePath -ArgumentList $args
if ($rc -ne 0) {
    Write-Host ""
    Write-Host ("PyInstaller Build fehlgeschlagen (rc=" + $rc + ").") -ForegroundColor Red
    Write-Host "Tipp: Stelle sicher, dass PyInstaller im selben Python installiert ist:" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\python -m pip install pyinstaller" -ForegroundColor Yellow
    exit $rc
}

Write-Host ""
Write-Host "Fertig. EXE unter dist\Finanzmanager\Finanzmanager.exe" -ForegroundColor Green
