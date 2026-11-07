"""Atendimento interno somente com perfil explícito; não fabrica guia externa."""
import copy
from core import digest
from payer_mapping import map_payer,validate_profile


def build_internal(order_document,order_model,profile):
 profile=validate_profile(profile)
 if not profile.get('homologado') or profile.get('exige_autorizacao',True):raise ValueError('Perfil interno deve ser homologado e dispensar autorização explicitamente.')
 current=order_model['fields'].get('Fonte pagadora',{}).get('value','')
 from core import norm
 if current and norm(current)!=norm(profile['fonte_pagadora']):raise ValueError('Fonte pagadora do pedido difere do perfil interno selecionado.')
 model=copy.deepcopy(order_model);model.update(tiss=True,internal=True,payer_profile=copy.deepcopy(profile))
 model['fields']['Fonte pagadora'].update(value=profile['fonte_pagadora'],origin_type='perfil_aprovado',document=None,page=None,box=None,confidence=None,snippet='Fonte selecionada no perfil homologado '+profile['id'])
 # The type is supplied by a human profile selection, with configuration provenance.
 model['fields']['Regime atendimento'].update(value=profile['tipo_atendimento'],origin_type='perfil_aprovado',reviewed=False)
 model['issues'].append({'message':'Atendimento interno: conferir escopo do perfil e ausência de guia externa.','reviewed':False,'reason':''})
 for e in model['exams']:
  e['quantidade_solicitada']=e.get('quantidade','');e['quantidade_autorizada']=''
 mapping=map_payer(model,profile)
 if mapping['errors']:raise ValueError('\n'.join(mapping['errors']))
 doc={'file':'Registro interno local (sem guia externa)','sha256':digest([order_document['sha256'],profile]),
      'document_type':'registro_interno','pages':[{'number':1,'method':'Configuração homologada','text':'Sem guia externa. Conferir pedido original e perfil interno.',
      'lines':[],'size':[600,800],'warnings':[]}],'local_path':None}
 return doc,model
