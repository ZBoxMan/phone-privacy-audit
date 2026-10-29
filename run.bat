@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

rem Phone privacy audit - Windows launcher
rem Double-click this file, or run:  run.bat phone-audit
rem Everything else lives in scripts\run.py (same code as macOS / Linux).

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  where py >nul 2>&1
  if not errorlevel 1 set "PY=py -3"
)

if not defined PY (
  echo.
  echo   Python not found.
  echo.
  echo   1. Install it from https://www.python.org/downloads/
  echo   2. On the first screen, tick "Add python.exe to PATH"
  echo   3. Close this window, open a new one, run this file again
  echo.
  pause
  exit /b 2
)

%PY% scripts\run.py %*
set "CODE=!ERRORLEVEL!"

if "%~1"=="" (
  echo.
  pause
)
exit /b !CODE!
