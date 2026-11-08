"""Gabarito de pedidos carimbados; nenhum documento externo é lido."""
import copy,json,tempfile
from pathlib import Path
from gerar_exemplos_carimbo import main as fixtures
from gerar_exemplos_tiss import catalog,NAMES
from scan_import import read_scan,build_cases,merge_reprocessed
from engine_v2 import read_document,parse_document
ROOT=Path(__file__).resolve().parent

def main():
    checks=[]
    def check(case,key,expected,actual,field=None,page=None):
        src=(field or {}).get('source_document',{});origin=page is None or (src.get('page')==page and bool((field or {}).get('box')))
        checks.append({'caso':case,'campo':key,'esperado':expected,'encontrado':actual,'passou':actual==expected and origin,
                      'origem':{'documento':src.get('file'),'pagina':src.get('page'),'regiao':(field or {}).get('box'),'trecho':(field or {}).get('snippet')}})
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp);files=fixtures(base/'exemplos');cat=catalog()
        def batch(name):return read_scan([files/name],base/'dados',cat,mode='single')
        for filename,types,page in [('01_pedido_carimbo_e_guia.pdf',['pedido','guia'],1),('02_guia_antes_pedido.pdf',['guia','pedido'],2),('03_quatro_paginas.pdf',['pedido','guia','continuação de guia','outro'],1),('05_pedido_girado.pdf',['pedido'],1)]:
            b=batch(filename);c=build_cases(b,[]);_,docs,m=c[0]
            check(filename,'Classificação',types,[i['kind'] for i in b['pages']]);check(filename,'Atendimentos',1,len(c));check(filename,'Páginas',len(types),sum(len(d['pages']) for d in docs.values()))
            for key,value in [('Paciente','PESSOA FICTICIA ALFA'),('Medico','DRA EXEMPLO SINTETICA'),('Conselho','CRM'),('Número conselho','0012345'),('UF conselho','GO')]:
                f=m['pedido']['fields'][key];check(filename,key,value,f['value'],f,page)
            check(filename,'Exames',5,len(m['pedido']['exams']))
            for i,(e,name) in enumerate(zip(m['pedido']['exams'],NAMES)):
                check(filename,'Exame '+str(i+1),name,e['descricao'],e,page);check(filename,'Quantidade '+str(i+1),'1',e['quantidade']);check(filename,'Sem código inventado '+str(i+1),'',e['codigo'])
        for filename in ['consentimento_carimbo.pdf','receita_carimbo.pdf','pedido_sem_carimbo.pdf']:check(filename,'Tipo incerto preservado','incerto',batch(filename)['pages'][0]['kind'])
        m=parse_document(read_document(files/'pedido_sem_quantidades.pdf'),[]);check('Quantidade ausente','Não presumir 1',['']*5,[e['quantidade'] for e in m['exams']])
        old=batch('01_pedido_carimbo_e_guia.pdf');old['pages'][0]['kind']='guia';new=batch('01_pedido_carimbo_e_guia.pdf');merge_reprocessed(new,old);check('Reprocessamento','Tipo automático corrigido','pedido',new['pages'][0]['kind'])
        old['pages'][0].update(kind='outro',classification_origin='manual',reviewed=True,reason='Revisão fictícia');new=batch('01_pedido_carimbo_e_guia.pdf');merge_reprocessed(new,old);check('Reprocessamento','Tipo humano mantido','outro',new['pages'][0]['kind'])
    report={'somente_sinteticos':True,'verificacoes':len(checks),'passaram':sum(x['passou'] for x in checks),'falharam':sum(not x['passou'] for x in checks),'resultados':checks}
    (ROOT/'docs/RELATORIO_CARIMBO_2_4_5.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in report.items() if k!='resultados'})
    if report['falharam']:raise ValueError('Há falhas de valores/origens; veja o gabarito.')

if __name__=='__main__':main()
