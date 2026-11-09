"""Valida o aplicativo real e, opcionalmente, o navegador; somente dados sintéticos."""
import argparse,json,tempfile,time,tkinter as tk
from pathlib import Path
from unittest.mock import patch
from workbench import create_workbench
from gerar_exemplos_tiss import catalog
ROOT=Path(__file__).resolve().parent
def main(browser=False):
    import validar_interface_250
    old=ROOT/'docs/RELATORIO_INTERFACE_2_5_0.json';backup=old.read_bytes()
    try:
        validar_interface_250.main();(ROOT/'docs/RELATORIO_CAMPOS_INTERFACE_2_5_2.json').write_bytes(old.read_bytes())
    finally:old.write_bytes(backup)
    rows=[]
    def check(name,expected,actual):rows.append({'verificacao':name,'esperado':expected,'encontrado':actual,'passou':expected==actual})
    with tempfile.TemporaryDirectory() as tmp:
        root=tk.Tk();app=create_workbench(root,Path(tmp)/'dados');app.catalog=catalog();ui=app.workspace
        try:
            with patch('app.filedialog.askopenfilenames',return_value=[str(ROOT/'exemplos_2_4_2/01_um_atendimento_quatro_paginas.pdf')]):ui.import_buttons['single'].invoke()
            end=time.monotonic()+90
            while app.busy and time.monotonic()<end:root.update();time.sleep(.01)
            check('Leitura concluída',False,app.busy);check('Uma ficha para o PDF',1,len(app.cases.get_children()));check('Quatro páginas preservadas',4,len(ui.page_panel.items));check('Classificação',['pedido','guia','continuação de guia','outro'],[i['kind'] for i in ui.page_panel.items])
            ui.go(1);root.update()
            from PIL import ImageGrab
            ImageGrab.grab().crop((root.winfo_rootx(),root.winfo_rooty(),root.winfo_rootx()+root.winfo_width(),root.winfo_rooty()+root.winfo_height())).save(ROOT/'docs/AGRUPAMENTO_2_5_2.png')
            ui.go(4);ui.save_draft_button.invoke();root.update();check('Rascunho acessível',True,'Rascunho salvo' in ui.notice.get());check('Sem preparo automático',None,app.store.get(app.cid)[3])
        finally:app.store.db.close();root.destroy()
    report={'somente_sinteticos':True,'verificacoes':rows,'passaram':sum(r['passou'] for r in rows),'falharam':sum(not r['passou'] for r in rows)}
    (ROOT/'docs/FLUXO_INTERFACE_2_5_2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    if report['falharam']:raise ValueError('Falha de fluxo da interface.')
    if browser:
        from rpa_simulada import SimulatedRPA
        from lis_simulado import demo_data,approve,APPROVALS
        data=demo_data();rpa=SimulatedRPA(data,approve(data,'REVISOR FICTICIO',{k:True for k in APPROVALS}),headless=True);rows=[]
        try:
            rpa.search_patient();p=rpa.page;check('Paciente existente localizado',True,'SIM-P1' in p.locator('#patient').inner_text());check('Identidade não confirmada automaticamente',False,p.locator('#identity').is_checked())
            p.locator('#identity').check();p.locator('#select').click();p.wait_for_function('window.identityConfirmed===true');rpa.fill_order()
            for key in ['guide','main_guide','operator_guide','password','crm','uf','payer']:check(key,data[key],p.locator('#'+key).input_value())
            check('Dois anexos sintéticos',2,p.evaluate('window.attachments.length'));check('Cinco procedimentos',5,len(p.locator('#exams').input_value().splitlines()));check('Confirmação final não automática',False,p.locator('#final').is_checked())
            p.locator('#final').check();result=rpa.submit_after_human();check('Paciente reutilizado','SIM-P1',result['patient_id']);check('Médico existente','SIM-M1',result['doctor_id']);check('Nenhuma O.S. real',None,result['os_real']);check('Cinco etiquetas demonstrativas',5,p.locator('.label').count())
            p.screenshot(path=str(ROOT/'docs/RPA_DEMO_2_5_2.png'),full_page=True)
            try:rpa.submit_after_human();blocked=False
            except ValueError:blocked=True
            check('Repetição bloqueada',True,blocked);check('Uma única O.S. fictícia',1,rpa.server.state.db.execute('SELECT COUNT(*) FROM os_demo').fetchone()[0])
        finally:rpa.close()
        report={'somente_sinteticos':True,'confirmacoes_humanas_simuladas_no_teste':True,'verificacoes':rows,'passaram':sum(r['passou'] for r in rows),'falharam':sum(not r['passou'] for r in rows)}
        (ROOT/'docs/RPA_INTERFACE_2_5_2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        if report['falharam']:raise ValueError('Falha de RPA fictícia.')
    print('Validação concluída com dados exclusivamente sintéticos.')
if __name__=='__main__':
    args=argparse.ArgumentParser();args.add_argument('--navegador',action='store_true');main(args.parse_args().navegador)
