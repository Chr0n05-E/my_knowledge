@echo off
rem Create / repair the desktop shortcut for the knowledge base console.
rem Double click this file. See docs\操作指南.md section 0 for details.
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found in PATH.
  pause
  exit /b 1
)
python "%~dp0tools\install_shortcut.py" %*
echo.
pause
