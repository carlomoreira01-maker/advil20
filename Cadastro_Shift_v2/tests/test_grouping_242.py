"""Contrato verificável para agrupamento provisório, conflitos e origens físicas."""
import copy,json,tempfile,unittest
from pathlib import Path
from engine_v2 import CaseStore,review_errors,compare_models,parse_document,read_document
from scan_import import read_scan,build_cases,save_batch,load_batch,confirm_group,apply_identity_edits,compatible
from gerar_exemplos_2_4_2 import main
from gerar_exemplos_tiss import catalog,VALUES
from tiss import SCHEMA

class Grouping242(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.fixture=tempfile.TemporaryDirectory();cls.files=main(cls.fixture.name)
 @classmethod
 def tearDownClass(cls):cls.fixture.cleanup()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name);self.cat=catalog();self.store=CaseStore(self.data/'db.sqlite3')
 def tearDown(self):self.store.db.close();self.tmp.cleanup()
 def read(self,name='01_um_atendimento_quatro_paginas.pdf',mode='single'):
  return read_scan([self.files/name],self.data,self.cat,mode=mode)
 def acknowledge(self,b):
  for i in b['pages']:
   if i['kind']=='outro':i.update(reviewed=True,reason='Conferi anexo fictício no original')
  confirm_group(b,b['pages'][0]['group'],'Revisor fictício','Conferi identificação e todas as páginas',{i['id'] for i in b['pages']})
 def test_quatro_paginas_uma_ficha_provisoria_sem_perder_pagina(self):
  b=self.read();self.assertEqual([i['kind'] for i in b['pages']],['pedido','guia','continuação de guia','outro'])
  cases=build_cases(b,self.cat);self.assertEqual(len(cases),1);_,d,m=cases[0]
  self.assertEqual(sum(len(doc['pages']) for doc in d.values()),4);self.assertEqual(len(d['apoio']['pages']),1)
  self.assertEqual(sorted(p['source']['page'] for doc in d.values() for p in doc['pages']),[1,2,3,4])
  self.assertTrue(m['pedido']['association_pending']);self.assertTrue(m['pedido']['classification_pending']);self.assertFalse(m['pedido']['identity_conflict'])
  self.assertEqual(m['pedido']['fields']['Paciente']['value'],'PESSOA FICTICIA ALFA')
  self.assertEqual(m['guia']['fields']['Paciente']['value'],'PESSOA FICTICIA');self.assertEqual(len(m['guia']['exams']),5)
 def test_conferencia_explicita_resolve_agrupamento_sem_resolver_outros_bloqueios(self):
  b=self.read();self.acknowledge(b);_,d,m=build_cases(b,self.cat)[0]
  self.assertFalse(m['pedido']['association_pending']);self.assertFalse(m['guia']['classification_pending'])
  self.assertTrue(review_errors(m));self.assertTrue(compare_models(m['pedido'],m['guia'],self.cat)['pendencias'])
 def test_confirmacao_sem_ver_paginas_ou_sem_identificadores_bloqueada(self):
  b=self.read()
  with self.assertRaisesRegex(ValueError,'Visualize todas'):confirm_group(b,'Atendimento 1','Revisor','Conferência fictícia',set())
  for i in b['pages']:
   for key in ['Carteira','Nascimento','CPF','CNS']:i['model']['fields'][key]['value']=''
  with self.assertRaisesRegex(ValueError,'Identificação insuficiente'):self.acknowledge(b)
 def test_conflito_nao_e_liberado_por_checkbox_motivo_ou_edicao_na_ficha(self):
  b=self.read('02_identificadores_incompativeis.pdf');self.assertEqual(len(build_cases(b,self.cat)),1)
  for i in b['pages']:i.update(reviewed=True,reason='Conferência fictícia')
  with self.assertRaisesRegex(ValueError,'incompatíveis'):self.acknowledge(b)
  _,_,m=build_cases(b,self.cat)[0];self.assertTrue(m['pedido']['identity_conflict'])
  for model in m.values():
   model['fields']['Paciente']['value']='PESSOA FICTICIA ALFA';model['fields']['Carteira']['value']=VALUES[8]
  self.assertIn('incompatíveis',' '.join(review_errors(m)))
 def test_modo_varios_pacientes_nao_junta_pacientes_por_arquivo(self):
  b=self.read('02_identificadores_incompativeis.pdf',mode='multiple');self.assertEqual(len(build_cases(b,self.cat)),2)
  self.assertNotEqual(b['pages'][0]['group'],b['pages'][1]['group'])
 def test_nome_parcial_com_identificador_confere_sem_nome_isolado_associar(self):
  b=self.read();a=b['pages'][0]['model'];g=b['pages'][1]['model'];self.assertTrue(compatible(a,g))
  other=copy.deepcopy(g)
  for k in ['Carteira','Nascimento']:other['fields'][k]['value']=''
  self.assertFalse(compatible(a,other));other['fields']['Carteira']['value']='0000000009';self.assertFalse(compatible(a,other))
 def test_campos_tiss_todos_com_origem_sem_troca_de_numero(self):
  b=self.read();_,_,m=build_cases(b,self.cat)[0]
  for n,expected in VALUES.items():
   if n==10:expected='PESSOA FICTICIA'
   with self.subTest(campo=n):
    field=m['guia']['fields'][SCHEMA[n][0]];self.assertEqual(field['value'],expected);self.assertEqual(field['source_document']['page'],2);self.assertTrue(field['box'])
  self.assertEqual([e['source_document']['page'] for e in m['guia']['exams']],[2,2,2,3,3])
 def test_movimentar_paginas_sem_reimportar_preserva_original_e_historico(self):
  b=self.read('02_identificadores_incompativeis.pdf');first=save_batch(self.store,b,self.cat,'Revisor')[0]
  b=load_batch(self.store,b['id']);b['pages'][1].update(group='Outro atendimento',reviewed=True,reason='Identificadores diferentes')
  cids=save_batch(self.store,b,self.cat,'Revisor',replace=True);self.assertEqual(len(cids),2)
  self.assertEqual(self.store.get(first)[1],2);self.assertTrue(self.store.db.execute('SELECT count(*) FROM revisoes_v2').fetchone()[0])
  for _,docs,m in build_cases(b,self.cat):self.assertFalse(m['pedido']['identity_conflict'])
  self.assertEqual(sum(len(doc['pages']) for _,docs,_ in build_cases(b,self.cat) for doc in docs.values()),2)
 def test_movimentacao_ou_correcao_revoga_confirmacao_anterior(self):
  b=self.read();self.acknowledge(b);self.assertFalse(build_cases(b,self.cat)[0][2]['pedido']['association_pending'])
  b['pages'][-1]['group']='Anexo separado';cases=build_cases(b,self.cat)
  self.assertTrue(all(m['pedido']['association_pending'] for _,_,m in cases))
 def test_correcao_ocr_por_pagina_com_origem_e_historico(self):
  b=self.read('02_identificadores_incompativeis.pdf');item=b['pages'][1];old=item['model']['fields']['Carteira']['value']
  apply_identity_edits(item,{'Carteira':'00000123'},'Revisor','Conferido no documento fictício')
  self.assertEqual(item['identity_edits']['Carteira']['original']['value'],old)
  self.assertEqual(item['model']['fields']['Carteira']['origin_type'],'correcao_manual_da_pagina')
  _,_,m=build_cases(b,self.cat)[0];self.assertEqual(m['guia']['fields']['Carteira']['value'],'00000123');self.assertTrue(m['pedido']['identity_conflict'])
 def test_duplicidade_e_remocao_de_paginas_bloqueadas(self):
  b=self.read();save_batch(self.store,b,self.cat,'Revisor')
  with self.assertRaisesRegex(ValueError,'já está'):save_batch(self.store,self.read(),self.cat,'Revisor')
  b['pages'].pop()
  with self.assertRaisesRegex(ValueError,'preservar todas'):save_batch(self.store,b,self.cat,'Revisor',replace=True)
 def test_reunir_lote_antigo_sem_ocr_novo(self):
  b=self.read(mode='multiple');self.assertGreater(len(build_cases(b,self.cat)),1);save_batch(self.store,b,self.cat,'Revisor')
  for item in b['pages']:item['group']='Atendimento provisório único'
  b['mode']='single';cids=save_batch(self.store,b,self.cat,'Revisor',replace=True)
  self.assertEqual(len(cids),1);self.assertEqual(sum(len(d['pages']) for d in self.store.get(cids[0])[0]['docs'].values()),4)
 def test_nome_inteiro_com_espacos_sem_absorver_controle_vizinho(self):
  for filename in ['04_nome_espacado.pdf','05_coluna_vizinha.pdf']:
   with self.subTest(arquivo=filename):
    m=parse_document(read_document(self.files/filename),self.cat)
    self.assertEqual(m['fields']['Paciente']['value'],'PRIMEIRO SEGUNDO TERCEIRO');self.assertNotIn('999999',m['fields']['Paciente']['value'])
 def test_nome_completo_impresso_na_continuacao_prevalece_sem_montar_nomes(self):
  import pymupdf
  file=self.data/'nomes.pdf';pdf=pymupdf.open()
  for name in ['PESSOA FICTICIA','PESSOA FICTICIA ALFA']:
   p=pdf.new_page()
   for x,y,text in [(30,40,'10 - Nome do beneficiario'),(30,65,name),(30,100,'8 - Numero da carteira'),(30,125,'0000087654'),(30,160,'15 - Nome do profissional solicitante'),(30,185,'MEDICO FICTICIO')]:p.insert_text((x,y),text,fontsize=12)
  pdf.save(file);pdf.close();b=read_scan([file],self.data,self.cat,mode='single');m=build_cases(b,self.cat)[0][2]['guia']
  self.assertEqual(m['fields']['Paciente']['value'],'PESSOA FICTICIA ALFA');self.assertEqual(m['fields']['Paciente']['source_document']['page'],2)
  self.assertEqual(len(m['fields']['Paciente']['origins']),2)
 def test_corrige_identificacao_de_lote_24_sem_campos_novos(self):
  b=self.read();item=b['pages'][1]
  for key in ['CPF','CNS']:item['model']['fields'].pop(key)
  apply_identity_edits(item,{'Carteira':'0000087654','CPF':'','CNS':''},'Revisor','Revisão fictícia de lote legado')
  self.assertEqual(item['model']['fields']['CPF']['value'],'');self.assertEqual(item['model']['fields']['CNS']['value'],'')

if __name__=='__main__':unittest.main()
