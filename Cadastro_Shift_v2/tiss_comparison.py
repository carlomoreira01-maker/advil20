"""Comparação TISS separa solicitação, autorização e execução; nenhuma aprovação automática."""
from core import norm,digest
from payer_mapping import map_payer
from identity_evidence import names_compatible, identifier, IDENTIFIERS


def compare_tiss(p,g,catalog):
 from engine_v2 import resolve_exam
 errors=[];rows=[]
 status=norm(g['fields'].get('Status',{}).get('value',''))
 if status and status not in ['AUTORIZADO','AUTORIZADA']:errors.append('Status explícito da guia incompatível com autorização; conferir.')
 mapping=map_payer(g,g.get('payer_profile'))
 internal=bool(g.get('internal') and not mapping['errors'] and (g.get('payer_profile') or {}).get('exige_autorizacao') is False)
 a=p['fields']['Paciente']['value'];b=g['fields']['Paciente']['value']
 if not a or not b or not names_compatible(a,b):errors.append('Identidade: nomes ausentes ou divergentes; bloqueado.')
 identifiers=IDENTIFIERS
 common=[k for k in identifiers if p['fields'].get(k,{}).get('value') and g['fields'].get(k,{}).get('value')]
 if not common:errors.append('Identidade: falta segundo identificador comum; nome isolado não confirma paciente.')
 if any(identifier(k,p['fields'][k]['value'])!=identifier(k,g['fields'][k]['value']) for k in common):errors.append('Identidade: identificadores divergentes; bloqueado.')
 for model in [p,g]:
  for key in identifiers:
   val=model['fields'].get(key,{}).get('value','')
   if val and not identifier(key,val):errors.append('Identidade: '+key+' inválido; conferir origem.')
  from tiss import SCHEMA,valid
  for key,kind in SCHEMA.values():
   val=model['fields'].get(key,{}).get('value','')
   if val and not valid(norm(val),kind):errors.append(key+': valor inválido; corrija o campo e confira a origem.')
  for key,field in model['fields'].items():
   annotation=field.get('not_applicable')
   if annotation:
    profile=g.get('payer_profile') or {}
    if not profile.get('homologado') or key not in profile.get('campos_nao_aplicaveis',[]) or any(annotation.get(k)!=profile.get(k) for k in ['id','aprovado_por','aprovado_em']) or field.get('value'):
     errors.append(key+': não aplicável sem regra vigente; confira o perfil homologado.')
 if not p['fields']['Medico']['value']:errors.append('Médico solicitante não identificado no pedido.')
 for key in ['Medico','Conselho','Número conselho','UF conselho']:
  if not g['fields'].get(key,{}).get('value'):errors.append('Solicitante: '+key+' não identificado; conferir cadastro.')
  a=p['fields'].get(key,{}).get('value','');b=g['fields'].get(key,{}).get('value','')
  if a and b and norm(a)!=norm(b):errors.append('Solicitante divergente entre pedido e guia: '+key+'.')
 maps=[]
 for title,model in [('Pedido',p),('Guia',g)]:
  found={}
  for e in model['exams']:
   cat,err=resolve_exam(e,catalog)
   if err:errors.append(title+': '+err)
   if cat and e.get('material') and cat.get('material') and norm(e['material'])!=norm(cat['material']):errors.append(title+': material divergente do catálogo.')
   if not cat:
    rows.append({'nome':e.get('descricao') or 'Não identificado','codigo_shift':'',
       'codigo_lido':e.get('codigo',''),'pedido':e.get('quantidade_solicitada',e.get('quantidade','')) if title=='Pedido' else '',
       'guia':e.get('quantidade_autorizada',e.get('quantidade','')) if title=='Guia' else '',
       'situacao':'Exame identificado — código interno pendente (correspondência não validada)',
       'pagina_pedido':e.get('page') if title=='Pedido' else None,'pagina_guia':e.get('page') if title=='Guia' else None})
    continue
   identity=cat.get('tuss') or cat.get('codigo_shift') or norm(cat['nome'])
   if identity in found:errors.append(title+': procedimento repetido na mesma seção; conferir.')
   found[identity]=(e,cat)
  maps.append(found)
 if not p['exams'] or not g['exams']:errors.append('Pedido ou guia sem procedimentos identificados.')
 for code in sorted(set(maps[0])|set(maps[1])):
  pedido=maps[0].get(code);guia=maps[1].get(code);item=(pedido or guia)[1]
  requested=pedido[0].get('quantidade_solicitada',pedido[0].get('quantidade','')) if pedido else ''
  authorized=guia[0].get('quantidade_autorizada','') if guia else ''
  qs=guia[0].get('quantidade_solicitada','') if guia else ''
  state='Conferir'
  if not pedido or not guia:state='Ausente no pedido' if not pedido else 'Ausente na guia'
  elif internal:state='Conferir'
  elif not authorized:state='Autorização não identificada'
  elif authorized.isdigit() and int(authorized)==0:state='Não autorizado'
  elif not requested.isdigit() or not authorized.isdigit() or int(requested)!=int(authorized):state='Quantidade divergente'
  elif qs and (not qs.isdigit() or int(qs)!=int(requested)):state='Quantidade solicitada divergente'
  if state!='Conferir':errors.append(code+': '+state)
  if pedido and (not requested.isdigit() or not 1<=int(requested)<=999):errors.append('Quantidade solicitada inválida; confira o pedido.')
  if not item.get('codigo_shift'):errors.append('Código interno Shift não fornecido pelo laboratório.')
  rows.append({**item,'pedido':requested,'guia':'Não se aplica' if internal else authorized,'situacao':'Exame identificado — código interno pendente' if not item.get('codigo_shift') and state=='Conferir' else state,'pagina_pedido':pedido[0]['page'] if pedido else None,'pagina_guia':guia[0]['page'] if guia else None})
 mapping=map_payer(g,g.get('payer_profile'))
 errors.extend(mapping['errors'])
 # A profile must explicitly permit an internal workflow; no global internal exemption.
 profile=g.get('payer_profile') or {}
 if profile.get('exige_autorizacao',True):
  for key in ['Senha autorização','Validade senha']:
   if not g['fields'].get(key,{}).get('value'):errors.append(key+' não identificada.')
  from datetime import datetime,date
  val=g['fields'].get('Validade senha',{}).get('value','')
  if val:
   try:
    if datetime.strptime(val,'%d/%m/%Y').date()<date.today():errors.append('Senha de autorização vencida.')
   except ValueError:errors.append('Validade da senha inválida.')
 return {'exames':rows,'pendencias':list(dict.fromkeys(errors)),'catalogo_hash':digest(catalog),'payer_mapping':mapping}
