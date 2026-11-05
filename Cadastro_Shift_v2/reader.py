"""Leitura local. Não inicia rede, não executa conteúdo de documentos."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from ocr_runtime import ocr_configuration

MAX_BYTES = 15 * 1024 * 1024


def ocr(image, language='por'):
    from PIL import ImageOps
    config = ocr_configuration(language)
    exe = config['exe']
    with tempfile.TemporaryDirectory(prefix='shift_demo_') as tmp:
        src = Path(tmp) / 'pagina.png'
        ImageOps.exif_transpose(image).convert('RGB').save(src)
        r = subprocess.run([exe, str(src), 'stdout', *config['args'], '-l', language, '--psm', '6'], capture_output=True, timeout=60, encoding='utf-8', errors='replace', creationflags=0x08000000 if os.name == 'nt' else 0)
        if r.returncode:
            raise ValueError('Falha no OCR local. Verifique a instalação do idioma ' + language + '.')
        return r.stdout


def read(path, language='por'):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Arquivo maior que 15 MB. Divida-o antes de importar.')
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == '.txt':
        text, method = data.decode('utf-8-sig'), 'Texto UTF-8'
    elif suffix == '.pdf':
        import pymupdf
        from PIL import Image
        parts = []
        with pymupdf.open(stream=data, filetype='pdf') as doc:
            if doc.is_encrypted or len(doc) > 30:
                raise ValueError('PDF protegido ou com mais de 30 páginas.')
            for page in doc:
                if page.rect.width * page.rect.height > 2_000_000:
                    raise ValueError('Página excede o limite de dimensões.')
                # Renderiza páginas inclusive as que contêm texto: disponível na conferência.
                text_page = page.get_text()
                if not text_page.strip():
                    pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                    text_page = ocr(Image.open(io.BytesIO(pix.tobytes('png'))), language)
                # Texto parcial pode ocultar imagem com exames: não aprovar sem revisão visual.
                parts.append(text_page)
            text = '\n'.join(parts)
        method = 'PDF: texto por página; OCR em páginas sem texto'
    elif suffix in ('.png', '.jpg', '.jpeg'):
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            if im.width * im.height > 25_000_000:
                raise ValueError('Imagem excede 25 megapixels.')
            text = ocr(im, language)
        method = 'OCR local Tesseract (' + language + ')'
    else:
        raise ValueError('Formato aceito: PDF, PNG, JPG, JPEG ou TXT.')
    if not text.strip():
        raise ValueError('Não foi possível reconhecer texto. Corrija a qualidade da digitalização.')
    return text, {'arquivo': path.name, 'sha256': hashlib.sha256(data).hexdigest(), 'metodo': method}


def preview(path, page_index=0):
    """Retorna imagem PIL, sem abrir navegador ou arquivo em aplicação externa."""
    from PIL import Image, ImageOps
    p = Path(path)
    if p.suffix.lower() == '.pdf':
        import pymupdf
        with pymupdf.open(p) as doc:
            if len(doc) > 30 or doc.is_encrypted:
                raise ValueError('PDF não permitido.')
            page = doc[page_index]
            if page.rect.width * page.rect.height > 2_000_000:
                raise ValueError('Página muito grande.')
            pix = page.get_pixmap(matrix=pymupdf.Matrix(1, 1))
            return Image.open(io.BytesIO(pix.tobytes('png'))).copy(), len(doc)
    with Image.open(p) as im:
        if im.width * im.height > 25_000_000:
            raise ValueError('Imagem muito grande.')
        return ImageOps.exif_transpose(im).copy(), 1
