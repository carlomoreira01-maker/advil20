"""Importação de escaneamentos integrais e classificação por página, inteiramente local."""
import copy
import hashlib
from pathlib import Path
import re
import uuid
from core import norm, digest
from engine_v2 import read_document, parse_document, FIELDS
from ocr_runtime import LocalReadError

KINDS=['pedido','guia','continuação de pedido','continuação de guia','outro','incerto']
IDENTIFIERS=['Nascimento','Carteira']


def value(model,key):return norm(model['fields'].get(key,{}).get('value',''))


def compatible(a,b):
 """Nome sozinho, proximidade e ordem de importação nunca associam pacientes."""
 names=[value(m,'Paciente') for m in [a,b]]
 if names[0] and names[1] and names[0]!=names[1]:return False
 common=[k for k in IDENTIFIERS if value(a,k) and value(b,k)]
 if any(value(a,k)!=value(b,k) for k in common):return False
 return bool(common and names[0] and names[1])


def classify(document,page,catalog):
 one={**document,'pages':[page]};one.pop('document_type',None)
 model=parse_document(one,catalog)
 text=norm(page.get('text',''))
 kind=model['document_type']
 if kind not in ['pedido','guia']:
  # Printed request headings need not contain the literal word PEDIDO.
  if value(model,'Paciente') and model['exams'] and re.search(r'\b(SOLICITACAO|SOLICITO|REQUISICAO)\b',text):kind='pedido'
  elif re.search(r'\b(RECIBO|COMPROVANTE|RESULTADO DE EXAME)\b',text):kind='outro'
  else:kind='incerto'
 if re.search(r'\bCONTINUA(?:CAO)?\b',text) and kind in ['pedido','guia']:kind='continuação de '+kind
 if kind=='guia' and model.get('tiss') and model['exams'] and not value(model,'Paciente') and not value(model,'Carteira') and not value(model,'Guia prestador'):
  kind='continuação de guia'
 return kind,model


def read_scan(paths,data,catalog,settings_path=None,progress=None):
 paths=[Path(p) for p in paths]
 if not 1<=len(paths)<=100:raise LocalReadError('Selecione de 1 a 100 arquivos.')
 target=Path(data)/'documentos';target.mkdir(parents=True,exist_ok=True)
 batch={'id':uuid.uuid4().hex,'sources':{},'pages':[],'version':1}
 seen=set()
 for index,path in enumerate(paths,1):
  if path.suffix.lower() not in ['.pdf','.png','.jpg','.jpeg']:raise LocalReadError('Importe PDF, JPG ou PNG.')
  if progress:progress(index,len(paths),'Lendo arquivo '+str(index)+' de '+str(len(paths)))
  document=read_document(path,settings_path=settings_path,
      progress=(lambda page,total:progress(index,len(paths),'Arquivo '+str(index)+'/'+str(len(paths))+' · lendo página '+str(page)+'/'+str(total))) if progress else None)
  sha=document['sha256']
  if sha in seen:continue
  seen.add(sha);raw=path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=sha:raise LocalReadError('Arquivo mudou durante a leitura. Importe novamente.')
  dest=target/(sha+path.suffix.lower())
  if not dest.exists():dest.write_bytes(raw)
  document['local_path']=str(dest.resolve());batch['sources'][sha]=document
  for page in document['pages']:
   kind,model=classify(document,page,catalog)
   batch['pages'].append({'id':sha+':'+str(page['number']),'source':sha,'page':page['number'],
       'kind':kind,'group':'','model':model,'reviewed':False,'reason':'',
       'classification_reason':'Rótulos/estrutura reconhecidos' if kind not in ['incerto','outro'] else 'Tipo não confirmado; conferir original.'})
 groups=[]
 for item in batch['pages']:
  matches=[group for group in groups if all(other['kind'] not in ['incerto','outro'] and compatible(item['model'],other['model']) for other in group)]
  # Unknown pages always remain separate for manual assignment, even with a name.
  if len(matches)==1 and item['kind'] not in ['incerto','outro']:
   group=matches[0];item['group']=group[0]['group'];group.append(item)
  else:
   item['group']='Atendimento '+str(len(groups)+1);groups.append([item])
 return batch


def build_cases(batch,catalog):
 """Grupos editáveis; nenhuma página é descartada, nem o PDF é recortado."""
 groups={}
 for item in batch['pages']:
  if item['kind'] not in KINDS or not item['group'].strip():raise LocalReadError('Defina tipo e atendimento para todas as páginas.')
  groups.setdefault(item['group'].strip(),[]).append(item)
 cases=[]
 for name,items in groups.items():
  docs={};models={}
  for role in ['pedido','guia']:
   selected=[i for i in items if i['kind'] in [role,'continuação de '+role] or (role=='pedido' and i['kind'] in ['outro','incerto'])]
   ids=[i['id'] for i in selected]
   doc={'file':name+' · '+role,'sha256':digest({'role':role,'pages':ids,'missing':batch['id'] if not ids else ''}),
        'document_type':role,'pages':[],'scan_batch':batch['id'],'scan_group':name,'page_ids':ids,
        'original_sources':[]}

   source_ids={i['source'] for i in selected}
   doc['original_sources']=[{k:s[k] for k in ['file','sha256','local_path']} for sha,s in batch['sources'].items() if sha in source_ids]
   for i in selected:
    source=batch['sources'][i['source']];page=copy.deepcopy(next(p for p in source['pages'] if p['number']==i['page']))
    page['source']={'sha256':source['sha256'],'file':source['file'],'path':source['local_path'],'page':page['number']}
    page['number']=len(doc['pages'])+1;doc['pages'].append(page)
   docs[role]=doc;model=parse_document(doc,catalog);models[role]=model
   model['scan_group']=name;model['classification_pending']=any(i['kind'] in ['incerto','outro'] or (i['reason'] and not i['reviewed']) for i in items)
   model['identity_conflict']=any(value(a['model'],key) and value(b['model'],key) and value(a['model'],key)!=value(b['model'],key)
       for n,a in enumerate(items) for b in items[n+1:] for key in IDENTIFIERS)
   if not selected:
    model['issues'].append({'message':role.capitalize()+': documento não identificado neste atendimento. Corrija a classificação ou use fluxo interno homologado.','reviewed':False,'reason':''})
    if role=='guia':model['tiss']=True
   if any(i['kind'] in ['incerto','outro'] for i in items):
    model['issues'].append({'message':'Há página com tipo incerto/outro. Identifique sua finalidade em Identificar documentos antes de preparar.','reviewed':False,'reason':''})
   if len(items)>1:
    # A manual grouping records the decision but never suppresses identity conflicts.
    refs=[i['model'] for i in items if value(i['model'],'Paciente')]
    model['association_pending']=len(refs)<len(items) or any(not compatible(a,b) for n,a in enumerate(refs) for b in refs[n+1:])
    if model['association_pending'] and all(i['reviewed'] and i['reason'].strip() for i in items):model['association_pending']=False
   else:model['association_pending']=False
   # Keep logical page for navigation and physical source for traceability.
   def provenance(obj):
    if isinstance(obj,dict):
     page_no=obj.get('page')
     if isinstance(page_no,int) and 1<=page_no<=len(doc['pages']):
      obj['source_document']=copy.deepcopy(doc['pages'][page_no-1]['source'])
     for key,v in list(obj.items()):
      if key!='source_document':provenance(v)
    elif isinstance(obj,list):
     for v in obj:provenance(v)
   provenance(model)
  cases.append((name,docs,models))
 return cases


def save_batch(store,batch,catalog,actor,replace=False):
 cases=build_cases(batch,catalog)
 # A stable physical-page fingerprint catches reimports in any file order.
 fingerprint=digest(sorted(i['id'] for i in batch['pages']))
 store.db.execute('CREATE TABLE IF NOT EXISTS scan_batches(id TEXT PRIMARY KEY,fingerprint TEXT UNIQUE,content TEXT)')
 store.db.execute('CREATE TABLE IF NOT EXISTS scan_cases(batch TEXT,group_name TEXT,caso TEXT,PRIMARY KEY(batch,group_name))')
 store.db.execute('CREATE TABLE IF NOT EXISTS scan_pages(id TEXT PRIMARY KEY,batch TEXT)')
 store.db.commit()
 import json
 duplicate=store.db.execute('SELECT id FROM scan_batches WHERE fingerprint=?',(fingerprint,)).fetchone()
 if duplicate and duplicate[0]!=batch['id']:raise LocalReadError('Este escaneamento já está na fila. Use Identificar documentos ou Reprocessar leitura no atendimento existente.')
 existing=store.db.execute('SELECT id,content FROM scan_batches WHERE id=?',(batch['id'],)).fetchone()
 result=[]
 with store.db:
  for item in batch['pages']:
   prior=store.db.execute('SELECT batch FROM scan_pages WHERE id=?',(item['id'],)).fetchone()
   if prior and prior[0]!=batch['id']:raise LocalReadError('Uma página deste arquivo já pertence a outro escaneamento na fila. Reabra o atendimento existente.')
   store.db.execute('INSERT OR IGNORE INTO scan_pages VALUES(?,?)',(item['id'],batch['id']))
  old=dict(store.db.execute('SELECT group_name,caso FROM scan_cases WHERE batch=?',(batch['id'],)))
  if old and not replace:raise LocalReadError('Escaneamento já importado.')
  for cid in old.values():
   if store.get(cid)[2]=='PREPARADO':raise LocalReadError('Há pré-cadastro preparado neste escaneamento. Reclassificação bloqueada para preservar a revisão.')
  if existing:
   original=json.loads(existing[1]);before={i['id'] for i in original['pages']}
   if before!={i['id'] for i in batch['pages']}:raise LocalReadError('Reclassificação deve preservar todas as páginas originais.')
   for sha,source in original['sources'].items():
    if batch['sources'][sha]['sha256']!=source['sha256']:raise LocalReadError('Original alterado.')
  for name,docs,models in cases:
   obj={'docs':docs,'models':models};encoded=json.dumps(obj,ensure_ascii=False)
   if name in old:
    cid=old.pop(name);previous,rev,_,_=store.get(cid)
    store.db.execute('INSERT OR IGNORE INTO revisoes_v2 VALUES(?,?,?)',(cid,rev,json.dumps(previous,ensure_ascii=False)))
    store.db.execute('INSERT INTO revisoes_v2 VALUES(?,?,?)',(cid,rev+1,json.dumps({**obj,'revisor':actor,'motivo':'Reclassificação/reprocessamento do escaneamento'},ensure_ascii=False)))
    store.db.execute('UPDATE casos_v2 SET current=?,revision=?,status=? WHERE id=?',(encoded,rev+1,'CONFERIR',cid))
   else:
    cid=uuid.uuid4().hex;key=digest([batch['id'],name,cid])
    store.db.execute('INSERT INTO casos_v2 VALUES(?,?,?,?,?,?,?)',(cid,key,encoded,encoded,1,'CONFERIR',None))
   result.append(cid);store.db.execute('INSERT OR REPLACE INTO scan_cases VALUES(?,?,?)',(batch['id'],name,cid));store.audit(cid,'CLASSIFICAR_ESCANEAMENTO',{})
  for cid in old.values():store.db.execute('UPDATE casos_v2 SET status=? WHERE id=?',('RECLASSIFICADO',cid))
  for name in old:store.db.execute('DELETE FROM scan_cases WHERE batch=? AND group_name=?',(batch['id'],name))
  store.db.execute('INSERT OR REPLACE INTO scan_batches VALUES(?,?,?)',(batch['id'],fingerprint,json.dumps(batch,ensure_ascii=False)))
 return result


def load_batch(store,batch_id):
 import json
 row=store.db.execute('SELECT content FROM scan_batches WHERE id=?',(batch_id,)).fetchone()
 if not row:raise LocalReadError('Escaneamento não localizado.')
 return json.loads(row[0])
