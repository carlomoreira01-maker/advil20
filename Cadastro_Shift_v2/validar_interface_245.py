"""Validação reproduzível na interface real, SOMENTE com documentos gerados fictícios."""
import json,tempfile,time,tkinter as tk
from pathlib import Path
from unittest.mock import patch
from app import App
from gerar_exemplos_carimbo import main as fixtures
from gerar_exemplos_tiss import catalog
from tests.test_mapping_sim import profile

ROOT=Path(__file__).resolve().parent

def main(capture=False):
    checks=[]
    def check(key,expected,actual):checks.append({'verificacao':key,'esperado':expected,'encontrado':actual,'passou':expected==actual})
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp);files=fixtures(base/'exemplos');root=tk.Tk();app=App(root,base/'dados');app.catalog=catalog()
        for row in app.catalog:row['codigo_shift']='SIM-LAB-'+row['tuss']
        try:
            with patch('app.filedialog.askopenfilenames',return_value=[str(files/'01_pedido_carimbo_e_guia.pdf')]):app.import_scan_button.invoke()
            end=time.monotonic()+120
            while app.busy and time.monotonic()<end:root.update();time.sleep(.01)
            check('Importação terminou',False,app.busy);root.update()
            check('Uma ficha',1,len(app.cases.get_children()));check('Duas páginas',2,len(app.page_panel.items))
            check('Tipos das páginas',['pedido','guia'],[i['kind'] for i in app.page_panel.items])
            app.save_review_button.invoke();root.update();check('Erro leva ao campo Revisor',True,root.focus_get()==app.actor_entry);check('Aviso nomeia Revisor',True,'Revisor' in app.review_hint.get())
            app.actor.set('REVISOR FICTICIO');app.review_reason.set('');app.tabs.select(app.page_tab);app.group_confirm_button.invoke();root.update()
            check('Motivo mostra a aba correta',str(app.review_container),app.tabs.select());check('Erro leva ao campo Motivo',True,root.focus_get()==app.reason_entry)
            app.review_reason.set('Conferência fictícia dos dados, exames, páginas e alertas')
            for button in app.page_panel.buttons:button.invoke();root.update()
            with patch('app.messagebox.askyesno',return_value=True):app.group_confirm_button.invoke()
            root.update();check('Agrupamento conferido',False,app.models['pedido']['association_pending'])
            check('Páginas vistas não são perdidas',True,all(len(v.seen)==len(v.doc['pages']) for v in app.views.values()))
            app.selected_profile=profile();app.assisted_button.invoke();root.update();h=app.review_assistant
            for key,value in [('Paciente','PESSOA FICTICIA ALFA'),('Medico','DRA EXEMPLO SINTETICA'),('Número conselho','0012345'),('UF conselho','GO')]:check('Campo visível '+key,value,app.field_vars['pedido'][key].get())
            check('Linhas de exames na conferência',10,len(h.exam_table.get_children()))
            for var in [*h.data_checks.values(),*h.exam_checks.values(),h.alert_check]:var.set(True)
            h.save_button.invoke();root.update();check('Conferência salva',True,h.saved);check('Sem pendências após revisão',[],app.comparison_errors)
            check('Botão aguarda confirmação final','disabled',str(h.prepare_button['state']))
            h.final_check.set(True);h.update_prepare();check('Botão liberado após confirmação','normal',str(h.prepare_button['state']))
            h.prepare_button.invoke();root.update();check('Estado final','PREPARADO',app.store.get(app.cid)[2]);check('Nenhuma O.S. real',None,app.store.get(app.cid)[3]['os_real'])
            check('Revisor e motivo persistidos',{'revisor':app.actor.get(),'motivo':app.review_reason.get()},app.store.get(app.cid)[0]['review_metadata'])
            if capture:
                from PIL import ImageGrab
                h.window.lift();root.update();x,y=h.window.winfo_rootx(),h.window.winfo_rooty()
                ImageGrab.grab().crop((x,y,x+h.window.winfo_width(),y+h.window.winfo_height())).save(ROOT/'docs/CONFERENCIA_FICTICIA_2_4_5.png')
        finally:app.store.db.close();root.destroy()
    report={'somente_sinteticos':True,'verificacoes':checks,'passaram':sum(x['passou'] for x in checks),'falharam':sum(not x['passou'] for x in checks)}
    (ROOT/'docs/RELATORIO_INTERFACE_2_4_5.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'verificacoes':len(checks),'passaram':report['passaram'],'falharam':report['falharam']}))
    if report['falharam']:raise ValueError('Verificação da interface falhou; veja os valores esperados/encontrados.')

if __name__=='__main__':main()
