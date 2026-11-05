"""Seleção manual, persistência e leitura ponta a ponta na interface real."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from app import App
from ocr_runtime import save_settings
from test_v2 import TEXT, scan_image, pdf_text


@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer display e SHIFT_GUI_TESTS=1')
class ConfiguracaoNaInterface(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='Interface OCR ação ')
        self.base=Path(self.tmp.name);self.root=tk.Tk();self.app=App(self.root,self.base/'dados')
        self.real=shutil.which('tesseract')
        self.exe=self.base/'Downloads'/'TESSERACT'/'tesseract.exe'
        self.exe.parent.mkdir(parents=True);shutil.copy2(self.real,self.exe)
        self.app.actor.set('Revisor ficticio')

    def tearDown(self):
        self.app.store.db.close();self.root.destroy();self.tmp.cleanup()

    def wait(self,predicate):
        end=time.monotonic()+40
        while not predicate() and time.monotonic()<end:self.root.update();time.sleep(.01)
        self.assertTrue(predicate(),'Operação não concluiu');self.root.update()

    def select_and_test(self,path):
        self.app.ocr_settings_window();dialog=self.app.ocr_dialog
        with patch('app.filedialog.askopenfilename',return_value=str(path)):
            dialog['choose']()
        self.assertEqual(dialog['path'].get(),str(path))
        dialog['test']();self.wait(lambda:self.app.ocr_health is not None)
        return dialog

    def test_seleciona_salva_reabre_e_importa_scan(self):
        self.wait(lambda:self.app.ocr_health is not None)
        dialog=self.select_and_test(self.exe)
        self.assertTrue(self.app.ocr_health['ok'])
        self.assertIn('OCR funcionando',self.app.ocr_status.get())
        self.assertIn('Caminho salvo',dialog['result'].get())
        self.assertEqual(json.loads(self.app.ocr_settings_path.read_text())['tesseract_path'],str(self.exe))
        dialog['window'].destroy()
        # A mesma configuração é lida na próxima abertura do diálogo.
        self.app.ocr_settings_window()
        self.assertEqual(self.app.ocr_dialog['path'].get(),str(self.exe))
        self.app.ocr_dialog['window'].destroy()
        p=self.base/'pedido.pdf';g=self.base/'guia.png'
        pdf_text(p,'PEDIDO MEDICO\n'+TEXT);scan_image('GUIA DE AUTORIZACAO\n'+TEXT).save(g)
        with patch('app.messagebox.showwarning') as warnings,patch('socket.socket',side_effect=AssertionError('Rede proibida')):
            self.app.import_pairs([(p,g)]);self.wait(lambda:not self.app.busy)
            warnings.assert_not_called()
        self.assertEqual(self.app.field_vars['guia']['Paciente'].get(),'PESSOA SINTETICA ALFA')
        self.assertEqual(self.app.field_vars['guia']['Guia'].get(),'TESTE-001')
        self.assertEqual(len(self.app.exam_tables['guia'].get_children()),2)
        self.assertIn('OCR',self.app.diagnostic_table.item(self.app.diagnostic_table.get_children()[1],'values')[3])
        if os.getenv('SHIFT_OCR_SCREENSHOT'):
            from PIL import ImageGrab
            self.app.ocr_settings_window();self.root.update()
            ImageGrab.grab(xdisplay=os.getenv('DISPLAY')).save(os.getenv('SHIFT_OCR_SCREENSHOT'))

    def test_falha_nao_salva_nem_fica_verde(self):
        self.wait(lambda:self.app.ocr_health is not None)
        save_settings(self.real,self.app.ocr_settings_path);original=self.app.ocr_settings_path.read_bytes()
        wrong=self.base/'errado.exe';wrong.write_text('nao executavel')
        dialog=self.select_and_test(wrong)
        self.assertFalse(self.app.ocr_health['ok'])
        self.assertNotIn('funcionando',self.app.ocr_status.get())
        self.assertEqual(self.app.ocr_settings_path.read_bytes(),original)
        self.assertNotIn('Caminho salvo',dialog['result'].get())
        self.assertEqual(str(dialog['button'].cget('state')),'normal')

    def test_reiniciar_programa_reutiliza_caminho_salvo(self):
        self.wait(lambda:self.app.ocr_health is not None)
        self.select_and_test(self.exe)
        self.app.store.db.close();self.root.destroy()
        self.root=tk.Tk();self.app=App(self.root,self.base/'dados')
        self.wait(lambda:self.app.ocr_health is not None)
        self.assertTrue(self.app.ocr_health['ok'])
        self.assertEqual(self.app.ocr_health['exe'],str(self.exe))
        self.app.ocr_settings_window()
        self.assertEqual(self.app.ocr_dialog['path'].get(),str(self.exe))

    def test_ausente_mostra_estado_visivel_e_nao_impede_abrir_configuracoes(self):
        self.wait(lambda:self.app.ocr_health is not None)
        with patch('ocr_runtime.tesseract_exe',return_value=None):
            self.app.check_ocr();self.wait(lambda:self.app.ocr_health is not None)
        self.assertFalse(self.app.ocr_health['ok'])
        self.assertIn('Tesseract ausente',self.app.ocr_status.get())
        self.app.ocr_settings_window();self.assertTrue(self.app.ocr_dialog['window'].winfo_exists())

    def test_selecao_cancelada_preserva_caminho(self):
        self.app.ocr_settings_window();dialog=self.app.ocr_dialog;before=dialog['path'].get()
        with patch('app.filedialog.askopenfilename',return_value=''):dialog['choose']()
        self.assertEqual(dialog['path'].get(),before)

    def test_localizar_automaticamente_preenche_downloads(self):
        self.app.ocr_settings_window();dialog=self.app.ocr_dialog
        with patch('ocr_runtime.shutil.which',return_value=None), \
             patch.dict(os.environ,{'USERPROFILE':str(self.base),'SHIFT_TESSERACT':''}):
            dialog['auto']()
        self.assertEqual(dialog['path'].get(),str(self.exe))
        self.assertFalse(self.app.ocr_settings_path.exists())

    def test_reanalisa_atendimento_com_ocr_antes_ausente_sem_duplicar(self):
        self.wait(lambda:self.app.ocr_health is not None)
        p=self.base/'pedido.pdf';g=self.base/'guia.png'
        pdf_text(p,'PEDIDO MEDICO\n'+TEXT);scan_image('GUIA DE AUTORIZACAO\n'+TEXT).save(g)
        with patch('engine_v2.tesseract_exe',return_value=None):
            self.app.import_pairs([(p,g)]);self.wait(lambda:not self.app.busy)
        cid=self.app.cid
        self.assertEqual(self.app.models['guia']['fields']['Paciente']['value'],'')
        save_settings(self.exe,self.app.ocr_settings_path)
        with patch('app.messagebox.askyesno',return_value=True):
            self.app.reanalyze_case();self.wait(lambda:not self.app.busy)
        self.assertEqual(self.app.cid,cid);self.assertEqual(len(self.app.cases.get_children()),1)
        self.assertEqual(self.app.rev,2)
        self.assertEqual(self.app.field_vars['guia']['Paciente'].get(),'PESSOA SINTETICA ALFA')
        self.assertEqual(len(self.app.exam_tables['guia'].get_children()),2)
        original=json.loads(self.app.store.db.execute('SELECT original FROM casos_v2 WHERE id=?',(cid,)).fetchone()[0])
        self.assertEqual(original['models']['guia']['fields']['Paciente']['value'],'')
        self.assertEqual(self.app.store.db.execute('SELECT count(*) FROM revisoes_v2 WHERE caso=?',(cid,)).fetchone()[0],2)

    def test_reanalise_cancelada_preserva_atendimento(self):
        self.wait(lambda:self.app.ocr_health is not None)
        p=self.base/'p.pdf';g=self.base/'g.pdf'
        pdf_text(p,'PEDIDO MEDICO\n'+TEXT);pdf_text(g,'GUIA DE AUTORIZACAO\n'+TEXT)
        self.app.import_pairs([(p,g)]);self.wait(lambda:not self.app.busy)
        original=self.app.store.get(self.app.cid)
        with patch('app.messagebox.askyesno',return_value=False):self.app.reanalyze_case()
        self.assertFalse(self.app.busy);self.assertEqual(self.app.store.get(self.app.cid),original)
