import copy,os,tempfile,time,tkinter as tk,unittest
from pathlib import Path
from unittest.mock import patch
from app import App
from engine_v2 import read_document,parse_document
from gerar_exemplos_tiss import make_guide,make_order,catalog,VALUES
from tiss import empty_field

@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer display e SHIFT_GUI_TESTS=1')
class RegionGUI243(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.root=tk.Tk();self.app=App(self.root,self.dir/'data');self.app.catalog=catalog();self.app.actor.set('REVISOR FICTICIO')
  p=self.dir/'pedido.pdf';g=self.dir/'guia.pdf';make_order(p);make_guide(g)
  self.app.import_pairs([(p,g)]);deadline=time.monotonic()+60
  while self.app.busy and time.monotonic()<deadline:self.root.update();time.sleep(.01)
  self.assertFalse(self.app.busy);self.root.update()
 def tearDown(self):self.app.store.db.close();self.root.destroy();self.tmp.cleanup()
 def test_candidatos_exigem_escolha_humana_e_nao_aprovam_cadastro(self):
  a=self.app;first=copy.deepcopy(a.models['guia']['fields']['Guia prestador']);second=copy.deepcopy(first);second['value']='00000999'
  a.models['guia']['fields']['Guia prestador']={**empty_field(),'candidates':[first,second]}
  a.loading=True;a.field_vars['guia']['Guia prestador'].set('Não identificado');a.loading=False
  a.locate_field('guia','Guia prestador');editor=a.candidate_editor;self.assertEqual(len(editor['table'].get_children()),2)
  editor['show']();self.assertEqual(a.views['guia'].index,0);editor['choose']()
  self.assertEqual(a.field_vars['guia']['Guia prestador'].get(),VALUES[2]);self.assertFalse(a.field_checks['guia']['Guia prestador'].get());self.assertFalse(a.confirm.get());self.assertEqual(str(a.prepare_button['state']),'disabled')
 def test_visualizacao_gira_sem_mudar_arquivo_e_preserva_origem(self):
  a=self.app;view=a.views['guia'];raw=(self.dir/'guia.pdf').read_bytes()
  view.doc['pages'][0]['orientation']=90;view.locate(1,a.models['guia']['fields']['Paciente']['box']);self.root.update()
  self.assertIn('Rotação 90',view.info.get());self.assertEqual(view.box,a.models['guia']['fields']['Paciente']['box'])
  view.rotate();self.root.update();self.assertIn('Rotação 180',view.info.get());self.assertEqual((self.dir/'guia.pdf').read_bytes(),raw)
 def test_codigo_numerico_nao_mapeado_nao_pode_ser_usado_como_conselho(self):
  a=self.app;a.models['guia']['fields']['Conselho']={**empty_field(),'candidates':[{'value':'06','page':1,'box':[10,10,20,20],'origin_type':'codigo_impresso_nao_mapeado'}]}
  a.loading=True;a.field_vars['guia']['Conselho'].set('Não identificado');a.loading=False
  a.locate_field('guia','Conselho');a.candidate_editor['show']()
  with self.assertRaisesRegex(ValueError,'correspondência homologada'):a.candidate_editor['choose']()
  self.assertEqual(a.field_vars['guia']['Conselho'].get(),'Não identificado')

if __name__=='__main__':unittest.main()
