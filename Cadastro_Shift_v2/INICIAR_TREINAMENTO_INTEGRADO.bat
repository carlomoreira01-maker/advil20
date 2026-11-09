@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Execute INSTALAR_WINDOWS.bat primeiro.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" treinamento_integrado.py
if errorlevel 1 pause
