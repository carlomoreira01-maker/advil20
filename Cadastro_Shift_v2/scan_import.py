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
from identity_evidence import IDENTIFIERS, value, compatible


def classify(document,page,catalog):
 one={**document,'pages':[page]};one.pop('document_type',None)
 model=parse_document(one,catalog)
 from document_classification import classify_page
 classification=classify_page(page,catalog);kind=classification['kind'];model['classification']=classification
 if kind=='guia' and model.get('tiss') and model['exams'] and not value(model,'Paciente') and not value(model,'Carteira') and not value(model,'Guia prestador'):
  kind='continuação de guia'
 classification['kind']=kind
 if kind in ['pedido','guia','continuação de pedido','continuação de guia']:model['document_type']=kind.replace('continuação de ','')
 return kind,model


def read_scan(paths,data,catalog,settings_path=None,progress=None,mode='multiple',cancel_event=None,workers=None,use_cache=True):
 from time import perf_counter
 from reading_control import check_cancelled,page_workers
 from reading_cache import ReadingCache
 import os
 started=perf_counter();timings=[]
 workers=max(1,min(2,workers or page_workers()))
 cache=ReadingCache(Path(data)/'cache_leitura')
 if mode not in ['single','multiple']:raise LocalReadError('Modo de importação inválido.')
 paths=[Path(p) for p in paths]
 if not 1<=len(paths)<=100:raise LocalReadError('Selecione de 1 a 100 arquivos.')
 target=Path(data)/'documentos';target.mkdir(parents=True,exist_ok=True)
 batch={'id':uuid.uuid4().hex,'sources':{},'pages':[],'version':2,'mode':mode,'group_reviews':{}}
 seen=set()
 for index,path in enumerate(paths,1):
  check_cancelled(cancel_event);tick=perf_counter();file_started=tick;hit=False;key=None
  if path.suffix.lower() not in ['.pdf','.png','.jpg','.jpeg']:raise LocalReadError('Importe PDF, JPG ou PNG.')
  if progress:progress(index,len(paths),'Lendo arquivo '+str(index)+' de '+str(len(paths)))
  try:
   if use_cache:key=cache.key(path,settings_path)
   document=cache.get(key) if key else None
  except (OSError,ValueError):document=None
  if document is not None:hit=True;document['file']=path.name
  else:
   document=read_document(path,settings_path=settings_path,workers=workers,cancel_event=cancel_event,
       progress=(lambda page,total:progress(index,len(paths),'Arquivo '+str(index)+'/'+str(len(paths))+' · lendo página '+str(page)+'/'+str(total))) if progress else None)
   check_cancelled(cancel_event)
   if key:
    try:cache.put(key,document)
    except OSError:pass  # Cache é opcional; leitura válida permanece disponível.
  reading_seconds=perf_counter()-tick;check_cancelled(cancel_event)
  sha=document['sha256']
  if sha in seen:continue
  seen.add(sha);raw=path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=sha:raise LocalReadError('Arquivo mudou durante a leitura. Importe novamente.')
  dest=target/(sha+path.suffix.lower())
  if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()!=sha:raise LocalReadError('A cópia local do documento original foi alterada. Restaure o arquivo pelo backup antes de continuar.')
  if not dest.exists():dest.write_bytes(raw)
  document['local_path']=str(dest.resolve());batch['sources'][sha]=document
  for page in document['pages']:
   check_cancelled(cancel_event);tick=perf_counter()
   kind,model=classify(document,page,catalog)
   page['interpretation_seconds']=perf_counter()-tick
   batch['pages'].append({'id':sha+':'+str(page['number']),'source':sha,'page':page['number'],
       'kind':kind,'classification_origin':'automatic','group':'','model':model,'reviewed':False,'reason':'',
       'classification_reason':model['classification']['reason']})
  timings.append({'file_number':index,'total_seconds':perf_counter()-file_started,'read_seconds':reading_seconds,'cache_hit':hit,'pages':[{'page':p['number'],'read_seconds':0 if hit else p.get('elapsed_seconds',0),'interpretation_seconds':p['interpretation_seconds'],'method':p['method']} for p in document['pages']]})
 batch['timing']={'files':timings,'total_seconds':perf_counter()-started,'workers':workers}
 if mode=='single':
  order={sha:i+1 for i,sha in enumerate(batch['sources'])}
  for item in batch['pages']:item['group']='Atendimento '+str(order[item['source']])
  return batch
 groups=[]
 for item in batch['pages']:
  matches=[group for group in groups if any(compatible(item['model'],other['model']) for other in group) and not assess_group([*group,item])['errors'] and all(other['kind'] not in ['incerto','outro'] for other in group)]
  # Unknown pages always remain separate for manual assignment, even with a name.
  if len(matches)==1 and item['kind'] not in ['incerto','outro']:
   group=matches[0];item['group']=group[0]['group'];group.append(item)
  else:
   item['group']='Atendimento '+str(len(groups)+1);groups.append([item])
 return batch


def merge_reprocessed(batch,previous):
 old_pages={p['id']:p for p in previous['pages']}
 if set(old_pages)!={p['id'] for p in batch['pages']}:raise LocalReadError('Os originais não correspondem às páginas importadas.')
 batch['id']=previous['id']
 for sha,source in batch['sources'].items():source['file']=previous['sources'][sha]['file']
 for item in batch['pages']:
  old=old_pages[item['id']];item['group']=old['group']
  manual=old.get('classification_origin')=='manual' or (old.get('reviewed') and bool(old.get('reason','').strip()))
  if manual:
   for key in ['kind','reviewed','reason']:item[key]=old[key]
   item['classification_origin']='manual'
  if old.get('identity_edits'):
   apply_identity_edits(item,{k:h['history'][-1]['after'] for k,h in old['identity_edits'].items()},'Reprocessamento local','Reaplicação de correção humana registrada')
   item['identity_edits']=copy.deepcopy(old['identity_edits'])
 batch['group_reviews']={}
 return batch


def group_fingerprint(items):
 return digest([{'id':i['id'],'kind':i['kind'],'identidade':{k:value(i['model'],k) for k in ['Paciente',*IDENTIFIERS]},
                 'reviewed':i['reviewed'],'identity_edits':i.get('identity_edits',{})} for i in items])


def assess_group(items):
 from identity_evidence import identifier,names_compatible,full_name
 errors=[];models=[i['model'] for i in items];name=full_name(models)
 names=[value(m,'Paciente') for m in models if value(m,'Paciente')]
 if names and not name:errors.append('Nomes incompatíveis entre páginas; confira a identificação ou separe os atendimentos.')
 for key in IDENTIFIERS:
  values={identifier(key,value(m,key)) for m in models if identifier(key,value(m,key))}
  if len(values)>1:errors.append(key+': identificadores incompatíveis entre páginas.')
  if any(value(m,key) and not identifier(key,value(m,key)) for m in models):errors.append(key+': identificação inválida/ilegível; confira a página.')
 sufficient=bool(name and len(name.split())>=2 and any(identifier(k,value(m,k)) for m in models for k in IDENTIFIERS))
 return {'errors':errors,'name':name,'sufficient':sufficient}


def confirm_group(batch,group,actor,reason,seen_ids):
 from datetime import datetime
 items=[i for i in batch['pages'] if i['group']==group]
 if not actor.strip() or not reason.strip():raise LocalReadError('Informe revisor e motivo para confirmar o agrupamento.')
 if not items:raise LocalReadError('Atendimento não localizado.')
 assessment=assess_group(items)
 if assessment['errors']:raise LocalReadError('Agrupamento bloqueado: '+' '.join(assessment['errors']))
 if not assessment['sufficient']:raise LocalReadError('Identificação insuficiente: confira nome completo e ao menos um identificador válido.')
 if any(i['id'] not in seen_ids for i in items):raise LocalReadError('Visualize todas as páginas deste atendimento antes de confirmar o agrupamento.')
 if any(i['kind']=='incerto' or (i['kind']=='outro' and (not i['reviewed'] or not i['reason'].strip())) for i in items):
  raise LocalReadError('Classifique as páginas desconhecidas e confirme a finalidade dos documentos complementares.')
 batch.setdefault('group_reviews',{})[group]={'fingerprint':group_fingerprint(items),'actor':actor.strip(),'reason':reason.strip(),'at':datetime.now().isoformat()}


def apply_identity_edits(item,edits,actor,reason):
 if not actor.strip() or not reason.strip():raise LocalReadError('Informe revisor e motivo para corrigir a identificação da página.')
 allowed=['Paciente',*IDENTIFIERS]
 for key,new in edits.items():
  if key not in allowed:raise LocalReadError('Campo de identificação desconhecido.')
  from tiss import empty_field
  field=item['model']['fields'].setdefault(key,empty_field())
  if field['value']==new:continue
  history=item.setdefault('identity_edits',{}).setdefault(key,{'original':copy.deepcopy(field),'history':[]})
  history['history'].append({'before':field['value'],'after':new,'actor':actor,'reason':reason})
  field.update(value=new,confidence=None,reviewed=False,origin_type='correcao_manual_da_pagina',candidates=[])


def _merged_fields(model,doc,selected):
 from identity_evidence import full_name,identifier
 from tiss import empty_field
 for key in FIELDS:
  candidates=[]
  for logical,item in enumerate(selected,1):
   field=copy.deepcopy(item['model']['fields'].get(key,empty_field()))
   if not field.get('value'):continue
   field['page']=logical;field['document']=doc['file'];field['source_document']=copy.deepcopy(doc['pages'][logical-1]['source'])
   candidates.append(field)
  if not candidates:continue
  if key in ['Paciente','Medico']:
   name=full_name([{'fields':{'Paciente':c}} for c in candidates])
   equivalent=bool(name);chosen=next((c for c in candidates if value({'fields':{'Paciente':c}},'Paciente')==name),candidates[0])
  else:
   keys={identifier(key,c['value']) if key in IDENTIFIERS else norm(c['value']) for c in candidates}
   equivalent=len(keys)==1;chosen=candidates[0]
  if equivalent:
   chosen['origins']=[{k:c.get(k) for k in ['document','page','box','snippet','source_document']} for c in candidates]
   model['fields'][key]=chosen
   model['issues']=[i for i in model['issues'] if not (i['message'].startswith('Campo '+key+' repetido') or i['message'].startswith('Campo '+key+' incerto ou conflitante'))]
  else:
   model['fields'][key]={**empty_field(doc['file']),'candidates':candidates,'diagnostic':'Valores conflitantes entre páginas; conferir cada origem.'}
   model['issues'].append({'message':'Campo '+key+' conflitante entre páginas; confira a origem antes de corrigir.','reviewed':False,'reason':''})


def build_cases(batch,catalog):
 """Uma ficha provisória pode conter páginas sem identificação; isso não a aprova."""
 groups={}
 for item in batch['pages']:
  if item['kind'] not in KINDS or not item['group'].strip():raise LocalReadError('Defina tipo e atendimento para todas as páginas.')
  groups.setdefault(item['group'].strip(),[]).append(item)
 cases=[]
 for name,items in groups.items():
  docs={};models={};assessment=assess_group(items)
  approval=batch.get('group_reviews',{}).get(name,{})
  confirmed=bool(approval.get('fingerprint')==group_fingerprint(items) and approval.get('actor') and approval.get('reason') and assessment['sufficient'] and not assessment['errors'])
  missing=any(not value(i['model'],'Paciente') for i in items)
  pending=(batch.get('mode','multiple')=='single' and not confirmed) or (not confirmed and (missing or not assessment['sufficient']))
  for role in ['pedido','guia','apoio']:
   selected=[i for i in items if (i['kind'] in ['outro','incerto'] if role=='apoio' else i['kind'] in [role,'continuação de '+role])]
   if role=='apoio' and not selected:continue
   ids=[i['id'] for i in selected]
   doc={'file':name+' · '+role,'sha256':digest({'role':role,'pages':ids,'missing':batch['id'] if not ids else ''}),
        'document_type':role,'pages':[],'scan_batch':batch['id'],'scan_group':name,'page_ids':ids,'original_sources':[]}
   source_ids={i['source'] for i in selected}
   doc['original_sources']=[{k:s[k] for k in ['file','sha256','local_path']} for sha,s in batch['sources'].items() if sha in source_ids]
   for item in selected:
    source=batch['sources'][item['source']];page=copy.deepcopy(next(p for p in source['pages'] if p['number']==item['page']))
    page['source']={'sha256':source['sha256'],'file':source['file'],'path':source['local_path'],'page':page['number']}
    page['number']=len(doc['pages'])+1;doc['pages'].append(page)
   docs[role]=doc
   if role=='apoio':continue  # Preserved and visible; never interpreted as a prescription.
   model=parse_document(doc,catalog);models[role]=model
   # Reconcile actual values from individual pages. Empty/partial continuation
   # must not erase a full name printed elsewhere in this same document.
   _merged_fields(model,doc,selected)
   model['interpretation'].update(fields_found=sum(bool(v['value']) for v in model['fields'].values()),exams_found=len(model['exams']))
   model.update(scan_group=name,scan_mode=batch.get('mode','multiple'),association_pending=pending,
       scan_association_confirmed=confirmed,identity_conflict=bool(assessment['errors']),
       scan_validation_errors=assessment['errors'],scan_patient_name=assessment['name'],
       classification_pending=any(i['kind']=='incerto' or (i['kind']=='outro' and (not i['reviewed'] or not i['reason'].strip())) for i in items))
   if not selected:
    model['issues'].append({'message':role.capitalize()+': documento não identificado neste atendimento. Corrija a classificação ou use fluxo interno homologado.','reviewed':False,'reason':''})
    if role=='guia':model['tiss']=True
   if model['classification_pending']:
    model['issues'].append({'message':'Há página desconhecida ou complementar sem revisão. Abra Identificar documentos.','reviewed':False,'reason':''})
   def provenance(obj):
    if isinstance(obj,dict):
     page_no=obj.get('page')
     if isinstance(page_no,int) and 1<=page_no<=len(doc['pages']) and not obj.get('source_document'):
      obj['source_document']=copy.deepcopy(doc['pages'][page_no-1]['source'])
     for key,v in list(obj.items()):
      if key!='source_document':provenance(v)
    elif isinstance(obj,list):
     for v in obj:provenance(v)
   provenance(model)
  cases.append((name,docs,models))
 return cases


def preserve_manual(previous,docs,models):
 """Mantém ajustes do mesmo conjunto físico de páginas, exigindo nova conferência."""
 for role,model in models.items():
  old=previous['models'].get(role,{})
  if old.get('payer_profile'):model['payer_profile']=copy.deepcopy(old['payer_profile'])
  before=previous['docs'].get(role,{}).get('page_ids',[]);after=docs[role].get('page_ids',[])
  if not before or set(before)!=set(after):continue
  page_map={i+1:after.index(pid)+1 for i,pid in enumerate(before)}
  for key,field in old.get('fields',{}).items():
   if field.get('origin_type') not in ['correcao_manual','escolha_humana_de_leitura','nao_aplicavel_perfil_homologado']:continue
   if field.get('not_applicable') and model['fields'][key]['value']:continue
   saved=copy.deepcopy(field);saved.update(reviewed=False)
   if saved.get('page') in page_map:saved['page']=page_map[saved['page']]
   model['fields'][key]=saved
  for exam in old.get('exams',[]):
   if exam.get('origin_type')!='correcao_manual':continue
   saved=copy.deepcopy(exam);saved.update(reviewed=False,page=page_map.get(exam.get('page'),exam.get('page')))
   matches=[i for i,e in enumerate(model['exams']) if e.get('page')==saved['page'] and e.get('raw')==exam.get('raw')]
   if len(matches)==1:model['exams'][matches[0]]=saved
   elif not exam.get('raw'):model['exams'].append(saved)
   else:
    model.setdefault('manual_unresolved',[]).append(saved)
    model['issues'].append({'message':'Correção manual de exame sem correspondência unívoca após reprocessamento; conferir histórico antes de resolver.','reviewed':False,'reason':''})
  for removal in old.get('removed_exams',[]):
   exam=removal['exam'];page=page_map.get(exam.get('page'))
   model['exams']=[e for e in model['exams'] if not (e.get('page')==page and e.get('raw')==exam.get('raw'))]
  if old.get('removed_exams'):model['removed_exams']=copy.deepcopy(old['removed_exams'])
  model['interpretation'].update(fields_found=sum(bool(v['value']) for v in model['fields'].values()),exams_found=len(model['exams']))


def save_batch(store,batch,catalog,actor,replace=False):
 from time import perf_counter
 tick=perf_counter()
 cases=build_cases(batch,catalog)
 batch.setdefault('timing',{})['consolidation_seconds']=perf_counter()-tick
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
   previous=store.get(old[name])[0] if name in old else None
   if previous:preserve_manual(previous,docs,models)
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
