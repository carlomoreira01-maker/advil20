import os,tempfile,time,tkinter as tk,unittest,threading
from pathlib import Path
from unittest.mock import patch
from workbench import create_workbench
from gerar_exemplos_tiss import catalog
ROOT=Path(__file__).resolve().parents[1]
@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer interface gráfica')
class OptimizationGUI251(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=tk.Tk();self.app=create_workbench(self.root,Path(self.tmp.name)/'dados');self.ui=self.app.workspace;self.app.catalog=catalog();self.root.update()
 def tearDown(self):self.app.store.db.close();self.root.destroy();self.tmp.cleanup()
 def wait(self):
  end=time.monotonic()+60
  while self.app.busy and time.monotonic()<end:self.root.update();time.sleep(.01)
  self.assertFalse(self.app.busy);self.root.update()
 def read(self,paths,scope='single'):
  self.ui.scope_tabs.select(0 if scope=='single' else 1)
  with patch('app.filedialog.askopenfilenames',return_value=[str(ROOT/p) for p in paths]):self.ui.import_buttons[scope].invoke();self.wait()
 def test_padrao_quatro_paginas_uma_ficha_e_rascunho(self):
  self.read(['exemplos_2_4_2/01_um_atendimento_quatro_paginas.pdf']);self.assertEqual(len(self.app.cases.get_children()),1);self.assertEqual(len(self.ui.page_panel.items),4);self.assertEqual(self.ui.case_title.get(),'PESSOA FICTICIA ALFA');self.ui.go(4);self.ui.save_draft_button.invoke();self.assertIn('Rascunho salvo',self.ui.notice.get())
 def test_lote_padrao_mantem_pdfs_distintos_mesmo_paciente(self):
  self.read(['exemplos_250/pedido_a.pdf','exemplos_250/guia_completa.pdf'],'multiple');self.assertFalse(self.ui.advanced_grouping.get());self.assertEqual(len(self.app.cases.get_children()),2)
 def test_reunir_pdf_dividido_antes_sem_reimportar_mantem_bloqueio(self):
  self.ui.advanced_grouping.set(True);self.read(['exemplos_250/02_dois_pacientes_quatro_paginas.pdf'],'multiple');self.assertEqual(len(self.app.cases.get_children()),2);self.app.actor.set('REVISOR FICTICIO')
  with patch('workbench.messagebox.askyesno',return_value=True),patch('scan_import.read_document',side_effect=AssertionError('Não deve reimportar')):self.ui.regroup_pdf_button.invoke();self.root.update()
  self.assertEqual(len(self.app.cases.get_children()),1);self.assertEqual(len(self.ui.page_panel.items),4);self.assertTrue(self.app.models['pedido']['identity_conflict'])
 def test_conflito_sinalizado_e_separacao_manual_sem_ocr(self):
  self.read(['exemplos_250/02_dois_pacientes_quatro_paginas.pdf']);self.assertEqual(len(self.app.cases.get_children()),1);self.assertTrue(self.app.models['guia']['identity_conflict']);self.app.actor.set('REVISOR FICTICIO');self.ui.move_button.invoke();self.ui.move_editor['target'].set('Novo atendimento')
  with patch('scan_import.read_document',side_effect=AssertionError('Não deve ler novamente')):self.ui.move_editor['button'].invoke();self.root.update()
  self.assertEqual(len(self.app.cases.get_children()),2)
 def test_cancelar_analise_nao_grava_caso_e_libera_interface(self):
  from reading_control import check_cancelled
  def slow(*args,**kwargs):
   while True:check_cancelled(kwargs['cancel_event']);time.sleep(.01)
  with patch('scan_import.read_document',side_effect=slow),patch('app.filedialog.askopenfilenames',return_value=[str(ROOT/'exemplos_250/01_um_paciente.pdf')]),patch('app.messagebox.showwarning') as warning:
   self.ui.import_buttons['single'].invoke();self.root.update();self.app.cancel_read_button.invoke();self.wait();warning.assert_not_called()
  self.assertFalse(self.app.cases.get_children());self.assertIn('cancelada',self.ui.notice.get());self.assertFalse(self.app.progress.winfo_exists())
 def test_navegacao_e_correcao_nao_disparam_ocr(self):
  self.read(['exemplos_250/01_um_paciente.pdf'])
  with patch('engine_v2.ocr_words',side_effect=AssertionError('OCR indevido')),patch('scan_import.read_document',side_effect=AssertionError('Leitura indevida')):
   for n in [2,3,4,1,0,2]:self.ui.nav_buttons[n].invoke();self.root.update()
   self.ui.inputs['Número conselho'].delete(0,'end');self.ui.inputs['Número conselho'].insert(0,'0012345');self.ui.go(4);self.ui.save_draft_button.invoke()
 def test_treinamento_exige_cinco_conferencias_e_revisor(self):
  from rpa_training_ui import open_training
  open_training(self.app);ui=self.app.rpa_training;ui['start'].invoke();self.root.update();self.assertIn('Confira',ui['notice'].get());self.assertEqual(str(ui['start']['state']),'normal');ui['window'].destroy()
