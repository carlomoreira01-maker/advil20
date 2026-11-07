"""Ponta a ponta na interface Tk: importação única até pré-cadastro LOCAL fictício."""
import copy,json,os,tempfile,time,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import patch
from app import App,UNIDENTIFIED,IMPORT_MODES
from gerar_exemplos_tiss import catalog,VALUES
from gerar_exemplos_2_4 import main,combine
from tests.test_mapping_sim import profile
from tiss import SCHEMA

@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer tela virtual/local e SHIFT_GUI_TESTS=1')
class ScanInterface(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.fixtures=tempfile.TemporaryDirectory();cls.files=main(cls.fixtures.name)
 @classmethod
 def tearDownClass(cls):cls.fixtures.cleanup()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=tk.Tk();self.app=App(self.root,Path(self.tmp.name)/'dados');self.app.catalog=catalog()
  for row in self.app.catalog:row['codigo_shift']='SIM-LAB-'+row['tuss']  # supplied by test only
  self.app.import_mode.set(IMPORT_MODES['multiple']);self.app.actor.set('REVISOR FICTICIO');self.root.update()
 def tearDown(self):
  self.app.store.db.close();self.root.destroy();self.tmp.cleanup()
 def wait(self):
  end=time.monotonic()+90
  while self.app.busy and time.monotonic()<end:self.root.update();time.sleep(.01)
  self.assertFalse(self.app.busy);self.root.update()
 def import_file(self,name,button=False):
  with patch('app.messagebox.showwarning') as warning:
   if button:
    with patch('app.filedialog.askopenfilenames',return_value=[str(self.files/name)]):self.app.import_scan_button.invoke()
   else:self.app.import_scans([self.files/name])
   self.wait();warning.assert_not_called()
 def review_save(self):
  a=self.app;a.selected_profile=profile()
  for role in ['pedido','guia']:
   for i in range(len(a.views[role].doc['pages'])):a.views[role].locate(i+1,None)
   a.page_checks[role].set(True);a.check_pages(role);a.forms.select(0 if role=='pedido' else 1)
   with patch('app.messagebox.askyesno',return_value=True):a.review_fields()
   for e in a.models[role]['exams']:e['reviewed']=True
   for issue in a.models[role]['issues']:issue.update(reviewed=True,reason='Conferido no original inteiramente fictício')
  with patch('app.simpledialog.askstring',return_value='Conferência fictícia completa'):a.save_review_button.invoke()
  self.root.update()
 def test_botao_unico_preenche_campos_tabela_e_avanca_apos_conferencia(self):
  self.import_file('01_pedido_e_guia.pdf',button=True);a=self.app
  self.assertEqual(a.tabs.select(),str(a.review_container));self.assertEqual(len(a.cases.get_children()),1)
  for n,v in VALUES.items():self.assertEqual(a.field_vars['guia'][SCHEMA[n][0]].get(),v)
  self.assertEqual(len(a.compare_table.get_children()),5);self.assertEqual(str(a.prepare_button['state']),'disabled')
  self.review_save();self.assertFalse(a.comparison_errors,a.comparison_errors)
  self.assertEqual(str(a.prepare_button['state']),'disabled');a.confirm.set(True)
  self.assertEqual(str(a.prepare_button['state']),'normal');a.prepare_button.invoke();self.root.update()
  self.assertEqual(a.store.get(a.cid)[2],'PREPARADO');self.assertIsNone(a.store.get(a.cid)[3]['os_real'])
 def test_guia_antes_pedido_e_origem_fisica(self):
  self.import_file('02_guia_antes_pedido.pdf');a=self.app
  self.assertEqual(a.field_vars['pedido']['Paciente'].get(),VALUES[10]);a.locate_field('pedido','Paciente')
  self.assertEqual(a.views['pedido'].doc['pages'][0]['source']['page'],2)
  self.assertIn('original 2',a.views['pedido'].info.get());self.review_save();a.confirm.set(True);a.prepare_button.invoke()
  self.assertEqual(a.store.get(a.cid)[2],'PREPARADO')
 def test_dois_pacientes_em_pdf_misturado_ficam_separados(self):
  self.import_file('03_quatro_paginas_misturadas.pdf');a=self.app;self.assertEqual(len(a.cases.get_children()),2)
  names=set()
  for cid in a.cases.get_children():
   a.open_case(cid);names.add(a.field_vars['pedido']['Paciente'].get());self.assertEqual(a.field_vars['pedido']['Paciente'].get(),a.field_vars['guia']['Paciente'].get())
   self.assertEqual(len(a.exam_tables['pedido'].get_children()),5)
  self.assertEqual(len(names),2)
 def test_guia_escaneada_girada_preenche_interface(self):
  self.import_file('04_guia_girada_e_pedido.pdf');a=self.app
  for n in [2,5,7,8,10,15,16,17,18]:self.assertEqual(a.field_vars['guia'][SCHEMA[n][0]].get(),VALUES[n])
  self.assertEqual(len(a.compare_table.get_children()),5);self.review_save();self.assertFalse(a.comparison_errors,a.comparison_errors)
  a.confirm.set(True);a.prepare_button.invoke();self.assertEqual(a.store.get(a.cid)[2],'PREPARADO')
 def test_ocr_ausente_conferencia_acessivel_e_preparo_bloqueado(self):
  from ocr_runtime import LocalReadError
  with patch('engine_v2.ocr_words',side_effect=LocalReadError('Tesseract ausente.')):self.import_file('04_guia_girada_e_pedido.pdf')
  a=self.app;self.assertEqual(a.tabs.select(),str(a.review_container));self.assertTrue(a.comparison_errors);self.assertEqual(str(a.prepare_button['state']),'disabled')
  a.manual_correction();self.assertEqual(a.tabs.select(),str(a.review_container))
 def test_exames_sem_catalogo_sao_exibidos_com_pendencia(self):
  self.app.catalog=[];self.import_file('01_pedido_e_guia.pdf');a=self.app
  self.assertEqual(len(a.compare_table.get_children()),10);self.assertTrue(a.analysis['pendencias']);self.assertEqual(str(a.prepare_button['state']),'disabled')
 def test_classificacao_manual_historico_e_reprocessamento(self):
  self.import_file('01_pedido_e_guia.pdf');a=self.app;cid=a.cid
  a.classification_window();ed=a.classification_editor;ed['table'].selection_set('0');self.root.update()
  ed['kind'].set('incerto');ed['reason'].set('Teste fictício de classificação');ed['reviewed'].set(True);ed['apply']()
  with patch('app.messagebox.askyesno',return_value=True):ed['save']()
  self.assertEqual(a.cid,cid);self.assertTrue(a.models['pedido']['classification_pending']);self.assertEqual(a.rev,2)
  a.classification_window();ed=a.classification_editor;ed['table'].selection_set('0');self.root.update()
  ed['kind'].set('pedido');ed['reason'].set('Pedido conferido no original fictício');ed['reviewed'].set(True);ed['apply']()
  with patch('app.messagebox.askyesno',return_value=True):ed['save']()
  self.assertFalse(a.models['pedido']['classification_pending']);self.assertEqual(len(a.models['pedido']['exams']),5)
  with patch('app.messagebox.askyesno',return_value=True):a.reanalyze_case();self.wait()
  self.assertEqual(a.cid,cid);self.assertEqual(a.rev,4);self.assertEqual(len(a.cases.get_children()),1)
 def test_editar_campo_invalida_conferencia_e_salvar_atualiza_comparacao(self):
  self.import_file('01_pedido_e_guia.pdf');a=self.app;self.review_save();a.confirm.set(True)
  self.assertEqual(str(a.prepare_button['state']),'normal');a.manual_correction();a.field_vars['guia']['Carteira'].set('00009999');self.root.update()
  self.assertFalse(a.confirm.get());self.assertFalse(a.field_checks['guia']['Carteira'].get());self.assertEqual(str(a.prepare_button['state']),'disabled')
  a.field_checks['guia']['Carteira'].set(True)
  with patch('app.simpledialog.askstring',return_value='Correção fictícia com divergência proposital'):a.save_review_button.invoke()
  self.assertIn('Identidade',' '.join(a.analysis['pendencias']));self.assertEqual(a.store.get(a.cid)[0]['models']['guia']['fields']['Carteira']['origin_type'],'correcao_manual')
 def test_correcao_manual_de_quantidade_atualiza_comparacao_e_libera_apos_revisao(self):
  from tkinter import ttk
  self.import_file('01_pedido_e_guia.pdf');a=self.app
  # Simula um erro de leitura; o original SINTÉTICO contém autorização 1.
  row=a.models['guia']['exams'][0];row['quantidade']='0';row['quantidade_autorizada']='0';a.render_rows('guia');a.show_comparison()
  self.assertIn('Não autorizado',' '.join(a.analysis['pendencias']))
  a.exam_tables['guia'].selection_set('0');a.edit_exam('guia');self.root.update()
  window=next(w for w in self.root.winfo_children() if isinstance(w,tk.Toplevel) and w.title().startswith('Conferir exame'))
  entry=next(w for w in window.winfo_children() if isinstance(w,ttk.Entry) and int(w.grid_info()['row'])==3)
  entry.delete(0,'end');entry.insert(0,'1')
  next(w for w in window.winfo_children() if isinstance(w,ttk.Checkbutton)).invoke()
  next(w for w in window.winfo_children() if isinstance(w,ttk.Button)).invoke();self.root.update()
  self.assertNotIn('Não autorizado',' '.join(a.analysis['pendencias']));self.assertEqual(a.models['guia']['exams'][0]['origin_type'],'correcao_manual')
  self.review_save();a.confirm.set(True);a.prepare_button.invoke();self.assertEqual(a.store.get(a.cid)[2],'PREPARADO')
 def test_exame_ausente_e_campo_vazio_nao_impedem_acesso_a_conferencia(self):
  combine(self.files/'pendente_gui.pdf',[self.files/'pedido_alfa.pdf',self.files/'guia_exame_ausente.pdf'])
  self.import_file('pendente_gui.pdf');a=self.app
  self.assertEqual(a.tabs.select(),str(a.review_container));self.assertEqual(len(a.compare_table.get_children()),5)
  self.assertIn('Ausente na guia',' '.join(a.analysis['pendencias']));a.manual_correction();self.review_save();a.confirm.set(True)
  self.assertEqual(str(a.prepare_button['state']),'disabled')

if __name__=='__main__':unittest.main()
