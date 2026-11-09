"""Interface principal real: navegação limpa, lote, rascunho e preparo protegido."""
import os,tempfile,time,tkinter as tk,unittest,copy
from pathlib import Path
from unittest.mock import patch
from workbench import create_workbench,KIND_LABELS
from gerar_exemplos_250 import main,CLINICAL,EXECUTOR,PATIENTS,PRIORITY
from gerar_exemplos_tiss import VALUES,catalog
from tests.test_mapping_sim import profile
from tiss import SCHEMA
from draft_workflow import load_draft
from scan_import import load_batch

@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer display e SHIFT_GUI_TESTS=1')
class WorkbenchGUI250(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.fixtures=tempfile.TemporaryDirectory();cls.files=main(cls.fixtures.name)
 @classmethod
 def tearDownClass(cls):cls.fixtures.cleanup()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=tk.Tk();self.app=create_workbench(self.root,Path(self.tmp.name)/'dados');self.ui=self.app.workspace;self.app.catalog=catalog();self.root.update()
 def tearDown(self):self.app.store.db.close();self.root.destroy();self.tmp.cleanup()
 def wait(self):
  end=time.monotonic()+150
  while self.app.busy and time.monotonic()<end:self.root.update();time.sleep(.01)
  self.assertFalse(self.app.busy);self.root.update()
 def import_file(self,file='01_um_paciente.pdf',scope='single'):
  self.ui.scope_tabs.select(0 if scope=='single' else 1)
  self.ui.advanced_grouping.set(scope=='multiple')
  with patch('app.filedialog.askopenfilenames',return_value=[str(self.files/file)]),patch('app.messagebox.showwarning') as warning:
   self.ui.import_buttons[scope].invoke();self.wait();warning.assert_not_called()
 def see(self):
  self.ui.go(1)
  for button in self.ui.page_panel.buttons:button.invoke();self.root.update()
 def test_interface_em_cinco_telas_e_duas_abas_reais(self):
  self.assertEqual(len(self.ui.panels),5);self.assertEqual([self.ui.scope_tabs.tab(i,'text') for i in range(2)],['Cadastro de um paciente','Cadastro de vários pacientes']);self.assertEqual(self.ui.phase,0)
  self.assertEqual(self.ui.import_buttons['single']['text'],'Importar documentos');self.assertFalse(self.app.tabs.winfo_ismapped());self.assertTrue(self.ui.frame.winfo_ismapped())
 def test_campos_prioritarios_preenchidos_nos_widgets_com_origem(self):
  self.import_file();self.ui.nav_buttons[2].invoke();self.root.update();expected={**VALUES,10:PATIENTS[0],23:CLINICAL,30:EXECUTOR}
  self.assertIn('Leitura concluída',self.ui.notice.get());self.assertNotIn('Lendo',self.ui.notice.get())
  for n in [*PRIORITY,16]:
   with self.subTest(campo=n):
    key=SCHEMA[n][0];widget=self.ui.inputs[key];actual=widget.get('1.0','end-1c') if n==23 else widget.get();self.assertEqual(actual,expected[n]);self.assertEqual(self.app.models['guia']['fields'][key]['source_document']['page'],2)
  self.ui.origin_buttons['Contratado executante'].invoke();self.root.update();self.assertIn('original 2',self.ui.source_view.info.get());self.assertTrue(self.ui.source_view.box)
 def test_lote_quatro_paginas_cria_dois_atendimentos_e_dois_rascunhos(self):
  self.import_file('02_dois_pacientes_quatro_paginas.pdf','multiple');self.assertEqual(len(self.app.cases.get_children()),2);self.assertEqual(len(self.ui.queues['multiple'].get_children()),2);self.assertEqual(self.ui.metrics[0].get(),'1')
  names=set()
  for cid in self.ui.queues['multiple'].get_children():
   self.ui.choose_case(cid);names.add(self.ui.inputs['Paciente'].get());self.assertEqual(self.app.models['pedido']['fields']['Paciente']['value'],self.app.models['guia']['fields']['Paciente']['value'])
  self.assertEqual(names,set(PATIENTS));self.ui.batch_drafts_button.invoke();self.root.update();self.assertIn('2 rascunhos',self.ui.notice.get())
  for cid in self.app.cases.get_children():self.assertIsNotNone(load_draft(self.app.store,cid));self.assertEqual(self.app.store.get(cid)[2],'CONFERIR');self.assertIsNone(self.app.store.get(cid)[3])
 def test_aba_individual_mantem_pdf_junto_e_bloqueia_conflito(self):
  self.import_file('02_dois_pacientes_quatro_paginas.pdf','single');self.assertEqual(len(self.app.cases.get_children()),1);self.assertTrue(self.app.models['pedido']['identity_conflict']);self.assertTrue(self.app.models['pedido']['association_pending'])
 def test_campos_vazios_nao_bloqueiam_navegacao_ou_rascunho(self):
  self.import_file('03_campos_vazios.pdf')
  for button in self.ui.nav_buttons:button.invoke();self.root.update()
  self.assertEqual(self.ui.phase,4);self.ui.next_button.invoke();self.root.update();self.assertIn('Rascunho salvo',self.ui.notice.get());draft=load_draft(self.app.store,self.app.cid)
  for key in ['Guia principal','Senha autorização','Guia operadora','Contratado executante']:self.assertEqual(draft['preview']['campos'][key]['valor'],'');self.assertEqual(draft['preview']['campos'][key]['estado_leitura'],'empty')
  self.assertFalse(draft['preview']['pronto_para_envio']);self.assertIsNone(self.app.store.get(self.app.cid)[3])
 def test_correcao_manual_salva_atualiza_pendencia_e_persiste_navegacao(self):
  self.import_file('05_leitura_incerta.pdf');self.app.actor.set('REVISOR FICTICIO');self.ui.go(2);self.ui.correct_information_button.invoke();self.root.update();entry=self.ui.inputs['Número conselho'];self.assertEqual(self.root.focus_get(),entry);entry.delete(0,'end');entry.insert(0,'0012345');self.root.update()
  self.ui.save_corrections_button.invoke();self.root.update();self.assertEqual(self.app.store.get(self.app.cid)[0]['models']['guia']['fields']['Número conselho']['value'],'0012345')
  self.assertNotIn('Número conselho não identificado',' '.join(self.app.comparison_errors));self.ui.go(4);self.ui.go(2);self.assertEqual(self.ui.inputs['Número conselho'].get(),'0012345')
 def test_troca_de_atendimento_preserva_edicao_em_rascunho(self):
  self.import_file('02_dois_pacientes_quatro_paginas.pdf','multiple');a,b=list(self.app.cases.get_children());self.ui.choose_case(a);self.ui.go(2);entry=self.ui.inputs['Contratado executante'];entry.delete(0,'end');entry.insert(0,'LABORATORIO CORRIGIDO FICTICIO')
  self.ui.choose_case(b);self.ui.choose_case(a);self.assertEqual(self.ui.inputs['Contratado executante'].get(),'LABORATORIO CORRIGIDO FICTICIO');self.assertIsNotNone(load_draft(self.app.store,a))
 def test_fluxo_principal_real_ate_pre_cadastro_validado_ficticio(self):
  self.import_file();self.app.actor.set('REVISOR FICTICIO')
  for row in self.app.catalog:row['codigo_shift']='SIM-LAB-'+row['tuss']
  self.see()
  with patch('app.messagebox.askyesno',return_value=True):self.ui.confirm_pages_button.invoke()
  self.root.update();self.app.selected_profile=profile();self.ui.compare_button.invoke();self.ui.go(4);self.ui.data_review.set(True);self.ui.exams_review.set(True);self.ui.validate_button.invoke();self.root.update()
  self.assertFalse(self.app.comparison_errors,self.app.comparison_errors);self.assertFalse(self.app.dirty());self.ui.final_confirm.set(True);self.ui.prepare_button.invoke();self.root.update()
  obj,_,status,out=self.app.store.get(self.app.cid);self.assertEqual(status,'PREPARADO');self.assertIsNone(out['os_real']);self.assertEqual(len(out['exames']),5);self.assertEqual(obj['models']['guia']['fields']['Contratado executante']['value'],EXECUTOR)
  self.assertIn('validado',self.ui.preview_title.get());self.assertEqual(self.ui.next_button['text'],'Exportar pré-cadastro validado')
 def test_pre_cadastro_so_de_guia_nao_inventa_pedido(self):
  self.import_file('guia_completa.pdf');self.ui.go(4);self.assertFalse(self.ui.preview['documentos_presentes']['pedido']);self.assertEqual(self.app.models['pedido']['exams'],[]);self.ui.save_draft_button.invoke();self.assertIsNone(self.app.store.get(self.app.cid)[3])
 def test_mover_pagina_sem_reimportar_preserva_paginas_e_bloqueia_conflito(self):
  self.import_file('02_dois_pacientes_quatro_paginas.pdf','multiple');self.app.actor.set('REVISOR FICTICIO');a,b=list(self.app.cases.get_children());self.ui.choose_case(b);group_a=self.app.store.get(a)[0]['docs']['pedido']['scan_group'];self.ui.go(1)
  idx=next(i for i,item in enumerate(self.ui.page_panel.items) if item['kind']=='guia');self.ui.page_panel.buttons[idx].invoke();self.ui.move_button.invoke();editor=self.ui.move_editor;editor['target'].set(group_a)
  with patch('scan_import.read_document',side_effect=AssertionError('Não deve reimportar')):editor['button'].invoke();self.root.update()
  self.ui.choose_case(a);self.assertTrue(self.app.models['guia']['identity_conflict']);self.see()
  with patch('app.messagebox.askyesno',return_value=True):self.ui.confirm_pages_button.invoke()
  self.assertIn('incompatíveis',self.ui.notice.get());self.assertIsNone(self.app.store.get(a)[3])
  obj=self.app.store.get(a)[0];batch=load_batch(self.app.store,obj['docs']['pedido']['scan_batch']);self.assertEqual(len(batch['pages']),4);self.ui.go(4);self.ui.save_draft_button.invoke();self.assertIsNotNone(load_draft(self.app.store,a))
 def test_revisor_e_motivo_ficam_visiveis_quando_faltam(self):
  self.import_file();self.ui.save_corrections_button.invoke();self.root.update();self.assertEqual(self.root.focus_get(),self.ui.actor_entry);self.assertIn('Revisor',self.ui.notice.get())
  self.app.actor.set('REVISOR FICTICIO');self.app.review_reason.set('');self.ui.go(1);self.ui.save_corrections_button.invoke();self.root.update();self.assertEqual(self.ui.phase,4);self.assertEqual(self.root.focus_get(),self.ui.reason_entry);self.assertIn('Motivo',self.ui.notice.get())
 def test_conferencia_detalhada_preservada_e_volta_sem_perder_campos(self):
  self.import_file();self.ui.show_advanced();self.root.update();self.assertTrue(self.ui.advanced);self.ui.hide_advanced();self.root.update();self.assertFalse(self.ui.advanced);self.assertEqual(self.ui.inputs['Contratado executante'].get(),EXECUTOR)
 def test_reprocessar_pelo_painel_e_reimportar_nao_duplica_atendimento(self):
  self.import_file();self.app.actor.set('REVISOR FICTICIO');cid=self.app.cid
  with patch('app.messagebox.askyesno',return_value=True):self.ui.reprocess_button.invoke()
  self.wait()
  self.assertEqual(self.app.cid,cid);self.assertEqual(len(self.ui.page_panel.items),2);self.assertEqual([i['kind'] for i in self.ui.page_panel.items],['pedido','guia']);self.assertEqual(self.ui.inputs['Contratado executante'].get(),EXECUTOR)
  with patch('app.filedialog.askopenfilenames',return_value=[str(self.files/'01_um_paciente.pdf')]),patch('app.messagebox.showwarning') as warning:
   self.ui.import_buttons['single'].invoke();self.wait()
  self.assertEqual(warning.call_count,1);self.assertIn('já está na fila',warning.call_args.args[1]);self.assertEqual(len(self.app.cases.get_children()),1);self.assertEqual(len(self.ui.queues['single'].get_children()),1)
 def test_janela_menor_mantem_navegacao_e_conferencia_com_rolagem(self):
  self.import_file();self.root.geometry('1024x688');self.root.update();self.ui.go(4);self.root.update()
  self.assertTrue(self.ui.next_button.winfo_ismapped());self.assertLess(self.ui.next_button.winfo_rooty()+self.ui.next_button.winfo_height(),self.root.winfo_rooty()+self.root.winfo_height()+1)
  self.ui.preview_canvas.yview_moveto(1);self.root.update();button=self.ui.prepare_button
  self.assertGreaterEqual(button.winfo_rooty(),self.ui.preview_canvas.winfo_rooty());self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),self.ui.preview_canvas.winfo_rooty()+self.ui.preview_canvas.winfo_height()+1)

if __name__=='__main__':unittest.main()
