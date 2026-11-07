import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from engine_v2 import read_document,parse_document,catalog_load,compare_models
from gerar_exemplos_tiss import make_guide,make_order,VALUES,catalog
from tiss import SCHEMA
ROOT=Path(__file__).resolve().parents[1]
class TISS(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.cat=catalog()
 def tearDown(self):self.tmp.cleanup()
 def model(self,**kwargs):
  p=self.dir/'guia.pdf';make_guide(p,**kwargs);return parse_document(read_document(p),self.cat)
 def test_campos_individuais_com_origem_e_zeros(self):
  model=self.model()
  for number,expected in VALUES.items():
   key=SCHEMA[number][0]
   with self.subTest(campo=number,nome=key):
    field=model['fields'][key];self.assertEqual(field['value'],expected)
    self.assertEqual(field['page'],1);self.assertEqual(field['tiss_number'],number)
    self.assertEqual(len(field['box']),4);self.assertIn(expected,field['snippet'])
  self.assertEqual(model['fields']['Guia']['value'],'')
  self.assertNotEqual(model['fields']['Senha autorização']['value'],model['fields']['Guia operadora']['value'])
 def test_tabela_cinco_sem_duplicar_execucao(self):
  model=self.model(repeated=True)
  self.assertEqual(len(model['exams']),5);self.assertEqual(len(model['tiss_detail']['executed_exams']),5)
  for e in model['exams']:
   self.assertEqual(e['quantidade_solicitada'],'1');self.assertEqual(e['quantidade_autorizada'],'1')
   self.assertEqual(len(e['execution_occurrences']),1)
 def test_autorizacao_ausente_nao_e_inferida(self):
  model=self.model(blank=True)
  for key in ['Senha autorização','Validade senha','Guia operadora']:self.assertEqual(model['fields'][key]['value'],'')
  self.assertTrue(all(e['quantidade_autorizada']=='' for e in model['exams']))
 def test_solicitada_um_autorizada_zero(self):
  model=self.model(zero=True);e=model['exams'][0]
  self.assertEqual(e['quantidade_solicitada'],'1');self.assertEqual(e['quantidade_autorizada'],'0')
  order=self.dir/'pedido.pdf';make_order(order);p=parse_document(read_document(order),self.cat)
  result=compare_models(p,model,self.cat)
  self.assertIn('Não autorizado',' '.join(result['pendencias']))
 def test_multiplas_paginas(self):
  model=self.model(multipage=True)
  self.assertEqual(len(model['exams']),5);self.assertEqual([e['page'] for e in model['exams']],[1,1,1,2,2])
 def test_numero_extra_nao_e_autorizacao(self):
  model=self.model();extra=model['tiss_detail']['extra_numbers']
  self.assertTrue(any(e['value']=='0000999988' for e in extra))
  self.assertEqual(model['fields']['Senha autorização']['value'],'00000555')
 def test_crm_ilegivel_nao_vira_cbo(self):
  model=self.model(crm_bad=True)
  self.assertEqual(model['fields']['Número conselho']['value'],'')
  self.assertEqual(model['fields']['Código solicitante']['value'],'000001313')
 def test_operadoras_variam_sem_homologacao_automatica(self):
  for name in ['UNIMED','IPASGO']:
   model=self.model(variant=name)
   self.assertEqual(model['fields']['Carteira']['value'],'0000087654')
   self.assertEqual(model['fields']['Fonte pagadora']['value'],name)
 def test_pacientes_diferentes_bloqueiam(self):
  order=self.dir/'pedido.pdf';make_order(order);p=parse_document(read_document(order),self.cat)
  result=compare_models(p,self.model(other=True),self.cat)
  self.assertTrue(any('Identidade' in e for e in result['pendencias']))
 def test_tuss_sem_codigo_shift_nao_inventa(self):
  path=self.dir/'cat.json';path.write_text(json.dumps(self.cat))
  cat=catalog_load(path);self.assertTrue(all(e['codigo_shift']=='' for e in cat))
  order=self.dir/'pedido.pdf';make_order(order);p=parse_document(read_document(order),cat)
  result=compare_models(p,self.model(),cat)
  self.assertIn('Código interno Shift não fornecido',' '.join(result['pendencias']))
 def test_catalogo_desconhecido_bloqueia(self):
  model=self.model();order=self.dir/'pedido.pdf';make_order(order)
  p=parse_document(read_document(order),[])
  result=compare_models(p,model,[])
  self.assertTrue(result['pendencias']);self.assertTrue(result['exames'])
  self.assertTrue(all(not row['codigo_shift'] for row in result['exames']))
  self.assertTrue(all('não validada' in row['situacao'] for row in result['exames']))
 def test_imagem_e_pdf_escaneado_reais(self):
  for filename in ['01_completa.png','01_escaneada.pdf']:
   model=parse_document(read_document(ROOT/'exemplos_tiss'/filename),self.cat)
   for number in [2,3,4,5,6,7,8,9,10,13,15,16,17,18,22]:
    with self.subTest(arquivo=filename,campo=number):self.assertEqual(model['fields'][SCHEMA[number][0]]['value'],VALUES[number])
   self.assertEqual(len(model['exams']),5)
   self.assertEqual([e['codigo'] for e in model['exams']],['90000001','90000002','90000003','90000004','90000005'])
   self.assertTrue(all(e['quantidade_solicitada']=='1' and e['quantidade_autorizada']=='1' for e in model['exams']))
 def test_pedido_quatro_orientacoes_e_inclinacao(self):
  for filename in ['05_pedido_0.png','05_pedido_90.png','05_pedido_180.png','05_pedido_270.png','05_pedido_inclinado.png']:
   with self.subTest(arquivo=filename):
    doc=read_document(ROOT/'exemplos_tiss'/filename);model=parse_document(doc,self.cat)
    self.assertEqual(model['fields']['Paciente']['value'],'PESSOA FICTICIA ALFA')
    self.assertEqual(len(model['exams']),5)
    box=model['fields']['Paciente']['box'];size=doc['pages'][0]['size']
    self.assertTrue(0<=box[0]<box[2]<=size[0]);self.assertTrue(0<=box[1]<box[3]<=size[1])
 def test_nome_dividido_em_duas_linhas(self):
  import pymupdf
  p=self.dir/'quebrado.pdf';d=pymupdf.open();pg=d.new_page()
  for x,y,text in [(30,40,'10 - Nome do beneficiario'),(30,62,'PESSOA FICTICIA'),(30,79,'ALFA'),(30,110,'15 - Nome do profissional solicitante'),(30,132,'DRA EXEMPLO'),(30,149,'SINTETICA')]:pg.insert_text((x,y),text,fontsize=11)
  d.save(p);d.close();m=parse_document(read_document(p),self.cat)
  self.assertEqual(m['fields']['Paciente']['value'],'PESSOA FICTICIA ALFA');self.assertEqual(m['fields']['Medico']['value'],'DRA EXEMPLO SINTETICA')
 def test_quantidade_ilegivel_nao_vira_um(self):
  import pymupdf
  p=self.dir/'ilegivel.pdf';make_guide(p);d=pymupdf.open(p);pg=d[0]
  pg.add_redact_annot(pymupdf.Rect(850,489,890,514));pg.apply_redactions();pg.insert_text((855,505),'?',fontsize=13)
  q=self.dir/'ilegivel2.pdf';d.save(q);d.close();m=parse_document(read_document(q),self.cat)
  self.assertEqual(m['exams'][0]['quantidade_autorizada'],'')
 def test_crm_ilegivel_bloqueia_preparo(self):
  order=self.dir/'pedido.pdf';make_order(order);p=parse_document(read_document(order),self.cat)
  result=compare_models(p,self.model(crm_bad=True),self.cat)
  self.assertIn('Número conselho não identificado',' '.join(result['pendencias']))
 def test_material_lido_da_coluna_sem_alterar_quantidade(self):
  m=self.model(material=True)
  self.assertEqual(m['exams'][0]['material'],'EDTA')
  self.assertTrue(all(e['quantidade_autorizada']=='1' for e in m['exams']))
  self.assertEqual(m['exams'][0]['cell_origins']['quantidade_autorizada']['snippet'],'1')
 def test_exame_desconhecido_permanece_com_codigo_lido(self):
  m=self.model(unknown=True)
  self.assertEqual(m['exams'][0]['codigo'],'90009999')
  order=self.dir/'p.pdf';make_order(order)
  result=compare_models(parse_document(read_document(order),self.cat),m,self.cat)
  self.assertTrue(any('não encontrado' in e for e in result['pendencias']))
 def test_descricao_em_duas_linhas_preserva_ambas_as_origens(self):
  import pymupdf
  p=self.dir/'duas.pdf';d=pymupdf.open();pg=d.new_page(width=1000,height=700)
  for x,y,t in [(30,30,'10 - Nome do beneficiario'),(30,52,'PESSOA FICTICIA ALFA'),(30,95,'PROCEDIMENTOS SOLICITADOS'),(30,120,'25 - Codigo'),(240,120,'26 - Descricao'),(680,120,'27 - Qtd solicitada'),(840,120,'28 - Qtd autorizada'),(30,150,'90000001'),(240,150,'Hemograma'),(680,150,'1'),(840,150,'1'),(240,166,'completo')]:pg.insert_text((x,y),t,fontsize=11)
  d.save(p);d.close();m=parse_document(read_document(p),self.cat)
  self.assertEqual(m['fields']['Paciente']['value'],'PESSOA FICTICIA ALFA')
  self.assertEqual(m['exams'][0]['descricao'],'Hemograma completo');self.assertEqual(len(m['exams'][0]['origins']),2)
  self.assertIn('completo',m['exams'][0]['snippet'])
 def test_quantidade_com_baixa_confianca_permanece_nao_identificada(self):
  p=self.dir/'baixo.pdf';make_guide(p);doc=read_document(p)
  for line in doc['pages'][0]['lines']:
   for word in line.get('words',[]):
    if word['text']=='1' and word['box'][0]>850:word['confidence']=12
  m=parse_document(doc,self.cat)
  self.assertTrue(all(e['quantidade_autorizada']=='' for e in m['exams']))
 def test_lista_numerada_de_pedido_nao_vira_guia_tiss(self):
  import pymupdf
  p=self.dir/'lista.pdf';d=pymupdf.open();pg=d.new_page()
  pg.insert_text((35,45),'PEDIDO MEDICO\nPaciente: PESSOA FICTICIA ALFA\nNascimento: 01/02/1995\nExames:\n1. Hemograma Qtd: 1\n2. Glicose Qtd: 1',fontsize=13)
  d.save(p);d.close();m=parse_document(read_document(p),self.cat)
  self.assertFalse(m['tiss']);self.assertEqual(m['document_type'],'pedido');self.assertEqual(len(m['exams']),2)
