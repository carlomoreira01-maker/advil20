"""Fluxo completo e visível: quatro miniaturas, revisão, conflitos e preparo local."""
import copy,os,tempfile,time,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import patch
from app import App,IMPORT_MODES
from gerar_exemplos_2_4_2 import main
from gerar_exemplos_tiss import catalog,VALUES
from tests.test_mapping_sim import profile

@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer display e SHIFT_GUI_TESTS=1')
class GroupingGUI242(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.fixtures=tempfile.TemporaryDirectory();cls.files=main(cls.fixtures.name)
 @classmethod
 def tearDownClass(cls):cls.fixtures.cleanup()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=tk.Tk();self.app=App(self.root,Path(self.tmp.name)/'dados');self.app.catalog=catalog();self.app.actor.set('REVISOR FICTICIO')
  for row in self.app.catalog:row['codigo_shift']='SIM-LAB-'+row['tuss']
  self.root.update()
 def tearDown(self):self.app.store.db.close();self.root.destroy();self.tmp.cleanup()
 def wait(self):
  end=time.monotonic()+120
  while self.app.busy and time.monotonic()<end:self.root.update();time.sleep(.01)
  self.assertFalse(self.app.busy);self.root.update()
 def import_pdf(self,name='01_um_atendimento_quatro_paginas.pdf',mode='single'):
  a=self.app;a.import_mode.set(IMPORT_MODES[mode])
  with patch('app.filedialog.askopenfilenames',return_value=[str(self.files/name)]),patch('app.messagebox.showwarning') as warning:
   a.import_scan_button.invoke();self.wait();warning.assert_not_called()
 def see_pages(self):
  for button in self.app.page_panel.buttons:button.invoke();self.root.update()
 def grouping_review(self):
  a=self.app;self.see_pages();a.classification_window();ed=a.classification_editor
  for i,page in enumerate(ed['batch']['pages']):
   if page['kind']=='outro':
    ed['table'].selection_set(str(i));self.root.update();ed['reviewed'].set(True);ed['reason'].set('Conferi documento complementar fictício');ed['apply']();self.root.update()
  ed['reason'].set('Conferi todas as páginas e os identificadores fictícios');ed['confirm']()
  with patch('app.messagebox.askyesno',return_value=True):ed['save']()
  self.root.update()
 def clinical_review(self):
  a=self.app;a.selected_profile=profile()
  for kind in ['pedido','guia']:
   for page in range(len(a.views[kind].doc['pages'])):a.views[kind].locate(page+1,None)
   a.page_checks[kind].set(True);a.check_pages(kind)
   for check in a.field_checks[kind].values():check.set(True)
   for e in a.models[kind]['exams']:e['reviewed']=True
   for issue in a.models[kind]['issues']:issue.update(reviewed=True,reason='Conferência do documento sintético')
  with patch('app.simpledialog.askstring',return_value='Conferência fictícia completa'):a.save_review_button.invoke()
  self.root.update()
 def test_quatro_paginas_mesma_ficha_campos_visiveis_ate_preparo(self):
  self.import_pdf();a=self.app;self.assertEqual(len(a.cases.get_children()),1);self.assertEqual(len(a.page_panel.buttons),4)
  self.assertEqual([p['kind'] for p in a.page_panel.items],['pedido','guia','continuação de guia','outro'])
  self.assertEqual(a.field_vars['pedido']['Paciente'].get(),'PESSOA FICTICIA ALFA');self.assertEqual(a.field_vars['guia']['Carteira'].get(),VALUES[8])
  self.assertEqual(a.field_vars['guia']['Guia prestador'].get(),VALUES[2]);self.assertEqual(a.field_vars['guia']['Senha autorização'].get(),VALUES[5])
  self.assertEqual(len(a.compare_table.get_children()),5);self.assertEqual(str(a.prepare_button['state']),'disabled')
  a.page_panel.buttons[3].invoke();self.assertIn('outro',a.page_panel.info.get());self.assertIn('original 4',a.page_panel.viewer.info.get())
  a.tabs.select(a.review_container);a.manual_correction();self.assertEqual(a.tabs.select(),str(a.review_container))
  self.grouping_review();self.assertFalse(a.models['pedido']['association_pending']);self.assertFalse(a.models['guia']['classification_pending'])
  self.clinical_review();self.assertFalse(a.comparison_errors,a.comparison_errors);a.confirm.set(True)
  self.assertEqual(str(a.prepare_button['state']),'normal');a.prepare_button.invoke();self.root.update()
  obj,_,status,out=a.store.get(a.cid);self.assertEqual(status,'PREPARADO');self.assertIsNone(out['os_real']);self.assertEqual(len(out['exames']),5)
  self.assertEqual(sum(len(d['pages']) for d in obj['docs'].values()),4)
 def test_conflito_impede_confirmacao_e_mover_pagina_resolve_separacao(self):
  self.import_pdf('02_identificadores_incompativeis.pdf');a=self.app;self.assertEqual(len(a.cases.get_children()),1)
  self.assertTrue(a.models['pedido']['identity_conflict']);self.see_pages();a.classification_window();ed=a.classification_editor
  ed['reason'].set('Revisei as duas pessoas fictícias')
  with self.assertRaisesRegex(ValueError,'incompatíveis'):ed['confirm']()
  ed['table'].selection_set('1');self.root.update();ed['group'].set('Paciente fictício separado');ed['reason'].set('Carteiras incompatíveis: separei os atendimentos');ed['reviewed'].set(True);ed['apply']()
  with patch('app.messagebox.askyesno',return_value=True):ed['save']()
  self.assertEqual(len(a.cases.get_children()),2)
  for cid in a.cases.get_children():a.open_case(cid);self.assertFalse(a.models['pedido']['identity_conflict']);self.assertEqual(str(a.prepare_button['state']),'disabled')
 def test_reprocessamento_preserva_paginas_e_modo_revoga_aprovacao(self):
  self.import_pdf();a=self.app;cid=a.cid;self.grouping_review();self.assertFalse(a.models['pedido']['association_pending'])
  with patch('app.messagebox.askyesno',return_value=True),patch('app.messagebox.showwarning') as warning:a.reanalyze_case();self.wait();warning.assert_not_called()
  self.assertEqual(a.cid,cid);self.assertEqual(len(a.cases.get_children()),1);self.assertEqual(len(a.page_panel.buttons),4)
  self.assertTrue(a.models['pedido']['association_pending']);self.assertEqual(a.field_vars['pedido']['Paciente'].get(),'PESSOA FICTICIA ALFA')
 def test_regroup_lote_anterior_sem_reimportar_e_sem_perda(self):
  self.import_pdf(mode='multiple');a=self.app;self.assertGreater(len(a.cases.get_children()),1)
  a.classification_window();ed=a.classification_editor;ed['reason'].set('Este PDF foi escaneado como um único atendimento provisório');ed['regroup']()
  with patch('app.messagebox.askyesno',return_value=True),patch('scan_import.read_document',side_effect=AssertionError('Não deve reimportar')):ed['save']()
  self.assertEqual(len(a.cases.get_children()),1);self.assertEqual(len(a.page_panel.buttons),4);self.assertTrue(a.models['pedido']['association_pending'])
 def test_modo_varios_pacientes_e_duplicidade(self):
  self.import_pdf('02_identificadores_incompativeis.pdf',mode='multiple');a=self.app;self.assertEqual(len(a.cases.get_children()),2)
  for cid in a.cases.get_children():a.open_case(cid);self.assertFalse(a.models['pedido']['identity_conflict'])
  with patch('app.messagebox.showwarning') as warning:
   a.import_scans([self.files/'02_identificadores_incompativeis.pdf'],mode='single');self.wait();self.assertTrue(warning.called)
  self.assertEqual(len(a.cases.get_children()),2)
 def test_ocr_real_quatro_paginas_preenche_campos_e_tabela(self):
  self.import_pdf('03_quatro_paginas_escaneadas.pdf');a=self.app
  self.assertEqual(len(a.cases.get_children()),1);self.assertEqual(len(a.page_panel.buttons),4)
  for key,expected in [('Paciente','PESSOA FICTICIA ALFA')]:self.assertEqual(a.field_vars['pedido'][key].get(),expected)
  for key,expected in [('Carteira',VALUES[8]),('Senha autorização',VALUES[5]),('Guia operadora',VALUES[7]),('Número conselho',VALUES[17])]:self.assertEqual(a.field_vars['guia'][key].get(),expected)
  self.assertEqual(len(a.exam_tables['guia'].get_children()),5);self.assertEqual(len(a.compare_table.get_children()),5)
 def test_corrigir_identificacao_pela_interface_e_reprocessar_preserva_historico(self):
  self.import_pdf();a=self.app;self.see_pages();a.classification_window();ed=a.classification_editor
  ed['table'].selection_set('1');self.root.update();ed['identity']['Carteira'].set('00000007');ed['reviewed'].set(True);ed['reason'].set('Simulação de erro de leitura fictício');ed['apply']();self.root.update()
  ed['reason'].set('Revisão humana do documento fictício')
  with self.assertRaisesRegex(ValueError,'incompatíveis'):ed['confirm']()
  ed['identity']['Carteira'].set(VALUES[8]);ed['reviewed'].set(True);ed['reason'].set('Corrigido após conferir o original fictício');ed['apply']();self.root.update()
  with patch('app.messagebox.askyesno',return_value=True):ed['save']()
  self.assertFalse(a.models['pedido']['identity_conflict']);self.assertEqual(a.models['guia']['fields']['Carteira']['origin_type'],'correcao_manual_da_pagina')
  cid=a.cid
  with patch('app.messagebox.askyesno',return_value=True):a.reanalyze_case();self.wait()
  from scan_import import load_batch
  obj=a.store.get(cid)[0];b=load_batch(a.store,obj['docs']['pedido']['scan_batch'])
  self.assertEqual(b['pages'][1]['identity_edits']['Carteira']['history'][-1]['after'],VALUES[8])
  self.assertEqual(a.field_vars['guia']['Carteira'].get(),VALUES[8]);self.assertTrue(a.models['pedido']['association_pending'])
 def test_setas_do_visualizador_mantem_pagina_tipo_e_revisao_sincronizados(self):
  self.import_pdf();a=self.app
  for _ in range(3):a.page_panel.viewer.move(1);self.root.update()
  self.assertEqual(a.page_panel.selected_id,a.page_panel.items[3]['id'])
  self.assertEqual(len(a.page_panel.seen_ids),4);self.assertIn('Tipo: outro',a.page_panel.info.get())
  a.classification_window();ed=a.classification_editor
  self.assertEqual(ed['table'].selection(),('3',));self.assertEqual(ed['kind'].get(),'outro')

if __name__=='__main__':unittest.main()
