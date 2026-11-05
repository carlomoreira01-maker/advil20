"""Regressões com documentos gerados localmente; nenhum dado clínico real."""
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import pymupdf
from PIL import Image
from engine_v2 import (read_document, parse_document, catalog_load, document_diagnostics,
                       compare_models, ocr_words, CaseStore)
from ocr_runtime import ocr_configuration, safe_failure, tesseract_exe
from test_v2 import TEXT, pdf_text, scan_image

ROOT = Path(__file__).resolve().parents[1]


class LeituraCorrigida(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='caminho com espaço ação ')
        self.base = Path(self.tmp.name)
        self.cat = catalog_load(ROOT/'catalogo_demo.json')

    def tearDown(self):
        self.tmp.cleanup()

    def read_model(self, text):
        p = self.base/'documento fictício.txt'
        p.write_text(text, encoding='utf-8')
        return parse_document(read_document(p), self.cat)

    def test_pdf_sem_dois_pontos_preenche_campos(self):
        p = self.base/'pedido médico.pdf'
        pdf_text(p, 'PEDIDO MEDICO\n'+TEXT.replace(': ', '  '))
        with patch('engine_v2.ocr_words', side_effect=AssertionError('OCR indevido')):
            d = read_document(p)
        m = parse_document(d, self.cat)
        self.assertEqual(d['document_type'], 'pedido')
        self.assertEqual(m['fields']['Paciente']['value'], 'PESSOA SINTETICA ALFA')
        self.assertEqual(m['fields']['Guia']['value'], 'TESTE-001')
        self.assertEqual(m['fields']['Fonte pagadora']['value'], 'CONVENIO FICTICIO')
        self.assertEqual(len(m['exams']), 2)
        self.assertEqual(m['fields']['Paciente']['page'], 1)
        self.assertIn('Pessoa Sintetica', m['fields']['Paciente']['snippet'])
        self.assertEqual(m['fields']['Paciente']['document'], p.name)

    def test_curto_digital_nao_exige_ocr(self):
        p = self.base/'curto.pdf'
        pdf_text(p, 'Paciente: Ana Ficticia')
        with patch('engine_v2.ocr_words', side_effect=AssertionError('OCR indevido')):
            d = read_document(p)
        self.assertEqual(d['pages'][0]['method'], 'Texto digital')

    def test_rotulos_acima_em_colunas(self):
        p = self.base/'colunas.pdf'
        doc = pymupdf.open();page = doc.new_page()
        for x,y,t in [(30,30,'Nome do beneficiario'),(310,30,'Data de nascimento'),
                      (30,50,'Pessoa Ficticia Delta'),(310,50,'01/02/1995'),
                      (30,90,'Exames:'),(30,115,'Hemograma | 1 | DEMO-HEM')]:
            page.insert_text((x,y),t,fontsize=11)
        doc.save(p);doc.close()
        m = parse_document(read_document(p), self.cat)
        self.assertEqual(m['fields']['Paciente']['value'], 'PESSOA FICTICIA DELTA')
        self.assertEqual(m['fields']['Nascimento']['value'], '01/02/1995')

    def test_campo_conflitante_nao_escolhe_um_paciente(self):
        m = self.read_model(TEXT+'Paciente: Pessoa Ficticia Diferente\n')
        self.assertEqual(m['fields']['Paciente']['value'], '')
        self.assertEqual(len(m['fields']['Paciente']['candidates']), 2)
        self.assertTrue(compare_models(m,m,self.cat)['pendencias'])

    def test_status_ausente_bloqueia(self):
        m = self.read_model(TEXT.replace('Status: AUTORIZADO\n',''))
        self.assertTrue(any('Status' in p for p in compare_models(m,m,self.cat)['pendencias']))

    def test_ocr_real_bilingue_caminho_unicode(self):
        p = self.base/'guia autorização.png'
        scan_image('GUIA DE AUTORIZACAO\n'+TEXT).save(p)
        with patch('socket.socket', side_effect=AssertionError('Rede proibida')):
            d = read_document(p)
        m = parse_document(d,self.cat)
        self.assertEqual(d['document_type'],'guia')
        self.assertEqual(m['fields']['Guia']['value'],'TESTE-001')
        self.assertEqual(len(m['exams']),2)
        self.assertEqual(document_diagnostics(d)[0]['languages'],'por+eng')

    def test_portugues_ingles_disponiveis_prefixo_externo_ignorado(self):
        with patch.dict(os.environ, {'TESSDATA_PREFIX': str(self.base/'inexistente')}):
            config = ocr_configuration()
        self.assertTrue({'por','eng'}.issubset(config['languages']))
        for lang in ['por','eng']:
            words = ocr_words(scan_image('Local synthetic example Hemograma'),lang)
            self.assertTrue(any('Hemograma' in w['text'] for w in words))

    def test_executavel_windows_configurado_entre_aspas(self):
        exe = self.base/'Program Files'/'Tesseract-OCR'/'tesseract.exe'
        exe.parent.mkdir(parents=True);exe.touch()
        with patch.dict(os.environ, {'SHIFT_TESSERACT':'"'+str(exe)+'"'}):
            self.assertEqual(tesseract_exe(),str(exe))
        with patch.dict(os.environ, {'SHIFT_TESSERACT': str(self.base/'nao existe.exe')}):
            self.assertIsNone(tesseract_exe())

    def test_idiomas_incompletos_diagnosticados(self):
        with patch.dict(os.environ, {'SHIFT_TESSDATA':str(self.base)}):
            with self.assertRaisesRegex(ValueError,'Idiomas OCR indisponíveis'):
                ocr_configuration()

    def test_saida_tsv_invalida_nao_passa_em_silencio(self):
        result = subprocess.CompletedProcess([],0,stdout='texto sem TSV',stderr='')
        with patch('engine_v2.run_local',return_value=result):
            with self.assertRaisesRegex(ValueError,'TSV'):
                ocr_words(Image.new('RGB',(300,200),'white'))

    def test_timeout_e_erro_com_dados_nao_vazam(self):
        p = self.base/'pessoa-ficticia.png';scan_image().save(p)
        for exc in [subprocess.TimeoutExpired('private-path',1),OSError('Paciente IDENTIFICAVEL')]:
            with patch('engine_v2.ocr_words',side_effect=exc):d=read_document(p)
            diag=document_diagnostics(d)
            self.assertTrue(diag[0]['failed']);self.assertEqual(diag[0]['characters'],0)
            self.assertNotIn('IDENTIFICAVEL',json.dumps(diag))
            self.assertNotIn('private-path',json.dumps(diag))
            self.assertNotIn(p.name,json.dumps(diag))

    def test_sem_ocr_digital_funciona_imagem_falha_visivel(self):
        pdf=self.base/'digital.pdf';pdf_text(pdf)
        image=self.base/'scan.png';scan_image().save(image)
        with patch('engine_v2.tesseract_exe',return_value=None):
            digital=read_document(pdf);scan=read_document(image)
        self.assertFalse(document_diagnostics(digital)[0]['failed'])
        self.assertTrue(document_diagnostics(scan)[0]['failed'])
        self.assertIn('Tesseract ausente',document_diagnostics(scan)[0]['detail'])

    def test_logs_sem_dados_revisoes_locais_preservadas(self):
        docs={}
        for k in ['pedido','guia']:
            p=self.base/(k+'.txt');p.write_text(TEXT+'\n'+k,encoding='utf-8');docs[k]=read_document(p)
        models={k:parse_document(d,self.cat) for k,d in docs.items()}
        s=CaseStore(self.base/'local.sqlite')
        try:
            cid=s.add(docs,models,'NOME DO REVISOR')
            s.save(cid,models,'NOME DO REVISOR','MOTIVO IDENTIFICAVEL',1)
            logs=json.dumps(s.db.execute('SELECT * FROM audit_v2').fetchall())
            for value in ['PESSOA SINTETICA','NOME DO REVISOR','MOTIVO IDENTIFICAVEL','Hemograma']:
                self.assertNotIn(value,logs)
            self.assertEqual(s.db.execute('SELECT count(*) FROM revisoes_v2').fetchone()[0],2)
        finally:s.db.close()

    def test_ocr_v1_preservado_sem_prefixo_global(self):
        from reader import read
        p=self.base/'legado.png';scan_image().save(p)
        text,_=read(p)
        self.assertIn('Hemograma',text)

    def test_auditoria_demo_v1_tambem_sem_dados_identificaveis(self):
        from core import Store
        store=Store(self.base/'demo.sqlite')
        try:
            cid=store.add(TEXT,TEXT,'REVISOR IDENTIFICAVEL')
            store.edit(cid,TEXT+'\n',TEXT,'REVISOR IDENTIFICAVEL','MOTIVO IDENTIFICAVEL')
            store.audit('REVISOR IDENTIFICAVEL',cid,'ERRO',{'mensagem':'PACIENTE IDENTIFICAVEL'})
            logs=json.dumps(store.db.execute('SELECT * FROM audit').fetchall())
            self.assertNotIn('IDENTIFICAVEL',logs)
            self.assertNotIn('Hemograma',logs)
            self.assertEqual(store.db.execute('SELECT count(*) FROM case_revisions').fetchone()[0],2)
        finally:store.db.close()
