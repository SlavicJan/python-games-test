@echo off
setlocal
REM Always run from this folder (project root)
pushd "%~dp0"

REM Prefer venv Python if present
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "main.py"
) else (
  echo [!] .venv not found. Running system python...
  python "main.py"
)

REM If game crashed, keep window open
if errorlevel 1 (
  echo.
  echo [!] Game exited with errorlevel %errorlevel%
  pause
)

popd
endlocal
