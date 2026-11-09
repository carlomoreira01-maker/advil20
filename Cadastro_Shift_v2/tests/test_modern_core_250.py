"""Campos prioritários, estados de leitura, rascunhos e segurança de associação."""
import copy,tempfile,unittest
from pathlib import Path
import pymupdf
from gerar_exemplos_250 import main,CLINICAL,EXECUTOR,PRIORITY,PATIENTS
from gerar_exemplos_tiss import VALUES,catalog
from engine_v2 import read_document,parse_document,CaseStore
from tiss import SCHEMA
from scan_import import read_scan,build_cases,save_batch
from draft_workflow import build_draft,save_draft,load_draft

class ModernCore250(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.fixtures=tempfile.TemporaryDirectory();cls.files=main(cls.fixtures.name)
 @classmethod
 def tearDownClass(cls):cls.fixtures.cleanup()
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name);self.cat=catalog()
 def tearDown(self):self.tmp.cleanup()
 def model(self,file):return parse_document(read_document(self.files/file),self.cat)
 def batch(self,file):return read_scan([self.files/file],self.data,self.cat,mode='multiple')
 def test_11_campos_mais_conselho_com_valores_origem_zeros(self):
  m=self.model('guia_completa.pdf');expected={**VALUES,10:PATIENTS[0],23:CLINICAL,30:EXECUTOR}
  for n in [*PRIORITY,16]:
   with self.subTest(campo=n):
    f=m['fields'][SCHEMA[n][0]];self.assertEqual(f['value'],expected[n]);self.assertEqual(f['tiss_number'],n);self.assertEqual(f['page'],1);self.assertEqual(len(f['box']),4);self.assertEqual(f['extraction_state'],'identified')
 def test_contratado_executante_nao_e_medico_e_fica_apos_tabela(self):
  m=self.model('guia_completa.pdf');self.assertEqual(m['fields']['Contratado executante']['value'],EXECUTOR);self.assertEqual(m['fields']['Medico']['value'],'DRA EXEMPLO SINTETICA');self.assertGreater(m['fields']['Contratado executante']['box'][1],m['exams'][-1]['box'][1])
 def test_campo23_multilinha_nao_inclui_cabecalho_e_nao_vira_exame(self):
  m=self.model('guia_sem_procedimentos.pdf');self.assertEqual(m['fields']['Indicação clínica']['value'],CLINICAL);self.assertEqual(m['exams'],[])
 def test_quatro_estados_vazio_incerto_nao_encontrado_identificado(self):
  blank=self.model('guia_campos_vazios.pdf')
  for key in ['Guia principal','Senha autorização','Guia operadora','Contratado executante']:
   self.assertEqual(blank['fields'][key]['value'],'');self.assertEqual(blank['fields'][key]['extraction_state'],'empty');self.assertTrue(blank['fields'][key]['located'])
  self.assertEqual(self.model('guia_crm_incerto.pdf')['fields']['Número conselho']['extraction_state'],'uncertain')
  self.assertEqual(self.model('guia_sem_campo30.pdf')['fields']['Contratado executante']['extraction_state'],'not_found')
  self.assertEqual(self.model('guia_completa.pdf')['fields']['Número conselho']['extraction_state'],'identified')
 def test_numero_conselho_separado_nao_e_cbo(self):
  m=self.model('guia_completa.pdf');self.assertEqual(m['fields']['Número conselho']['value'],'0012345');self.assertEqual(m['fields']['CBO']['value'],'225125');self.assertNotEqual(m['fields']['Número conselho']['box'],m['fields']['CBO']['box'])
 def test_nome_empresarial_nao_usa_restricoes_de_nome_de_pessoa(self):
  for name in ['LABORATORIO PROFISSIONAL 00','LABTESTE']:
   out=self.data/(name.replace(' ','_')+'.pdf')
   with pymupdf.open(self.files/'guia_completa.pdf') as d:
    p=d[0];p.add_redact_annot(pymupdf.Rect(228,728,890,760));p.apply_redactions();p.insert_text((230,745),name,fontsize=14);d.save(out)
   self.assertEqual(parse_document(read_document(out),self.cat)['fields']['Contratado executante']['value'],name)
 def test_rotulos_fundidos_sem_numero_sao_localizados(self):
  out=self.data/'fundidos.pdf'
  with pymupdf.open(self.files/'guia_completa.pdf') as d:
   p=d[0]
   for rect in [(30,382,350,398),(228,706,580,725)]:p.add_redact_annot(pymupdf.Rect(rect))
   p.apply_redactions();p.insert_text((35,395),'IndicacaoClinica',fontsize=10);p.insert_text((230,720),'NomeDoContratadoExecutante',fontsize=10);d.save(out)
  m=parse_document(read_document(out),self.cat);self.assertEqual(m['fields']['Indicação clínica']['value'],CLINICAL);self.assertEqual(m['fields']['Contratado executante']['value'],EXECUTOR)
 def test_pdf_quatro_paginas_dois_pacientes_gera_dois_atendimentos(self):
  b=self.batch('02_dois_pacientes_quatro_paginas.pdf');cases=build_cases(b,self.cat);self.assertEqual(len(cases),2)
  for _,docs,m in cases:self.assertEqual(m['pedido']['fields']['Paciente']['value'],m['guia']['fields']['Paciente']['value']);self.assertFalse(m['pedido']['identity_conflict'])
  self.assertEqual(sorted(p['source']['page'] for _,docs,_ in cases for d in docs.values() for p in d['pages']),[1,2,3,4])
 def test_so_guia_nao_cria_pedido_ou_exames_solicitados(self):
  _,docs,m=build_cases(self.batch('guia_completa.pdf'),self.cat)[0];self.assertEqual(docs['pedido']['pages'],[]);self.assertEqual(m['pedido']['exams'],[])
  d=build_draft({'docs':docs,'models':m},self.cat,'FICTICIO',1);self.assertFalse(d['documentos_presentes']['pedido']);self.assertTrue(d['documentos_presentes']['guia']);self.assertTrue(d['pendencias']);self.assertFalse(d['pronto_para_envio'])
 def test_rascunho_com_campos_vazios_nao_prepara_ou_autoriza(self):
  store=CaseStore(self.data/'base.sqlite3')
  try:
   cid=save_batch(store,self.batch('03_campos_vazios.pdf'),self.cat,'')[0];obj,rev,_,_=store.get(cid);before=copy.deepcopy(obj)
   result=save_draft(store,cid,obj['models'],self.cat,expected_revision=rev);self.assertEqual(result['tipo'],'RASCUNHO_LOCAL_NAO_ENVIAR');self.assertTrue(result['pendencias']);self.assertIsNone(result['os_real']);self.assertEqual(store.get(cid)[0],before);self.assertEqual(store.get(cid)[1],rev);self.assertEqual(store.get(cid)[2],'CONFERIR');self.assertIsNone(store.get(cid)[3])
   with self.assertRaises(ValueError):store.prepare(cid,self.cat,'REVISOR',rev,result.get('catalogo_hash',''),True)
  finally:store.db.close()
 def test_rascunho_restaura_correcao_e_nao_sobrepoe_revisao_nova(self):
  store=CaseStore(self.data/'base.sqlite3')
  try:
   cid=save_batch(store,self.batch('01_um_paciente.pdf'),self.cat,'REVISOR')[0];obj,rev,_,_=store.get(cid);m=copy.deepcopy(obj['models']);m['guia']['fields']['Contratado executante']['value']='LABORATORIO CORRIGIDO FICTICIO'
   save_draft(store,cid,m,self.cat,expected_revision=rev);self.assertEqual(load_draft(store,cid)['models']['guia']['fields']['Contratado executante']['value'],'LABORATORIO CORRIGIDO FICTICIO')
   store.save(cid,obj['models'],'REVISOR','Nova revisão fictícia',rev);self.assertIsNone(load_draft(store,cid))
  finally:store.db.close()
 def test_ocr_real_guia_girada_dos_campos_prioritarios(self):
  m=self.model('04_guia_girada.pdf');expected={**VALUES,10:PATIENTS[0],23:CLINICAL,30:EXECUTOR}
  from core import norm
  for n in [*PRIORITY,16]:
   with self.subTest(campo=n):self.assertEqual(norm(m['fields'][SCHEMA[n][0]]['value']),norm(expected[n]));self.assertEqual(m['fields'][SCHEMA[n][0]]['page'],1);self.assertTrue(m['fields'][SCHEMA[n][0]]['box'])

if __name__=='__main__':unittest.main()
