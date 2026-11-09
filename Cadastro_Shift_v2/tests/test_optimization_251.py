"""Regressões sintéticas do agrupamento, cache, OCR controlado e classificação."""
import copy,json,subprocess,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf
from scan_import import read_scan,build_cases,confirm_group
from engine_v2 import read_document,parse_document
from gerar_exemplos_tiss import catalog
from reading_cache import ReadingCache
from reading_control import ReadCancelled,reading_context
from tiss_names import name_words

ROOT=Path(__file__).resolve().parents[1]
class Optimization251(unittest.TestCase):
 def test_numero_workers_limitado_por_configuracao(self):
  from reading_control import page_workers
  with patch.dict('os.environ',{'SHIFT_OCR_WORKERS':'1'}):self.assertEqual(page_workers(),1)
  with patch.dict('os.environ',{'SHIFT_OCR_WORKERS':'900'}):self.assertIn(page_workers(),[1,2])
  with patch.dict('os.environ',{'SHIFT_OCR_WORKERS':'invalido'}):self.assertEqual(page_workers(),1)
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def test_quatro_paginas_um_atendimento_nomes_parciais_sem_nome(self):
  b=read_scan([ROOT/'exemplos_2_4_2/01_um_atendimento_quatro_paginas.pdf'],self.data,catalog(),mode='single');c=build_cases(b,catalog())
  self.assertEqual(len(c),1);self.assertEqual(len(b['pages']),4);self.assertEqual([i['kind'] for i in b['pages']],['pedido','guia','continuação de guia','outro']);self.assertTrue(c[0][2]['pedido']['association_pending']);self.assertFalse(c[0][2]['pedido']['identity_conflict'])
 def test_pdfs_distintos_nao_se_unem_mesmo_nome(self):
  b=read_scan([ROOT/'exemplos_250/pedido_a.pdf',ROOT/'exemplos_250/guia_completa.pdf'],self.data,catalog(),mode='single');self.assertEqual(len(build_cases(b,catalog())),2)
 def test_conflito_preserva_paginas_e_bloqueia_confirmacao(self):
  b=read_scan([ROOT/'exemplos_250/02_dois_pacientes_quatro_paginas.pdf'],self.data,catalog(),mode='single');self.assertEqual(len(build_cases(b,catalog())),1)
  with self.assertRaisesRegex(ValueError,'bloqueado'):confirm_group(b,'Atendimento 1','REVISOR FICTICIO','Conferência fictícia',{i['id'] for i in b['pages']})
  self.assertEqual(len(b['pages']),4)
 def test_cache_reutiliza_leitura_mas_reinterpreta_sem_revisor(self):
  path=ROOT/'exemplos_250/01_um_paciente.pdf';a=read_scan([path],self.data,catalog(),mode='single')
  with patch('scan_import.read_document',side_effect=AssertionError('Releitura indevida')):b=read_scan([path],self.data,catalog(),mode='single')
  self.assertTrue(b['timing']['files'][0]['cache_hit']);self.assertEqual(a['pages'][0]['model']['fields']['Paciente']['value'],b['pages'][0]['model']['fields']['Paciente']['value'])
 def test_chave_cache_invalida_arquivo_config_idioma_modelo(self):
  p=self.data/'d.pdf';p.write_bytes(b'FICTICIO');cfg=self.data/'ocr.json';cfg.write_text('{}');cache=ReadingCache(self.data/'cache');a=cache.key(p,cfg)
  p.write_bytes(b'OUTRO FICTICIO');self.assertNotEqual(a,cache.key(p,cfg));a=cache.key(p,cfg);cfg.write_text('{"tesseract_path":"outro"}');self.assertNotEqual(a,cache.key(p,cfg))
  from reading_cache import signature
  self.assertNotEqual(signature(language='por'),signature(language='por+eng'))
  with tempfile.TemporaryDirectory() as model:
   q=Path(model)/'por.traineddata';q.write_bytes(b'A')
   with patch.dict('os.environ',{'SHIFT_TESSDATA':model}):
    a=signature(language='por');q.write_bytes(b'B');self.assertNotEqual(a,signature(language='por'))
 def test_cache_corrompido_e_falha_ocr_nao_reutilizados(self):
  c=ReadingCache(self.data);(self.data/'bad.json.gz').write_bytes(b'invalido');self.assertIsNone(c.get('bad'));c.put('falha',{'pages':[{'failed':True}]});self.assertIsNone(c.get('falha'))
 def test_cancelamento_nao_devolve_lote_parcial(self):
  event=threading.Event();event.set()
  with self.assertRaises(ReadCancelled):read_scan([ROOT/'exemplos_250/01_um_paciente.pdf'],self.data,[],mode='single',cancel_event=event)
 def test_cancelamento_interrompe_processo_local(self):
  from ocr_runtime import run_local
  import sys
  event=threading.Event();timer=threading.Timer(.2,event.set);timer.start();tick=time.monotonic()
  try:
   with reading_context(event),self.assertRaises(ReadCancelled):run_local([sys.executable,'-c','import time; time.sleep(10)'])
  finally:timer.cancel()
  self.assertLess(time.monotonic()-tick,3)
 def test_paralelismo_ocr_limitado_preserva_ordem_e_coordenadas(self):
  path=self.data/'tres.pdf';doc=pymupdf.open()
  for i in range(3):doc.new_page()
  doc.save(path);doc.close();active=0;maximum=0;lock=threading.Lock()
  def ocr(*args,**kwargs):
   nonlocal active,maximum
   with lock:active+=1;maximum=max(maximum,active)
   time.sleep(.08)
   with lock:active-=1
   return [{'text':t,'box':[20+i*70,30,70+i*70,60],'confidence':100} for i,t in enumerate(['DOCUMENTO','FICTICIO'])]
  with patch('engine_v2.ocr_words',side_effect=ocr):d=read_document(path,workers=2)
  self.assertEqual(maximum,2);self.assertEqual([p['number'] for p in d['pages']],[1,2,3]);self.assertEqual(d['pages'][0]['lines'][0]['words'][0]['box'],[8,12,28,24])
 def test_nao_da_coluna_vizinha_nao_entra_no_nome(self):
  words=[{'text':t,'box':[x,20,x+40,35],'confidence':99} for x,t in [(20,'PESSOA'),(70,'FICTICIA'),(120,'DE'),(165,'OLIVEIRA'),(240,'NÃO')]]
  self.assertEqual(' '.join(w['text'] for w in name_words(words)),'PESSOA FICTICIA DE OLIVEIRA')
 def test_pedido_titulo_alternativo_e_guia_nao_duplicados(self):
  f=self.data/'pedido.pdf';doc=pymupdf.open();p=doc.new_page();p.insert_text((30,40),'PEDIDO DE EXAMES\nPaciente: PESSOA FICTICIA\nCRM 0012345 GO\nExames: HEMOGRAMA\nGLICOSE');doc.save(f);doc.close()
  b=read_scan([f],self.data,[],mode='single');_,docs,m=build_cases(b,[])[0];self.assertEqual(b['pages'][0]['kind'],'pedido');self.assertFalse(docs['guia']['pages']);self.assertFalse(m['guia']['exams'])
 def test_guias_sem_pedido_mantem_origem_e_doze_campos(self):
  b=read_scan([ROOT/'exemplos_250/guia_completa.pdf'],self.data,catalog(),mode='single');_,docs,m=build_cases(b,catalog())[0]
  self.assertFalse(docs['pedido']['pages']);self.assertEqual(len(m['guia']['exams']),5)
  from priority_fields import PRIORITY
  for _,key,_ in PRIORITY:self.assertTrue(m['guia']['fields'][key]['value']);self.assertEqual(m['guia']['fields'][key]['source_document']['page'],1)
