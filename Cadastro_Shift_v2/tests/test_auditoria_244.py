"""Regressões da auditoria; documentos e gabaritos inteiramente fictícios."""
import copy,tempfile,unittest
from pathlib import Path
from engine_v2 import read_document,parse_document,resolve_exam,compare_models,CaseStore
from scan_import import read_scan,build_cases,save_batch,load_batch,compatible
from gerar_exemplos_auditoria import main,PATIENT
from gerar_exemplos_tiss import catalog,VALUES
from tests.test_mapping_sim import profile
from tiss import SCHEMA
from payer_mapping import validate_profile,mark_not_applicable

class Auditoria244(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.fixtures=tempfile.TemporaryDirectory();cls.files=main(cls.fixtures.name)
 @classmethod
 def tearDownClass(cls):cls.fixtures.cleanup()
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name);self.cat=catalog()
 def tearDown(self):self.tmp.cleanup()
 def model(self,name):return parse_document(read_document(self.files/name),self.cat)
 def batch(self,name):return read_scan([self.files/name],self.data,self.cat,mode='single')
 def test_01_quatro_paginas_tipos_e_uma_ficha(self):
  b=self.batch('01_quatro_paginas.pdf');self.assertEqual([i['kind'] for i in b['pages']],['pedido','guia','continuação de guia','outro'])
  c=build_cases(b,self.cat);self.assertEqual(len(c),1);self.assertEqual(sum(len(d['pages']) for d in c[0][1].values()),4)
  self.assertEqual(len(c[0][2]['pedido']['exams']),5);self.assertEqual(len(c[0][2]['guia']['exams']),5)
 def test_02_ordem_invertida(self):
  b=self.batch('02_ordem_invertida.pdf');self.assertEqual([i['kind'] for i in b['pages']],['guia','pedido'])
  _,_,m=build_cases(b,self.cat)[0];self.assertEqual(m['pedido']['fields']['Paciente']['source_document']['page'],2)
 def test_03_nome_completo_particulas_e_origem(self):
  m=self.model('04_crm_go.pdf');field=m['fields']['Paciente'];self.assertEqual(field['value'],PATIENT);self.assertEqual(field['page'],1);self.assertEqual(len(field['box']),4)
 def test_04_campos_16_17_18_cbo_e_tamanhos(self):
  for i,expected in enumerate(['12','00123','0012345','0001234567'],1):
   with self.subTest(crm=expected):
    m=self.model(f'crm_tamanho_{i}.pdf')
    for key,value in [('Conselho','CRM'),('Número conselho',expected),('UF conselho','GO'),('CBO','225125')]:self.assertEqual(m['fields'][key]['value'],value)
    field=m['fields']['Número conselho'];self.assertEqual(field['tiss_number'],17);self.assertEqual(field['page'],1);self.assertLess(field['box'][2],388)
 def test_05_guia_incompleta_nao_inventa(self):
  m=self.model('05_guia_incompleta.pdf')
  for key in ['Guia principal','Senha autorização','Validade senha']:self.assertEqual(m['fields'][key]['value'],'')
  self.assertTrue(all(e['quantidade_autorizada']=='' for e in m['exams']))
 def test_06_cinco_exames_quantidades_separadas(self):
  _,_,m=build_cases(self.batch('06_quantidades.pdf'),self.cat)[0]
  r=compare_models(m['pedido'],m['guia'],self.cat);self.assertEqual(len(r['exames']),5);self.assertIn('Não autorizado',' '.join(r['pendencias']))
  first=m['guia']['exams'][0];self.assertEqual(first['quantidade_solicitada'],'1');self.assertEqual(first['quantidade_autorizada'],'0')
 def test_07_ajustes_e_perfil_persistem_apos_classificacao(self):
  b=self.batch('07_conferencia.pdf');store=CaseStore(self.data/'cases.sqlite3')
  try:
   cid=save_batch(store,b,self.cat,'REVISOR FICTICIO')[0];obj,rev,_,_=store.get(cid)
   g=obj['models']['guia'];g['fields']['Número conselho'].update(value='0012345',origin_type='correcao_manual',reviewed=True);g['payer_profile']=profile()
   e=g['exams'][0];e.update(quantidade='2',quantidade_autorizada='2',origin_type='correcao_manual',reviewed=True)
   store.save(cid,obj['models'],'REVISOR FICTICIO','Correção fictícia',rev)
   save_batch(store,load_batch(store,b['id']),self.cat,'REVISOR FICTICIO',replace=True)
   g=store.get(cid)[0]['models']['guia'];self.assertEqual(g['fields']['Número conselho']['value'],'0012345');self.assertFalse(g['fields']['Número conselho']['reviewed']);self.assertEqual(g['payer_profile']['id'],profile()['id']);self.assertEqual(g['exams'][0]['quantidade_autorizada'],'2');self.assertFalse(g['exams'][0]['reviewed'])
  finally:store.db.close()
 def test_08_conflito_bloqueado(self):
  _,_,m=build_cases(self.batch('08_conflito.pdf'),self.cat)[0];self.assertTrue(m['guia']['identity_conflict'])
 def test_09_incerto_nao_vira_pedido(self):
  b=self.batch('09_incerto.pdf');self.assertEqual(b['pages'][0]['kind'],'incerto');_,d,_=build_cases(b,self.cat)[0];self.assertFalse(d['pedido']['pages']);self.assertTrue(d['apoio']['pages'])
 def test_apenas_dois_rotulos_de_nome_nao_confirmam_guia(self):
  import pymupdf
  path=self.data/'sem_tipo.pdf';pdf=pymupdf.open();p=pdf.new_page()
  for x,y,text in [(30,40,'10 - Nome do beneficiario'),(30,65,'PESSOA FICTICIA ALFA'),(30,110,'15 - Nome do profissional solicitante'),(30,135,'MEDICO FICTICIO')]:p.insert_text((x,y),text,fontsize=11)
  pdf.save(path);pdf.close()
  b=read_scan([path],self.data,self.cat,mode='single');self.assertEqual(b['pages'][0]['kind'],'incerto');self.assertEqual(b['pages'][0]['model']['fields']['Paciente']['value'],'PESSOA FICTICIA ALFA')
 def test_10_pedido_com_campos_tiss_preserva_tipo_campos_lista(self):
  m=self.model('10_pedido_estruturado.pdf');self.assertEqual(m['document_type'],'pedido');self.assertEqual(len(m['exams']),5)
  for key,value in [('Paciente',PATIENT),('Conselho','CRM'),('Número conselho','0012345'),('UF conselho','GO')]:self.assertEqual(m['fields'][key]['value'],value)
 def test_campos_tiss_gabarito_completo(self):
  m=self.model('04_crm_go.pdf')
  for number,expected in {**VALUES,10:PATIENT,19:'225125'}.items():
   with self.subTest(campo=number):
    field=m['fields'][SCHEMA[number][0]];self.assertEqual(field['value'],expected);self.assertEqual(field['page'],1);self.assertEqual(len(field['box']),4)
 def test_carimbo_divergente_nao_vira_sexto_exame(self):
  m=self.model('12_carimbo_divergente.pdf');self.assertEqual(len(m['exams']),5)
  f=m['fields']['Número conselho'];self.assertEqual(f['value'],'');self.assertEqual({c['value'] for c in f['candidates']},{'0012345','0099999'})
 def test_uf_ausente_nao_inventa_go(self):self.assertEqual(self.model('11_sem_uf.pdf')['fields']['UF conselho']['value'],'')
 def test_catalogo_sem_interno_nao_aceita_tuss_de_outro_exame(self):
  row,error=resolve_exam({'descricao':'Hemograma','codigo':'90000002'},self.cat);self.assertIsNone(row);self.assertIn('diferentes',error)
 def test_sobrenome_e_nascimento_sozinhos_nao_associam(self):
  a=self.model('04_crm_go.pdf');b=copy.deepcopy(a);a['fields']['Paciente']['value']='SANTOS'
  for m in [a,b]:
   for key in ['Carteira','CPF','CNS']:m['fields'][key]['value']=''
  self.assertFalse(compatible(a,b))
 def test_correcao_manual_de_crm_ou_uf_invalida_bloqueia(self):
  p=self.model('pedido.pdf');g=self.model('04_crm_go.pdf');g['payer_profile']=profile()
  for key,value in [('Número conselho','CBO225125'),('UF conselho','??'),('CBO','12')]:
   changed=copy.deepcopy(g);changed['fields'][key]['value']=value
   self.assertIn(key+': valor inválido',' '.join(compare_models(p,changed,self.cat)['pendencias']))
 def test_nao_aplicavel_exige_regra_e_nao_dispensa_autorizacao(self):
  p=profile();p['campos_nao_aplicaveis']=['Senha autorização']
  with self.assertRaisesRegex(ValueError,'exige autorização'):validate_profile(p)
  p=profile();p['campos_nao_aplicaveis']=['Guia principal'];g=self.model('05_guia_incompleta.pdf');mark_not_applicable(g,p)
  self.assertEqual(g['fields']['Guia principal']['not_applicable']['id'],p['id']);self.assertEqual(g['fields']['Guia principal']['value'],'')
  with self.assertRaisesRegex(ValueError,'valor impresso'):mark_not_applicable(self.model('04_crm_go.pdf'),p)
 def test_dois_consensos_divergentes_exigem_conferencia(self):
  from tiss_refinement import reconcile_fields
  from tiss import empty_field
  fields={key:empty_field('fic') for key,_ in SCHEMA.values()};variants=[]
  for i,v in enumerate(['000001','000001','000002','000002']):
   model={'fields':copy.deepcopy(fields)};model['fields']['Guia prestador'].update(value=v,confidence=95,page=1,box=[10,10,20,20])
   variants.append(({'id':'leitura-'+str(i),'targets':[2]},model))
  reconcile_fields(fields,{'number':1},variants,[]);self.assertEqual(fields['Guia prestador']['value'],'');self.assertEqual(len(fields['Guia prestador']['candidates']),2)

if __name__=='__main__':unittest.main()
