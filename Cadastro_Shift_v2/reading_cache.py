"""Cache privado local: conteúdo OCR nunca sai da pasta de dados do usuário."""
import gzip,hashlib,json,os,tempfile,time,zlib
from pathlib import Path
from ocr_runtime import load_settings,tesseract_exe,ROOT

def file_hash(path):
    try:return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except (OSError,TypeError):return None
def signature(settings_path=None,language='por+eng'):
    exe=tesseract_exe(settings_path);data=Path(os.getenv('SHIFT_TESSDATA') or ROOT/'tessdata')
    values={'settings':load_settings(settings_path),'language':language,'exe':exe,'binary':file_hash(exe),
        'models':{lang:file_hash(data/(lang+'.traineddata')) for lang in language.split('+')},
        'reader':{name:file_hash(ROOT/name) for name in ['engine_v2.py','ocr_processing.py','ocr_regions.py','ocr_runtime.py','tiss.py','tiss_geometry.py','tiss_names.py','tiss_refinement.py']}}
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()

class ReadingCache:
    def __init__(self,folder):self.folder=Path(folder)
    def key(self,path,settings_path=None):
        content=file_hash(path)
        if content is None:raise ValueError('Arquivo não localizado para leitura.')
        return hashlib.sha256((content+signature(settings_path)).encode()).hexdigest()
    def get(self,key):
        path=self.folder/(key+'.json.gz')
        try:
            with gzip.open(path,'rt',encoding='utf-8') as f:value=json.load(f)
            if value['key']!=key or not isinstance(value['document']['pages'],list):return None
            os.utime(path,None);return value['document']
        except (OSError,ValueError,KeyError,TypeError,EOFError,zlib.error):return None
    def put(self,key,document):
        if any(p.get('failed') for p in document['pages']):return
        self.folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        temp=None
        try:
            with tempfile.NamedTemporaryFile(dir=self.folder,delete=False) as f:temp=Path(f.name)
            with gzip.open(temp,'wt',encoding='utf-8') as f:json.dump({'key':key,'document':document},f,ensure_ascii=False)
            os.replace(temp,self.folder/(key+'.json.gz'))
            files=sorted(self.folder.glob('*.json.gz'),key=lambda p:p.stat().st_mtime,reverse=True);size=0
            for i,path in enumerate(files):
                size+=path.stat().st_size
                if i>=128 or size>256*1024*1024:path.unlink(missing_ok=True)
        finally:
            if temp is not None:temp.unlink(missing_ok=True)
