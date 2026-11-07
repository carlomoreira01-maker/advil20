"""Relatório por valor e origem física, apenas fixtures sintéticas verificadas por SHA."""
from pathlib import Path
import hashlib,json,tempfile
from scan_import import read_scan,build_cases,confirm_group
from gerar_exemplos_tiss import catalog,VALUES,CODES,NAMES
from tiss import SCHEMA
ROOT=Path(__file__).resolve().parent


def main():
    base=ROOT/'exemplos_2_4_2';manifest=json.loads((base/'manifesto_sha256.json').read_text());results=[]
    def verify(file):
        if hashlib.sha256(file.read_bytes()).hexdigest()!=manifest.get(file.name):raise ValueError('Fixture alterada. Não usar documentos reais neste relatório.')
    def check(file,key,expected,obtained,origin=None,page=None):
        physical=(origin or {}).get('source_document',{})
        provenance=page is None or (physical.get('page')==page and bool((origin or {}).get('box')))
        results.append({'documento_ficticio':file,'campo':key,'esperado':expected,'obtido':obtained,'passou':expected==obtained and provenance,
            'origem':{'arquivo':physical.get('file'),'pagina_original':physical.get('page'),'regiao':(origin or {}).get('box'),'trecho':(origin or {}).get('snippet')}})
    for filename in ['01_um_atendimento_quatro_paginas.pdf','03_quatro_paginas_escaneadas.pdf']:
        file=base/filename;verify(file)
        with tempfile.TemporaryDirectory() as tmp:
            batch=read_scan([file],tmp,catalog(),mode='single');cases=build_cases(batch,catalog());_,docs,m=cases[0]
            check(filename,'Quantidade de fichas',1,len(cases));check(filename,'Páginas preservadas',4,sum(len(d['pages']) for d in docs.values()))
            check(filename,'Arquivo integral preservado',True,Path(next(iter(batch['sources'].values()))['local_path']).read_bytes()==file.read_bytes())
            for index,kind in enumerate(['pedido','guia','continuação de guia','outro']):check(filename,'Tipo página '+str(index+1),kind,batch['pages'][index]['kind'])
            check(filename,'Nome completo impresso no pedido','PESSOA FICTICIA ALFA',m['pedido']['fields']['Paciente']['value'],m['pedido']['fields']['Paciente'],1)
            for n,expected in VALUES.items():
                if n==10:expected='PESSOA FICTICIA'
                field=m['guia']['fields'][SCHEMA[n][0]];check(filename,str(n)+' '+SCHEMA[n][0],expected,field['value'],field,2)
            check(filename,'Número de procedimentos',5,len(m['guia']['exams']))
            for index,(code,name) in enumerate(zip(CODES,NAMES)):
                if index>=len(m['guia']['exams']):continue
                exam=m['guia']['exams'][index]
                for key,value in [('codigo',code),('descricao',name),('quantidade_solicitada','1'),('quantidade_autorizada','1')]:
                    check(filename,'Procedimento '+str(index+1)+' '+key,value,exam.get(key,''),exam.get('cell_origins',{}).get(key,{}),2 if index<3 else 3)
            check(filename,'Associação ainda provisória',True,m['pedido']['association_pending'])
            batch['pages'][3].update(reviewed=True,reason='Conferi anexo sintético')
            confirm_group(batch,'Atendimento 1','REVISOR FICTICIO','Conferi quatro páginas e identificadores',{i['id'] for i in batch['pages']})
            check(filename,'Associação confirmada explicitamente',False,build_cases(batch,catalog())[0][2]['pedido']['association_pending'])
    for filename in ['04_nome_espacado.pdf','05_coluna_vizinha.pdf']:
        from engine_v2 import read_document,parse_document
        file=base/filename;verify(file);model=parse_document(read_document(file),[]);field=model['fields']['Paciente']
        origin={**field,'source_document':{'file':filename,'page':field['page']}}
        check(filename,'Nome completo sem coluna vizinha','PRIMEIRO SEGUNDO TERCEIRO',field['value'],origin,1)
    with tempfile.TemporaryDirectory() as tmp:
        file=base/'02_identificadores_incompativeis.pdf';verify(file);b=read_scan([file],tmp,[],mode='single')
        try:confirm_group(b,'Atendimento 1','REVISOR FICTICIO','Tentativa fictícia de confirmar conflito',{i['id'] for i in b['pages']});blocked=False
        except ValueError:blocked=True
        check(file.name,'Conflito bloqueia confirmação',True,blocked)
    report={'somente_sinteticos':True,'verificacoes':len(results),'passaram':sum(r['passou'] for r in results),'falharam':sum(not r['passou'] for r in results),'resultados':results}
    (ROOT/'docs/RELATORIO_CAMPOS_2_4_2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print({k:v for k,v in report.items() if k!='resultados'})
    if report['falharam']:raise ValueError('Há falhas de valor ou origem física; consulte o relatório por campo.')

if __name__=='__main__':main()
