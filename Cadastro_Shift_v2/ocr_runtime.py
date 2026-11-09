"""Configuração e diagnóstico de OCR exclusivamente local, sem conteúdo clínico em logs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent


class LocalReadError(ValueError):
    """Erro conhecido cuja mensagem não contém dados do documento."""


def settings_file():
    override = os.getenv('SHIFT_OCR_CONFIG', '').strip().strip('"')
    if override:
        return Path(override)
    appdata = os.getenv('APPDATA')
    if appdata:
        return Path(appdata) / 'CadastroAssistidoShift' / 'ocr.json'
    return ROOT / 'dados_v2' / 'configuracao_ocr.json'


def load_settings(path=None):
    path = Path(path) if path is not None else settings_file()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise LocalReadError('Não foi possível ler a configuração OCR. Abra Configurações OCR e salve novamente.') from exc
    if not isinstance(data, dict) or not isinstance(data.get('tesseract_path', ''), str):
        raise LocalReadError('Configuração OCR inválida. Selecione novamente o executável nas Configurações OCR.')
    return data


def save_settings(executable, path=None):
    """Persistência atômica, local e fora do código; nunca grava documentos/credenciais."""
    path = Path(path) if path is not None else settings_file()
    executable = str(executable).strip().strip('"')
    if not executable or not Path(executable).is_file():
        raise LocalReadError('O executável selecionado não existe. Escolha tesseract.exe.')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.ocr-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'version': 1, 'tesseract_path': str(Path(executable).resolve())}, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def registry_candidates():
    """Consulta somente chaves conhecidas do Tesseract no Windows; não altera o Registro."""
    if os.name != 'nt':
        return []
    import winreg
    found = []
    keys = [(r'SOFTWARE\Tesseract-OCR', 'Path'),
            (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Tesseract-OCR', 'InstallLocation'),
            (r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\tesseract.exe', '')]
    for hive in [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]:
        for view in [winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY]:
            for key, value in keys:
                try:
                    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as handle:
                        location = winreg.QueryValueEx(handle, value)[0]
                    if isinstance(location, str):
                        p = Path(os.path.expandvars(location.strip().strip('"')))
                        found.append(p if p.suffix.lower() == '.exe' else p / 'tesseract.exe')
                except OSError:
                    continue
    return found


def candidate_executables(settings_path=None, include_saved=True):
    candidates = []
    if include_saved:
        # Arquivo corrompido gera erro explícito no diagnóstico, mas não impede
        # a busca automática/manual de recuperar a configuração.
        try:
            candidates.append(load_settings(settings_path).get('tesseract_path'))
        except LocalReadError:
            pass
    candidates.extend([os.getenv('SHIFT_TESSERACT'), shutil.which('tesseract')])
    candidates.extend(registry_candidates())
    for base in [os.getenv('ProgramFiles', r'C:\Program Files'),
                 os.getenv('ProgramFiles(x86)', r'C:\Program Files (x86)')]:
        candidates.append(Path(base) / 'Tesseract-OCR' / 'tesseract.exe')
    local = Path(os.getenv('LOCALAPPDATA', '.'))
    candidates.extend(local / p / 'tesseract.exe' for p in ['Programs/Tesseract-OCR', 'Tesseract-OCR'])
    profile = Path(os.getenv('USERPROFILE') or Path.home())
    # Busca finita: inclui instalações portáteis como Downloads\TESSERACT.
    for base in [profile / 'Downloads', profile / 'Desktop', ROOT, ROOT.parent]:
        candidates.extend(base / p / 'tesseract.exe' for p in ['TESSERACT', 'Tesseract-OCR'])
    candidates.append(ROOT / 'tesseract.exe')
    found = []; seen = set()
    for item in candidates:
        if item:
            item = str(item).strip().strip('"')
            if item and item not in seen:
                seen.add(item); found.append(item)
    return found


def tesseract_exe(settings_path=None, include_saved=True):
    # Um caminho antigo que deixou de existir não deve ocultar uma instalação válida.
    return next((p for p in candidate_executables(settings_path, include_saved) if Path(p).is_file()), None)


def run_local(args, timeout=120):
    from reading_control import current_event,check_cancelled
    import time
    event=current_event()
    if event is not None:
        check_cancelled();started=time.monotonic()
        with subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding='utf-8',errors='replace',env={**os.environ,'OMP_THREAD_LIMIT':'1'},creationflags=0x08000000 if os.name=='nt' else 0) as process:
            try:
                while True:
                    check_cancelled()
                    if time.monotonic()-started>timeout:raise subprocess.TimeoutExpired(args,timeout)
                    try:
                        out,err=process.communicate(timeout=.1);return subprocess.CompletedProcess(args,process.returncode,out,err)
                    except subprocess.TimeoutExpired:pass
            except BaseException:
                process.kill();process.communicate();raise
    return subprocess.run(args, capture_output=True, encoding='utf-8', errors='replace',
                          timeout=timeout, env={**os.environ,'OMP_THREAD_LIMIT':os.environ.get('OMP_THREAD_LIMIT','2')}, creationflags=0x08000000 if os.name == 'nt' else 0)


def ocr_configuration(language='por+eng', exe=None, settings_path=None):
    exe = exe or tesseract_exe(settings_path)
    if not exe:
        raise LocalReadError('Tesseract ausente. Abra Configurações OCR e selecione tesseract.exe.')
    if not Path(exe).is_file():
        raise LocalReadError('Executável OCR não encontrado. Selecione tesseract.exe novamente.')
    requested = language.split('+')
    if not requested or any(not p.isalpha() for p in requested):
        raise LocalReadError('Idioma OCR inválido. Use por, eng ou por+eng.')
    explicit = os.getenv('SHIFT_TESSDATA', '').strip().strip('"')
    bundled = ROOT / 'tessdata'
    args = []
    if explicit:
        args = ['--tessdata-dir', str(Path(explicit))]
    elif all((bundled / (p + '.traineddata')).is_file() for p in requested):
        args = ['--tessdata-dir', str(bundled)]
    result = run_local([str(exe), *args, '--list-langs'], timeout=15)
    available = sorted(p.strip() for p in result.stdout.splitlines()
                       if p.strip().isalpha() and len(p.strip()) <= 12)
    if result.returncode or any(p not in available for p in requested):
        missing = ', '.join(p for p in requested if p not in available)
        raise LocalReadError('Idiomas OCR indisponíveis: ' + (missing or language) +
                            '. Extraia novamente a pasta tessdata do pacote (por e eng) ou confira SHIFT_TESSDATA.')
    return {'exe': str(exe), 'args': args, 'languages': available, 'requested': language}


def check_ocr_health(exe=None, settings_path=None):
    """Estado verde exige mecanismo, dois idiomas e OCR REAL de uma imagem fictícia."""
    try:
        if exe is None:
            load_settings(settings_path)  # não omitir configuração ilegível no diagnóstico
        config = ocr_configuration('por+eng', exe=exe, settings_path=settings_path)
        version = run_local([config['exe'], '--version'], timeout=15)
        if version.returncode or 'tesseract' not in version.stdout.lower():
            raise LocalReadError('O arquivo selecionado não respondeu como Tesseract. Escolha tesseract.exe.')
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new('RGB', (1400, 220), 'white')
        font = None
        for name in ['arial.ttf', 'DejaVuSans.ttf']:
            try:
                font = ImageFont.truetype(name, 42); break
            except OSError:
                continue
        font = font or ImageFont.load_default(size=42)
        ImageDraw.Draw(image).text((30, 60), 'Teste OCR local Hemograma', font=font, fill='black')
        with tempfile.TemporaryDirectory(prefix='shift_ocr_check_') as tmp:
            path = Path(tmp) / 'teste.png'; image.save(path)
            for lang in ['por', 'eng', 'por+eng']:
                result = run_local([config['exe'], str(path), 'stdout', *config['args'],
                                    '-l', lang, '--psm', '6'], timeout=30)
                if result.returncode or 'hemograma' not in result.stdout.casefold():
                    raise LocalReadError('OCR não leu a imagem fictícia no idioma ' + lang +
                                        '. Verifique o executável e os modelos em Configurações OCR.')
        return {'ok': True, 'message': 'OCR funcionando · português e inglês · teste de leitura aprovado',
                'languages': config['languages'], 'exe': config['exe']}
    except Exception as exc:
        return {'ok': False, 'message': safe_failure(exc), 'languages': []}


def safe_failure(exc):
    """Mensagens técnicas sem caminho, nome de arquivo, texto OCR ou stderr."""
    if isinstance(exc, LocalReadError):
        return str(exc)
    if isinstance(exc, subprocess.TimeoutExpired):
        return 'Tempo limite do OCR excedido; confira a instalação e tente novamente.'
    if isinstance(exc, PermissionError):
        return 'Acesso negado ao arquivo ou pasta local. Confira as permissões.'
    if isinstance(exc, FileNotFoundError):
        return 'Arquivo ou executável local não encontrado. Confira a instalação.'
    if isinstance(exc, OSError):
        return 'Não foi possível executar o OCR local. Escolha tesseract.exe e confira suas dependências.'
    return 'Falha local (' + type(exc).__name__ + '). Execute o diagnóstico de instalação e confira o documento.'
