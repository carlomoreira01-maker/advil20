"""Leitura geométrica conservadora de rótulos TISS/SP-SADT. Sem integração externa."""
import re
from datetime import datetime
from core import norm
from ocr_processing import union_box, source_box

SCHEMA={
 2:('Guia prestador','id'),3:('Guia principal','id'),4:('Data autorização','date'),
 5:('Senha autorização','id'),6:('Validade senha','date'),7:('Guia operadora','id'),
 8:('Carteira','id'),9:('Validade carteira','date'),10:('Paciente','name'),
 13:('Código solicitante','id'),15:('Medico','name'),16:('Conselho','council'),
 17:('Número conselho','number'),18:('UF conselho','uf'),22:('Data solicitação','date')}
EXTRA_FIELDS=['Guia prestador','Guia principal','Data autorização','Senha autorização','Validade senha',
 'Guia operadora','Carteira','Validade carteira','Código solicitante','Conselho','Número conselho','UF conselho',
 'Data solicitação','Indicação clínica','Regime atendimento','Data execução']
STARTS={2:'NUMERO GUIA',3:'NUMERO GUIA',4:'DATA',5:'SENHA',6:'VALIDADE',7:'NUMERO GUIA',8:'NUMERO CARTEIRA',
9:'VALIDADE',10:'NOME',13:'CODIGO',15:'NOME',16:'CONSELHO',17:'NUMERO',18:'UF',22:'DATA',
25:'CODIGO',26:'DESCRICAO',27:'QUANTIDADE QTD QTDE QTD.',28:'QUANTIDADE QTD QTDE QTD.'}
UFS=set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())


def empty_field(document=None):
 return {'value':'','page':None,'box':None,'confidence':None,'reviewed':False,'document':document,'snippet':'','candidates':[]}


def valid(value,kind):
 if not value:return False
 if kind=='id':return bool(re.fullmatch(r'[A-Z0-9][A-Z0-9./-]*',value)) and bool(re.search(r'\d',value))
 if kind=='number':return bool(re.fullmatch(r'\d+',value))
 if kind=='date':
  try:datetime.strptime(value,'%d/%m/%Y');return True
  except ValueError:return False
 if kind=='uf':return value in UFS
 if kind=='council':return value in {'CRM','CRO','COREN','CRBM','CRF','CREFITO','CRP','CRN','CRFA'}
 return len(value.split())>=2 and not re.search(r'\d',value) and not any(t in value for t in ['CONTRATADO','BENEFICIARIO','PROFISSIONAL','CONSELHO'])


def anchors(page):
 found=[]
 for line in page['lines']:
  words=line.get('words',[])
  row=[]
  for i,w in enumerate(words):
   token=norm(w['text']);match=re.fullmatch(r'(\d{1,2})(?:([-.)])([A-ZÀ-Ÿ].*)?)?',token)
   if not match:continue
   num=int(match[1])
   if num not in STARTS:continue
   nxt=norm(words[i+1]['text']).strip(':-') if i+1<len(words) else ''
   punct=bool(match[2]) or (i+1<len(words) and words[i+1]['text'] in ['-','–',')'])
   if not punct and nxt not in STARTS[num].split():continue
   row.append({'num':num,'x':w['box'][0],'y':w['box'][1],'height':w['box'][3]-w['box'][1],
               'index':i,'line':line})
  for j,a in enumerate(row):
   a['right']=row[j+1]['x']-3 if j+1<len(row) else max(page['size'][0],max((w['box'][2] for l in page['lines'] for w in l.get('words',[])),default=0))+1
   segment=words[a['index']:(row[j+1]['index'] if j+1<len(row) else len(words))]
   a['header']=segment;a['bottom']=max(w['box'][3] for w in segment)
   # Inline value after an explicit separator is accepted without using a fixed cell coordinate.
   found.append(a)
 return found


def extract(document):
 fields={key:empty_field(document.get('file')) for key,_ in SCHEMA.values()}
 found_any=False;exams=[];executed=[];extra=[];issues=[];section='solicitados';headers=None
 for page in document['pages']:
  aa=anchors(page)
  validated=[a for a in aa if any(token in re.sub(r'\d+[-.)]', ' ',norm(' '.join(w['text'] for w in a['header']))).split() for token in STARTS[a['num']].split())]
  # A numbered prescription list is not a TISS form. Require multiple semantically valid anchors.
  if len(validated)>=2 and (any(a['num'] in [2,5,7,8,10,15] for a in validated) or 'SP/SADT' in norm(page.get('text',''))):found_any=True
  all_words=[w for l in page['lines'] for w in l.get('words',[])]
  for a in aa:
   if a['num'] not in SCHEMA:continue
   key,kind=SCHEMA[a['num']]
   label=re.sub(r'\d+[-.)]', ' ', norm(' '.join(w['text'] for w in a['header'])))
   if not any(token in label.split() for token in STARTS[a['num']].split()):continue
   next_y=min((b['y'] for b in aa if b['y']>a['bottom'] and b['x']<a['right'] and b['right']>a['x']),default=a['bottom']+a['height']*6)
   height=max(a['height'],8)
   region=[w for w in all_words if a['x']-3<=w['box'][0]<a['right'] and a['bottom']+1<=w['box'][1]<min(next_y-2,a['bottom']+height*6)]
   # Do not carry another field's label or procedure table into a cell.
   region=[w for w in region if not any(w in b['header'] for b in aa)]
   from engine_v2 import group_lines
   lines=group_lines(region)
   candidate=[]
   if kind=='name':
    name_lines=[l for l in lines if re.search(r'[A-Z]',norm(l['text'])) and not re.search(r'\d',l['text'])
                and not any(t in norm(l['text']) for t in ['BENEFICIARIO','PROFISSIONAL','SOLICITANTE','CONTRATADO','OPERADORA','CONSELHO','PROCEDIMENTOS','EXAMES','SOLICITADOS','EXECUTADOS'])]
    joined=norm(' '.join(l['text'] for l in name_lines))
    if valid(joined,kind):
     ws=[w for l in name_lines for w in l['words']]
     candidate=[joined,{'text':' / '.join(l['text'] for l in name_lines),'words':ws,'box':union_box(ws,False),'confidence':min(l['confidence'] for l in name_lines)}]
   # A label may wrap: select the first valid value row, retaining its precise box.
   for line in ([] if candidate else lines):
    value=norm(line['text']).strip(' :|')
    if kind in ['id','number','date']:value=re.sub(r'\s+','',value)
    if valid(value,kind):candidate=[value,line];break
   if not candidate:
    raw=' '.join(w['text'] for w in a['header'])
    if ':' in raw:
     value=norm(raw.rsplit(':',1)[1]).strip()
     if valid(value,kind):candidate=[value,{'words':a['header'],'text':raw,'box':a['line']['box'],'confidence':a['line']['confidence']}]
   if not candidate:continue
   value,line=candidate
   src={'value':value,'document':document.get('file'),'page':page['number'],'box':source_box(line),
        'confidence':line['confidence'],'snippet':' '.join(w['text'] for w in a['header'])+' / '+line['text'],
        'reviewed':False,'candidates':[],'tiss_number':a['num'],'origin_type':'campo_estruturado'}
   previous=fields[key]
   if previous['candidates'] or (previous['value'] and norm(previous['value'])!=value) or line['confidence']<65:
    src['candidates']=previous['candidates']+([previous] if previous['value'] else [])+[dict(src)]
    src['value']='';issues.append('Campo '+key+' incerto ou conflitante; conferir origem.')
   fields[key]=src
  # Procedure columns are associated geometrically, independently of label punctuation.
  headers=None
  for line in page['lines']:
   n=norm(line['text']);words=line.get('words',[])
   if re.search(r'(PROCEDIMENTOS|EXAMES).*(EXECUTADOS|REALIZADOS)',n):section='executados';headers=None;continue
   if re.search(r'(PROCEDIMENTOS|EXAMES).*(SOLICITADOS|AUTORIZADOS)',n):section='solicitados';headers=None;continue
   row_anchors=[a for a in aa if a['line'] is line and a['num'] in [25,26,27,28]]
   if len(row_anchors)>=2 and any(a['num']==25 for a in row_anchors):
    headers=[(a['x'],{25:'codigo',26:'descricao',27:'quantidade_solicitada',28:'quantidade_autorizada'}[a['num']]) for a in row_anchors]
    headers.extend((w['box'][0],'material') for w in words if norm(w['text']) in ['MATERIAL','AMOSTRA'])
    headers.sort();continue
   if 'CODIGO' in n and ('DESCRICAO' in n or 'PROCEDIMENTO' in n):
    cols=[]
    for index,w in enumerate(words):
     token=norm(w['text']).strip('.:')
     if token in ['CODIGO','TUSS']:cols.append((w['box'][0],'codigo'))
     elif token in ['DESCRICAO','PROCEDIMENTO']:cols.append((w['box'][0],'descricao'))
     elif token in ['MATERIAL','AMOSTRA']:cols.append((w['box'][0],'material'))
     elif token in ['QTD','QTDE','QUANTIDADE']:
      suffix=norm(' '.join(x['text'] for x in words[index+1:index+3]))
      key='quantidade_executada' if section=='executados' else 'quantidade_autorizada' if suffix.startswith('AUT') else 'quantidade_solicitada'
      cols.append((w['box'][0],key))
    if len(cols)>=2:headers=cols;continue
   if headers:
    if not words:continue
    cells={k:[] for _,k in headers}
    for w in words:
     cols=[(x,k) for x,k in headers if w['box'][0]>=x-5]
     if cols:cells[cols[-1][1]].append(w)
    text={k:' '.join(w['text'] for w in ws).strip() for k,ws in cells.items()}
    code=re.sub(r'\s+','',text.get('codigo',''))
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{1,39}',code) or not text.get('descricao'):
     # Description continuation is allowed only next to an identified preceding row.
     bucket=executed if section=='executados' else exams
     if not code and bucket and text.get('descricao') and not text.get('quantidade_solicitada') and not text.get('quantidade_autorizada') and bucket[-1]['page']==page['number']:
      previous=bucket[-1]
      previous['descricao']+=' '+text['descricao']
      origin={'page':page['number'],'box':source_box(line),'document':document.get('file'),'snippet':line['text']}
      previous['origins'].append(origin)
      oldbox=previous['box'];newbox=origin['box'];previous['box']=[min(oldbox[0],newbox[0]),min(oldbox[1],newbox[1]),max(oldbox[2],newbox[2]),max(oldbox[3],newbox[3])]
      previous['snippet']+=' / '+line['text']
     continue
    src={'page':page['number'],'box':source_box(line),'confidence':line['confidence'],'reviewed':False,
         'document':document.get('file'),'snippet':line['text'],'raw':line['text'],'notes':[]}
    row={**src,**text,'codigo':code,'material':text.get('material',''),'section':section,'origins':[dict(src)]}
    for qty in ['quantidade_solicitada','quantidade_autorizada','quantidade_executada']:
     row[qty]=re.sub(r'\s+','',row.get(qty,''))
     if not re.fullmatch(r'\d{1,3}',row[qty]) or not cells.get(qty) or min(w['confidence'] for w in cells[qty])<80:row[qty]=''
    row['cell_origins']={k:{'page':page['number'],'box':union_box(ws),'snippet':' '.join(w['text'] for w in ws),'document':document.get('file')} for k,ws in cells.items()}
    row['quantidade']=row['quantidade_autorizada']
    if row['quantidade_autorizada'] in ['', '0']:row['notes'].append('Quantidade autorizada ausente, zero ou ilegível. Não autorizado por inferência.')
    (executed if section=='executados' else exams).append(row)
   if re.search(r'\b(ETIQUETA|PROTOCOLO|CONTROLE|ATENDIMENTO)\b',n) or (aa and line['box'][1]<min(a['y'] for a in aa) and re.search(r'\b\d{5,}\b',n)):
    for code in re.findall(r'\b\d{3,}\b',n):extra.append({'value':code,'purpose':'não verificada','page':page['number'],'box':source_box(line),'snippet':line['text']})
 # Executed procedures never create a second request or supply missing authorization.
 for e in exams:
  e['execution_occurrences']=[x for x in executed if x['codigo']==e['codigo'] and norm(x['descricao'])==norm(e['descricao'])]
 for row in executed:
  if not any(e['codigo']==row['codigo'] and norm(e['descricao'])==norm(row['descricao']) for e in exams):issues.append('Procedimento executado sem correspondente na solicitação; conferir original.')
 return {'detected':found_any,'fields':fields,'exams':exams,'executed_exams':executed,'extra_numbers':extra,'issues':issues,
         'layout_profile':'rótulos numerados SP/SADT; homologação local pendente'}
