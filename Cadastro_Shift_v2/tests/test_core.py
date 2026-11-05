import copy
from datetime import date
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core import Store, catalog_load, compare, digest
from exporter import export_order
from reader import read

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 5)


class Workflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Store(Path(self.tmp.name) / 'test.sqlite3')
        self.cat = catalog_load(ROOT / 'catalogo_demo.json')
        self.p = (ROOT/'exemplos/01_pedido.txt').read_text(encoding='utf-8')
        self.g = (ROOT/'exemplos/01_guia.txt').read_text(encoding='utf-8')

    def tearDown(self):
        self.db.db.close()
        self.tmp.cleanup()

    def add(self, p=None, g=None):
        return self.db.add(p or self.p, g or self.g, 'Teste')

    def run_order(self, cid, reviewed=True, cat=None, rev=1):
        c = cat or self.cat
        return self.db.simulate(cid,c,'Teste',reviewed,rev,digest(c),TODAY)

    def test_happy_path_and_labels(self):
        order = self.run_order(self.add())
        self.assertIsNone(order['os_real'])
        self.assertEqual(len(order['exames']),2)
        paths=export_order(order,Path(self.tmp.name))
        self.assertIn('DEMONSTRAÇÃO',paths[1].read_text(encoding='utf-8'))
        self.assertEqual(json.loads(paths[0].read_text(encoding='utf-8'))['modo'],'DEMONSTRACAO')

    def test_review_required(self):
        with self.assertRaises(ValueError): self.run_order(self.add(),False)
        self.assertEqual(self.db.db.execute('SELECT count(*) FROM orders').fetchone()[0],0)

    def test_import_duplicate(self):
        self.add()
        with self.assertRaises(ValueError): self.add()

    def test_business_duplicate_different_document_bytes(self):
        self.run_order(self.add())
        cid=self.add(self.p+'\n',self.g+'\n')
        with self.assertRaisesRegex(ValueError,'duplicidade'): self.run_order(cid)
        self.assertEqual(self.db.get(cid)[2],'PENDENTE')

    def test_identity_and_optional_birth(self):
        for g in [self.g.replace('Aurora','Outra'),self.g.replace('15/05/1995','16/05/1995'),self.g.replace('15/05/1995','')]:
            self.assertTrue(compare(self.p,g,self.cat,TODAY)['pendencias'])
        p=self.p.replace('Nascimento: 15/05/1995\n','');g=self.g.replace('Nascimento: 15/05/1995\n','')
        self.assertFalse(compare(p,g,self.cat,TODAY)['pendencias'])

    def test_authorization_checks(self):
        for g in [self.g.replace('AUTORIZADO','NEGADO'),self.g.replace('31/12/2099','01/01/2000'),self.g.replace('Validade: 31/12/2099','Validade:'),self.g.replace('Glicose | 1','Glicose | 2'),self.g.replace('Glicose | 1 | DEMO-GLI','')]:
            self.assertTrue(compare(self.p,g,self.cat,TODAY)['pendencias'])

    def test_unknown_code_negation_and_duplicate(self):
        for p in [self.p+'Exame secreto | 1 | 123\n',self.p.replace('DEMO-HEM','DEMO-ERRADO'),self.p.replace('Hemograma |','Nao fazer Hemograma |'),self.p+'Hemograma | 1 | DEMO-HEM\n',self.p.replace(' | 1 |',' | -1 |')]:
            self.assertTrue(compare(p,self.g,self.cat,TODAY)['pendencias'])

    def test_ambiguous_catalog(self):
        cat=self.cat+[dict(self.cat[0],codigo_shift='DEMO-OUTRO')]
        self.assertTrue(compare(self.p,self.g,cat,TODAY)['pendencias'])

    def test_missing_marker_and_prose(self):
        for p in [self.p.replace('DEMONSTRAÇÃO',''), self.p+'Observacao nao estruturada']:
            self.assertTrue(compare(p,self.g,self.cat,TODAY)['pendencias'])

    def test_stale_revision_and_audit(self):
        cid=self.add()
        self.db.edit(cid,self.p+'\n',self.g,'Teste','Correção sintética')
        with self.assertRaises(ValueError): self.run_order(cid)
        self.run_order(cid,rev=2)
        audit=self.db.db.execute('SELECT detail FROM audit WHERE action="CORRECAO"').fetchone()[0]
        self.assertIn('antes',audit);self.assertIn('depois',audit)
        with self.assertRaises(ValueError): self.db.edit(cid,self.p,self.g,'Teste','Tentar editar')

    def test_catalog_changed(self):
        cid=self.add()
        changed=copy.deepcopy(self.cat);changed[0]['material']='Alterado'
        with self.assertRaises(ValueError): self.db.simulate(cid,changed,'Teste',True,1,digest(self.cat),TODAY)

    def test_repeat_simulate(self):
        cid=self.add();self.run_order(cid)
        with self.assertRaises(ValueError): self.run_order(cid)

    def test_catalog_real_code_rejected(self):
        p=Path(self.tmp.name)/'catalog.json'
        cat=copy.deepcopy(self.cat);cat[0]['tuss']='12345678'
        p.write_text(json.dumps(cat),encoding='utf-8')
        with self.assertRaises(ValueError): catalog_load(p)

    def test_pdf_and_text(self):
        for ext in ['pdf','txt']:
            text,meta=read(ROOT/f'exemplos/01_pedido.{ext}')
            self.assertIn('DEMO-HEM',text)
            self.assertEqual(len(meta['sha256']),64)

    def test_mixed_pdf_ocr_per_page(self):
        with patch('reader.ocr',return_value='TEXTO OCR PAGINA 2') as mock:
            text,_=read(ROOT/'exemplos/pdf_misto_teste.pdf')
            self.assertIn('DEMO-HEM',text)
            self.assertIn('TEXTO OCR PAGINA 2',text)
            mock.assert_called_once()

    def test_html_escaped(self):
        order=self.run_order(self.add());order['paciente']['Paciente']='<script>alert(1)</script>'
        paths=export_order(order,Path(self.tmp.name))
        self.assertNotIn('<script>',paths[1].read_text(encoding='utf-8'))

    def test_data_survives_restart(self):
        cid=self.add();self.run_order(cid)
        second=Store(Path(self.tmp.name)/'test.sqlite3')
        self.assertEqual(second.get(cid)[2],'SIMULADO')
        self.assertIsNotNone(second.order(cid));second.db.close()

    def test_import_and_simulation_offline(self):
        with patch('socket.socket',side_effect=AssertionError('Rede proibida')):
            self.run_order(self.add())


if __name__=='__main__': unittest.main()
