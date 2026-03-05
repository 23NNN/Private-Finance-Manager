@echo off
setlocal EnableExtensions

REM Repo-Root ist eine Ebene über scripts\
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%\.."

set "DEMO_DIR=%CD%\demo_data"
set "LOG_DIR=%DEMO_DIR%\logs"

REM Zusätzlich als ENV setzen (falls App/Settings ENV bevorzugt)
set "FINANZMANAGER_DATA_DIR=%DEMO_DIR%"
set "FINANZMANAGER_LOG_DIR=%LOG_DIR%"

if not exist "%DEMO_DIR%" mkdir "%DEMO_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM Python finden (py -3 bevorzugt)
set "PY=py -3"
%PY% -c "import sys" >nul 2>nul
if errorlevel 1 (
  set "PY=python"
)

echo.
echo === Demo-Daten erzeugen (Mini) ===
%PY% scripts\build_demo_data.py --data-dir "%DEMO_DIR%" --mini
if errorlevel 1 (
  echo.
  echo Fehler beim Erzeugen der Demo-Daten.
  popd
  exit /b 1
)

echo.
echo === App starten ===
%PY% app.py --data-dir "%DEMO_DIR%" --log-dir "%LOG_DIR%"

popd
endlocal
