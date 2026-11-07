"""Somente dados sintéticos. Inclui execução real do OCR em português."""
import copy, io, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from engine_v2 import *
from app import load_manifest
ROOT=Path(__file__).resolve().parents[1]
TEXT='''Paciente: Pessoa Sintetica Alfa
Nascimento: 01/02/1995
Fonte pagadora: Convenio Ficticio
Operadora: Operadora Sintetica
Guia: TESTE-001
Medico: Dra. Exemplo
Validade: 31/12/2099
Status: AUTORIZADO
Exames:
Hemograma | 1 | DEMO-HEM
Glicose | 2 | DEMO-GLI
'''

def pdf_text(path,text=TEXT):
    d=pymupdf.open();p=d.new_page();p.insert_text((40,40),text,fontsize=12);d.save(path);d.close()
def scan_image(text=TEXT):
    im=Image.new('RGB',(1900,1500),'white');draw=ImageDraw.Draw(im)
    try:font=ImageFont.truetype('DejaVuSans.ttf',34)
    except OSError:
        try:font=ImageFont.truetype('arial.ttf',34)
        except OSError:font=ImageFont.load_default(size=34)
    draw.multiline_text((65,55),text,font=font,fill='black',spacing=18);return im

class V2(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.cat=catalog_load(ROOT/'catalogo_demo.json')
    def tearDown(self):self.tmp.cleanup()
    def model(self,text=TEXT):
        p=self.dir/'data.txt';p.write_text(text,encoding='utf-8');return parse_document(read_document(p),self.cat)
    def reviewed(self,m):
        m=copy.deepcopy(m)
        for f in m['fields'].values():f['reviewed']=True
        for e in m['exams']:e['reviewed']=True
        for i in m['issues']:i.update(reviewed=True,reason='Conferido no original sintético')
        m['pages_reviewed']=True;return m
    def store_case(self,s,text=TEXT):
        docs={}
        for k,t in [('pedido',text),('guia',text+'\n')]:
            p=self.dir/(k+'.txt');p.write_text(t,encoding='utf-8');docs[k]=read_document(p)
        models={k:self.reviewed(parse_document(d,self.cat)) for k,d in docs.items()}
        return s.add(docs,models,'Teste'),models
    def test_digital_pdf_avoids_ocr(self):
        path=self.dir/'digital.pdf';pdf_text(path)
        with patch('engine_v2.ocr_words',side_effect=AssertionError('OCR desnecessário')):d=read_document(path);m=parse_document(d,self.cat)
        self.assertEqual(d['pages'][0]['method'],'Texto digital');self.assertEqual(m['fields']['Paciente']['value'],'PESSOA SINTETICA ALFA');self.assertEqual(len(m['exams']),2);self.assertEqual(m['exams'][1]['quantidade'],'2');self.assertEqual(m['exams'][1]['page'],1)
    def table(self,columns,values):
        path=self.dir/'table.pdf';d=pymupdf.open();p=d.new_page();p.insert_text((40,40),'Paciente: Pessoa Sintetica Alfa\nNascimento: 01/02/1995\nExames:',fontsize=11)
        for x,t in columns:p.insert_text((x,110),t,fontsize=11)
        for y,row in enumerate(values):
            for (x,_),t in zip(columns,row):p.insert_text((x,140+y*30),t,fontsize=11)
        d.save(path);d.close();return parse_document(read_document(path),self.cat)
    def test_pdf_table_columns_association(self):
        m=self.table([(40,'Codigo'),(170,'Descricao'),(380,'Qtd'),(450,'Material')],[['DEMO-HEM','Hemograma','2','EDTA'],['DEMO-GLI','Glicose','3','Plasma']])
        self.assertEqual([(e['codigo'],e['descricao'],e['quantidade'],e['material']) for e in m['exams']],[('DEMO-HEM','Hemograma','2','EDTA'),('DEMO-GLI','Glicose','3','Plasma')])
    def test_table_reordered_columns(self):
        m=self.table([(40,'Descricao'),(230,'Qtd'),(330,'Codigo')],[['Glicose','4','DEMO-GLI']]);self.assertEqual(m['exams'][0]['quantidade'],'4');self.assertEqual(m['exams'][0]['codigo'],'DEMO-GLI')
    def test_lists_and_no_invented_quantity(self):
        m=self.model(TEXT.split('Exames:')[0]+'Exames:\n- Hemograma\n2. Glicemia em jejum Qtd: 3\n');self.assertEqual(m['exams'][0]['quantidade'],'');self.assertEqual(m['exams'][1]['quantidade'],'3');self.assertTrue(compare_models(m,m,self.cat)['pendencias'])
    def test_real_portuguese_image_ocr_png_and_jpg(self):
        for ext in ['png','jpg']:
            path=self.dir/('scan.'+ext);scan_image().save(path);d=read_document(path);m=parse_document(d,self.cat)
            self.assertIn('PESSOA SINTETICA ALFA',m['fields']['Paciente']['value']);self.assertEqual(len(m['exams']),2);self.assertEqual([e['quantidade'] for e in m['exams']],['1','2']);self.assertTrue(all(e['confidence'] is not None for e in m['exams']))
    def test_scanned_pdf_real_ocr(self):
        path=self.dir/'scan.pdf';b=io.BytesIO();scan_image().save(b,format='PNG');d=pymupdf.open();p=d.new_page(width=760,height=600);p.insert_image(p.rect,stream=b.getvalue());d.save(path);d.close();doc=read_document(path);self.assertIn('OCR',doc['pages'][0]['method']);m=parse_document(doc,self.cat);self.assertEqual(len(m['exams']),2);self.assertEqual(m['fields']['Guia']['value'],'TESTE-001')
    def test_multipage_mixed_only_needed_ocr(self):
        path=self.dir/'mixed.pdf';pdf_text(path,TEXT.split('Exames:')[0]+'Exames:\nHemograma | 1 | DEMO-HEM');d=pymupdf.open(path);p=d.new_page();b=io.BytesIO();scan_image('Exames:\nGlicose | 2 | DEMO-GLI').save(b,format='PNG');p.insert_image(p.rect,stream=b.getvalue());d.save(self.dir/'mixed2.pdf');d.close()
        with patch('engine_v2.ocr_words',wraps=ocr_words) as mock:doc=read_document(self.dir/'mixed2.pdf')
        self.assertEqual(mock.call_count,1);m=parse_document(doc,self.cat);self.assertEqual([e['page'] for e in m['exams']],[1,2]);self.assertEqual([e['codigo'] for e in m['exams']],['DEMO-HEM','DEMO-GLI'])
    def test_hybrid_page_not_silently_skipped(self):
        path=self.dir/'hybrid.pdf';d=pymupdf.open();p=d.new_page();p.insert_text((30,30),'Paciente: Pessoa Sintetica Alfa\nNascimento: 01/02/1995\nMedico: Dra. Exemplo',fontsize=12);b=io.BytesIO();scan_image('Exames:\nGlicose | 2 | DEMO-GLI').save(b,format='PNG');p.insert_image(pymupdf.Rect(20,120,575,780),stream=b.getvalue());d.save(path);d.close()
        with patch('engine_v2.ocr_words',wraps=ocr_words) as mock:doc=read_document(path)
        self.assertEqual(mock.call_count,1);m=parse_document(doc,self.cat);self.assertTrue(any('GLI' in e['codigo'] for e in m['exams']))
    def test_illegible_blank_and_missing_ocr(self):
        p=self.dir/'blank.png';Image.new('RGB',(800,800),'white').save(p);d=read_document(p);m=parse_document(d,self.cat);self.assertTrue(d['pages'][0]['warnings']);self.assertTrue(review_errors({'pedido':m}));self.assertTrue(compare_models(m,m,self.cat)['pendencias'])
        with patch('engine_v2.tesseract_exe',return_value=None):d=read_document(p)
        self.assertIn('Tesseract ausente',d['pages'][0]['warnings'][0])
    def test_real_illegible_blurred_document_blocks(self):
        from PIL import ImageFilter
        path=self.dir/'blurred.png';scan_image().filter(ImageFilter.GaussianBlur(15)).save(path)
        m=parse_document(read_document(path),self.cat)
        self.assertTrue(compare_models(m,m,self.cat)['pendencias'])
        self.assertTrue(review_errors({'pedido':m}))
    def test_low_confidence_requires_row_review(self):
        d={'pages':[{'number':1,'warnings':[],'lines':[{'text':'Exames:','box':[0,0,1,1],'confidence':100,'words':[]},{'text':'Hemograma | 1 | DEMO-HEM','box':[0,2,1,3],'confidence':31,'words':[]}]}]};m=parse_document(d,self.cat);self.assertIn('OCR incerto',m['exams'][0]['notes'][-1]);self.assertFalse(m['exams'][0]['reviewed'])
    def test_fields_aliases_multiple_on_line(self):
        m=self.model(TEXT.replace('Paciente: Pessoa Sintetica Alfa\nNascimento: 01/02/1995','Nome do beneficiario: Pessoa Sintetica Alfa   Data de nascimento: 01/02/1995').replace('Guia:','Numero da guia:').replace('Medico:','Medico solicitante:'));self.assertEqual(m['fields']['Paciente']['value'],'PESSOA SINTETICA ALFA');self.assertEqual(m['fields']['Nascimento']['value'],'01/02/1995');self.assertEqual(m['fields']['Guia']['value'],'TESTE-001')
    def test_patient_mismatch_and_absence(self):
        for text in [TEXT.replace('Pessoa Sintetica Alfa','Pessoa Sintetica Beta'),TEXT.replace('01/02/1995','03/04/1998'),TEXT.replace('Nascimento: 01/02/1995','Nascimento:')]:self.assertTrue(compare_models(self.model(),self.model(text),self.cat)['pendencias'])
    def test_missing_exam_quantity_and_codes(self):
        for text,needle in [(TEXT.replace('Glicose | 2 | DEMO-GLI',''),'Ausente'),(TEXT.replace('Glicose | 2','Glicose | 5'),'Quantidade'),(TEXT.replace('DEMO-GLI','DEMO-ERRADO'),'Código')]:self.assertIn(needle,' '.join(compare_models(self.model(),self.model(text),self.cat)['pendencias']))
    def test_catalog_real_codes_and_equivalence(self):
        cat=copy.deepcopy(self.cat);cat[0]['tuss']='12345678';cat[0]['codigo_shift']='LAB-001';cat[0]['equivalencias']=[{'codigo':'OLD-001','aprovada':True,'aprovado_por':'Responsavel sintetico','aprovado_em':'2026-11-05'}];p=self.dir/'catalog.json';p.write_text(json.dumps(cat),encoding='utf-8');loaded=catalog_load(p);self.assertIsNone(resolve_exam({'descricao':'Hemograma','codigo':'OLD-001'},loaded)[1]);cat[0]['equivalencias'][0]['aprovada']=False;p.write_text(json.dumps(cat),encoding='utf-8')
        with self.assertRaises(ValueError):catalog_load(p)
    def test_catalog_conflict_ambiguous_material(self):
        m=self.model();m['exams'][0]['codigo']='DEMO-GLI';self.assertIn('diferentes',' '.join(compare_models(m,m,self.cat)['pendencias']));cat=self.cat+[dict(self.cat[0],codigo_shift='OTHER')];self.assertIn('ambíguo',' '.join(compare_models(self.model(),self.model(),cat)['pendencias']));m=self.model();m['exams'][0]['material']='Urina';self.assertIn('material',' '.join(compare_models(m,m,self.cat)['pendencias']))
    def test_review_gate_and_success_offline(self):
        s=CaseStore(self.dir/'local.sqlite');cid,m=self.store_case(s)
        with self.assertRaises(ValueError):s.prepare(cid,self.cat,'Teste',1,digest(self.cat),False)
        m['pedido']['exams'][0]['reviewed']=False;s.save(cid,m,'Teste','Desmarcar',1)
        with self.assertRaises(ValueError):s.prepare(cid,self.cat,'Teste',2,digest(self.cat),True)
        m['pedido']['exams'][0]['reviewed']=True;s.save(cid,m,'Teste','Conferido',2)
        with patch('socket.socket',side_effect=AssertionError('Sem rede')):out=s.prepare(cid,self.cat,'Teste',3,digest(self.cat),True)
        self.assertIsNone(out['os_real']);self.assertEqual(out['tipo'],'PRE_CADASTRO_LOCAL_NAO_ENVIADO');self.assertEqual(out['conferencia']['pedido']['exams'][0]['page'],1)
        with self.assertRaises(ValueError):s.prepare(cid,self.cat,'Teste',3,digest(self.cat),True)
        s.db.close()
    def test_restart_stale_catalog_duplicate(self):
        db=self.dir/'local.sqlite';s=CaseStore(db);cid,m=self.store_case(s)
        with self.assertRaises(ValueError):s.prepare(cid,self.cat,'Teste',2,digest(self.cat),True)
        with self.assertRaises(ValueError):s.prepare(cid,self.cat,'Teste',1,'stale',True)
        with self.assertRaises(ValueError):self.store_case(s)
        s.prepare(cid,self.cat,'Teste',1,digest(self.cat),True);cid2,_=self.store_case(s,TEXT+'\n')
        with self.assertRaisesRegex(ValueError,'duplicado'):s.prepare(cid2,self.cat,'Teste',1,digest(self.cat),True)
        s.db.close();s=CaseStore(db);self.assertEqual(s.get(cid)[2],'PREPARADO');self.assertIsNotNone(s.get(cid)[3]);s.db.close()
    def test_batch_pair_safety(self):
        for name in ['a.txt','b.txt','c.txt','d.txt']:(self.dir/name).write_text(TEXT,encoding='utf-8')
        p=self.dir/'lote.csv';p.write_text('pedido;guia\na.txt;b.txt\nc.txt;d.txt',encoding='utf-8');self.assertEqual(len(load_manifest(p)),2)
        for text in ['pedido;guia\na.txt;b.txt\na.txt;d.txt','pedido;guia\n../fora.txt;b.txt','pedido;guia\na.txt;']:
            p.write_text(text,encoding='utf-8')
            with self.assertRaises(ValueError):load_manifest(p)
    def test_same_file_cannot_be_pedido_and_guia(self):
        p=self.dir/'same.txt';p.write_text(TEXT,encoding='utf-8');d=read_document(p);m=self.model();store=CaseStore(self.dir/'same.sqlite')
        with self.assertRaisesRegex(ValueError,'mesmo arquivo'):store.add({'pedido':d,'guia':d},{'pedido':m,'guia':m},'Teste')
        store.db.close()
    def test_encrypted_unsupported(self):
        p=self.dir/'invalid.bin';p.write_bytes(b'hello')
        with self.assertRaises(ValueError):read_document(p)
        d=pymupdf.open();d.new_page();p=self.dir/'protected.pdf';d.save(p,encryption=pymupdf.PDF_ENCRYPT_AES_256,owner_pw='synthetic',user_pw='test');d.close()
        with self.assertRaises(ValueError):read_document(p)
    def test_alerts_block_even_with_reviewed_fields(self):
        s=CaseStore(self.dir/'local.sqlite');cid,m=self.store_case(s);m['pedido']['issues'][0]['reason']='';s.save(cid,m,'Teste','Alerta',1)
        with self.assertRaisesRegex(ValueError,'alertas'):s.prepare(cid,self.cat,'Teste',2,digest(self.cat),True)
        s.db.close()
    def test_repeated_fields_duplicate_exams(self):
        m=self.model(TEXT.replace('Exames:','Paciente: Outra Pessoa Sintetica\nExames:')+'Hemograma | 1 | DEMO-HEM\n');self.assertTrue(any('repetido' in i['message'] for i in m['issues']));self.assertIn('repetido',' '.join(compare_models(m,m,self.cat)['pendencias']))
    def test_duplicate_with_legacy_identity_hash(self):
        store=CaseStore(self.dir/'legacy.sqlite');cid,models=self.store_case(store)
        out=store.prepare(cid,self.cat,'Teste',1,digest(self.cat),True)
        out['identidade_hash']=digest([norm(models['pedido']['fields']['Paciente']['value']),models['pedido']['fields']['Nascimento']['value'],norm(models['guia']['fields']['Guia']['value'])])
        with store.db:store.db.execute('UPDATE casos_v2 SET output=? WHERE id=?',(json.dumps(out),cid))
        other,_=self.store_case(store,TEXT+'\n')
        with self.assertRaisesRegex(ValueError,'duplicado'):store.prepare(other,self.cat,'Teste',1,digest(self.cat),True)
        store.db.close()
if __name__=='__main__':unittest.main()
