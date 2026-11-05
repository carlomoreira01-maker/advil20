"""Fluxo de interface com dados sintéticos; ativar SHIFT_GUI_TESTS=1."""
import copy,json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
from app import App,ROOT
from engine_v2 import read_document,parse_document

@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Teste visual opcional: SHIFT_GUI_TESTS=1')
class Interface(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=tk.Tk();self.app=App(self.root,Path(self.tmp.name));self.app.actor.set('Revisor sintetico');self.root.update()
    def tearDown(self):
        self.app.store.db.close();self.root.destroy();self.tmp.cleanup()
    def test_import_review_prepare_and_export(self):
        app=self.app
        with patch('app.messagebox.showwarning') as warning:
            app.import_pairs([(ROOT/'exemplos_v2/01_pedido_digital.pdf',ROOT/'exemplos_v2/01_guia_escaneada.pdf')])
            deadline=time.monotonic()+30
            while app.busy and time.monotonic()<deadline:self.root.update();time.sleep(.02)
            self.assertFalse(app.busy);warning.assert_not_called()
        self.assertEqual(len(app.cases.get_children()),1);self.assertEqual(len(app.models['pedido']['exams']),2)
        app.tabs.select(app.review_container);self.root.update()
        self.assertEqual(len(app.compare_table.get_children()),2)
        # Campos de catálogo e campos do formulário têm conferência explícita.
        for k in ['pedido','guia']:
            for check in app.field_checks[k].values():check.set(True)
            for e in app.models[k]['exams']:e['reviewed']=True
            for issue in app.models[k]['issues']:issue.update(reviewed=True,reason='Conferido no original sintético')
            app.page_checks[k].set(True);app.check_pages(k)
        with patch('app.simpledialog.askstring',return_value='Conferência sintética completa'):app.save()
        app.confirm.set(True);app.prepare();self.assertEqual(app.store.get(app.cid)[2],'PREPARADO')
        out=Path(self.tmp.name)/'pre_cadastro.json'
        with patch('app.filedialog.asksaveasfilename',return_value=str(out)):app.export()
        self.assertIsNone(json.loads(out.read_text(encoding='utf-8'))['os_real'])
        if os.getenv('SHIFT_QA_SCREENSHOT'):
            from PIL import ImageGrab
            app.tabs.select(app.review_container);self.root.update();ImageGrab.grab(xdisplay=os.getenv('DISPLAY')).save(os.getenv('SHIFT_QA_SCREENSHOT'))
    def test_paging_zoom_source_and_field_invalidation(self):
        app=self.app;docs={}
        for k,p in [('pedido','03_pedido_multipagina.pdf'),('guia','01_guia_escaneada.pdf')]:
            d=read_document(ROOT/'exemplos_v2'/p);d['local_path']=str(ROOT/'exemplos_v2'/p);docs[k]=d
        models={k:parse_document(d,app.catalog) for k,d in docs.items()};cid=app.store.add(docs,models,'Teste');app.open_case(cid);self.root.update()
        v=app.views['pedido'];self.assertEqual(v.seen,{1})
        app.page_checks['pedido'].set(True)
        with patch('app.messagebox.showinfo'):app.check_pages('pedido')
        self.assertFalse(app.page_checks['pedido'].get());v.move(1);v.scale(1.25);self.assertEqual(v.seen,{1,2});self.assertEqual(v.zoom,1.25)
        app.field_checks['pedido']['Paciente'].set(True);app.confirm.set(True);app.field_vars['pedido']['Paciente'].set('Outra pessoa sintética')
        self.assertFalse(app.field_checks['pedido']['Paciente'].get());self.assertFalse(app.confirm.get())
        app.locate_field('pedido','Medico');self.assertEqual(v.index,0)
        app.catalog_window();self.root.update()
        for w in self.root.winfo_children():
            if isinstance(w,tk.Toplevel):w.destroy()
