"""Relatório por campo APENAS para fixtures fictícias cujo SHA256 é verificado."""
from pathlib import Path
import hashlib,json
from gerar_exemplos_tiss import VALUES,catalog,NAMES,CODES
from tiss import SCHEMA
from engine_v2 import read_document,parse_document
ROOT=Path(__file__).resolve().parent


def main():
 fixtures=ROOT/'exemplos_tiss'
 manifest=json.loads((fixtures/'manifesto_sha256.json').read_text())
 results=[]
 cases={'01_completa.pdf':{},'01_completa.png':{},'01_escaneada.pdf':{},'02_sem_autorizacao.pdf':{4:'',5:'',6:'',7:''},
        '03_autorizada_zero.pdf':{},'04_duas_tabelas.pdf':{},'06_multipagina.pdf':{},
        '07_outro_paciente.pdf':{10:'PESSOA FICTICIA BETA',8:'0000099999'},'10_crm_ilegivel.pdf':{17:''},'11_unimed.pdf':{}}
 for filename,overrides in cases.items():
  path=fixtures/filename
  if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest.get(filename):raise ValueError('Fixture alterada. Não processar documentos reais neste relatório.')
  model=parse_document(read_document(path),catalog())
  for number,expected in {**VALUES,**overrides}.items():
   key=SCHEMA[number][0];field=model['fields'][key]
   results.append({'arquivo_ficticio':filename,'campo_tiss':number,'nome':key,'esperado':expected,'obtido':field['value'],
                   'passou':field['value']==expected and (not expected or bool(field['page'] and field['box'])),
                   'origem':{'pagina':field['page'],'regiao':field['box'],'trecho':field['snippet']}})
  for index,exam in enumerate(model['exams']):
   expected_values={'codigo':CODES[index],'descricao':NAMES[index],'quantidade_solicitada':'1',
                    'quantidade_autorizada':'' if filename=='02_sem_autorizacao.pdf' else '0' if filename=='03_autorizada_zero.pdf' and index==0 else '1'}
   for key,expected in expected_values.items():
    origin=exam.get('cell_origins',{}).get(key,{})
    results.append({'arquivo_ficticio':filename,'procedimento':index+1,'nome':key,'esperado':expected,'obtido':exam.get(key,''),
                    'passou':exam.get(key,'')==expected and (not expected or bool(origin.get('page') and origin.get('box'))),'origem':origin})
 report={'somente_dados_ficticios':True,'verificacoes':len(results),'passaram':sum(x['passou'] for x in results),'falharam':sum(not x['passou'] for x in results),'campos':results}
 (ROOT/'docs/RELATORIO_CAMPOS_2_3.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('Verificações por campo:',report['verificacoes'],'aprovadas:',report['passaram'],'falhas:',report['falharam'])
 if report['falharam']:raise ValueError('Relatório contém falhas de extração ou origem.')

if __name__=='__main__':main()
