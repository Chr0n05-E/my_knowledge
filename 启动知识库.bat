@echo off
rem Knowledge base GUI launcher - double click this file.
rem Opens tools\gui.pyw with pythonw so no console window is left behind.
setlocal
set "GUI=%~dp0tools\gui.pyw"
if not exist "%GUI%" (
  echo Cannot find "%GUI%"
  pause
  exit /b 1
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw "%GUI%"
) else (
  start "" python "%GUI%"
)
