"""Configuração do OCR local. Nunca lê documentos pela rede nem expõe stderr."""
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


class LocalReadError(ValueError):
    """Erro conhecido cuja mensagem não contém dados do documento."""



def tesseract_exe():
    configured = os.getenv('SHIFT_TESSERACT', '').strip().strip('"')
    if configured:
        # Um caminho explicitamente configurado não pode ser ignorado silenciosamente.
        return configured if Path(configured).is_file() else None
    candidates = [shutil.which('tesseract')]
    for base in [os.getenv('ProgramFiles', r'C:\Program Files'),
                 os.getenv('ProgramFiles(x86)', r'C:\Program Files (x86)')]:
        candidates.append(str(Path(base) / 'Tesseract-OCR' / 'tesseract.exe'))
    local = Path(os.getenv('LOCALAPPDATA', '.'))
    candidates.extend(str(local / p / 'tesseract.exe') for p in
                      ['Programs/Tesseract-OCR', 'Tesseract-OCR'])
    return next((str(p) for p in candidates if p and Path(p).is_file()), None)


def run_local(args, timeout=120):
    return subprocess.run(args, capture_output=True, encoding='utf-8', errors='replace',
                          timeout=timeout, creationflags=0x08000000 if os.name == 'nt' else 0)


def ocr_configuration(language='por+eng', exe=None):
    exe = exe or tesseract_exe()
    if not exe:
        raise LocalReadError('Tesseract ausente ou SHIFT_TESSERACT inválido. Execute INSTALAR_WINDOWS.bat.')
    requested = language.split('+')
    if not requested or any(not p.isalpha() for p in requested):
        raise LocalReadError('Idioma OCR inválido. Use por, eng ou por+eng.')
    explicit = os.getenv('SHIFT_TESSDATA', '').strip().strip('"')
    bundled = ROOT / 'tessdata'
    args = []
    if explicit:
        args = ['--tessdata-dir', str(Path(explicit))]
    elif all((bundled / (p + '.traineddata')).is_file() for p in requested):
        # Não depende de TESSDATA_PREFIX herdado de outra instalação no Windows.
        args = ['--tessdata-dir', str(bundled)]
    result = run_local([exe, *args, '--list-langs'], timeout=15)
    available = sorted(p.strip() for p in result.stdout.splitlines()
                       if p.strip().isalpha() and len(p.strip()) <= 12)
    if result.returncode or any(p not in available for p in requested):
        missing = ', '.join(p for p in requested if p not in available)
        raise LocalReadError('Idiomas OCR indisponíveis: ' + (missing or language) +
                         '. Execute INSTALAR_WINDOWS.bat ou confira SHIFT_TESSDATA.')
    return {'exe': exe, 'args': args, 'languages': available, 'requested': language}


def safe_failure(exc):
    """Mensagens técnicas sem caminho, nome de arquivo, texto OCR ou stderr."""
    if isinstance(exc, LocalReadError):
        return str(exc)
    if isinstance(exc, subprocess.TimeoutExpired):
        return 'Tempo limite do OCR excedido; confira a qualidade e tente novamente.'
    if isinstance(exc, PermissionError):
        return 'Acesso negado ao arquivo ou pasta local. Confira as permissões.'
    if isinstance(exc, FileNotFoundError):
        return 'Arquivo ou executável local não encontrado. Confira a instalação.'
    # ValueErrors de bibliotecas também podem conter caminhos/dados do documento.
    return 'Falha local (' + type(exc).__name__ + '). Execute o diagnóstico de instalação e confira o documento.'
