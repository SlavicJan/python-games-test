@echo off
setlocal
pushd "%~dp0"

REM One-click: create venv + install deps if needed, then run
if not exist ".venv\Scripts\python.exe" (
  call install_deps.bat
)

call run_game.bat
popd
endlocal
