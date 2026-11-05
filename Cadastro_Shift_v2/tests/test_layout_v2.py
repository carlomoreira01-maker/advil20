import tempfile,unittest
from pathlib import Path
import pymupdf
from engine_v2 import read_document,parse_document,catalog_load
ROOT=Path(__file__).resolve().parents[1]
class Layout(unittest.TestCase):
    def test_parallel_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'parallel.pdf';d=pymupdf.open();p=d.new_page(width=1000,height=700)
            p.insert_text((30,30),'Paciente: Pessoa Sintetica Alfa\nNascimento: 01/02/1995',fontsize=11)
            for offset in [0,500]:
                for x,t in [(30,'Codigo'),(150,'Descricao'),(410,'Qtd')]:p.insert_text((x+offset,100),t,fontsize=11)
            for x,t in [(30,'DEMO-HEM'),(150,'Hemograma'),(410,'2'),(530,'DEMO-GLI'),(650,'Glicose'),(910,'3')]:p.insert_text((x,140),t,fontsize=11)
            d.save(path);d.close();m=parse_document(read_document(path),catalog_load(ROOT/'catalogo_demo.json'))
            self.assertEqual([(e['codigo'],e['descricao'],e['quantidade']) for e in m['exams']],[('DEMO-HEM','Hemograma','2'),('DEMO-GLI','Glicose','3')])
    def test_label_above_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'labels.txt';path.write_text('8 - Nome do beneficiario\nPessoa Sintetica Alfa\nData de nascimento\n01/02/1995\nExames:\nHemograma | 1 | DEMO-HEM',encoding='utf-8')
            m=parse_document(read_document(path),catalog_load(ROOT/'catalogo_demo.json'));self.assertEqual(m['fields']['Paciente']['value'],'PESSOA SINTETICA ALFA');self.assertEqual(m['fields']['Nascimento']['value'],'01/02/1995')
    def test_wrapped_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'wrap.pdf';d=pymupdf.open();p=d.new_page()
            p.insert_text((30,30),'Paciente: Pessoa Sintetica Alfa\nNascimento: 01/02/1995',fontsize=11)
            for x,t in [(30,'Codigo'),(160,'Descricao'),(430,'Qtd')]:p.insert_text((x,100),t,fontsize=11)
            for x,t in [(30,'DEMO-HEM'),(160,'Hemograma'),(430,'2')]:p.insert_text((x,140),t,fontsize=11)
            p.insert_text((160,155),'completo',fontsize=11);d.save(path);d.close();m=parse_document(read_document(path),catalog_load(ROOT/'catalogo_demo.json'))
            self.assertEqual(len(m['exams']),1);self.assertEqual(m['exams'][0]['descricao'],'Hemograma completo');self.assertEqual(m['exams'][0]['quantidade'],'2')
