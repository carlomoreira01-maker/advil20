"""Mapeamento de fonte pagadora explícito. Modelos não são regras homologadas."""
import copy,json,re
from pathlib import Path
from core import norm

DESTINATIONS={'Matrícula','Guia','Senha/Autorização','Guia principal','Guia operadora','Indicação clínica','Regime de atendimento','Data de execução'}
SOURCES={'Carteira','Guia prestador','Guia principal','Guia operadora','Senha autorização','Indicação clínica','Regime atendimento','Data execução'}


def validate_profile(profile):
 if not isinstance(profile,dict):raise ValueError('Perfil deve ser um objeto.')
 if not all(profile.get(k) for k in ['id','nome','fonte_pagadora','tipo_atendimento']):raise ValueError('Perfil precisa de fonte pagadora, tipo de atendimento e procedimentos aplicáveis.')
 if not isinstance(profile.get('procedimentos'),list) or any(not isinstance(c,str) or not c for c in profile['procedimentos']):raise ValueError('Procedimentos devem ser uma lista.')
 if profile.get('homologado') and not profile['procedimentos']:raise ValueError('Homologação precisa delimitar procedimentos ou aprovar * explicitamente.')
 if profile.get('homologado') and not all(profile.get(k) for k in ['aprovado_por','aprovado_em']):raise ValueError('Homologação exige responsável e data.')
 if profile.get('homologado'):
  from datetime import datetime
  try:datetime.strptime(profile['aprovado_em'],'%Y-%m-%d')
  except ValueError:raise ValueError('Data de homologação inválida.')
 for dest,source in profile.get('mapeamento',{}).items():
  if dest not in DESTINATIONS or source not in SOURCES:raise ValueError('Mapeamento desconhecido ou ambíguo.')
 for dest,default in profile.get('valores_tecnicos',{}).items():
  if dest not in DESTINATIONS or not isinstance(default,dict) or not all(default.get(k) for k in ['valor','aprovado_por','aprovado_em']):raise ValueError('Valor técnico exige aprovação individual explícita.')
 if any(x not in DESTINATIONS for x in profile.get('obrigatorios',[])):raise ValueError('Campo obrigatório desconhecido.')
 return copy.deepcopy(profile)


def load_profiles(path):
 rows=json.loads(Path(path).read_text(encoding='utf-8'))
 if not isinstance(rows,list):raise ValueError('Perfis devem ser uma lista.')
 ids=set()
 for row in rows:
  validate_profile(row)
  if row['id'] in ids:raise ValueError('Perfil duplicado.')
  ids.add(row['id'])
 return rows


def map_payer(model,profile,procedure_codes=None):
 result={'values':{},'origins':{},'errors':[],'profile_id':None}
 if not profile:result['errors'].append('Selecione um perfil de fonte pagadora homologado.');return result
 try:profile=validate_profile(profile)
 except ValueError as exc:result['errors'].append(str(exc));return result
 result['profile_id']=profile['id']
 if not profile.get('homologado'):result['errors'].append('Perfil ainda não homologado pela equipe responsável.')
 payer=model['fields'].get('Fonte pagadora',{}).get('value','')
 if norm(payer)!=norm(profile['fonte_pagadora']):result['errors'].append('Perfil não corresponde à fonte pagadora do documento.')
 attendance=model['fields'].get('Regime atendimento',{}).get('value','')
 if norm(attendance)!=norm(profile['tipo_atendimento']):result['errors'].append('Tipo de atendimento não confirmado para este perfil.')
 codes=procedure_codes if procedure_codes is not None else [e['codigo'] for e in model['exams']]
 if '*' not in profile['procedimentos'] and any(c not in profile['procedimentos'] for c in codes):result['errors'].append('Procedimento fora do escopo homologado do perfil.')
 for dest,source in profile.get('mapeamento',{}).items():
  field=model['fields'].get(source,{})
  result['values'][dest]=field.get('value','');result['origins'][dest]=copy.deepcopy(field)
 for dest,default in profile.get('valores_tecnicos',{}).items():
  if not result['values'].get(dest) and profile.get('homologado'):
   result['values'][dest]=default['valor'];result['origins'][dest]={'origin_type':'valor_técnico_aprovado','approval':copy.deepcopy(default)}
 for required in profile.get('obrigatorios',[]):
  if not result['values'].get(required):result['errors'].append('Fonte pagadora: falta '+required+'.')
 return result
