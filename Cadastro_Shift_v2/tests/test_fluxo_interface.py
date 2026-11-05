"""Fluxos reais Tkinter + PyMuPDF + Tesseract com entradas sintéticas."""
import os
from pathlib import Path
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from app import App, UNIDENTIFIED
from engine_v2 import read_document
from test_v2 import TEXT, pdf_text, scan_image


@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS')=='1','Requer display e SHIFT_GUI_TESTS=1')
class FluxoCompleto(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='Interface ação ')
        self.base=Path(self.tmp.name);self.root=tk.Tk();self.app=App(self.root,self.base/'dados')
        self.app.actor.set('Revisor Ficticio');self.root.update()

    def tearDown(self):
        self.app.store.db.close();self.root.destroy();self.tmp.cleanup()

    def import_and_wait(self,pairs):
        self.app.import_pairs(pairs)
        deadline=time.monotonic()+45
        while self.app.busy and time.monotonic()<deadline:
            self.root.update();time.sleep(.01)
        self.assertFalse(self.app.busy,'Leitura não concluiu')
        self.root.update()

    def pair(self,ext='png'):
        p=self.base/'pedido médico.pdf';g=self.base/('guia autorização.'+ext)
        pdf_text(p,'PEDIDO MEDICO\n'+TEXT.replace(': ','  '))
        if ext=='pdf':pdf_text(g,'GUIA DE AUTORIZACAO\n'+TEXT)
        else:scan_image('GUIA DE AUTORIZACAO\n'+TEXT).save(g)
        return p,g

    def test_importacao_dialogos_ocr_preenche_campos_visiveis(self):
        p,g=self.pair()
        with patch('app.filedialog.askopenfilename',side_effect=[str(p),str(g)]), \
             patch('app.read_document',wraps=read_document) as read, \
             patch('socket.socket',side_effect=AssertionError('Rede proibida')), \
             patch('app.messagebox.showwarning') as warning:
            self.app.import_pair()
            deadline=time.monotonic()+45
            while self.app.busy and time.monotonic()<deadline:self.root.update();time.sleep(.01)
            self.assertFalse(self.app.busy);self.assertEqual(read.call_count,2);warning.assert_not_called()
        for kind in ['pedido','guia']:
            fields=self.app.field_vars[kind]
            self.assertEqual(fields['Paciente'].get(),'PESSOA SINTETICA ALFA')
            self.assertEqual(fields['Fonte pagadora'].get(),'CONVENIO FICTICIO')
            self.assertEqual(fields['Guia'].get(),'TESTE-001')
            self.assertEqual(len(self.app.exam_tables[kind].get_children()),2)
        rows=[self.app.diagnostic_table.item(i,'values') for i in self.app.diagnostic_table.get_children()]
        self.assertEqual(len(rows),2);self.assertTrue(all(int(r[4])>100 for r in rows))
        self.assertIn('Texto digital',rows[0][3]);self.assertIn('OCR',rows[1][3])
        self.assertEqual(self.app.tabs.select(),str(self.app.review_container))
        self.assertEqual(self.app.store.get(self.app.cid)[2],'CONFERIR')
        self.app.locate_field('pedido','Paciente')
        self.assertIn('Pessoa Sintetica',self.app.origin_text.get('1.0','end'))

    def test_inversao_identificada_e_corrigida_pelos_titulos(self):
        p,g=self.pair('pdf');self.import_and_wait([(g,p)])
        self.assertEqual(self.app.models['pedido']['document_type'],'pedido')
        self.assertEqual(self.app.models['guia']['document_type'],'guia')

    def test_reabrir_caso_restaura_campos_e_diagnostico(self):
        p,g=self.pair('pdf');self.import_and_wait([(p,g)])
        cid=self.app.cid
        self.app.diagnostic_table.delete(*self.app.diagnostic_table.get_children())
        self.app.open_case(cid)
        self.assertEqual(len(self.app.diagnostic_table.get_children()),2)
        self.assertEqual(self.app.field_vars['pedido']['Paciente'].get(),'PESSOA SINTETICA ALFA')

    def test_ocr_ausente_erro_no_painel_e_sem_aprovacao(self):
        p,g=self.pair()
        with patch('engine_v2.tesseract_exe',return_value=None):self.import_and_wait([(p,g)])
        self.assertEqual(self.app.field_vars['guia']['Paciente'].get(),UNIDENTIFIED)
        self.assertEqual(self.app.collect()['guia']['fields']['Paciente']['value'],'')
        self.assertTrue(self.app.analysis['pendencias'])
        rows=[self.app.diagnostic_table.item(i,'values') for i in self.app.diagnostic_table.get_children()]
        self.assertIn('Tesseract ausente',rows[1][5])
        self.app.confirm.set(True)
        with self.assertRaises(ValueError):self.app.prepare()

    def test_erro_inesperado_worker_libera_estado_sem_dados_nos_logs(self):
        p,g=self.pair('pdf')
        with patch('app.read_document',side_effect=RuntimeError('Paciente IDENTIFICAVEL')), \
             patch('app.messagebox.showwarning') as warning:
            self.import_and_wait([(p,g)])
        self.assertEqual(len(self.app.cases.get_children()),0)
        self.assertTrue(warning.called)
        self.assertNotIn('IDENTIFICAVEL',str(warning.call_args_list))
        self.assertFalse(self.app.progress.winfo_exists())
        self.import_and_wait([(p,g)])
        self.assertEqual(len(self.app.cases.get_children()),1)

    def test_quantidade_codigo_divergentes_visiveis_bloqueiam(self):
        p,g=self.pair('pdf')
        pdf_text(g.with_name('divergente.pdf'),'GUIA DE AUTORIZACAO\n'+TEXT.replace('Glicose | 2','Glicose | 4').replace('DEMO-HEM','DEMO-INCERTO'))
        self.import_and_wait([(p,g.with_name('divergente.pdf'))])
        errors=' '.join(self.app.analysis['pendencias'])
        self.assertIn('Quantidade divergente',errors);self.assertIn('Código',errors)
        with self.assertRaises(ValueError):self.app.prepare()
