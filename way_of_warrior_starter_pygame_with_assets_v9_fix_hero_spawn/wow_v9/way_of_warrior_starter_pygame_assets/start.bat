@echo off
cd /d "%~dp0"
call install_deps.bat
if errorlevel 1 (
  echo.
  echo [!] install_deps failed.
  pause
  exit /b 1
)
call run_game.bat
