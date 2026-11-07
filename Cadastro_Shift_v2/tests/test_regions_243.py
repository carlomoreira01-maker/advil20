"""Regressões de geometria observadas em formulários; apenas dados fictícios."""
import copy,tempfile,unittest
from pathlib import Path
import pymupdf
from engine_v2 import read_document,parse_document,group_lines
from gerar_exemplos_tiss import make_guide,VALUES,catalog
from tiss import SCHEMA
from tiss_geometry import header_token,anchors
from tiss_names import name_words
from document_geometry import rotated_box

class Regions243(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.cat=catalog()
 def tearDown(self):self.tmp.cleanup()
 def guide(self,**kwargs):
  file=self.dir/'ficticio.pdf';make_guide(file,**kwargs);return read_document(file)
 def regional(self,doc,family,targets,words):
  page=doc['pages'][0];page.setdefault('regional_readings',[])
  for i in range(2):page['regional_readings'].append({'id':family+'-'+str(i),'family':family,'targets':targets,'bounds':[0,0,*page['size']],'words':copy.deepcopy(words)})
 def test_guia_ausente_recuperada_por_duas_leituras_com_origem(self):
  doc=self.guide();words=[w for l in doc['pages'][0]['lines'] for w in l['words']]
  original=copy.deepcopy(words)
  for w in words:
   if w['text']==VALUES[2]:w['text']='?'
  doc['pages'][0]['lines']=group_lines(words);self.regional(doc,'header',[2,3,4,5,6,7],original)
  m=parse_document(doc,self.cat);f=m['fields']['Guia prestador']
  self.assertEqual(f['value'],VALUES[2]);self.assertEqual(f['regional_agreements'],2);self.assertEqual(f['page'],1);self.assertEqual(len(f['box']),4);self.assertFalse(f['reviewed'])
 def test_leituras_divergentes_nao_escolhem_identificador(self):
  doc=self.guide();original=copy.deepcopy([w for l in doc['pages'][0]['lines'] for w in l['words']])
  for line in doc['pages'][0]['lines']:
   for w in line['words']:
    if w['text']==VALUES[8]:w['text']='0000000009'
  self.regional(doc,'beneficiary',[8,9,10],original);m=parse_document(doc,self.cat)
  self.assertEqual(m['fields']['Carteira']['value'],'');self.assertGreaterEqual(len(m['fields']['Carteira']['candidates']),2)
 def test_uma_leitura_nao_preenche_campo_ausente(self):
  doc=self.guide();original=copy.deepcopy([w for l in doc['pages'][0]['lines'] for w in l['words']])
  for line in doc['pages'][0]['lines']:
   for w in line['words']:
    if w['text']==VALUES[2]:w['text']='?'
  doc['pages'][0]['lines']=group_lines([w for l in doc['pages'][0]['lines'] for w in l['words']]);self.regional(doc,'header',[2],original);doc['pages'][0]['regional_readings'].pop()
  m=parse_document(doc,self.cat);self.assertEqual(m['fields']['Guia prestador']['value'],'');self.assertTrue(m['fields']['Guia prestador']['candidates'])
 def test_autorizacao_zero_lida_na_regiao_nao_vira_um(self):
  doc=self.guide(zero=True);page=doc['pages'][0];original=copy.deepcopy([w for l in page['lines'] for w in l['words']])
  words=[w for l in page['lines'] for w in l['words'] if not (w['text']=='0' and w['box'][0]>850)]
  page['lines']=group_lines(words);self.regional(doc,'table',[],original);m=parse_document(doc,self.cat)
  self.assertEqual(m['exams'][0]['quantidade_solicitada'],'1');self.assertEqual(m['exams'][0]['quantidade_autorizada'],'0');self.assertEqual(m['exams'][0]['cell_origins']['quantidade_autorizada']['regional_agreements'],2)
 def test_execucao_nao_supre_autorizacao_ausente(self):
  doc=self.guide(blank=True,repeated=True);original=copy.deepcopy([w for l in doc['pages'][0]['lines'] for w in l['words']]);self.regional(doc,'table',[],original)
  m=parse_document(doc,self.cat);self.assertEqual(len(m['exams']),5);self.assertTrue(all(e['quantidade_autorizada']=='' for e in m['exams']))
 def test_sobrenome_nascimento_nao_e_data_e_rodape_limita_data(self):
  file=self.dir/'data.pdf';pdf=pymupdf.open();p=pdf.new_page()
  p.insert_text((30,40),'Nascimento SOBRENOME FICTICIO SEM DATA',fontsize=12)
  p.insert_text((30,90),'Data Nasc: 01/02/1995 Sexo: F Estado: FICTICIO',fontsize=12);pdf.save(file);pdf.close()
  m=parse_document(read_document(file),[]);self.assertEqual(m['fields']['Nascimento']['value'],'01/02/1995');self.assertEqual(m['fields']['Nascimento']['snippet'],'Nascimento: 01/02/1995')
 def test_cabecalho_abaixo_do_nome_nao_e_sobrenome(self):
  words=[{'text':t,'box':[x,50,x+30,58],'confidence':95} for x,t in [(30,'PESSOA'),(65,'FICTICIA'),(100,'ALFA')]]
  words.extend([{'text':t,'box':[x,63,x+45,75],'confidence':95} for x,t in [(30,'CABECALHO'),(80,'AUXILIAR')]])
  self.assertEqual(' '.join(w['text'] for w in name_words(words)),'PESSOA FICTICIA ALFA')
 def test_letra_isolada_em_outra_coluna_nao_e_nome(self):
  words=[{'text':t,'box':[x,50,x+30,58],'confidence':95} for x,t in [(30,'PESSOA'),(65,'FICTICIA'),(100,'ALFA'),(600,'X')]]
  self.assertEqual(' '.join(w['text'] for w in name_words(words)),'PESSOA FICTICIA ALFA')
 def test_palavra_que_cruza_borda_pertence_a_coluna_do_centro(self):
  pdf=pymupdf.open();p=pdf.new_page(width=700,height=400)
  for x,y,t in [(30,30,'10 - Nome do beneficiario'),(30,52,'PESSOA FICTICIA ALFA'),(100,100,'16 - Conselho'),(250,100,'17 - Numero do conselho'),(450,100,'18 - UF'),(130,125,'CRM'),(247,125,'0012345'),(475,125,'GO')]:p.insert_text((x,y),t,fontsize=10)
  f=self.dir/'borda.pdf';pdf.save(f);pdf.close();m=parse_document(read_document(f),[])
  self.assertEqual(m['fields']['Conselho']['value'],'CRM');self.assertEqual(m['fields']['Número conselho']['value'],'0012345')
 def test_rotulos_fundidos_sao_expandidos_sem_mudar_valores(self):
  self.assertEqual(header_token('NomedoBeneficiario'),'NOME DO BENEFICIARIO');self.assertEqual(header_token('Qt.Solic.'),'QT SOLICITADA');self.assertEqual(header_token('Qt.Aut.'),'QT AUTORIZADA')
  self.assertEqual(header_token('0000012345'),'0000012345')
 def test_caixas_ao_girar_visualizacao_referenciam_original(self):
  box=[20,30,60,90];size=[200,400]
  self.assertEqual(rotated_box(box,size,90),[30,140,90,180]);self.assertEqual(rotated_box(box,size,270),[310,20,370,60]);self.assertEqual(box,[20,30,60,90])
 def test_data_validade_nao_pode_virar_senha(self):
  pdf=pymupdf.open();p=pdf.new_page(width=800,height=400)
  for x,y,t in [(30,30,'10 - Nome do beneficiario'),(30,52,'PESSOA FICTICIA ALFA'),(30,100,'5 - Senha'),(300,100,'6-Data Validade da senha'),(300,122,'31/12/2099')]:p.insert_text((x,y),t,fontsize=10)
  f=self.dir/'validade.pdf';pdf.save(f);pdf.close();m=parse_document(read_document(f),[])
  self.assertEqual(m['fields']['Senha autorização']['value'],'');self.assertEqual(m['fields']['Validade senha']['value'],'31/12/2099')
 def test_identificador_nao_aceita_data_de_campo_vizinho(self):
  from tiss import valid
  self.assertFalse(valid('31/12/2099','id'));self.assertTrue(valid('00000123','id'))

if __name__=='__main__':unittest.main()
