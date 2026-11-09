"""Cenários adversos sintéticos: confirmações, revisões e integridade dos originais."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from engine_v2 import CaseStore,digest,compare_models,review_errors
from scan_import import read_scan,save_batch,confirm_group
from gerar_exemplos_tiss import catalog
from draft_workflow import save_draft,load_draft
from lis_simulado import Simulation,demo_data,approve,APPROVALS
from tests.test_mapping_sim import profile
ROOT=Path(__file__).resolve().parents[1]
ATTACHMENTS=[{'name':'pedido.pdf','sha256':'0'*64},{'name':'guia.pdf','sha256':'1'*64}]

def simulation():
    data=demo_data();return data,Simulation(data,approve(data,'REVISOR FICTICIO',{k:True for k in APPROVALS}),ATTACHMENTS)

class Hardening252(unittest.TestCase):
 def test_payloads_malformados_nao_abrem_sessao_ou_geram_erros_ocultos(self):
  with self.assertRaises(ValueError):Simulation(None,None,None)
  with self.assertRaises(ValueError):approve(demo_data(),None,None)
  for field,value in [('patient',[]),('exams',['codigo invalido']),('case_id',1)]:
   d=demo_data();d[field]=value
   with self.subTest(field=field),self.assertRaises(ValueError):Simulation(d,approve(d,'REVISOR FICTICIO',{k:True for k in APPROVALS}),ATTACHMENTS)
 def test_selecao_divergente_revoga_confirmacao_anterior(self):
  d,s=simulation()
  try:
   token=s.select({'query':d['patient'],'id':'SIM-P1','reviewed':True})['identity_token']
   with self.assertRaises(ValueError):s.select({'query':d['patient'],'id':'SIM-P2','reviewed':True})
   self.assertFalse(s.selected)
   with self.assertRaises(ValueError):s.create({'data':d,'attachments':ATTACHMENTS,'identity_token':token,'final':True})
   self.assertIsNone(s.order)
  finally:s.db.close()
 def test_nova_pesquisa_e_token_antigo_nao_autorizam_os(self):
  d,s=simulation()
  try:
   token=s.select({'query':d['patient'],'id':'SIM-P1','reviewed':True})['identity_token'];s.search(d['patient'])
   with self.assertRaises(ValueError):s.create({'data':d,'attachments':ATTACHMENTS,'identity_token':token,'final':True})
   s.select({'query':d['patient'],'id':'SIM-P1','reviewed':True})
   with self.assertRaises(ValueError):s.create({'data':d,'attachments':ATTACHMENTS,'identity_token':token,'final':True})
   result=s.create({'data':d,'attachments':ATTACHMENTS,'identity_token':s.selection_token,'final':True});self.assertIsNone(result['os_real'])
  finally:s.db.close()
 def test_quantidade_ou_exames_diferentes_dos_anexos_sao_rejeitados(self):
  for change in ['quantidade','exame']:
   d=demo_data()
   if change=='quantidade':d['exams'][0]['quantity']=2
   else:d['exams'].pop()
   with self.subTest(change=change),self.assertRaisesRegex(ValueError,'documentos fictícios'):Simulation(d,approve(d,'REVISOR FICTICIO',{k:True for k in APPROVALS}),ATTACHMENTS)
 def test_booleano_nao_substitui_quantidade_numerica_aprovada(self):
  d,s=simulation()
  try:
   s.select({'query':d['patient'],'id':'SIM-P1','reviewed':True});changed=copy.deepcopy(d);changed['exams'][0]['quantity']=True
   with self.assertRaises(ValueError):s.create({'data':changed,'attachments':ATTACHMENTS,'identity_token':s.selection_token,'final':True})
  finally:s.db.close()
 def test_reimportacao_detecta_copia_local_corrompida_mesmo_com_cache(self):
  with tempfile.TemporaryDirectory() as tmp:
   b=read_scan([ROOT/'exemplos_250/01_um_paciente.pdf'],tmp,catalog(),mode='single');original=next(iter(b['sources'].values()));Path(original['local_path']).write_bytes(b'ARQUIVO FICTICIO ALTERADO')
   with self.assertRaisesRegex(ValueError,'alterada'):read_scan([ROOT/'exemplos_250/01_um_paciente.pdf'],tmp,catalog(),mode='single')
 def test_rascunho_nao_pode_assumir_revisao_nova(self):
  with tempfile.TemporaryDirectory() as tmp:
   store=CaseStore(Path(tmp)/'base.sqlite3');cat=catalog()
   try:
    cid=save_batch(store,read_scan([ROOT/'exemplos_250/01_um_paciente.pdf'],tmp,cat,mode='single'),cat,'REVISOR')[0];obj,rev,_,_=store.get(cid);stale=copy.deepcopy(obj['models']);new=copy.deepcopy(stale);new['guia']['fields']['Contratado executante']['value']='LABORATORIO REVISAO NOVA FICTICIA';store.save(cid,new,'REVISOR','Conferência fictícia',rev)
    with self.assertRaisesRegex(ValueError,'mudou'):save_draft(store,cid,stale,cat,expected_revision=rev)
    self.assertIsNone(load_draft(store,cid));self.assertEqual(store.get(cid)[0]['models'],new)
    save_draft(store,cid,new,cat,expected_revision=rev+1,metadata={'motivo':'Nota fictícia'});self.assertEqual(load_draft(store,cid)['metadata']['motivo'],'Nota fictícia')
   finally:store.db.close()
 def test_preparo_reconfere_integridade_e_nao_grava_se_original_mudou(self):
  with tempfile.TemporaryDirectory() as tmp:
   cat=catalog()
   for row in cat:row['codigo_shift']='SIM-LAB-'+row['tuss']
   b=read_scan([ROOT/'exemplos_250/01_um_paciente.pdf'],tmp,cat,mode='single');confirm_group(b,'Atendimento 1','REVISOR','Conferência fictícia',{i['id'] for i in b['pages']});store=CaseStore(Path(tmp)/'base.sqlite3')
   try:
    cid=save_batch(store,b,cat,'REVISOR')[0];obj,rev,_,_=store.get(cid);models=obj['models'];models['guia']['payer_profile']=profile()
    for m in models.values():
     m['pages_reviewed']=True
     for f in m['fields'].values():f['reviewed']=True
     for e in m['exams']:e['reviewed']=True
     for issue in m['issues']:issue.update(reviewed=True,reason='Conferência fictícia')
    self.assertEqual(compare_models(models['pedido'],models['guia'],cat)['pendencias']+review_errors(models),[])
    store.save(cid,models,'REVISOR','Conferência fictícia',rev);source=Path(next(iter(b['sources'].values()))['local_path']);original=source.read_bytes();source.write_bytes(b'ALTERACAO FICTICIA')
    with self.assertRaisesRegex(ValueError,'alterada'):store.prepare(cid,cat,'REVISOR',rev+1,digest(cat),True)
    self.assertIsNone(store.get(cid)[3]);source.write_bytes(original);out=store.prepare(cid,cat,'REVISOR',rev+1,digest(cat),True);self.assertIsNone(out['os_real'])
   finally:store.db.close()

@unittest.skipUnless(os.getenv('SHIFT_BROWSER_TESTS')=='1','Requer navegador local')
class BrowserHardening252(unittest.TestCase):
 def setUp(self):
  from rpa_simulada import SimulatedRPA
  self.data=demo_data();self.rpa=SimulatedRPA(self.data,approve(self.data,'REVISOR FICTICIO',{k:True for k in APPROVALS}),headless=True)
 def tearDown(self):self.rpa.close()
 def confirm(self):
  self.rpa.search_patient();p=self.rpa.page;p.locator('#identity').check();p.locator('#select').click();p.wait_for_function('window.identityConfirmed===true')
 def test_alterar_e_reverter_identidade_exige_nova_confirmacao(self):
  self.confirm();p=self.rpa.page;p.locator('#carteira').fill('0000099999');p.locator('#carteira').fill(self.data['patient']['carteira'])
  with self.assertRaisesRegex(ValueError,'novamente'):self.rpa.fill_order()
  self.assertEqual(p.locator('#guide').input_value(),'');self.rpa.search_patient();self.assertFalse(p.locator('#identity').is_checked());self.confirm();self.rpa.fill_order();p.locator('#final').check();self.assertIsNone(self.rpa.submit_after_human()['os_real'])
 def test_nova_pesquisa_revoga_confirmacao_no_navegador(self):
  self.confirm();self.rpa.search_patient()
  with self.assertRaises(ValueError):self.rpa.fill_order()
  self.assertIsNone(self.rpa.server.state.order)
 def test_requisicao_malformada_retorna_bloqueio_sem_os(self):
  response=self.rpa.page.request.post(self.rpa.server.url+'/select',data=[],headers={'X-Demo-Session':self.rpa.server.state.nonce});self.assertEqual(response.status,400);self.assertIsNone(self.rpa.server.state.order)
 def test_inspecao_descarta_valores_html_senhas_tokens_e_ids_pessoais(self):
  from shift_inspection import inspect_structure
  p=self.rpa.page;p.set_content('''<label>Nome do paciente<input name="nomePaciente" value="PESSOA CONFIDENCIAL FICTICIA"></label><input type="hidden" value="TOKEN CONFIDENCIAL FICTICIO"><input id="mat-input-2" name="numeroCarteira" value="NUMERO CONFIDENCIAL FICTICIO"><input id="paciente_NOME_CONFIDENCIAL" value="DADO CLINICO FICTICIO">''')
  report=inspect_structure(p,expected_host='127.0.0.1');text=json.dumps(report)
  for private in ['PESSOA CONFIDENCIAL FICTICIA','TOKEN CONFIDENCIAL FICTICIO','NUMERO CONFIDENCIAL FICTICIO','paciente_NOME_CONFIDENCIAL','DADO CLINICO FICTICIO']:self.assertNotIn(private,text)
  self.assertFalse(report['permite_gravacao']);self.assertFalse(report['autenticacao_verificada']);self.assertTrue(any(c['seletores_candidatos'] for c in report['controles']))
 def test_inspecao_de_login_nao_exporta_controles_da_conta(self):
  from shift_inspection import inspect_structure
  p=self.rpa.page;p.set_content('<input value="LOGIN FICTICIO"><input type="password" value="SEGREDO FICTICIO">');report=inspect_structure(p,expected_host='127.0.0.1');self.assertTrue(report['login_visivel']);self.assertEqual(report['controles'],[]);self.assertNotIn('SEGREDO',json.dumps(report))
 def test_inspecao_recusa_outro_dominio(self):
  from shift_inspection import inspect_structure
  with self.assertRaisesRegex(ValueError,'domínio autorizado'):inspect_structure(self.rpa.page)

@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer display local')
class GUIHardening252(unittest.TestCase):
 def setUp(self):
  import tkinter as tk
  from workbench import create_workbench
  self.tmp=tempfile.TemporaryDirectory();self.root=tk.Tk();self.app=create_workbench(self.root,Path(self.tmp.name)/'dados');self.app.catalog=catalog();self.root.update()
 def tearDown(self):self.app.store.db.close();self.root.destroy();self.tmp.cleanup()
 def test_inspecao_so_inicia_navegador_apos_acao_explicita(self):
  from shift_inspection_ui import open_inspection
  from unittest.mock import patch
  with patch('shift_inspection_ui.threading.Thread',side_effect=AssertionError('Não iniciar automaticamente')):
   open_inspection(self.app);self.root.update();state=self.app.shift_inspection;self.assertIsNone(state['report']);self.assertEqual(str(state['capture']['state']),'disabled');self.assertIn('Abrir navegador',state['notice'].get());self.assertIn('somente de leitura',state['window'].title());state['window'].destroy()
 def test_interface_recusa_rascunho_de_revisao_antiga_e_preserva_nova(self):
  from unittest.mock import patch
  import time
  with patch('app.filedialog.askopenfilenames',return_value=[str(ROOT/'exemplos_250/01_um_paciente.pdf')]):self.app.workspace.import_buttons['single'].invoke()
  end=time.monotonic()+40
  while self.app.busy and time.monotonic()<end:self.root.update();time.sleep(.01)
  self.assertFalse(self.app.busy);cid=self.app.cid;obj,rev,_,_=self.app.store.get(cid);new=copy.deepcopy(obj['models']);new['guia']['fields']['Contratado executante']['value']='LABORATORIO NOVO FICTICIO';self.app.store.save(cid,new,'REVISOR FICTICIO','Revisão nova fictícia',rev)
  self.app.workspace.go(4);self.app.workspace.save_draft_button.invoke();self.root.update();self.assertIn('mudou',self.app.workspace.notice.get());self.assertEqual(self.app.store.get(cid)[0]['models'],new);self.assertIsNone(load_draft(self.app.store,cid))
