"""Campos principais e estados de leitura, separados das exigências de autorização."""
PRIORITY=[(10,'Paciente','Nome completo'),(8,'Carteira','Carteirinha'),
 (2,'Guia prestador','Guia no prestador'),(3,'Guia principal','Guia principal'),
 (7,'Guia operadora','Guia da operadora'),(5,'Senha autorização','Senha / autorização'),
 (15,'Medico','Médico solicitante'),(17,'Número conselho','Número no conselho'),
 (18,'UF conselho','UF'),(23,'Indicação clínica','Indicação clínica'),
 (30,'Contratado executante','Contratado executante'),(16,'Conselho','Conselho profissional')]
STATE_LABELS={'identified':'Identificado','empty':'Campo vazio','uncertain':'Leitura incerta','not_found':'Campo não localizado'}

def field_state(field):
 if field.get('value'):return 'identified'
 if field.get('candidates'):return 'uncertain'
 return field.get('extraction_state','not_found')


def state_label(field):
 if field.get('origin_type') in ['correcao_manual','escolha_humana_de_leitura']:return 'Corrigido manualmente — conferir'
 return STATE_LABELS[field_state(field)]


def source_role(obj,key):
 """Escolhe valor realmente impresso, sem completar nomes nem criar documento."""
 from identity_evidence import names_compatible
 docs=obj['docs'];models=obj['models'];role='guia' if docs.get('guia',{}).get('pages') else 'pedido'
 if role=='guia' and docs.get('pedido',{}).get('pages') and key in ['Paciente','Medico']:
  a=models['guia']['fields'][key]['value'];b=models['pedido']['fields'][key]['value']
  if b and (not a or (names_compatible(a,b) and len(b.split())>len(a.split()))):return 'pedido'
 return role
