"""Instala bibliotecas Python do projeto. Sem PowerShell, winget ou alteração de segurança."""
from pathlib import Path
import subprocess,sys


def main():
 root=Path(__file__).resolve().parent
 if not (3,12)<=sys.version_info[:2]<(3,15):
  print('Instale Python 3.12 a 3.14 pelo site oficial python.org.');return 1
 venv=root/'.venv';python=venv/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
 if not python.exists():subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
 print('Instalando somente as bibliotecas fixadas em requirements.txt. Nenhum documento é enviado.')
 subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','-r',str(root/'requirements.txt')],cwd=root,check=True)
 print('Bibliotecas instaladas. Abra INICIAR_WINDOWS.bat e confira Configurações OCR.')
 print('Se o antivírus detectar uma ameaça, mantenha o bloqueio e solicite análise do nome da ameaça/arquivo. Não desative proteções.')
 return 0

if __name__=='__main__':
 try:sys.exit(main())
 except subprocess.CalledProcessError:print('Instalação incompleta. Confira a mensagem do instalador de bibliotecas.');sys.exit(1)
 except OSError:print('Não foi possível acessar Python ou a pasta local.');sys.exit(1)
