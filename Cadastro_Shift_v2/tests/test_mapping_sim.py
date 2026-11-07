import copy,tempfile,unittest
from pathlib import Path
from engine_v2 import parse_document,read_document,compare_models
from gerar_exemplos_tiss import make_order,make_guide,catalog
from payer_mapping import map_payer,validate_profile
from internal_workflow import build_internal
from simulador import SimulatedShift

def profile(payer='IPASGO',internal=False):
 return {'id':'FICTICIO','nome':'Perfil ficticio aprovado','fonte_pagadora':payer,'tipo_atendimento':'AMBULATORIAL',
 'procedimentos':['90000001','90000002','90000003','90000004','90000005'],'homologado':True,'aprovado_por':'RESPONSAVEL FICTICIO','aprovado_em':'2026-11-07',
 'exige_autorizacao':not internal,'mapeamento':{'Matrícula':'Carteira','Guia':'Guia prestador','Senha/Autorização':'Senha autorização','Guia principal':'Guia principal','Guia operadora':'Guia operadora'},
 'obrigatorios':[] if internal else ['Matrícula','Guia','Senha/Autorização','Guia operadora'],'valores_tecnicos':{}}

class Mapping(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.cat=catalog()
  g=self.base/'g.pdf';p=self.base/'p.pdf';make_guide(g);make_order(p)
  self.doc=read_document(p);self.p=parse_document(self.doc,self.cat);self.g=parse_document(read_document(g),self.cat)
 def tearDown(self):self.tmp.cleanup()
 def test_mapeamento_explicito_nao_confunde_campos(self):
  result=map_payer(self.g,profile());self.assertFalse(result['errors'])
  self.assertEqual(result['values']['Guia'],'00000111');self.assertEqual(result['values']['Guia operadora'],'00000777')
  self.assertEqual(result['values']['Senha/Autorização'],'00000555');self.assertEqual(result['values']['Matrícula'],'0000087654')
  self.assertEqual(result['origins']['Guia']['tiss_number'],2)
 def test_perfil_nao_homologado_ou_fonte_divergente_bloqueiam(self):
  for mod in [{'homologado':False},{'fonte_pagadora':'OUTRA'},{'tipo_atendimento':'INTERNO'},{'procedimentos':['99999999']}]:
   p=profile();p.update(mod);self.assertTrue(map_payer(self.g,p)['errors'])
 def test_valor_tecnico_exige_aprovacao(self):
  p=profile();p['valores_tecnicos']={'Guia':{'valor':'0'}}
  with self.assertRaises(ValueError):validate_profile(p)
 def test_interno_sem_guia_somente_no_escopo_aprovado(self):
  self.p['fields']['Regime atendimento']['value']='AMBULATORIAL'
  p=profile('FONTE FICTICIA INTERNA',True);p['mapeamento']={};doc,model=build_internal(self.doc,self.p,p)
  self.assertIsNone(doc['local_path']);self.assertTrue(model['internal'])
  for row in self.cat:row['codigo_shift']='INTERNO-FICTICIO-'+row['tuss']
  result=compare_models(self.p,model,self.cat)
  self.assertFalse(result['pendencias'],result['pendencias'])
  self.assertTrue(all(e['guia']=='Não se aplica' for e in result['exames']))
  p['homologado']=False
  with self.assertRaises(ValueError):build_internal(self.doc,self.p,p)
 def test_interno_nao_dispensa_outro_procedimento(self):
  p=profile('FONTE FICTICIA INTERNA',True);p['mapeamento']={};p['procedimentos']=['99999999']
  with self.assertRaises(ValueError):build_internal(self.doc,self.p,p)

class Simulation(unittest.TestCase):
 def setUp(self):self.sim=SimulatedShift();self.query={'nome':'PESSOA FICTICIA ALFA','nascimento':'01/02/1995','carteira':'0000087654'}
 def test_nome_isolado_e_identificadores_divergentes(self):
  with self.assertRaises(ValueError):self.sim.search({'nome':self.query['nome']})
  self.assertEqual(self.sim.search({**self.query,'carteira':'0000099999'}),[])
 def test_confirmacao_medico_anexos_e_duplicidade(self):
  token=self.sim.confirm(self.query,'SIM-P1',True)
  data={'token':token,'reviewed':True,'crm':'0012345','uf':'GO','case_id':'FICTICIO-1','payer':'CONVENIO FICTICIO','guide':'00000111',
  'exams':[{'code':'90000001','quantity':1}],'attachments':[{'ficticio':True},{'ficticio':True}]}
  result=self.sim.prepare(data);self.assertIsNone(result['os_real']);self.assertTrue(result['os_simulada'].startswith('OS-SIM-'))
  with self.assertRaises(ValueError):self.sim.prepare(data)
  with self.assertRaises(ValueError):self.sim.doctor('999999','SP')
 def test_paciente_novo_somente_confirmado_sem_duplicar(self):
  with self.assertRaises(ValueError):self.sim.create_patient(self.query,False)
  with self.assertRaises(ValueError):self.sim.create_patient(self.query,True)
  new={'nome':'PESSOA FICTICIA GAMA','nascimento':'01/01/1990','carteira':'0000066666'}
  self.assertTrue(self.sim.create_patient(new,True)['id'].startswith('SIM-P-'))

class ExplicitStatus(unittest.TestCase):
 def test_status_negado_bloqueia_mesmo_com_quantidade_positiva(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'p.pdf';g=Path(tmp)/'g.pdf';make_order(p);make_guide(g)
   cat=catalog()
   for row in cat:row['codigo_shift']='FICTICIO-'+row['tuss']
   order=parse_document(read_document(p),cat);guide=parse_document(read_document(g),cat)
   guide['payer_profile']=profile();guide['fields']['Status']['value']='NEGADO'
   result=compare_models(order,guide,cat)
   self.assertIn('Status explícito',' '.join(result['pendencias']))
 def test_operadora_nao_substitui_fonte_pagadora(self):
  with tempfile.TemporaryDirectory() as tmp:
   g=Path(tmp)/'g.pdf';make_guide(g);m=parse_document(read_document(g),catalog())
   m['fields']['Fonte pagadora']['value']='';m['fields']['Operadora']['value']='IPASGO'
   self.assertTrue(map_payer(m,profile())['errors'])
