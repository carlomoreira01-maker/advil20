"""Fluxo real da nova conferência, metadados em foco e bloqueios preservados."""
import os,time,tempfile,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import patch
from app import App
from gerar_exemplos_carimbo import main
from gerar_exemplos_tiss import catalog
from tests.test_mapping_sim import profile

@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer display local e SHIFT_GUI_TESTS=1')
class Conferencia245(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.tmp=tempfile.TemporaryDirectory();cls.files=main(cls.tmp.name)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):
  self.tmpdata=tempfile.TemporaryDirectory();self.root=tk.Tk();self.app=App(self.root,Path(self.tmpdata.name));self.app.catalog=catalog()
  for row in self.app.catalog:row['codigo_shift']='SIM-LAB-'+row['tuss']
  self.root.update()
 def tearDown(self):self.app.store.db.close();self.root.destroy();self.tmpdata.cleanup()
 def import_pdf(self,file='01_pedido_carimbo_e_guia.pdf'):
  a=self.app
  with patch('app.filedialog.askopenfilenames',return_value=[str(self.files/file)]),patch('app.messagebox.showwarning') as warning:
   a.import_scan_button.invoke();end=time.monotonic()+120
   while a.busy and time.monotonic()<end:self.root.update();time.sleep(.01)
   self.assertFalse(a.busy);self.root.update();warning.assert_not_called()
 def see_and_confirm(self):
  a=self.app;a.actor.set('REVISOR FICTICIO')
  for button in a.page_panel.buttons:button.invoke();self.root.update()
  with patch('app.messagebox.askyesno',return_value=True):a.group_confirm_button.invoke()
  self.root.update();self.assertFalse(a.models['pedido']['association_pending']);self.assertTrue(all(len(v.seen)==len(v.doc['pages']) for v in a.views.values()))
 def assistant(self):self.app.assisted_button.invoke();self.root.update();return self.app.review_assistant
 def checked(self,helper):
  for variable in [*helper.data_checks.values(),*helper.exam_checks.values(),helper.alert_check]:variable.set(True)
 def test_falta_revisor_ou_motivo_destaca_e_foca_o_campo_sem_salvar(self):
  self.import_pdf();a=self.app;before=a.rev
  a.prepare_button.event_generate('<Button-1>',x=5,y=5);self.root.update()
  self.assertEqual(self.root.focus_get(),a.actor_entry);self.assertIn('Revisor',a.review_hint.get())
  with patch('app.simpledialog.askstring') as popup:a.save_review_button.invoke();self.root.update();popup.assert_not_called()
  self.assertEqual(self.root.focus_get(),a.actor_entry);self.assertIn('Revisor',a.review_hint.get());self.assertEqual(a.rev,before)
  a.actor.set('REVISOR FICTICIO');a.review_reason.set('');a.tabs.select(a.page_tab);a.group_confirm_button.invoke();self.root.update()
  self.assertEqual(a.tabs.select(),str(a.review_container))
  self.assertEqual(self.root.focus_get(),a.reason_entry);self.assertIn('Motivo',a.review_hint.get());self.assertEqual(a.rev,before)
 def test_fluxo_carimbo_ate_pre_cadastro_sem_mutar_validadores(self):
  self.import_pdf();a=self.app;self.see_and_confirm();a.selected_profile=profile();h=self.assistant()
  self.assertIn('DRA EXEMPLO SINTETICA',h.summary.get('1.0','end'));self.assertEqual(len(h.exam_table.get_children()),10)
  self.checked(h);h.save_button.invoke();self.root.update();self.assertTrue(h.saved);self.assertIn('SEM PENDÊNCIAS',h.message.get());self.assertEqual(str(h.prepare_button['state']),'disabled')
  h.final_check.set(True);h.update_prepare();self.assertEqual(str(h.prepare_button['state']),'normal');h.prepare_button.invoke();self.root.update()
  self.assertEqual(a.store.get(a.cid)[2],'PREPARADO');self.assertIsNone(a.store.get(a.cid)[3]['os_real']);self.assertIn('PREPARADO',h.message.get())
 def test_erro_metadado_no_assistente_mostra_o_campo_dentro_da_janela(self):
  self.import_pdf();a=self.app;h=self.assistant();h.save_button.invoke();self.root.update();self.assertEqual(self.root.focus_get(),h.entries['actor']);self.assertIn('Revisor',h.message.get());self.assertFalse(h.saved)
  a.actor.set('REVISOR FICTICIO');a.review_reason.set('');h.save_button.invoke();self.root.update();self.assertEqual(self.root.focus_get(),h.entries['reason']);self.assertIn('Motivo',h.message.get())
 def test_conferencia_salva_mas_autorizacao_zero_continua_bloqueada(self):
  self.import_pdf('04_autorizada_zero.pdf');a=self.app;self.see_and_confirm();a.selected_profile=profile();h=self.assistant();self.checked(h);h.save_button.invoke();self.root.update()
  self.assertTrue(h.saved);self.assertIn('CONFERÊNCIA SALVA',h.message.get());self.assertIn('Não autorizado',h.message.get());h.final_check.set(True);h.update_prepare();self.assertEqual(str(h.prepare_button['state']),'disabled');self.assertIsNone(a.store.get(a.cid)[3])
 def test_sem_catalogo_nao_inventa_codigo_e_explicita_configuracao(self):
  self.app.catalog=[];self.import_pdf();self.see_and_confirm();h=self.assistant();self.checked(h);h.save_button.invoke();self.root.update()
  self.assertTrue(h.saved);self.assertIn('catálogo',h.message.get());self.assertIn('responsável do laboratório',h.message.get());self.assertEqual(str(h.prepare_button['state']),'disabled')
 def test_quatro_paginas_confirmacao_simplificada_preserva_vistas(self):
  self.import_pdf('03_quatro_paginas.pdf');self.assertEqual(len(self.app.cases.get_children()),1);self.assertEqual(len(self.app.page_panel.buttons),4);self.see_and_confirm()
  self.assertFalse(self.app.models['pedido']['classification_pending']);self.app.selected_profile=profile();h=self.assistant();self.checked(h);h.save_button.invoke();self.root.update();self.assertTrue(h.saved);self.assertFalse(self.app.comparison_errors,self.app.comparison_errors)
 def test_motivo_editado_apos_salvar_exige_novo_salvamento(self):
  self.import_pdf();a=self.app;self.see_and_confirm();a.selected_profile=profile();h=self.assistant();self.checked(h);h.save_button.invoke();self.root.update();a.review_reason.set('Nova observação fictícia');self.root.update()
  self.assertTrue(a.dirty());self.assertFalse(h.saved);self.assertEqual(str(h.prepare_button['state']),'disabled')
 def test_exemplo_ficticio_completo_sem_configurar_shift(self):
  a=self.app;a.catalog=[];a.actor.set('REVISOR FICTICIO')
  with patch('app.messagebox.showwarning') as warning:
   a.examples_button.invoke();end=time.monotonic()+60
   while a.busy and time.monotonic()<end:self.root.update();time.sleep(.01)
   self.assertFalse(a.busy);self.root.update();warning.assert_not_called()
  first=a.cases.get_children()[0];a.cases.selection_set(first);a.open_case(first);h=self.assistant()
  self.assertEqual(str(h.confirm_pages_button['state']),'disabled');self.checked(h);h.save_button.invoke();self.root.update();self.assertTrue(h.saved);self.assertFalse(a.comparison_errors,a.comparison_errors)
  h.final_check.set(True);h.update_prepare();h.prepare_button.invoke();self.root.update();self.assertEqual(a.store.get(a.cid)[2],'PREPARADO');self.assertIsNone(a.store.get(a.cid)[3]['os_real'])

if __name__=='__main__':unittest.main()
