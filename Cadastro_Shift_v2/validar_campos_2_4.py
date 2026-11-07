"""Relatório de valores e origem; somente fixtures sintéticas com hashes aprovados."""
import hashlib,json,tempfile
from pathlib import Path
from scan_import import read_scan,build_cases
from gerar_exemplos_tiss import VALUES,CODES,NAMES,catalog
from tiss import SCHEMA
ROOT=Path(__file__).resolve().parent


def main():
 fixture=ROOT/'exemplos_2_4';manifest=json.loads((fixture/'manifesto_sha256.json').read_text())
 rows=[]
 cases={'01_pedido_e_guia.pdf':[('PESSOA FICTICIA ALFA',2)],'02_guia_antes_pedido.pdf':[('PESSOA FICTICIA ALFA',1)],
        '03_quatro_paginas_misturadas.pdf':[('PESSOA FICTICIA BETA',1),('PESSOA FICTICIA ALFA',3)],
        '04_guia_girada_e_pedido.pdf':[('PESSOA FICTICIA ALFA',1)]}
 for filename,expected_cases in cases.items():
  path=fixture/filename
  if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest.get(filename):raise ValueError('Fixture alterada; não usar documentos reais neste relatório.')
  with tempfile.TemporaryDirectory() as tmp:
   batch=read_scan([path],tmp,catalog());models=build_cases(batch,catalog())
   for patient,page in expected_cases:
    m=next(m for _,_,m in models if m['guia']['fields']['Paciente']['value']==patient)
    expected={**VALUES,10:patient,8:'0000099999' if patient.endswith('BETA') else VALUES[8]}
    def check(name,expected,obtained,origin):
     physical=origin.get('source_document',{})
     rows.append({'arquivo_ficticio':filename,'paciente_ficticio':patient,'campo':name,'esperado':expected,'obtido':obtained,
       'passou':obtained==expected and physical.get('page')==page and bool(origin.get('box')),
       'origem':{'arquivo':physical.get('file'),'pagina_original':physical.get('page'),'regiao':origin.get('box'),'trecho':origin.get('snippet')}})
    for n,value in expected.items():
     field=m['guia']['fields'][SCHEMA[n][0]];check(str(n)+' '+SCHEMA[n][0],value,field['value'],field)
    for i,(code,name) in enumerate(zip(CODES,NAMES)):
     exam=m['guia']['exams'][i]
     for key,value in [('codigo',code),('descricao',name),('quantidade_solicitada','1'),('quantidade_autorizada','1')]:
      check('Procedimento '+str(i+1)+' '+key,value,exam.get(key,''),exam.get('cell_origins',{}).get(key,{}))
 report={'somente_sinteticos':True,'verificacoes':len(rows),'passaram':sum(r['passou'] for r in rows),'falharam':sum(not r['passou'] for r in rows),'campos':rows}
 (ROOT/'docs/RELATORIO_CAMPOS_2_4.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print({k:v for k,v in report.items() if k!='campos'})
 if report['falharam']:raise ValueError('Existem falhas por campo ou origem no relatório.')

if __name__=='__main__':main()
