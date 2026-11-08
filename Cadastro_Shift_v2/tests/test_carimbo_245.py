"""Contraprovas de carimbo, classificação, lista sem catálogo e reprocessamento."""
import copy,tempfile,unittest
from pathlib import Path
from gerar_exemplos_carimbo import main
from gerar_exemplos_tiss import catalog,NAMES
from engine_v2 import read_document,parse_document
from scan_import import read_scan,build_cases,merge_reprocessed

class Carimbo245(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.tmp=tempfile.TemporaryDirectory();cls.files=main(cls.tmp.name)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):self.data=tempfile.TemporaryDirectory();self.cat=catalog()
 def tearDown(self):self.data.cleanup()
 def batch(self,file):return read_scan([self.files/file],self.data.name,self.cat,mode='single')
 def test_pedido_sem_titulo_com_carimbo_e_exames_sem_catalogo(self):
  b=self.batch('01_pedido_carimbo_e_guia.pdf');self.assertEqual([p['kind'] for p in b['pages']],['pedido','guia'])
  _,docs,models=build_cases(b,[])[0];m=models['pedido'];self.assertEqual(len(m['exams']),5)
  for key,v in [('Paciente','PESSOA FICTICIA ALFA'),('Medico','DRA EXEMPLO SINTETICA'),('Conselho','CRM'),('Número conselho','0012345'),('UF conselho','GO')]:self.assertEqual(m['fields'][key]['value'],v)
  self.assertEqual(m['fields']['Medico']['source_document']['page'],1);self.assertEqual(m['fields']['Medico']['origin_type'],'nome_no_carimbo_impresso');self.assertEqual(m['fields']['Número conselho']['origin_type'],'identificacao_livre_ou_carimbo')
  self.assertEqual([e['descricao'] for e in m['exams']],NAMES);self.assertTrue(all(e['codigo']=='' and e['quantidade']=='1' for e in m['exams']))
 def test_guia_com_carimbo_continua_guia_e_ordem_invertida(self):
  b=self.batch('02_guia_antes_pedido.pdf');self.assertEqual([p['kind'] for p in b['pages']],['guia','pedido']);self.assertEqual(len(b['pages'][0]['model']['exams']),5)
 def test_carimbo_em_consentimento_receita_e_sem_lista_nao_basta(self):
  for file in ['consentimento_carimbo.pdf','receita_carimbo.pdf','pedido_sem_carimbo.pdf']:
   with self.subTest(file=file):self.assertEqual(self.batch(file)['pages'][0]['kind'],'incerto')
 def test_quantidade_ausente_nao_e_inventada(self):
  m=parse_document(read_document(self.files/'pedido_sem_quantidades.pdf'),[]);self.assertEqual(len(m['exams']),5);self.assertTrue(all(e['quantidade']=='' for e in m['exams']))
 def test_prefixo_dra_nao_cria_divergencia_mas_nome_diferente_bloqueia(self):
  from engine_v2 import compare_models
  from tests.test_mapping_sim import profile
  _,_,models=build_cases(self.batch('01_pedido_carimbo_e_guia.pdf'),self.cat)[0]
  p,g=models['pedido'],models['guia'];g['payer_profile']=profile()
  g['fields']['Medico']['value']='EXEMPLO SINTETICA'
  self.assertNotIn('Solicitante divergente',' '.join(compare_models(p,g,self.cat)['pendencias']))
  g['fields']['Medico']['value']='OUTRA MEDICA FICTICIA'
  self.assertIn('Solicitante divergente',' '.join(compare_models(p,g,self.cat)['pendencias']))
 def test_reprocessamento_corrige_classificacao_antiga_automatica(self):
  current=self.batch('01_pedido_carimbo_e_guia.pdf');old=copy.deepcopy(current);old['pages'][0]['kind']='guia';old['pages'][0].pop('classification_origin',None)
  new=self.batch('01_pedido_carimbo_e_guia.pdf');merge_reprocessed(new,old)
  self.assertEqual(new['pages'][0]['kind'],'pedido');self.assertEqual(new['id'],old['id']);self.assertEqual(new['sources'][new['pages'][0]['source']]['file'],'01_pedido_carimbo_e_guia.pdf');self.assertFalse(new['group_reviews'])
 def test_reprocessamento_preserva_correcao_humana_explicita(self):
  old=self.batch('01_pedido_carimbo_e_guia.pdf');old['pages'][0].update(kind='outro',classification_origin='manual',reviewed=True,reason='Finalidade conferida no teste fictício')
  new=self.batch('01_pedido_carimbo_e_guia.pdf');merge_reprocessed(new,old);self.assertEqual(new['pages'][0]['kind'],'outro');self.assertEqual(new['pages'][0]['classification_origin'],'manual')
 def test_quatro_paginas_uma_ficha_sem_confundir_continuacao(self):
  b=self.batch('03_quatro_paginas.pdf');self.assertEqual([p['kind'] for p in b['pages']],['pedido','guia','continuação de guia','outro']);cases=build_cases(b,self.cat);self.assertEqual(len(cases),1);self.assertEqual(sum(len(d['pages']) for d in cases[0][1].values()),4)
 def test_ocr_real_pedido_girado_carimbo_e_lista(self):
  b=self.batch('05_pedido_girado.pdf');self.assertEqual(b['pages'][0]['kind'],'pedido');m=b['pages'][0]['model']
  self.assertEqual(m['fields']['Medico']['value'],'DRA EXEMPLO SINTETICA');self.assertEqual(m['fields']['Número conselho']['value'],'0012345');self.assertEqual(m['fields']['UF conselho']['value'],'GO');self.assertEqual(len(m['exams']),5)

if __name__=='__main__':unittest.main()
