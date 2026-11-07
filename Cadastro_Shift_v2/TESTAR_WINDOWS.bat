@echo off
setlocal
cd /d "%~dp0"
set "SHIFT_GUI_TESTS=1"
if not exist ".venv\Scripts\python.exe" (
 echo Execute INSTALAR_WINDOWS.bat primeiro.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" diagnostico.py
if errorlevel 1 (
 pause
 exit /b 1
)
for /f "delims=" %%T in ('".venv\Scripts\python.exe" instalacao_aux.py localizar-ocr') do set "SHIFT_TESSERACT=%%T"
set "SHIFT_OCR_CONFIG=%TEMP%\shift_testes_%RANDOM%.json"
".venv\Scripts\python.exe" -m unittest discover -s tests -v
set "TEST_RESULT=%ERRORLEVEL%"
pause
exit /b %TEST_RESULT%
