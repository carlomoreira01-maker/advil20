@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 python instalar_local.py
) else (
 py -3 instalar_local.py
)
set "INSTALL_RESULT=%ERRORLEVEL%"
pause
exit /b %INSTALL_RESULT%
