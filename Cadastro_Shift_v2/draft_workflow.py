"""Rascunho local não é autorização, preparação validada, envio ou O.S."""
import copy,json
from datetime import datetime
from priority_fields import PRIORITY,field_state,source_role


def build_draft(obj,catalog,cid,revision):
 from engine_v2 import compare_models,review_errors
 models=obj['models'];result=compare_models(models['pedido'],models['guia'],catalog)
 pending=list(dict.fromkeys(result['pendencias']+review_errors(models)))
 roles={role:bool(obj['docs'].get(role,{}).get('pages')) for role in ['pedido','guia']}
 fields={}
 for number,key,label in PRIORITY:
  role=source_role(obj,key);field=copy.deepcopy(models[role]['fields'].get(key,{}))
  fields[key]={'numero_tiss':number,'rotulo':label,'valor':field.get('value',''),'estado_leitura':field_state(field),'origem':field,'documento_funcao':role}
 return {'tipo':'RASCUNHO_LOCAL_NAO_ENVIAR','caso':cid,'revisao_base':revision,'gerado_em':datetime.now().isoformat(),
  'os_real':None,'enviado_ao_shift':False,'pronto_para_envio':False,'documentos_presentes':roles,
  'campos':fields,'exames':copy.deepcopy(result['exames']),'pendencias':pending,
  'validacao_concluida':not pending,'aviso':'Rascunho com informações para conferência. Não cria cadastro, autorização ou ordem de serviço.'}


def save_draft(store,cid,models,catalog,*,expected_revision,metadata=None):
 from engine_v2 import FIELDS
 from ocr_runtime import LocalReadError
 store.db.execute('CREATE TABLE IF NOT EXISTS rascunhos_locais(caso TEXT PRIMARY KEY,revision INTEGER,conteudo TEXT)')
 with store.db:
  store.db.execute('BEGIN IMMEDIATE');obj,rev,status,_=store.get(cid)
  if type(expected_revision) is not int or rev!=expected_revision:raise LocalReadError('O atendimento mudou em outra revisão. Reabra a ficha antes de salvar o rascunho; a revisão atual foi preservada.')
  if status=='PREPARADO':raise ValueError('Pré-cadastro já preparado; o resultado validado permanece preservado.')
  if set(models)!=set(obj['models']):raise ValueError('Rascunho deve manter as funções dos documentos do atendimento.')
  for model in models.values():
   if any(not isinstance(model.get('fields',{}).get(k,{}).get('value'),str) for k in FIELDS):raise ValueError('Campo inválido no rascunho.')
  snapshot={**obj,'models':copy.deepcopy(models)};result=build_draft(snapshot,catalog,cid,rev)
  payload={'models':models,'preview':result,'metadata':{'motivo':(metadata or {}).get('motivo','')}}
  store.db.execute('INSERT OR REPLACE INTO rascunhos_locais VALUES(?,?,?)',(cid,rev,json.dumps(payload,ensure_ascii=False)))
  store.audit(cid,'SALVAR_RASCUNHO',{'revisao':rev})
 return result


def load_draft(store,cid):
 store.db.execute('CREATE TABLE IF NOT EXISTS rascunhos_locais(caso TEXT PRIMARY KEY,revision INTEGER,conteudo TEXT)')
 row=store.db.execute('SELECT revision,conteudo FROM rascunhos_locais WHERE caso=?',(cid,)).fetchone()
 if not row:return None
 _,rev,status,_=store.get(cid)
 return json.loads(row[1]) if row[0]==rev and status!='PREPARADO' else None
