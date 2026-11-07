"""Regressões de casos relatados pelo usuário — apenas dados fictícios."""
import tempfile
import unittest
from pathlib import Path
import pymupdf
from engine_v2 import parse_document, read_document
from scan_import import read_scan, build_cases


class Regressao241(unittest.TestCase):
    def test_nome_composto_na_mesma_linha_com_espaco_grande(self):
        # A primeira palavra isolada não pode ser descartada por conter apenas
        # um nome, enquanto o sobrenome fica em outro agrupamento espacial.
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / 'guia_ficticia.pdf'
            pdf = pymupdf.open()
            page = pdf.new_page(width=1000, height=350)
            for x, y, content in [
                (30, 40, '10 - Nome do beneficiario'),
                (30, 65, 'PRIMEIRO'),
                (220, 65, 'SEGUNDO TERCEIRO'),
                (30, 120, '15 - Nome do profissional solicitante'),
                (30, 145, 'MEDICO FICTICIO'),
            ]:
                page.insert_text((x, y), content, fontsize=12)
            pdf.save(file)
            pdf.close()
            model = parse_document(read_document(file), [])
            self.assertEqual(model['fields']['Paciente']['value'], 'PRIMEIRO SEGUNDO TERCEIRO')

    def test_pagina_incerta_nao_se_torna_pedido_automaticamente(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / 'folha_sem_tipo.pdf'
            pdf = pymupdf.open()
            page = pdf.new_page()
            page.insert_text((40, 45), 'Documento ficticio sem tipo confirmado', fontsize=12)
            pdf.save(file)
            pdf.close()
            batch = read_scan([file], Path(d) / 'dados', [])
            self.assertEqual(batch['pages'][0]['kind'], 'incerto')
            _, documents, models = build_cases(batch, [])[0]
            self.assertEqual(len(documents['pedido']['pages']), 0)
            self.assertEqual(len(documents['guia']['pages']), 0)
            self.assertEqual(len(documents['apoio']['pages']), 1)
            self.assertTrue(models['pedido']['classification_pending'])
            self.assertTrue(models['guia']['classification_pending'])


if __name__ == '__main__':
    unittest.main()
