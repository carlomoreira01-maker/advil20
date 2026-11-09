"""Gabarito reproduzível da interface principal; gera e usa só documentos fictícios."""
import argparse,json,tempfile,time,tkinter as tk
from pathlib import Path
from unittest.mock import patch
from core import norm
from workbench import create_workbench
from gerar_exemplos_250 import main as generate,CLINICAL,EXECUTOR,PATIENTS,PRIORITY
from gerar_exemplos_tiss import VALUES,catalog
from tiss import SCHEMA
from draft_workflow import load_draft
from tests.test_mapping_sim import profile

ROOT=Path(__file__).resolve().parent


def main(capture=False):
    fields=[];checks=[]
    def check(name,expected,actual):checks.append({'verificacao':name,'esperado':expected,'encontrado':actual,'passou':expected==actual})
    def wait(app,root):
        end=time.monotonic()+180
        while app.busy and time.monotonic()<end:root.update();time.sleep(.01)
        if app.busy:raise RuntimeError('A leitura fictícia não terminou no tempo previsto.')
        root.update()
    def click(button,root):
        # Eventos de mouse percorrem os bindings do widget, além dos testes invoke.
        root.update()
        ancestor=button
        while ancestor is not None and ancestor!=ui.preview_area:ancestor=getattr(ancestor,'master',None)
        if ancestor==ui.preview_area:
            height=max(1,ui.preview_area.winfo_reqheight());ui.preview_canvas.yview_moveto(max(0,(button.winfo_rooty()-ui.preview_area.winfo_rooty()-30)/height));root.update()
        button.event_generate('<Enter>');button.event_generate('<ButtonPress-1>',x=8,y=8);button.event_generate('<ButtonRelease-1>',x=8,y=8);root.update()
    def screenshot(root,name):
        if not capture:return
        from PIL import ImageGrab
        root.lift();root.update();x,y=root.winfo_rootx(),root.winfo_rooty();ImageGrab.grab().crop((x,y,x+root.winfo_width(),y+root.winfo_height())).save(ROOT/'docs'/name)
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp);files=generate(base/'exemplos')
        def open_ui(index):
            root=tk.Tk();app=create_workbench(root,base/('dados_'+str(index)));app.catalog=catalog();root.update();return root,app,app.workspace
        def import_file(root,app,ui,name,scope='single'):
            ui.scope_tabs.select(0 if scope=='single' else 1);ui.advanced_grouping.set(scope=='multiple');root.update()
            with patch('app.filedialog.askopenfilenames',return_value=[str(files/name)]):click(ui.import_buttons[scope],root)
            wait(app,root)
        expected={**VALUES,10:PATIENTS[0],23:CLINICAL,30:EXECUTOR}
        scenarios=[('01_um_paciente.pdf',2,{},{}),('03_campos_vazios.pdf',2,{3:'',5:'',7:'',30:''},{3:'empty',5:'empty',7:'empty',30:'empty'}),
                   ('05_leitura_incerta.pdf',2,{17:''},{17:'uncertain'}),('04_guia_girada.pdf',1,{},{}),('guia_sem_campo30.pdf',1,{30:''},{30:'not_found'})]
        for index,(name,page,changes,states) in enumerate(scenarios):
            root,app,ui=open_ui(index)
            try:
                import_file(root,app,ui,name);click(ui.nav_buttons[2],root)
                for n in [*PRIORITY,16]:
                    key=SCHEMA[n][0];field=app.models['guia']['fields'][key];src=field.get('source_document',{});wanted=changes.get(n,expected[n]);widget=ui.inputs[key];visible=widget.get('1.0','end-1c') if n==23 else widget.get()
                    actual_state=field.get('extraction_state','not_found');expected_state=states.get(n,'identified')
                    located=(src.get('page')==page and bool(field.get('box'))) if expected_state!='not_found' else not field.get('page')
                    expected_visible=field['value'] or ('' if n==23 else 'Não identificado')
                    passed=norm(wanted)==norm(field['value']) and visible==expected_visible and actual_state==expected_state and located
                    fields.append({'documento_ficticio':name,'numero_tiss':n,'campo':key,'esperado':wanted,'extraido':field['value'],'esperado_interface':expected_visible,'preenchido_na_interface':visible,
                        'estado_esperado':expected_state,'estado_encontrado':actual_state,'passou':passed,
                        'origem':{'arquivo':Path(src['file']).name if src.get('file') else None,'pagina_original':src.get('page'),'regiao':field.get('box'),'trecho':field.get('snippet')}})
                if index==0:
                    screenshot(root,'TELA_DADOS_2_5_0.png');click(ui.nav_buttons[3],root);screenshot(root,'TELA_EXAMES_2_5_0.png')
                click(ui.nav_buttons[4],root);click(ui.next_button,root)
                check(name+' rascunho salvo com eventos de mouse',True,load_draft(app.store,app.cid) is not None)
                check(name+' navegação não prepara automaticamente',None,app.store.get(app.cid)[3])
                if index==1:ui.preview_canvas.yview_moveto(0);root.update();screenshot(root,'TELA_RASCUNHO_2_5_0.png')
                if index==2:
                    app.actor.set('REVISOR FICTICIO');click(ui.nav_buttons[2],root);click(ui.correct_information_button,root)
                    entry=ui.inputs['Número conselho'];check('Correção leva ao campo incerto',True,root.focus_get()==entry);entry.delete(0,'end');entry.insert(0,'0012345');click(ui.save_corrections_button,root)
                    check('Correção manual persiste no banco','0012345',app.store.get(app.cid)[0]['models']['guia']['fields']['Número conselho']['value'])
                    click(ui.nav_buttons[4],root);check('Correção atualiza pendência do número',False,any('Número conselho não identificado' in s for s in ui.preview['pendencias']))
            finally:app.store.db.close();root.destroy()
        root,app,ui=open_ui('lote')
        try:
            import_file(root,app,ui,'02_dois_pacientes_quatro_paginas.pdf','multiple');check('Quatro páginas de duas pessoas',2,len(app.cases.get_children()))
            groups=[]
            for cid in app.cases.get_children():
                ui.choose_case(cid);obj=app.store.get(cid)[0];groups.append((obj['models']['guia']['fields']['Paciente']['value'],sum(len(d['pages']) for d in obj['docs'].values())))
            check('Duas fichas, duas páginas por pessoa',sorted((p,2) for p in PATIENTS),sorted(groups));click(ui.nav_buttons[0],root);screenshot(root,'TELA_INICIO_2_5_0.png')
            click(ui.batch_drafts_button,root);check('Rascunhos do lote',2,sum(load_draft(app.store,cid) is not None for cid in app.cases.get_children()))
        finally:app.store.db.close();root.destroy()
        root,app,ui=open_ui('completo')
        try:
            import_file(root,app,ui,'01_um_paciente.pdf');app.actor.set('REVISOR FICTICIO');app.review_reason.set('Conferência fictícia dos originais, dados, exames e alertas')
            for row in app.catalog:row['codigo_shift']='SIM-LAB-'+row['tuss']
            click(ui.nav_buttons[1],root)
            for b in ui.page_panel.buttons:click(b,root)
            with patch('app.messagebox.askyesno',return_value=True):click(ui.confirm_pages_button,root)
            screenshot(root,'TELA_DOCUMENTOS_2_5_0.png');app.selected_profile=profile();click(ui.nav_buttons[3],root);click(ui.compare_button,root);click(ui.nav_buttons[4],root)
            ui.data_review.set(True);ui.exams_review.set(True);click(ui.validate_button,root);check('Sem pendências após revisão fictícia',[],app.comparison_errors)
            ui.final_confirm.set(True);click(ui.prepare_button,root);check('Preparo local pelo fluxo principal','PREPARADO',app.store.get(app.cid)[2]);out=app.store.get(app.cid)[3]
            check('Cinco exames na demonstração',5,len(out['exames']));check('Nenhuma O.S. real',None,out['os_real']);ui.preview_canvas.yview_moveto(0);root.update();screenshot(root,'TELA_PREPARADO_2_5_0.png')
        finally:app.store.db.close();root.destroy()
    report={'somente_sinteticos':True,'plataforma':'Linux / Tkinter real / Tesseract local','eventos_mouse':True,'campos':fields,'fluxo':checks,
            'verificacoes':len(fields)+len(checks),'passaram':sum(r['passou'] for r in fields+checks),'falharam':sum(not r['passou'] for r in fields+checks)}
    (ROOT/'docs/RELATORIO_INTERFACE_2_5_0.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['campos','fluxo']},ensure_ascii=False))
    if report['falharam']:raise ValueError('Há divergências no gabarito; consulte o relatório por campo/interface.')

if __name__=='__main__':
    args=argparse.ArgumentParser();args.add_argument('--capturar',action='store_true');main(args.parse_args().capturar)
