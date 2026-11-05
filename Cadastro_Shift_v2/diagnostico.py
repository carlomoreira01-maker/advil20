"""Verifica dependências e OCR local com dados sintéticos, sem rede ou PHI."""
import sys
import tempfile
from pathlib import Path


def main():
    import hashlib, json
    td=Path(__file__).resolve().parent/'tessdata'
    for name,expected in json.loads((td/'MODELOS.sha256.json').read_text()).items():
        if hashlib.sha256((td/name).read_bytes()).hexdigest()!=expected:
            from ocr_runtime import LocalReadError
            raise LocalReadError('Modelo OCR corrompido. Extraia novamente o pacote completo.')
    print('Integridade dos modelos português e inglês: OK')
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont
    from engine_v2 import ocr_words, read_document
    from ocr_runtime import ocr_configuration
    print('Python:',sys.version.split()[0]);print('PyMuPDF:',pymupdf.VersionBind)
    config=ocr_configuration('por+eng')
    print('Tesseract: disponível. Idiomas:', ', '.join(config['languages']))
    im=Image.new('RGB',(1600,250),'white');draw=ImageDraw.Draw(im)
    for name in ['arial.ttf','DejaVuSans.ttf']:
        try:font=ImageFont.truetype(name,42);break
        except OSError:font=None
    font=font or ImageFont.load_default(size=42)
    draw.text((25,60),'Synthetic example Hemograma',fill='black',font=font)
    for lang in ['por','eng','por+eng']:
        text=' '.join(w['text'] for w in ocr_words(im,lang))
        if 'Hemograma' not in text:raise ValueError('OCR não reconheceu a imagem sintética de teste.')
        print('OCR',lang,': OK')
    with tempfile.TemporaryDirectory(prefix='shift_check_') as tmp:
        path=Path(tmp)/'digital.pdf'
        doc=pymupdf.open();p=doc.new_page();p.insert_text((35,40),'Paciente: Exemplo Ficticio\nExames: Hemograma');doc.save(path);doc.close()
        result=read_document(path)
        if result['pages'][0]['method']!='Texto digital' or 'Exemplo Ficticio' not in result['pages'][0]['text']:
            raise ValueError('Leitura digital sintética falhou.')
    print('PDF digital: OK. Processamento exclusivamente local.')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        from ocr_runtime import safe_failure
        print('FALHA:',safe_failure(exc));sys.exit(1)
