"""Relatório esperado/encontrado, valores e origem. Apenas PDFs sintéticos gerados aqui."""
import json,tempfile
from pathlib import Path
from gerar_exemplos_auditoria import main as generate,PATIENT
from gerar_exemplos_tiss import catalog,VALUES,CODES,NAMES
from scan_import import read_scan,build_cases,confirm_group
from engine_v2 import parse_document,read_document,compare_models
from tiss import SCHEMA
ROOT=Path(__file__).resolve().parent


def main():
    results=[]
    def check(case,key,expected,actual,field=None,page=None):
        origin=(field or {}).get('source_document',{})
        sourced=page is None or (origin.get('page')==page and bool((field or {}).get('box')))
        results.append({'caso':case,'campo':key,'esperado':expected,'encontrado':actual,'passou':expected==actual and sourced,
            'origem':{'arquivo':origin.get('file'),'pagina':origin.get('page'),'regiao':(field or {}).get('box'),'trecho':(field or {}).get('snippet')}})
    with tempfile.TemporaryDirectory() as tmp:
        files=generate(Path(tmp)/'pdfs');cat=catalog()
        def batch(filename):return read_scan([files/filename],Path(tmp)/'dados',cat,mode='single')
        for filename,types,p_page,g_page in [('01_quatro_paginas.pdf',['pedido','guia','continuação de guia','outro'],1,2),('02_ordem_invertida.pdf',['guia','pedido'],2,1),('03_nome_composto.pdf',['pedido','guia'],1,2)]:
            b=batch(filename);c=build_cases(b,cat);_,docs,m=c[0]
            check(filename,'Tipos por página',types,[i['kind'] for i in b['pages']]);check(filename,'Atendimentos provisórios',1,len(c));check(filename,'Páginas preservadas',len(types),sum(len(d['pages']) for d in docs.values()))
            check(filename,'Original integral preservado',True,next(iter(b['sources'].values()))['sha256']==read_document(files/filename)['sha256'] and Path(next(iter(b['sources'].values()))['local_path']).read_bytes()==(files/filename).read_bytes())
            for role,page in [('pedido',p_page),('guia',g_page)]:check(filename,'Paciente '+role,PATIENT,m[role]['fields']['Paciente']['value'],m[role]['fields']['Paciente'],page)
            for number,expected in {**VALUES,10:PATIENT,19:'225125'}.items():
                field=m['guia']['fields'][SCHEMA[number][0]];check(filename,str(number)+' '+SCHEMA[number][0],expected,field['value'],field,g_page)
            check(filename,'Exames no pedido',5,len(m['pedido']['exams']));check(filename,'Exames na guia',5,len(m['guia']['exams']))
            for i,(code,name) in enumerate(zip(CODES,NAMES)):
                exam=m['guia']['exams'][i];page=3 if filename.startswith('01_') and i>=3 else g_page
                for key,expected in [('codigo',code),('descricao',name),('quantidade_solicitada','1'),('quantidade_autorizada','1')]:check(filename,'Exame '+str(i+1)+' '+key,expected,exam.get(key,''),exam['cell_origins'][key],page)
        for i,number in enumerate(['12','00123','0012345','0001234567'],1):
            filename=f'crm_tamanho_{i}.pdf';_,_,models=build_cases(batch(filename),cat)[0]
            for key,expected in [('Conselho','CRM'),('Número conselho',number),('UF conselho','GO'),('CBO','225125')]:
                field=models['guia']['fields'][key];check('04_conselho '+filename,key,expected,field['value'],field,1)
        model=parse_document(read_document(files/'05_guia_incompleta.pdf'),cat)
        for key in ['Guia principal','Senha autorização','Validade senha']:check('05_guia_incompleta',key,'',model['fields'][key]['value'])
        check('05_guia_incompleta','Quantidades autorizadas',['']*5,[e['quantidade_autorizada'] for e in model['exams']])
        _,_,m=build_cases(batch('06_quantidades.pdf'),cat)[0];r=compare_models(m['pedido'],m['guia'],cat)
        check('06_exames','Solicitadas',['1']*5,[e['quantidade_solicitada'] for e in m['guia']['exams']]);check('06_exames','Autorizadas',['0','1','1','1','1'],[e['quantidade_autorizada'] for e in m['guia']['exams']]);check('06_exames','Primeira comparação','Não autorizado',r['exames'][0]['situacao'])
        b=batch('08_conflito.pdf')
        try:confirm_group(b,'Atendimento 1','REVISOR FICTICIO','Teste de conflito sintético',{i['id'] for i in b['pages']});blocked=False
        except ValueError:blocked=True
        check('08_conflito','Confirmação bloqueada',True,blocked)
        check('09_incerto','Tipo','incerto',batch('09_incerto.pdf')['pages'][0]['kind'])
        m=parse_document(read_document(files/'10_pedido_estruturado.pdf'),cat)
        check('10_pedido_estruturado','Tipo','pedido',m['document_type']);check('10_pedido_estruturado','Exames preservados',5,len(m['exams']));check('10_pedido_estruturado','Conselho preservado','CRM',m['fields']['Conselho']['value'])
        m=parse_document(read_document(files/'11_sem_uf.pdf'),cat);check('UF ausente','Sem inferir GO','',m['fields']['UF conselho']['value'])
        m=parse_document(read_document(files/'12_carimbo_divergente.pdf'),cat);check('Carimbo conflitante','Número pendente','',m['fields']['Número conselho']['value']);check('Carimbo conflitante','Não virou sexto exame',5,len(m['exams']))
    gui=json.loads((ROOT/'docs/RELATORIO_INTERFACE_2_4_4.json').read_text())
    gui_names={x['teste'] for x in gui['verificacoes']}
    for name in ['test_corrigir_crm_salvar_resolve_e_avanca','test_resolver_quantidade_por_botao_atualiza_e_avanca','test_quatro_paginas_campos17_cbo_visiveis_ate_pre_cadastro']:
        subset=[x for x in gui['verificacoes'] if x['teste']==name]
        check('07_conferência e 09_interface',name+' chegou a PREPARADO',True,bool(subset) and all(x['passou'] for x in subset) and any(x['encontrado']=='PREPARADO' for x in subset))
    check('09_interface','Casos gráficos distintos',6,len(gui_names))
    report={'somente_sinteticos':True,'verificacoes':len(results),'passaram':sum(x['passou'] for x in results),'falharam':sum(not x['passou'] for x in results),'resultados':results}
    (ROOT/'docs/RELATORIO_AUDITORIA_2_4_4.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='resultados'},ensure_ascii=False))
    if report['falharam']:raise ValueError('Falha de valor, origem ou fluxo: consulte o relatório por campo.')

if __name__=='__main__':main()
