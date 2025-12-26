@echo off
setlocal
pushd "%~dp0"

REM Create venv only once
if not exist ".venv\Scripts\python.exe" (
  echo Creating venv...
  python -m venv .venv
)

echo Installing requirements...
REM No forced pip upgrade (avoids reinstall loop)
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo Done. You can now run: run_game.bat
pause
popd
endlocal
