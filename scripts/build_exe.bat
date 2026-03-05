@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%\.."

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

set "PY=py -3"
%PY% -c "import sys" >nul 2>nul
if errorlevel 1 set "PY=python"

%PY% -m PyInstaller scripts\finanzmanager.spec
echo.
echo Fertig. EXE unter dist\Finanzmanager\Finanzmanager.exe
popd
endlocal
