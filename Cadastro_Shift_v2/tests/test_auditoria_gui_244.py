"""Cliques na interface real, somente PDFs/pacientes/códigos fictícios."""
import os,json,tempfile,time,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import patch
from app import App,IMPORT_MODES,NOT_APPLICABLE
from gerar_exemplos_auditoria import main,PATIENT
from gerar_exemplos_tiss import catalog,VALUES
from tests.test_mapping_sim import profile
import tests.test_grouping_gui_242 as grouping

@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer display e SHIFT_GUI_TESTS=1')
class AuditoriaGUI244(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.fixtures=tempfile.TemporaryDirectory();cls.files=main(cls.fixtures.name);cls.report=[]
 @classmethod
 def tearDownClass(cls):
  if os.getenv('SHIFT_AUDIT_GUI_REPORT'):Path(os.environ['SHIFT_AUDIT_GUI_REPORT']).write_text(json.dumps({'somente_sinteticos':True,'verificacoes':cls.report},ensure_ascii=False,indent=2)+'\n')
  cls.fixtures.cleanup()
 def assertEqual(self,first,second,msg=None):
  self.report.append({'teste':self._testMethodName,'esperado':second,'encontrado':first,'passou':first==second})
  return super().assertEqual(first,second,msg)
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=tk.Tk();self.app=App(self.root,Path(self.tmp.name)/'dados');self.app.actor.set('REVISOR FICTICIO');self.app.catalog=catalog()
  for row in self.app.catalog:row['codigo_shift']='SIM-LAB-'+row['tuss']
  self.root.update()
 def tearDown(self):self.app.store.db.close();self.root.destroy();self.tmp.cleanup()
 see_pages=grouping.GroupingGUI242.see_pages
 grouping_review=grouping.GroupingGUI242.grouping_review
 clinical_review=grouping.GroupingGUI242.clinical_review
 def import_pdf(self,name):
  a=self.app;a.import_mode.set(IMPORT_MODES['single'])
  with patch('app.filedialog.askopenfilenames',return_value=[str(self.files/name)]),patch('app.messagebox.showwarning') as warning:
   a.import_scan_button.invoke();end=time.monotonic()+120
   while a.busy and time.monotonic()<end:self.root.update();time.sleep(.01)
   self.assertFalse(a.busy);self.root.update();warning.assert_not_called()
 def pending(self,action,field=None,role=None):
  a=self.app;a.show_comparison()
  index=next(i for i,s in enumerate(a.pending_steps) if s['action']==action and (field is None or s['field']==field) and (role is None or s['role']==role))
  a.pending_table.selection_set(str(index));a.pending_button.invoke();self.root.update()
 def finish(self):
  a=self.app;self.clinical_review();self.assertFalse(a.comparison_errors,a.comparison_errors);self.assertFalse(a.pending_steps)
  a.confirm.set(True);self.assertEqual(str(a.prepare_button['state']),'normal');a.prepare_button.invoke();self.root.update();self.assertEqual(a.store.get(a.cid)[2],'PREPARADO');self.assertIsNone(a.store.get(a.cid)[3]['os_real'])
 def test_quatro_paginas_campos17_cbo_visiveis_ate_pre_cadastro(self):
  self.import_pdf('01_quatro_paginas.pdf');a=self.app;self.assertEqual(len(a.cases.get_children()),1);self.assertEqual(len(a.page_panel.buttons),4)
  for key,value in [('Paciente',PATIENT),('Conselho','CRM'),('Número conselho','0012345'),('UF conselho','GO'),('CBO','225125')]:self.assertEqual(a.field_vars['guia'][key].get(),value)
  self.assertEqual(len(a.compare_table.get_children()),5);self.assertEqual(a.tabs.select(),str(a.review_container));self.grouping_review();self.finish()
 def test_corrigir_crm_salvar_resolve_e_avanca(self):
  self.import_pdf('07_conferencia.pdf');a=self.app;self.grouping_review()
  self.assertIn('Número conselho não identificado',' '.join(a.comparison_errors));self.pending('field','Número conselho','guia')
  a.field_vars['guia']['Número conselho'].set('0012345')
  with patch('app.simpledialog.askstring',return_value='CRM conferido no gabarito fictício'):a.save_review_button.invoke()
  self.root.update();self.assertEqual(a.store.get(a.cid)[0]['models']['guia']['fields']['Número conselho']['value'],'0012345');self.finish()
 def test_resolver_quantidade_por_botao_atualiza_e_avanca(self):
  self.import_pdf('06_quantidades.pdf');a=self.app;self.grouping_review();self.assertIn('Não autorizado',' '.join(a.comparison_errors));self.pending('exam',role='guia')
  editor=a.exam_editor;editor['variables']['quantidade'].set('1');editor['checked'].set(True);editor['button'].invoke();self.root.update()
  self.assertEqual(a.models['guia']['exams'][0]['quantidade_autorizada'],'1');self.assertNotIn('Não autorizado',' '.join(a.comparison_errors));self.finish()
 def test_nao_aplicavel_homologado_persiste_sem_dispensar_senha(self):
  self.import_pdf('14_nao_aplicavel.pdf');a=self.app;a.selected_profile=profile();a.selected_profile['campos_nao_aplicaveis']=['Guia principal']
  with patch('app.messagebox.askyesno',return_value=True):a.na_button.invoke()
  self.assertEqual(a.field_vars['guia']['Guia principal'].get(),NOT_APPLICABLE)
  with patch('app.simpledialog.askstring',return_value='Regra fictícia conferida'):a.save_review_button.invoke()
  a.open_case(a.cid);self.assertEqual(a.field_vars['guia']['Guia principal'].get(),NOT_APPLICABLE);self.assertIn('Senha autorização não identificada',' '.join(a.comparison_errors));self.assertEqual(str(a.prepare_button['state']),'disabled')
 def test_botao_confirmar_nao_aprova_identificadores_incompativeis(self):
  self.import_pdf('08_conflito.pdf');a=self.app;self.assertEqual(len(a.cases.get_children()),1);self.see_pages();a.classification_window();ed=a.classification_editor
  ed['reason'].set('Tentativa de associação fictícia incompatível')
  def buttons(w):
   for child in w.winfo_children():
    if child.winfo_class()=='TButton':yield child
    yield from buttons(child)
  button=next(b for b in buttons(ed['window']) if b.cget('text')=='Confirmar agrupamento')
  with patch('app.messagebox.showerror') as error:button.invoke();self.assertIn('incompatíveis',str(error.call_args))
  self.assertTrue(a.models['guia']['identity_conflict']);self.assertEqual(str(a.prepare_button['state']),'disabled')
 def test_pdf_girado_ocr_preenche_crm_go_e_cbo(self):
  self.import_pdf('13_guia_girada.pdf');a=self.app
  for key,value in [('Paciente',PATIENT),('Número conselho','0012345'),('Conselho','CRM'),('UF conselho','GO'),('CBO','225125')]:self.assertEqual(a.field_vars['guia'][key].get(),value)
  self.assertEqual(len(a.exam_tables['guia'].get_children()),5);self.assertEqual(a.views['guia'].doc['pages'][0]['orientation'],270)

if __name__=='__main__':unittest.main()
