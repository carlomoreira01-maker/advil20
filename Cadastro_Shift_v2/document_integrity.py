"""Confere as cópias locais por conteúdo; erros não revelam caminhos ou dados clínicos."""
import hashlib
from pathlib import Path
from ocr_runtime import LocalReadError

def verified_sources(docs,data_dir=None):
    seen={}
    for doc in docs.values():
        originals=doc.get('original_sources',[])
        if not originals and doc.get('local_path') and not doc.get('scan_batch'):originals=[doc]
        for source in originals:
            sha=source['sha256']
            if sha in seen:continue
            local=Path(data_dir)/'documentos'/(sha+Path(source['file']).suffix.lower()) if data_dir is not None else None
            path=local if local is not None and local.is_file() else Path(source.get('local_path',''))
            try:actual=hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:raise LocalReadError('Documento original local indisponível. Restaure a pasta de documentos do backup antes de continuar.') from None
            if actual!=sha:raise LocalReadError('A cópia local de um documento foi alterada. A preparação foi bloqueada; restaure o original do backup.')
            seen[sha]=path
    return seen
