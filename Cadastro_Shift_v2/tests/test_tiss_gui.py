import json,os,tempfile,time,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import patch
from app import App,UNIDENTIFIED
from engine_v2 import catalog_load
from gerar_exemplos_tiss import make_guide,make_order,catalog,VALUES
from tiss import SCHEMA

@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer display e SHIFT_GUI_TESTS=1')
class TissInterface(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=tk.Tk();self.app=App(self.root,self.base/'dados')
  self.app.catalog=catalog();self.app.actor.set('REVISOR FICTICIO');self.root.update()
 def tearDown(self):self.app.store.db.close();self.root.destroy();self.tmp.cleanup()
 def wait(self):
  deadline=time.monotonic()+90
  while self.app.busy and time.monotonic()<deadline:self.root.update();time.sleep(.01)
  self.assertFalse(self.app.busy);self.root.update()
 def test_campos_tiss_e_quantidades_aparecem_na_interface(self):
  pedido=self.base/'p.pdf';guia=self.base/'g.pdf';make_order(pedido);make_guide(guia,repeated=True)
  self.app.import_pairs([(pedido,guia)]);self.wait()
  for num,value in VALUES.items():self.assertEqual(self.app.field_vars['guia'][SCHEMA[num][0]].get(),value)
  self.app.forms.select(1);self.app.field_tabs['guia'].select(1);self.root.update()
  self.assertTrue(self.app.field_entries['guia']['Senha autorização'].winfo_ismapped())
  self.assertEqual(len(self.app.exam_tables['guia'].get_children()),5)
  rows=[self.app.exam_tables['guia'].item(i,'values') for i in self.app.exam_tables['guia'].get_children()]
  self.assertTrue(all(r[2]=='1' and r[3]=='1' for r in rows))
  diag=[self.app.diagnostic_table.item(i,'values') for i in self.app.diagnostic_table.get_children()]
  self.assertTrue(all(r[7]=='Preenchida' for r in diag));self.assertTrue(all('campos' in r[6] for r in diag))
 def test_scan_real_preenche_paciente_senha_crm(self):
  pedido=self.base/'p.pdf';make_order(pedido)
  self.app.import_pairs([(pedido,Path(__file__).resolve().parents[1]/'exemplos_tiss/01_escaneada.pdf')]);self.wait()
  for key,expected in [('Paciente',VALUES[10]),('Senha autorização',VALUES[5]),('Número conselho',VALUES[17]),('UF conselho',VALUES[18])]:self.assertEqual(self.app.field_vars['guia'][key].get(),expected)
  self.assertEqual(len(self.app.exam_tables['guia'].get_children()),5)
  self.assertTrue(all(self.app.exam_tables['guia'].item(i,'values')[2:4]==('1','1') for i in self.app.exam_tables['guia'].get_children()))
 def test_autorizacao_zero_fica_visivel_e_bloqueia(self):
  pedido=self.base/'p.pdf';guia=self.base/'g.pdf';make_order(pedido);make_guide(guia,zero=True)
  self.app.import_pairs([(pedido,guia)]);self.wait()
  row=self.app.exam_tables['guia'].item(self.app.exam_tables['guia'].get_children()[0],'values')
  self.assertEqual(row[2:4],('1','0'));self.assertIn('Não autorizado',' '.join(self.app.analysis['pendencias']))
  with self.assertRaises(ValueError):self.app.prepare()
 def test_catalogo_producao_nao_carrega_codigos_demo(self):
  self.assertFalse(self.app.catalog_path.exists())
  r=tk.Tk();other=App(r,self.base/'limpo')
  try:self.assertEqual(other.catalog,[])
  finally:other.store.db.close();r.destroy()
 def test_falha_de_interface_diferenciada_do_ocr(self):
  pedido=self.base/'p.pdf';guia=self.base/'g.pdf';make_order(pedido);make_guide(guia)
  with patch.object(self.app,'open_case',side_effect=RuntimeError('falha controlada')),patch('app.messagebox.showwarning'):
   self.app.import_pairs([(pedido,guia)]);self.wait()
  rows=[self.app.diagnostic_table.item(i,'values') for i in self.app.diagnostic_table.get_children()]
  self.assertTrue(all('Texto digital' in r[3] for r in rows));self.assertTrue(all('FALHA na atualização'==r[7] for r in rows))
 def test_lote_dois_pacientes_mantem_atendimentos_independentes(self):
  pairs=[]
  for i,other in enumerate([False,True]):
   p=self.base/f'p{i}.pdf';g=self.base/f'g{i}.pdf';make_order(p,other=other);make_guide(g,other=other);pairs.append((p,g))
  self.app.import_pairs(pairs)
  self.assertEqual(len(self.app.pending_imports),2)
  self.wait();self.assertEqual(len(self.app.cases.get_children()),2)
  found={}
  for cid in self.app.cases.get_children():
   self.app.open_case(cid)
   name=self.app.field_vars['pedido']['Paciente'].get();self.assertEqual(name,self.app.field_vars['guia']['Paciente'].get())
   found[name]=self.app.field_vars['guia']['Carteira'].get()
  self.assertEqual(found,{'PESSOA FICTICIA ALFA':'0000087654','PESSOA FICTICIA BETA':'0000099999'})
 def test_configura_perfil_pela_interface_sem_editar_codigo(self):
  self.app.payer_window();self.app.payer_manager['edit']();editor=self.app.profile_editor
  for key,value in {'id':'FICTICIO','nome':'Perfil ficticio','fonte_pagadora':'IPASGO','tipo_atendimento':'AMBULATORIAL','procedimentos':'90000001;90000002','aprovado_por':'RESPONSAVEL FICTICIO','aprovado_em':'2026-11-07'}.items():editor['variables'][key].set(value)
  editor['mapping']['Guia'].set('Guia prestador');editor['mapping']['Senha/Autorização'].set('Senha autorização');editor['required']['Guia'].set(True);editor['approved'].set(True)
  editor['save']();self.root.update()
  saved=json.loads((self.app.data/'perfis_pagadores.json').read_text())
  self.assertEqual(saved[0]['mapeamento']['Guia'],'Guia prestador');self.assertEqual(saved[0]['mapeamento']['Senha/Autorização'],'Senha autorização')
  self.app.payer_manager['choose']();self.assertEqual(self.app.selected_profile['id'],'FICTICIO')
 def test_interno_sem_guia_externa_na_interface(self):
  from test_mapping_sim import profile
  p=self.base/'interno.pdf';make_order(p)
  self.app.selected_profile=profile('FONTE FICTICIA INTERNA',True);self.app.selected_profile['mapeamento']={}
  with patch('app.filedialog.askopenfilename',return_value=str(p)):self.app.import_internal()
  self.root.update();self.assertTrue(self.app.models['guia']['internal'])
  self.assertEqual(len(self.app.cases.get_children()),1)
  self.assertEqual(self.app.field_vars['pedido']['Paciente'].get(),'PESSOA FICTICIA ALFA')
  self.app.locate_field('guia','Paciente')
  self.assertIn('pedido',self.app.origin_text.get('1.0','end'))
 def test_tiss_conferencia_ate_pre_cadastro_local_com_codigos_fornecidos(self):
  from test_mapping_sim import profile
  p=self.base/'p.pdf';g=self.base/'g.pdf';make_order(p);make_guide(g)
  # These internal codes are explicitly PROVIDED BY THIS SYNTHETIC TEST, never inferred by the application.
  for row in self.app.catalog:row['codigo_shift']='SIM-LAB-'+row['tuss']
  self.app.import_pairs([(p,g)]);self.wait();self.app.selected_profile=profile()
  for kind in ['pedido','guia']:
   for check in self.app.field_checks[kind].values():check.set(True)
   for exam in self.app.models[kind]['exams']:exam['reviewed']=True
   for issue in self.app.models[kind]['issues']:issue.update(reviewed=True,reason='Conferência fictícia completa')
   self.app.page_checks[kind].set(True);self.app.check_pages(kind)
  with patch('app.simpledialog.askstring',return_value='Conferência fictícia com perfil de teste'):self.app.save()
  self.assertFalse(self.app.analysis['pendencias'],self.app.analysis['pendencias'])
  self.app.confirm.set(True);self.app.prepare()
  output=self.app.store.get(self.app.cid)[3]
  self.assertIsNone(output['os_real']);self.assertEqual(len(output['exames']),5)
  self.assertEqual(output['payer_mapping']['values']['Guia'],'00000111')
  self.assertEqual(output['payer_mapping']['values']['Senha/Autorização'],'00000555')
