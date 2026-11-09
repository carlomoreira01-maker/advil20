"""Extração e conferência conservadoras. Sem rede ou integração LIS."""
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from datetime import datetime, date
from core import norm, digest
from ocr_processing import source_box
from ocr_runtime import tesseract_exe, ocr_configuration, run_local, safe_failure, LocalReadError

from tiss import EXTRA_FIELDS, empty_field
FIELDS = ['Paciente', 'Nascimento', 'Fonte pagadora', 'Operadora', 'Guia', 'Medico', 'Validade', 'Status'] + EXTRA_FIELDS + ['CPF','CNS']
ALIASES = {
    'NOME DO PACIENTE':'Paciente', 'NOME DO BENEFICIARIO':'Paciente', 'BENEFICIARIO':'Paciente', 'PACIENTE':'Paciente',
    'DATA DE NASCIMENTO':'Nascimento', 'NASCIMENTO':'Nascimento', 'DATA NASC.':'Nascimento', 'DN':'Nascimento',
    'FONTE PAGADORA':'Fonte pagadora', 'CONVENIO':'Fonte pagadora', 'OPERADORA':'Operadora',
    'NUMERO DA GUIA':'Guia', 'N DA GUIA':'Guia', 'GUIA':'Guia',
    'MEDICO SOLICITANTE':'Medico', 'SOLICITANTE':'Medico', 'MEDICO':'Medico',
    'VALIDADE':'Validade', 'STATUS':'Status'
}
ALIASES.update({
    'NOME DO BENEFICIARIO/PACIENTE':'Paciente', 'NOME PACIENTE':'Paciente',
    'DATA NASCIMENTO':'Nascimento', 'DATA NASC':'Nascimento', 'DATA DE NASC.':'Nascimento',
    'CONVENIO / PLANO':'Fonte pagadora', 'PLANO DE SAUDE':'Fonte pagadora',
    'NOME DA OPERADORA':'Operadora', 'NUMERO GUIA':'Guia', 'Nº GUIA':'Guia',
    'Nº DA GUIA':'Guia', 'N° DA GUIA':'Guia', 'NUMERO GUIA OPERADORA':'Guia',
    'NUMERO DA GUIA ATRIBUIDO PELA OPERADORA':'Guia',
    'NOME DO PROFISSIONAL SOLICITANTE':'Medico', 'NOME DO CONTRATADO SOLICITANTE':'Medico',
    'SITUACAO DA GUIA':'Status', 'STATUS DA GUIA':'Status', 'SITUACAO':'Status'
})
ALIASES.update({k.upper():k for k in EXTRA_FIELDS})
ALIASES.update({'REGIME DE ATENDIMENTO':'Regime atendimento','INDICACAO CLINICA':'Indicação clínica','MATRICULA':'Carteira','CARTEIRINHA':'Carteira','CRM':'Número conselho','UF DO CONSELHO':'UF conselho'})
ALIASES.update({'CPF':'CPF','CNS':'CNS','CARTAO NACIONAL DE SAUDE':'CNS'})
ALIASES = {norm(k): v for k, v in ALIASES.items()}
MAX_BYTES = 30 * 1024 * 1024


def ocr_words(image, language='por+eng', settings_path=None):
    exe=tesseract_exe(settings_path) if settings_path is not None else tesseract_exe()
    if not exe:raise LocalReadError('Tesseract ausente. Abra Configurações OCR.')
    config=ocr_configuration(language,exe)
    from ocr_processing import recognize_page
    return recognize_page(image,lambda im,psm:_ocr_once(im,config,language,psm))


def _ocr_once(image, config, language, psm=3):
    from PIL import ImageOps
    with tempfile.TemporaryDirectory(prefix='shift_ocr_') as tmp:
        path = Path(tmp) / 'pagina.png'
        ImageOps.autocontrast(ImageOps.exif_transpose(image).convert('L')).save(path, dpi=(300, 300))
        result = run_local([config['exe'], str(path), 'stdout', *config['args'],
                            '-l', language, '--psm', str(psm), '-c', 'tessedit_create_tsv=1'])
        if result.returncode:
            raise LocalReadError('Falha no OCR local. Execute diagnostico.py para verificar mecanismo e idiomas.')
        words = []
        try:
            reader=csv.DictReader(io.StringIO(result.stdout), delimiter='\t')
            if not {'text','conf','left','top','width','height'}.issubset(reader.fieldnames or []):
                raise LocalReadError('OCR não retornou a tabela TSV esperada. Execute diagnostico.py.')
            for row in reader:
                if row.get('text', '').strip() and float(row['conf']) >= 0:
                    x, y, w, h = (int(row[k]) for k in ['left', 'top', 'width', 'height'])
                    words.append({'text': row['text'], 'box': [x, y, x+w, y+h],
                                  'confidence': float(row['conf'])})
        except (ValueError, KeyError, TypeError) as exc:
            raise LocalReadError('Resposta TSV inválida do OCR local.') from exc
        return words


def group_lines(words):
    """Agrupa por linha visual; mantém espaços entre colunas e caixas de origem."""
    groups = []
    for word in sorted(words, key=lambda w: ((w['box'][1]+w['box'][3])/2, w['box'][0])):
        b = word['box']; cy=(b[1]+b[3])/2
        matching = [g for g in groups if abs(g['cy']-cy) <= max(2, min(g['height'], b[3]-b[1])*.42)]
        if matching:
            g=min(matching, key=lambda g:abs(g['cy']-cy)); g['words'].append(word)
        else:
            groups.append({'cy':cy,'height':b[3]-b[1],'words':[word]})
    result=[]
    for g in groups:
        ws=sorted(g['words'], key=lambda w:w['box'][0]); text=''
        prev=None
        for w in ws:
            gap = w['box'][0]-prev['box'][2] if prev else 0
            text += (('   ' if gap > max(12, g['height']*1.4) else ' ') if prev else '')+w['text']
            prev=w
        result.append({'text':text,'words':ws,'box':[min(w['box'][0] for w in ws),min(w['box'][1] for w in ws),max(w['box'][2] for w in ws),max(w['box'][3] for w in ws)],
                       'confidence':min(w['confidence'] for w in ws)})
    return result


def usable(words):
    text=' '.join(w['text'] for w in words)
    # Documentos digitais curtos também são utilizáveis; tamanho não indica digitalização.
    return len(re.findall(r'[A-Za-zÀ-ÿ]',text)) >= 5 and len(words)>=2 and text.count('\ufffd')<=1


def detect_document_type(document):
    from document_classification import document_type
    return document_type(document)


def document_diagnostics(document):
    """Apenas metadados operacionais: nenhum nome, caminho, hash ou texto clínico."""
    return [{'page': p['number'], 'executed': p.get('executed', True),
             'method': p['method'], 'characters': len(p.get('text', '')),
             'failed': bool(p.get('warnings')), 'warnings': len(p.get('warnings', [])),
             'detail': ' '.join(p.get('warnings', [])),
             'languages': p.get('languages', '')} for p in document['pages']]


def read_document(path, language='por+eng', settings_path=None, progress=None, workers=1, cancel_event=None):
    import pymupdf
    from PIL import Image, ImageOps
    from time import perf_counter
    from reading_control import check_cancelled, reading_context, ReadCancelled
    from concurrent.futures import ThreadPoolExecutor
    started=perf_counter();check_cancelled(cancel_event)
    path=Path(path)
    if path.stat().st_size>MAX_BYTES: raise LocalReadError('Limite: 30 MB por documento.')
    raw=path.read_bytes(); pages=[]; ext=path.suffix.lower()
    def page_data(words, method, number, size, warnings=None):
        readings={}
        for word in words:
            if word.get('regional_reading'):
                rid=word['regional_reading'];reading=readings.setdefault(rid,{'id':rid,'family':word['regional_family'],'targets':word['regional_targets'],'bounds':word['regional_bounds'],'words':[]});reading['words'].append(word)
        words=[w for w in words if not w.get('regional_reading')]
        lines=group_lines(words)
        warnings=list(warnings or [])
        for word in words:warnings.extend(word.get('regional_warnings',[]))
        if not usable(words): warnings.append('Página sem texto utilizável; verificar original e preencher manualmente.')
        return {'number':number,'method':method,'size':list(size),'lines':lines,'warnings':warnings,
                'text':'\n'.join(l['text'] for l in lines), 'executed':True,
                'characters':sum(len(l['text']) for l in lines),
                'orientation':words[0].get('orientation',0) if words else 0,
                'deskew':words[0].get('deskew',0) if words else 0,'regional_readings':list(readings.values()),
                'failed':bool(warnings), 'languages':language if 'OCR' in method else ''}
    if ext=='.pdf':
        with pymupdf.open(stream=raw,filetype='pdf') as pdf:
            if pdf.is_encrypted or len(pdf)>30: raise LocalReadError('PDF protegido ou com mais de 30 páginas.')
            pending=[]
            def finish(words,hybrid,image,number,size,tick):
                with reading_context(cancel_event):
                    result=perform(words,hybrid,image,number,size)
                result['elapsed_seconds']=perf_counter()-tick
                return result
            def perform(words,hybrid,image,number,size):
                warnings=[]
                if not usable(words) or hybrid:
                    try:
                        ws=ocr_words(image,language,settings_path=settings_path)
                        # Coordenadas sempre normalizadas para pontos PDF.
                        for w in ws:
                            w['box']=[v/2.5 for v in w['box']]
                            if 'original_box' in w:w['original_box']=[v/2.5 for v in w['original_box']]
                            if 'regional_bounds' in w:w['regional_bounds']=[v/2.5 for v in w['regional_bounds']]
                        if hybrid and usable(words):
                            # Mantém texto digital fora da imagem; suprime duplicação espacial.
                            for w in words:
                                b=w['box']; cx=(b[0]+b[2])/2;cy=(b[1]+b[3])/2
                                if not any(o['box'][0]-3<=cx<=o['box'][2]+3 and o['box'][1]-3<=cy<=o['box'][3]+3 for o in ws): ws.append(w)
                        digital_present=usable(words)
                        words=ws;method='OCR local / página mista' if hybrid and digital_present else 'OCR local'
                    except ReadCancelled:raise
                    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                        warnings.append(safe_failure(exc));method='OCR falhou / revisão manual'
                else: method='Texto digital'
                return page_data(words,method,number,size,warnings)
            with ThreadPoolExecutor(max_workers=max(1,min(2,int(workers)))) as pool:
                for i,p in enumerate(pdf):
                    page_started=perf_counter()
                    check_cancelled(cancel_event)
                    if progress:progress(i+1,len(pdf))
                    if p.rect.width*p.rect.height>2_000_000:raise LocalReadError('Página muito grande.')
                    words=[{'text':w[4],'box':list(w[:4]),'confidence':100.0} for w in p.get_text('words')]
                    raster_boxes=[info['bbox'] for info in p.get_image_info()]
                    hybrid=any(abs((b[2]-b[0])*(b[3]-b[1]))>p.rect.width*p.rect.height*.30 and not usable([w for w in words if b[0]<=(w['box'][0]+w['box'][2])/2<=b[2] and b[1]<=(w['box'][1]+w['box'][3])/2<=b[3]]) for b in raster_boxes)
                    image=None
                    if not usable(words) or hybrid:
                        pix=p.get_pixmap(matrix=pymupdf.Matrix(2.5,2.5));image=Image.open(io.BytesIO(pix.tobytes('png')));image.load()
                    future=pool.submit(finish,words,hybrid,image,i+1,(p.rect.width,p.rect.height),page_started)
                    pending.append(future)
                    if len(pending)>=max(1,min(2,int(workers))):pages.append(pending.pop(0).result())
                for future in pending:pages.append(future.result())
    elif ext in ('.png','.jpg','.jpeg'):
        if progress:progress(1,1)
        with Image.open(io.BytesIO(raw)) as im:
            if im.width*im.height>25_000_000: raise LocalReadError('Imagem excede 25 megapixels.')
            im=ImageOps.exif_transpose(im).convert('RGB'); warnings=[]
            tick=perf_counter()
            try:
                with reading_context(cancel_event):words=ocr_words(im,language,settings_path=settings_path)
            except ReadCancelled:raise
            except (ValueError, OSError, subprocess.TimeoutExpired) as exc: words=[];warnings=[safe_failure(exc)]
            pages.append(page_data(words,'OCR falhou / revisão manual' if warnings else 'OCR local',1,im.size,warnings));pages[-1]['elapsed_seconds']=perf_counter()-tick
    elif ext=='.txt':
        lines=[]
        for i,line in enumerate(raw.decode('utf-8-sig').splitlines()):
            if line.strip(): lines.append({'text':line.strip(),'words':[], 'box':[0,i*15,600,i*15+14],'confidence':100})
        pages=[{'number':1,'method':'Texto UTF-8','size':[600,900],'lines':lines,'text':'\n'.join(l['text'] for l in lines),'warnings':[]}]
    else: raise LocalReadError('Use PDF, JPG, PNG ou TXT.')
    document={'file':path.name,'sha256':hashlib.sha256(raw).hexdigest(),'pages':pages}
    check_cancelled(cancel_event)
    document['document_type']=detect_document_type(document)
    document['elapsed_seconds']=perf_counter()-started
    return document


def catalog_load(path):
    rows=json.loads(Path(path).read_text(encoding='utf-8'))
    seen=set()
    if not isinstance(rows,list): raise ValueError('Catálogo deve ser uma lista.')
    for row in rows:
        if not isinstance(row.get('nome'),str) or not row['nome'].strip():raise ValueError('Nome padronizado obrigatório.')
        for key in ['codigo_shift','material']:
            if not isinstance(row.get(key,''),str):raise ValueError('Código interno e material devem ser texto.')
            row.setdefault(key,'')
        if not row['codigo_shift'] and not row.get('tuss'):raise ValueError('Informe TUSS ou código interno validado; não invente códigos.')
        code=norm(row['codigo_shift'])
        if code and code in seen: raise ValueError('Código interno duplicado.')
        if code:seen.add(code)
        if row.get('tuss') and not re.fullmatch(r'\d{8}',str(row['tuss'])): raise ValueError('TUSS deve ter 8 dígitos ou ficar vazio.')
        if not isinstance(row.get('sinonimos'),list) or not all(isinstance(v,str) for v in row['sinonimos']): raise ValueError('Sinônimos inválidos.')
        for rule in row.get('equivalencias',[]):
            if not all(rule.get(k) for k in ['codigo','aprovado_por','aprovado_em']) or rule.get('aprovada') is not True: raise ValueError('Equivalência precisa de aprovação explícita, responsável e data.')
    return rows


def resolve_exam(exam, catalog):
    name=norm(exam.get('descricao','')); code=norm(str(exam.get('codigo','')))
    names=[r for r in catalog if name and name in {norm(v) for v in [r['nome'],*r['sinonimos']]}]
    codes=[r for r in catalog if code and code in {norm(str(v)) for v in [r['codigo_shift'],r.get('tuss') or '',*[q['codigo'] for q in r.get('equivalencias',[]) if q.get('aprovada') is True]]}]
    if len(names)>1 or len(codes)>1: return None,'Catálogo ambíguo.'
    if names and codes and names[0] is not codes[0]: return None,'Código e descrição apontam para exames diferentes.'
    row=(names or codes or [None])[0]
    if not row: return None,'Exame não encontrado no catálogo.'
    if code and not codes: return row,'Código ausente do catálogo ou divergente.'
    if name and not names: return row,'Descrição não corresponde a nome ou sinônimo aprovado.'
    return row,None


def layout_lines(lines):
    """Separa tabelas paralelas com cabeçalhos repetidos, sem cruzar colunas."""
    for i,line in enumerate(lines):
        words=line.get('words',[])
        for token in ['CODIGO','DESCRICAO','PROCEDIMENTO']:
            starts=[w['box'][0] for w in words if norm(w['text']).strip('.:')==token]
            if len(starts)==2:
                boundary=starts[1]-10
                before=lines[:i];columns=[[],[]]
                for row in lines[i:]:
                    if not row.get('words'):
                        columns[0].append(row);continue
                    for col in [0,1]:
                        selected=[w for w in row['words'] if (w['box'][0]>=boundary)==bool(col)]
                        if selected:columns[col].extend(group_lines(selected))
                return before+columns[0]+columns[1]
    return lines


def labeled_lines(lines):
    """Aceita rótulo em linha própria e valor logo abaixo (ex.: guias impressas)."""
    result=[];i=0
    while i<len(lines):
        line=lines[i];n=norm(line['text'])
        # Guias com vários rótulos acima de valores: usar as coordenadas de coluna,
        # em vez de concatenar paciente e nascimento num único campo.
        words=line.get('words',[]);labels=[];pos=0
        while pos<len(words):
            match=None
            for end in range(len(words),pos,-1):
                label_text=norm(' '.join(w['text'] for w in words[pos:end])).strip(' :')
                label_text=re.sub(r'^\d{1,3}\s*[-.)]\s*','',label_text)
                if label_text in ALIASES:match=(end,label_text);break
            if match:
                labels.append((words[pos]['box'][0],match[1]));pos=match[0]
            else:break
        if len(labels)>1 and pos==len(words) and i+1<len(lines):
            nxt=lines[i+1];cells=[]
            for column,(x,label_text) in enumerate(labels):
                end=labels[column+1][0]-8 if column+1<len(labels) else float('inf')
                selected=[w for w in nxt.get('words',[]) if x-8<=w['box'][0]<end]
                if selected:
                    cell=group_lines(selected)[0]
                    if norm(cell['text']).strip(' :') in ALIASES:break
                    cells.append({**cell,'text':label_text+': '+cell['text']})
            else:
                if cells:result.extend(cells);i+=2;continue
        label=re.sub(r'^\d{1,3}\s*[-.)]\s*','',n).strip(' :')
        if label in ALIASES and i+1<len(lines):
            nxt=lines[i+1];value=norm(nxt['text'])
            if value and ':' not in value and value not in ALIASES and not re.search(r'\b(EXAMES|DESCRICAO|CODIGO|QUANTIDADE)\b',value):
                b=line['box'];c=nxt['box']
                result.append({**nxt,'text':label+': '+nxt['text'],'box':[min(b[0],c[0]),min(b[1],c[1]),max(b[2],c[2]),max(b[3],c[3])]});i+=2;continue
        result.append(line);i+=1
    return result


def parse_document(document, catalog):
    fields={k:{'value':'','page':None,'box':None,'confidence':None,'reviewed':False,
               'document':document.get('file'), 'snippet':'', 'candidates':[]} for k in FIELDS}
    exams=[]; issues=[]; in_exams=False; headers=None
    alias_pattern='|'.join(re.escape(a) for a in sorted(ALIASES,key=len,reverse=True))
    for page in document['pages']:
        headers=None
        for warning in page['warnings']: issues.append({'message':f'Página {page["number"]}: {warning}','reviewed':False,'reason':''})
        for line in labeled_lines(layout_lines(page['lines'])):
            text=line['text']; n=norm(text)
            src={'page':page['number'],'box':source_box(line),'confidence':line['confidence'],'reviewed':False,
                 'document':document.get('file'), 'snippet':text}
            if n.strip(' :') in ('DEMONSTRACAO','PEDIDO MEDICO','GUIA AUTORIZADA','GUIA DE AUTORIZACAO',
                                'SOLICITACAO DE EXAMES','REQUISICAO DE EXAMES','GUIA SP/SADT','GUIA DE SP/SADT'):
                continue
            # Aceita formulários numerados, com dois pontos, hífen ou apenas espaços.
            n=re.sub(r'^\d{1,3}\s*[-.)]\s*','',n)
            matches=list(re.finditer(r'(?<!\w)('+alias_pattern+r')\s*[:=]\s*',n))
            if not matches:
                # Sem delimitador, só o rótulo inicial é inequívoco. "Convenio"
                # dentro do valor "Fonte pagadora  Convenio Ficticio" é dado.
                matches=list(re.finditer(r'^('+alias_pattern+r')(?:\s+-\s+|\s+(?=\S))',n))
            if matches:
                # norm altera somente acentos/espaços: usa trechos originais via separação de rótulos.
                # Extrai múltiplos campos da mesma linha pelos índices da versão normalizada.
                for j,m in enumerate(matches):
                    value=n[m.end():matches[j+1].start() if j+1<len(matches) else len(n)].strip(' |;')
                    key=ALIASES[m.group(1)]
                    field_src=src
                    if key=='Nascimento':
                        # A surname/clinical sentence containing NASCIMENTO is
                        # not a date. Footer rows can also contain sex/age after
                        # the actual date; preserve only the printed date token.
                        birth=re.match(r'^(\d{1,2}/\d{1,2}/\d{4})(?=$|\s|[|;])',value)
                        if not birth:continue
                        value=birth[1]
                        from tiss import valid
                        if not valid(value,'date'):
                            issues.append({'message':'Nascimento com data inválida; conferir o original.','reviewed':False,'reason':''});continue
                        date_words=[w for w in line.get('words',[]) if norm(w['text']).strip(' |;')==value]
                        if date_words:
                            field_src={**src,'box':source_box({'words':date_words,'box':line['box']}),
                                       'confidence':min(w['confidence'] for w in date_words),'snippet':'Nascimento: '+value}
                    previous=fields[key]
                    candidates=previous.get('candidates', [])
                    if previous['value'] and norm(previous['value'])!=norm(value):
                        candidates=[{k:v for k,v in previous.items() if k!='candidates'}, {'value':value,**field_src}]
                        issues.append({'message':f'Campo {key} repetido com valor diferente na página {page["number"]}. Conferência obrigatória.','reviewed':False,'reason':''})
                        fields[key]={'value':'',**field_src,'candidates':candidates}
                    elif candidates or field_src['confidence'] < 60:
                        fields[key]={'value':'',**field_src,'candidates':candidates+[{'value':value,**field_src}]}
                    else: fields[key]={'value':value,**field_src,'candidates':[]}
                continue
            if re.match(r'^(EXAMES|PROCEDIMENTOS|ITENS SOLICITADOS|PROCEDIMENTOS AUTORIZADOS)\b',n): in_exams=True; continue
            # Cabeçalhos de tabela: coordenadas permitem descrição, quantidade e código em qualquer ordem.
            if any(h in n.split() for h in ['CODIGO','TUSS','COD.']) and any(h in n.split() for h in ['DESCRICAO','EXAME','PROCEDIMENTO']):
                in_exams=True;headers=[]
                for w in line.get('words',[]):
                    token=norm(w['text']).strip('.:')
                    key=next((k for k,labels in [('codigo',{'CODIGO','COD','TUSS'}),('descricao',{'DESCRICAO','EXAME','PROCEDIMENTO'}),('quantidade',{'QTD','QTDE','QUANTIDADE'}),('material',{'MATERIAL','AMOSTRA'})] if token in labels),None)
                    if key: headers.append((w['box'][0],key))
                headers.sort();continue
            if n in ('DEMONSTRACAO','PEDIDO MEDICO','GUIA AUTORIZADA','GUIA DE AUTORIZACAO'):continue
            # Linhas fora da seção só são exames quando começam por um nome exato de catálogo.
            known=any(re.match(r'^'+re.escape(norm(s))+r'(?:\s|$)',n) for r in catalog for s in [r['nome'],*r['sinonimos']])
            if not in_exams and not known: continue
            if n.startswith(('OBSERVACAO','ASSINATURA','CRM','TOTAL','DATA:')) or re.match(r'^(?:DR[.]?|DRA[.]?|CARIMBO)\s',n):
                in_exams=False;continue
            row={'descricao':'','codigo':'','quantidade':'','material':'',**src,'raw':text,'notes':[]}
            parts=[s.strip() for s in text.split('|')]
            if len(parts)==3 and re.fullmatch(r'\d+',parts[1]):
                row.update(descricao=parts[0],quantidade=parts[1],codigo=parts[2])
            elif headers and line.get('words'):
                cells={k:[] for _,k in headers}
                for w in line['words']:
                    options=[(x,k) for x,k in headers if w['box'][0]>=x-8]
                    if options: cells[options[-1][1]].append(w['text'])
                row.update({k:' '.join(v) for k,v in cells.items()})
            else:
                cells=re.split(r'\s{2,}|\s*[;|]\s*',text)
                code=re.match(r'^(\d{8}|DEMO-[A-Za-z0-9-]+)\s+(.+)$',text)
                if code: row['codigo']=code[1];text=code[2];cells=re.split(r'\s{2,}',text)
                # Quantidade explicitamente rotulada ou em coluna final. Nunca supor 1.
                qty=re.search(r'(?:\bQTD(?:E)?\.?\s*[:=]?\s*|\bQUANTIDADE\s*[:=]?\s*)(\d+)\s*$',text,re.I)
                if qty: row['quantidade']=qty[1];text=text[:qty.start()].strip()
                elif len(cells)>1 and re.fullmatch(r'\d{1,3}',cells[-1]): row['quantidade']=cells[-1];text=' '.join(cells[:-1])
                mat=re.search(r'\b(?:MATERIAL|AMOSTRA)\s*:\s*(.+)$',text,re.I)
                if mat:row['material']=mat[1];text=text[:mat.start()].strip()
                row['descricao']=re.sub(r'^\s*(?:[-•]|\d{1,2}[.)])\s*','',text).strip()
            if not row['descricao'] and not row['codigo']: continue
            if headers and exams and not row['codigo'] and not row['quantidade'] and not row['material'] and row['descricao'] and exams[-1]['page']==row['page'] and exams[-1]['codigo']:
                standalone,_=resolve_exam(row,catalog)
                if standalone is None:
                    prev=exams[-1];prev['descricao']+=' '+row['descricao'];prev['raw']+=' / '+row['raw']
                    prev['confidence']=min(prev['confidence'],row['confidence']);prev['box']=[min(prev['box'][0],row['box'][0]),min(prev['box'][1],row['box'][1]),max(prev['box'][2],row['box'][2]),max(prev['box'][3],row['box'][3])]
                    prev['notes'].append('Descrição quebrada em linhas: conferir associação no original.');continue
            _,err=resolve_exam(row,catalog)
            if err:row['notes'].append(err)
            if not str(row['quantidade']).isdigit() or not 1<=int(row['quantidade'])<=999:row['notes'].append('Quantidade ausente ou inválida.')
            if row['confidence']<80:row['notes'].append('OCR incerto: confiança mínima menor que 80%.')
            exams.append(row)
    if not exams:issues.append({'message':'Nenhum exame identificado. Confira todas as páginas e adicione os exames manualmente.','reviewed':False,'reason':''})
    # A heurística não garante cobertura: revisão visual de todas as páginas é sempre explícita.
    issues.append({'message':'Conferir todas as páginas, inclusive linhas/colunas não reconhecidas, rasuras e autorização.','reviewed':False,'reason':''})
    if not fields['Operadora']['value']:
        branded=[]
        for page in document['pages']:
            for line in page['lines'][:3]:
                names=re.findall(r'\b(?:IPASGO|UNIMED)\b',norm(line['text']))
                for name in names:branded.append((name,page,line))
        if len({name for name,_,_ in branded})==1:
            name,page,line=branded[0]
            fields['Operadora']={'value':name,'page':page['number'],'box':source_box(line),'confidence':line['confidence'],'reviewed':False,'document':document.get('file'),'snippet':line['text'],'candidates':[],'origin_type':'marca_literal_no_cabecalho'}
    from tiss import extract
    structured=extract(document)
    from professional import free_identification,reconcile
    free=free_identification(document)
    professional_issues=[]
    if structured['detected']:reconcile(structured['fields'],free,professional_issues)
    else:
        for key,field in free.items():
            if field['value'] or field.get('candidates'):
                if key=='Medico' and fields[key]['value']:
                    from prescription_layout import doctor_name
                    if doctor_name(fields[key]['value'])!=doctor_name(field['value']):
                        fields[key]={**empty_field(document.get('file')),'candidates':[copy.deepcopy(fields[key]),field],
                                     'diagnostic':'Médico do campo e do carimbo divergem; conferir origens.'}
                    else:fields[key].setdefault('corroborating_origins',[]).append(field)
                else:fields[key]=field
    if structured['detected']:
        from tiss import SCHEMA,valid
        kinds={key:kind for key,kind in SCHEMA.values()}
        for key,value in structured['fields'].items():
            # An empty structured cell must not erase a valid labelled reading.
            # Conflicts/candidates, on the other hand, must stay pending.
            if value['value'] or value.get('candidates') or not valid(fields[key]['value'],kinds[key]):fields[key]=value
        fields['Guia']=empty_field(document.get('file'))
        fields['Validade']=empty_field(document.get('file'))
        if structured['exams']:exams=structured['exams']
        else:
            # Indicação clínica é contexto, mesmo quando menciona HEMOGRAMA.
            # Não pode reaparecer como exame pela detecção genérica de nomes.
            def in_clinical_region(exam):
                b=exam.get('box')
                if not b:return False
                cx,cy=(b[0]+b[2])/2,(b[1]+b[3])/2
                return any(r['page']==exam['page'] and r['box'] and r['box'][0]-2<=cx<=r['box'][2]+2 and r['box'][1]-2<=cy<=r['box'][3]+2 for r in structured.get('field_regions',[]))
            exams=[e for e in exams if not in_clinical_region(e)]
        issues=[i for i in issues if not i['message'].startswith('Nenhum exame')]
        for msg in structured['issues']+professional_issues:issues.append({'message':msg,'reviewed':False,'reason':''})
        if not exams:issues.append({'message':'Interpretação TISS: nenhum procedimento identificado. Conferir tabela.','reviewed':False,'reason':''})
    if not structured['detected']:
        from prescription_layout import evidence as prescription_evidence
        for page in document['pages']:
            pad=prescription_evidence(page,catalog)
            if not pad['supported']:continue
            for line in pad['exam_lines']:
                if any(e['page']==page['number'] and abs(e['box'][1]-source_box(line)[1])<4 for e in exams):continue
                text=re.sub(r'^\s*(?:[-•]|\d{1,2}[.)])\s*','',line['text']);code='';qty=''
                match=re.match(r'^(\d{8})\s+(.+)$',text)
                if match:code,text=match[1],match[2]
                match=re.search(r'\b(?:QTD(?:E)?[.]?|QUANTIDADE)\s*[:=]?\s*(\d{1,3})\s*$',text,re.I)
                if match:qty=match[1];text=text[:match.start()].strip()
                notes=[];_,err=resolve_exam({'descricao':text,'codigo':code},catalog)
                if err:notes.append(err)
                if not qty:notes.append('Quantidade ausente; conferir no original, sem presumir 1.')
                exams.append({'descricao':text,'codigo':code,'quantidade':qty,'material':'','page':page['number'],
                    'box':source_box(line),'confidence':line['confidence'],'reviewed':False,'document':document.get('file'),
                    'snippet':line['text'],'raw':line['text'],'notes':notes,'origin_type':'lista_em_pedido_carimbado'})
        if exams:issues=[i for i in issues if not i['message'].startswith('Nenhum exame identificado')]
    for field in fields.values():
        if field['value']:field['extraction_state']='identified'
        elif field.get('candidates'):field['extraction_state']='uncertain'
        else:field.setdefault('extraction_state','not_found')
    return {'fields':fields,'exams':exams,'issues':issues,'pages_reviewed':False,
            'document_type':document.get('document_type', detect_document_type(document)),
            'tiss':structured['detected'],'tiss_detail':structured if structured['detected'] else None,
            'interpretation':{'executed':True,'fields_found':sum(bool(v['value']) for v in fields.values()),'exams_found':len(exams)}}


def compare_models(p,g,catalog):
    if g.get('tiss'):
        from tiss_comparison import compare_tiss
        return compare_tiss(p,g,catalog)
    errors=[]; rows=[]
    for key in ['Paciente','Nascimento']:
        a=p['fields'][key]['value'];b=g['fields'][key]['value']
        if not a or not b:errors.append(f'{key}: preencher nos dois documentos para confirmar a associação.')
        elif norm(a)!=norm(b):errors.append(f'{key}: documentos de pacientes diferentes ou dado divergente.')
    for model in [p,g]:
        dob=model['fields']['Nascimento']['value']
        if dob:
            try:
                if datetime.strptime(dob,'%d/%m/%Y').date()>date.today(): raise ValueError()
            except ValueError:errors.append('Nascimento inválido: use DD/MM/AAAA.')
    for key in ['Fonte pagadora','Operadora','Guia']:
        a=p['fields'][key]['value'];b=g['fields'][key]['value']
        if a and b and norm(a)!=norm(b):errors.append(f'{key} divergente entre pedido e guia.')
    if not g['fields']['Guia']['value']:errors.append('Número da guia ausente.')
    if not (g['fields']['Fonte pagadora']['value'] or g['fields']['Operadora']['value']):errors.append('Fonte pagadora/operadora ausente na guia.')
    if not p['fields']['Medico']['value']:errors.append('Médico solicitante ausente.')
    status=norm(g['fields']['Status']['value'])
    if status!='AUTORIZADO':errors.append('Status da guia ausente ou diferente de AUTORIZADO.')
    val=g['fields']['Validade']['value']
    if val:
        try:
            if datetime.strptime(val,'%d/%m/%Y').date()<date.today():errors.append('Guia vencida.')
        except ValueError:errors.append('Validade inválida.')
    maps=[]
    for title,model in [('Pedido',p),('Guia',g)]:
        found={}
        if not model['exams']:errors.append(title+': nenhum exame.')
        for e in model['exams']:
            row,err=resolve_exam(e,catalog)
            if err:errors.append(title+': '+err+' '+e['descricao'])
            if not row:
                rows.append({'nome':e.get('descricao') or 'Não identificado','codigo_shift':'','codigo_lido':e.get('codigo',''),
                  'pedido':e.get('quantidade','') if title=='Pedido' else '', 'guia':e.get('quantidade','') if title=='Guia' else '',
                  'situacao':'Catálogo: correspondência não validada','pagina_pedido':e.get('page') if title=='Pedido' else None,'pagina_guia':e.get('page') if title=='Guia' else None})
            if not str(e['quantidade']).isdigit() or not 1<=int(e['quantidade'])<=999:errors.append(title+': quantidade inválida '+e['descricao']);continue
            if row:
                code=row.get('tuss') or row['codigo_shift'] or norm(row['nome'])
                if code in found:errors.append(title+': exame repetido '+code)
                found[code]=(e,row)
                if not row['codigo_shift']:errors.append('Código interno Shift não fornecido pelo laboratório.')
                if e['material'] and norm(e['material'])!=norm(row['material']):errors.append(title+': material difere do catálogo: '+e['descricao'])
        maps.append(found)
    for code in sorted(set(maps[0])|set(maps[1])):
        a=maps[0].get(code);b=maps[1].get(code)
        qa=int(a[0]['quantidade']) if a else 0; qb=int(b[0]['quantidade']) if b else 0
        state='Conferir'
        if not a or not b:state='Ausente no pedido' if not a else 'Ausente na guia'
        elif qa!=qb:state='Quantidade divergente'
        if state!='Conferir':errors.append(code+': '+state)
        r=(a or b)[1]
        rows.append({**r,'pedido':qa,'guia':qb,'situacao':state,'pagina_pedido':a[0]['page'] if a else None,'pagina_guia':b[0]['page'] if b else None})
    return {'exames':rows,'pendencias':list(dict.fromkeys(errors)),'catalogo_hash':digest(catalog)}


def review_errors(models):
    errors=[]
    for kind,m in models.items():
        errors.extend(kind+': '+e for e in m.get('scan_validation_errors',[]))
        if m.get('identity_conflict'):errors.append(kind+': identificadores incompatíveis nas páginas agrupadas. Separe os pacientes em Identificar documentos.')
        if m.get('classification_pending'):errors.append(kind+': classificação de página pendente. Abra Identificar documentos.')
        if m.get('association_pending'):errors.append(kind+': associação das páginas não confirmada. Confira identificadores em Identificar documentos.')
        if not m['pages_reviewed']:errors.append(kind+': originais ainda não conferidos.')
        if any(not v['reviewed'] for v in m['fields'].values()):errors.append(kind+': confira todos os campos, inclusive ausências.')
        if any(not e['reviewed'] for e in m['exams']):errors.append(kind+': confira cada exame.')
        if any(not i['reviewed'] or not i['reason'].strip() for i in m['issues']):errors.append(kind+': registre a resolução dos alertas.')
    return errors


class CaseStore:
    def __init__(self,path):
        self.data_dir=Path(path).resolve().parent
        self.db=sqlite3.connect(path)
        self.db.executescript('CREATE TABLE IF NOT EXISTS casos_v2(id TEXT PRIMARY KEY, hash TEXT UNIQUE, original TEXT, current TEXT, revision INTEGER, status TEXT, output TEXT); CREATE TABLE IF NOT EXISTS audit_v2(at TEXT,caso TEXT,acao TEXT,detalhe TEXT);')
        self.db.execute('CREATE TABLE IF NOT EXISTS revisoes_v2(caso TEXT, revision INTEGER, conteudo TEXT, PRIMARY KEY(caso,revision))')
        self.db.commit()
    def audit(self,cid,action,data):
        # Registros operacionais não guardam paciente, texto, arquivo, revisor ou motivo livre.
        # Originais e revisões permanecem no registro local do caso, separados dos logs.
        detail={'evento':action}
        if 'revisao' in data:detail['revisao']=data['revisao']
        if 'antes' in data:detail['alteracao_registrada_no_caso']=True
        self.db.execute('INSERT INTO audit_v2 VALUES(?,?,?,?)',
                        (datetime.now().isoformat(),cid,action,json.dumps(detail,ensure_ascii=False)))
    def add(self,docs,models,actor):
        if docs['pedido']['sha256']==docs['guia']['sha256']:raise ValueError('Pedido e guia são o mesmo arquivo. Selecione os dois documentos correspondentes.')
        cid=uuid.uuid4().hex;key=digest([docs[k]['sha256'] for k in ['pedido','guia']]);obj={'docs':docs,'models':models}
        try:
            with self.db:
                self.db.execute('INSERT INTO casos_v2 VALUES(?,?,?,?,?,?,?)',(cid,key,json.dumps(obj,ensure_ascii=False),json.dumps(obj,ensure_ascii=False),1,'CONFERIR',None));self.audit(cid,'IMPORTAR',{'revisor':actor,'hash':key})
        except sqlite3.IntegrityError as exc:raise ValueError('Este par já está na fila.') from exc
        return cid
    def get(self,cid):
        r=self.db.execute('SELECT current,revision,status,output FROM casos_v2 WHERE id=?',(cid,)).fetchone()
        if not r:raise ValueError('Caso inexistente.')
        obj=json.loads(r[0])
        for model in obj['models'].values():
            for key in FIELDS:model['fields'].setdefault(key,empty_field())
        return obj,r[1],r[2],json.loads(r[3]) if r[3] else None
    def save(self,cid,models,actor,reason,revision,documents=None):
        if not actor.strip() or not reason.strip():raise ValueError('Informe revisor e motivo da conferência.')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            obj,rev,status,_=self.get(cid)
            if rev!=revision or status=='PREPARADO':raise ValueError('Caso mudou ou já foi preparado. Reabra para conferir.')
            before=copy.deepcopy(obj['models']);before_docs=copy.deepcopy(obj['docs']);obj['models']=models
            obj['review_metadata']={'revisor':actor.strip(),'motivo':reason.strip()}
            if documents is not None:
                if sorted(d['sha256'] for d in documents.values())!=sorted(d['sha256'] for d in obj['docs'].values()):
                    raise ValueError('Reanálise deve usar os mesmos documentos do atendimento.')
                obj['docs']=documents
            # Revisões clínicas são dados locais do caso, nunca registros técnicos.
            self.db.execute('INSERT OR IGNORE INTO revisoes_v2 VALUES(?,?,?)',
                            (cid,rev,json.dumps({'models':before,'docs':before_docs},ensure_ascii=False)))
            self.db.execute('INSERT INTO revisoes_v2 VALUES(?,?,?)',
                            (cid,rev+1,json.dumps({'models':models,'docs':obj['docs'],'revisor':actor,'motivo':reason},ensure_ascii=False)))
            self.db.execute('UPDATE casos_v2 SET current=?,revision=revision+1 WHERE id=?',(json.dumps(obj,ensure_ascii=False),cid))
            self.audit(cid,'CONFERIR',{'revisor':actor,'motivo':reason,'antes':before,'depois':models})
    def prepare(self,cid,catalog,actor,revision,cat_hash,confirmed):
        with self.db:
            self.db.execute('BEGIN IMMEDIATE');obj,rev,status,_=self.get(cid)
            if not confirmed or not actor.strip():raise ValueError('Confirmação humana e revisor obrigatórios.')
            if rev!=revision or digest(catalog)!=cat_hash or status=='PREPARADO':raise ValueError('Revisão/catálogo mudou ou pré-cadastro já preparado.')
            from document_integrity import verified_sources
            verified_sources(obj['docs'],self.data_dir)
            models=obj['models'];result=compare_models(models['pedido'],models['guia'],catalog)
            errors=result['pendencias']+review_errors(models)
            if errors:raise ValueError('\n'.join(errors))
            identity=digest([norm(models['pedido']['fields']['Paciente']['value']),models['pedido']['fields']['Nascimento']['value'],
                             {k:models['guia']['fields'].get(k,{}).get('value','') for k in ['Guia','Guia prestador','Guia principal','Guia operadora','Senha autorização','Carteira']},
                             models['guia'].get('payer_profile',{}).get('id','')])
            legacy_identity=digest([norm(models['pedido']['fields']['Paciente']['value']),models['pedido']['fields']['Nascimento']['value'],norm(models['guia']['fields']['Guia']['value'])])
            for (s,) in self.db.execute('SELECT output FROM casos_v2 WHERE output IS NOT NULL'):
                if json.loads(s)['identidade_hash'] in [identity,legacy_identity]:raise ValueError('Possível pré-cadastro duplicado: paciente, nascimento e guia já preparados.')
            output={'versao':2,'tipo':'PRE_CADASTRO_LOCAL_NAO_ENVIADO','os_real':None,'revisor':actor,'caso':cid,'revisao':rev,'identidade_hash':identity,'catalogo':copy.deepcopy(catalog),'documentos':{k:{'arquivo':d['file'],'sha256':d['sha256']} for k,d in obj['docs'].items()},'conferencia':models,**result}
            self.db.execute('UPDATE casos_v2 SET status=?,output=? WHERE id=?',('PREPARADO',json.dumps(output,ensure_ascii=False),cid));self.audit(cid,'PREPARAR',{'revisor':actor,'revisao':rev})
            return output
