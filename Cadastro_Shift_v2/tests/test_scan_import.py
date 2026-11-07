"""Importação, associação, proveniência e bloqueios com dados inteiramente fictícios."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from engine_v2 import CaseStore,compare_models,review_errors,read_document,parse_document
from scan_import import read_scan,build_cases,save_batch,load_batch
from gerar_exemplos_tiss import catalog,VALUES
from gerar_exemplos_2_4 import main,combine
from tiss import SCHEMA

class Scan(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.fixtures=tempfile.TemporaryDirectory();cls.files=main(cls.fixtures.name)
 @classmethod
 def tearDownClass(cls):cls.fixtures.cleanup()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name);self.cat=catalog();self.store=CaseStore(self.data/'casos.sqlite3')
 def tearDown(self):self.store.db.close();self.tmp.cleanup()
 def read(self,name):return read_scan([self.files/name],self.data,self.cat)
 def test_pedido_e_guia_ou_ordem_invertida(self):
  for name,pedido,guia in [('01_pedido_e_guia.pdf',1,2),('02_guia_antes_pedido.pdf',2,1)]:
   with self.subTest(arquivo=name):
    b=self.read(name);cases=build_cases(b,self.cat);self.assertEqual(len(cases),1)
    _,docs,m=cases[0];self.assertEqual(len(m['pedido']['exams']),5);self.assertEqual(len(m['guia']['exams']),5)
    self.assertEqual(m['pedido']['fields']['Paciente']['source_document']['page'],pedido)
    for n,expected in VALUES.items():
     with self.subTest(campo=n):
      field=m['guia']['fields'][SCHEMA[n][0]];self.assertEqual(field['value'],expected);self.assertEqual(field['source_document']['page'],guia);self.assertEqual(len(field['box']),4)
    for row in m['guia']['exams']:
     self.assertEqual(row['source_document']['page'],guia)
     for key in ['codigo','descricao','quantidade_solicitada','quantidade_autorizada']:self.assertEqual(row['cell_origins'][key]['source_document']['page'],guia)
 def test_pdf_original_integral_preservado(self):
  b=self.read('01_pedido_e_guia.pdf');src=next(iter(b['sources'].values()));original=(self.files/'01_pedido_e_guia.pdf').read_bytes()
  self.assertEqual(Path(src['local_path']).read_bytes(),original);self.assertEqual(src['sha256'],hashlib.sha256(original).hexdigest())
  _,docs,_=build_cases(b,self.cat)[0];self.assertNotEqual(docs['pedido']['sha256'],docs['guia']['sha256']);self.assertEqual(len(src['pages']),2)
 def test_quatro_paginas_dois_pacientes_nao_misturam(self):
  b=self.read('03_quatro_paginas_misturadas.pdf');cases=build_cases(b,self.cat);self.assertEqual(len(cases),2)
  for _,docs,m in cases:
   self.assertEqual(m['pedido']['fields']['Paciente']['value'],m['guia']['fields']['Paciente']['value'])
   self.assertFalse(m['pedido']['association_pending']);self.assertFalse(m['pedido']['identity_conflict'])
  self.assertEqual(sorted(p['source']['page'] for _,d,_ in cases for doc in d.values() for p in doc['pages']),[1,2,3,4])
 def test_nome_isolado_nao_associa(self):
  b=self.read('01_pedido_e_guia.pdf')
  from scan_import import compatible
  a=copy.deepcopy(b['pages'][0]['model']);other=copy.deepcopy(a)
  for key in ['Nascimento','Carteira']:a['fields'][key]['value']='';other['fields'][key]['value']=''
  self.assertFalse(compatible(a,other))
 def test_grupo_manual_pacientes_incompativeis_continua_bloqueado(self):
  b=self.read('03_quatro_paginas_misturadas.pdf')
  for p in b['pages']:p.update(group='Grupo manual',reviewed=True,reason='Teste fictício propositalmente incorreto')
  _,_,m=build_cases(b,self.cat)[0];self.assertTrue(m['pedido']['identity_conflict']);self.assertIn('identificadores incompatíveis',' '.join(review_errors(m)))
 def test_tabela_densa_cinco_sem_duplicar_execucao(self):
  m=parse_document(read_document(self.files/'guia_densa.pdf'),self.cat)
  self.assertEqual(len(m['exams']),5);self.assertEqual(len(m['tiss_detail']['executed_exams']),5)
  self.assertTrue(all(len(e['execution_occurrences'])==1 for e in m['exams']))
 def test_quantidade_zero_ausente_e_procedimento_ausente(self):
  p=parse_document(read_document(self.files/'pedido_alfa.pdf'),self.cat)
  for name,expected in [('guia_zero.pdf','Não autorizado'),('guia_sem_autorizacao.pdf','Autorização não identificada'),('guia_exame_ausente.pdf','Ausente na guia')]:
   g=parse_document(read_document(self.files/name),self.cat);result=compare_models(p,g,self.cat)
   self.assertIn(expected,' '.join(result['pendencias']));self.assertTrue(result['exames'])
 def test_sem_catalogo_exames_continuam_visiveis_sem_codigos_inventados(self):
  b=self.read('01_pedido_e_guia.pdf');_,_,m=build_cases(b,[])[0];result=compare_models(m['pedido'],m['guia'],[])
  self.assertEqual(len(result['exames']),10);self.assertTrue(all(not e['codigo_shift'] for e in result['exames']));self.assertTrue(result['pendencias'])
 def test_reimportacao_e_sobreposicao_bloqueadas(self):
  b=self.read('01_pedido_e_guia.pdf');save_batch(self.store,b,self.cat,'Revisor fictício')
  with self.assertRaisesRegex(ValueError,'já está'):save_batch(self.store,self.read('01_pedido_e_guia.pdf'),self.cat,'Revisor fictício')
  b2=read_scan([self.files/'01_pedido_e_guia.pdf',self.files/'pedido_beta.pdf'],self.data,self.cat)
  with self.assertRaisesRegex(ValueError,'já pertence'):save_batch(self.store,b2,self.cat,'Revisor fictício')
 def test_reclassificacao_preserva_historico_e_todas_as_paginas(self):
  b=self.read('01_pedido_e_guia.pdf');cid=save_batch(self.store,b,self.cat,'Revisor fictício')[0]
  old=load_batch(self.store,b['id']);old['pages'][0].update(kind='incerto',reason='Classificação em revisão',reviewed=True)
  self.assertEqual(save_batch(self.store,old,self.cat,'Revisor fictício',replace=True),[cid]);self.assertEqual(self.store.get(cid)[1],2)
  self.assertTrue(self.store.get(cid)[0]['models']['pedido']['classification_pending'])
  self.assertTrue(self.store.db.execute('SELECT count(*) FROM revisoes_v2').fetchone()[0])
  removed=copy.deepcopy(old);removed['pages'].pop()
  with self.assertRaisesRegex(ValueError,'preservar todas'):save_batch(self.store,removed,self.cat,'Revisor fictício',replace=True)
 def test_incompleto_ocr_ausente_ainda_cria_atendimento_para_correcao(self):
  from ocr_runtime import LocalReadError
  with patch('engine_v2.ocr_words',side_effect=LocalReadError('Tesseract ausente.')):b=self.read('04_guia_girada_e_pedido.pdf')
  cases=build_cases(b,self.cat);self.assertTrue(cases);self.assertIn('incerto',[i['kind'] for i in b['pages']])
  self.assertTrue(any(d['pages'] for _,docs,_ in cases for d in docs.values()))
 def test_orientacao_nao_premia_token_gigante(self):
  from ocr_processing import recognize_page
  from PIL import Image
  calls=[]
  def recognize(im,psm):
   calls.append(psm)
   if psm==6 and len(calls)<=4:
    angle=[0,90,180,270][len(calls)-1]
    words=['PACIENTE','EXAMES','NASCIMENTO'] if angle==90 else ['x'*10000]
    return [{'text':t,'box':[10,10,50,20],'confidence':95} for t in words]
   return [{'text':'PACIENTE','box':[10,10,50,20],'confidence':95}]
  words=recognize_page(Image.new('L',(300,400),200),recognize);self.assertEqual(words[0]['orientation'],90)
 def test_guia_densa_escaneada_girada_valores_e_origens(self):
  b=self.read('04_guia_girada_e_pedido.pdf');cases=build_cases(b,self.cat);self.assertEqual(len(cases),1)
  _,docs,m=cases[0];self.assertEqual(docs['guia']['pages'][0]['orientation'],270)
  for n,expected in VALUES.items():
   with self.subTest(campo=n):
    f=m['guia']['fields'][SCHEMA[n][0]];self.assertEqual(f['value'],expected);self.assertEqual(f['source_document']['page'],1)
  self.assertEqual(len(m['guia']['exams']),5);self.assertTrue(all(e['quantidade_autorizada']=='1' for e in m['guia']['exams']))
 def test_continuacao_sem_identidade_fica_separada_para_revisao(self):
  from gerar_exemplos_tiss import make_guide
  file=self.data/'continua.pdf';make_guide(file,multipage=True)
  b=read_scan([file],self.data,self.cat)
  self.assertEqual(b['pages'][1]['kind'],'continuação de guia');self.assertNotEqual(b['pages'][0]['group'],b['pages'][1]['group'])
  self.assertEqual(len(build_cases(b,self.cat)),2)
 def test_png_e_jpg_na_importacao_unica(self):
  import io,pymupdf
  from PIL import Image
  with pymupdf.open(self.files/'guia_densa.pdf') as pdf:
   im=Image.open(io.BytesIO(pdf[0].get_pixmap(matrix=pymupdf.Matrix(3,3)).tobytes('png')))
  for ext in ['png','jpg']:
   with self.subTest(formato=ext):
    file=self.data/('imagem.'+ext);im.convert('RGB').save(file)
    b=read_scan([file],self.data,self.cat);cases=build_cases(b,self.cat);self.assertEqual(len(cases),1)
    model=cases[0][2]['guia'];self.assertEqual(model['fields']['Carteira']['value'],VALUES[8]);self.assertEqual(len(model['exams']),5)
 def test_codigo_ilegivel_nao_oculta_descricao_e_codigo_local_nao_e_inventado(self):
  import pymupdf
  original=self.files/'guia_densa.pdf';file=self.data/'codigo_ausente.pdf'
  with pymupdf.open(original) as pdf:
   p=pdf[0];p.add_redact_annot(pymupdf.Rect(78,229,130,241));p.apply_redactions();pdf.save(file)
  m=parse_document(read_document(file),self.cat);self.assertEqual(len(m['exams']),5)
  self.assertEqual(m['exams'][0]['codigo'],'');self.assertEqual(m['exams'][0]['descricao'],'Hemograma')
  self.assertEqual(m['exams'][0]['quantidade_solicitada'],'1');self.assertEqual(m['exams'][0]['quantidade_autorizada'],'1')
  self.assertEqual(len(m['exams'][0]['cell_origins']['descricao']['box']),4)

if __name__=='__main__':unittest.main()
