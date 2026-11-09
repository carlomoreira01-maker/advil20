@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Execute INSTALAR_WINDOWS.bat primeiro.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto falhou
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto falhou
echo Simulacao instalada. Abra Mais opcoes e Treinamento RPA no programa.
pause
exit /b 0
:falhou
echo Instalacao incompleta. Confira a mensagem acima. Nao desative protecoes.
pause
exit /b 1
