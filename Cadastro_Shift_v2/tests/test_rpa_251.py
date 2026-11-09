import os,tempfile,unittest,copy
from pathlib import Path
from lis_simulado import demo_data,approve,APPROVALS,Simulation
ATTACHMENTS=[{"name":"pedido.pdf","sha256":"0"*64},{"name":"guia.pdf","sha256":"1"*64}]
class RpaContract251(unittest.TestCase):
 def approval(self,data):return approve(data,'REVISOR FICTICIO',{k:True for k in APPROVALS})
 def test_sem_revisao_ou_payload_alterado_bloqueia(self):
  d=demo_data()
  with self.assertRaises(ValueError):approve(d,'',{})
  a=self.approval(d);d['password']='OUTRA'
  with self.assertRaises(ValueError):Simulation(d,a,[])
 def test_dados_fora_do_treinamento_bloqueados(self):
  d=demo_data();d['patient']['nome']='PESSOA FORA DO TREINO'
  with self.assertRaises(ValueError):Simulation(d,self.approval(d),ATTACHMENTS)
 def test_homonimo_ou_nome_isolado_nao_confirma(self):
  d=demo_data();s=Simulation(d,self.approval(d),ATTACHMENTS)
  try:
   with self.assertRaises(ValueError):s.search({'nome':d['patient']['nome']})
   with self.assertRaises(ValueError):s.select({'query':d['patient'],'id':'SIM-P2','reviewed':True})
  finally:s.db.close()
 def test_duplicidade_persistente_inclui_guia_com_outro_id(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'demo.sqlite3';d=demo_data();s=Simulation(d,self.approval(d),ATTACHMENTS,path)
   s.select({'query':d['patient'],'id':'SIM-P1','reviewed':True})
   with self.assertRaises(ValueError):s.create({'data':d,'attachments':ATTACHMENTS,'final':False})
   out=s.create({'data':d,'attachments':ATTACHMENTS,'final':True});self.assertIsNone(out['os_real']);s.db.close();d['case_id']='DEMO-OUTRO-ID';s=Simulation(d,self.approval(d),ATTACHMENTS,path)
   try:
    s.select({'query':d['patient'],'id':'SIM-P1','reviewed':True})
    with self.assertRaisesRegex(ValueError,'duplicidade'):s.create({'data':d,'attachments':ATTACHMENTS,'final':True})
   finally:s.db.close()

@unittest.skipUnless(os.getenv('SHIFT_BROWSER_TESTS')=='1','Requer navegador local')
class RpaBrowser251(unittest.TestCase):
 def setUp(self):
  from rpa_simulada import SimulatedRPA
  self.data=demo_data();self.rpa=SimulatedRPA(self.data,approve(self.data,'REVISOR FICTICIO',{k:True for k in APPROVALS}),headless=True)
 def tearDown(self):self.rpa.close()
 def confirm(self):
  self.rpa.search_patient();p=self.rpa.page;p.locator('#identity').check();p.locator('#select').click();p.wait_for_function('window.identityConfirmed===true')
 def test_fluxo_playwright_completo_anexos_medico_os_e_etiquetas(self):
  self.confirm();self.rpa.fill_order();p=self.rpa.page;self.assertIn('SIM-M1',p.locator('#doctor_result').inner_text());self.assertEqual(p.locator('#guide').input_value(),'00000111');self.assertEqual(p.locator('#exams').input_value().count('\n'),4)
  with self.assertRaises(ValueError):self.rpa.submit_after_human()
  p.locator('#final').check();out=self.rpa.submit_after_human();self.assertIsNone(out['os_real']);self.assertEqual(p.locator('.label').count(),5);self.assertIn('DEMONSTRAÇÃO SEM VALIDADE',p.locator('.label').first.inner_text())
  p.locator('#create').click();p.wait_for_function("document.querySelector('#result').textContent.includes('bloqueada')")
  with self.assertRaisesRegex(ValueError,'bloqueada'):self.rpa.submit_after_human()
 def test_mutacao_apos_aprovacao_e_sem_anexos_nao_gravam(self):
  self.confirm();self.rpa.fill_order();p=self.rpa.page;p.locator('#password').fill('OUTRA');p.locator('#final').check();p.locator('#create').click();p.wait_for_function("document.querySelector('#result').textContent.includes('bloqueada')");self.assertIsNone(self.rpa.server.state.order)
 def test_externo_e_interceptado_e_paciente_exige_confirmacao(self):
  self.rpa.search_patient()
  with self.assertRaises(ValueError):self.rpa.fill_order()
  result=self.rpa.page.evaluate("fetch('https://example.com').then(()=>false).catch(()=>true)");self.assertTrue(result)
 def test_dois_identificadores_reutilizam_cadastro_sem_pedir_o_terceiro(self):
  from rpa_simulada import SimulatedRPA
  self.rpa.close();self.data['patient'].pop('nascimento');self.rpa=SimulatedRPA(self.data,approve(self.data,'REVISOR FICTICIO',{k:True for k in APPROVALS}),headless=True)
  self.confirm();self.rpa.fill_order();self.rpa.page.locator('#final').check();out=self.rpa.submit_after_human();self.assertEqual(out['patient_id'],'SIM-P1');self.assertIn('01/02/1995',self.rpa.page.locator('#patient').inner_text())
