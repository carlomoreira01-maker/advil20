"""Navegador temporário de inspeção, com login manual e sem captura de credenciais."""
import json,os,queue,shutil,threading,tkinter as tk
from tkinter import ttk,filedialog
from pathlib import Path
from shift_inspection import SHIFT_LOGIN,inspect_structure

def open_inspection(app):
    existing=getattr(app,'shift_inspection',None)
    if existing and existing['window'].winfo_exists():existing['window'].lift();return
    window=tk.Toplevel(app.root);window.title('Shift de produção — inspeção somente de leitura');window.geometry('820x460')
    ttk.Label(window,text='Inspeção local das telas do Shift',font=('Segoe UI',16,'bold'),padding=15).pack(anchor='w')
    ttk.Label(window,text='Entre manualmente no navegador e abra somente a tela autorizada para inspeção. O programa não preenche formulários, não cria O.S. e não imprime etiquetas. Não há gravação de senha ou sessão.',wraplength=760,padding=12).pack(fill='x')
    notice=tk.StringVar(value='Clique em Abrir navegador. Se faltar o navegador, execute INSTALAR_SIMULACAO_RPA.bat antes.');ttk.Label(window,textvariable=notice,wraplength=760,padding=12).pack(fill='x')
    commands=queue.Queue();events=queue.Queue();stop=threading.Event();state={'window':window,'report':None}
    def launch():
        open_button.configure(state='disabled');notice.set('Abrindo o endereço informado. O login será digitado por você, somente no navegador.')
        def worker():
            browser=None;play=None
            try:
                from playwright.sync_api import sync_playwright
                play=sync_playwright().start();exe=os.getenv('SHIFT_CHROMIUM') or shutil.which('chromium');opts={'headless':False,'chromium_sandbox':True}
                if exe:opts['executable_path']=exe
                proxy=os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
                if proxy:opts['proxy']={'server':proxy}
                browser=play.chromium.launch(**opts);context=browser.new_context();page=context.new_page()
                try:page.goto(SHIFT_LOGIN,wait_until='domcontentloaded',timeout=30000);events.put(('ready','Navegador aberto. Faça o login manual e abra a tela autorizada; depois clique em Inspecionar estrutura.'))
                except Exception:events.put(('ready','O site não carregou. Verifique a rede e o certificado; não ignore bloqueios de segurança. Você pode tentar novamente pelo navegador.'))
                while not stop.is_set():
                    try:command=commands.get_nowait()
                    except queue.Empty:command=None
                    if command=='inspect':
                        try:
                            active=next((p for p in reversed(context.pages) if not p.is_closed()),None)
                            if active is None:raise ValueError('Navegador encerrado. Feche esta janela e abra a inspeção novamente.')
                            events.put(('report',inspect_structure(active)))
                        except ValueError as exc:events.put(('notice',str(exc)))
                        except Exception:events.put(('notice','Não foi possível inspecionar esta tela. Aguarde o carregamento e tente novamente. Nenhum conteúdo foi salvo.'))
                    live=next((p for p in reversed(context.pages) if not p.is_closed()),None)
                    if live is None:break
                    live.wait_for_timeout(150)
            except Exception:events.put(('notice','Inspeção encerrada ou navegador indisponível. Instale o componente opcional e reabra esta janela. Nenhum formulário foi enviado pelo programa.'))
            finally:
                if browser:browser.close()
                if play:play.stop()
        threading.Thread(target=worker,daemon=True).start()
    open_button=ttk.Button(window,text='Abrir navegador para login manual',command=launch);open_button.pack(pady=8)
    capture=ttk.Button(window,text='Inspecionar estrutura da tela atual',state='disabled',command=lambda:commands.put('inspect'));capture.pack(pady=8)
    def save():
        if not state['report']:notice.set('Abra o navegador e inspecione a tela primeiro.');return
        path=filedialog.asksaveasfilename(parent=window,title='Salvar estrutura sem valores dos campos',initialfile='estrutura_shift_sem_valores.json',defaultextension='.json',filetypes=[('JSON','*.json')])
        if path:Path(path).write_text(json.dumps(state['report'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8');notice.set('Estrutura salva localmente, sem valores dos campos, senha, cookies, HTML ou captura da tela.')
    ttk.Button(window,text='Salvar relatório estrutural local',command=save).pack(pady=8)
    ttk.Button(window,text='Encerrar inspeção',command=lambda:(stop.set(),window.destroy())).pack(pady=8)
    def poll():
        if not window.winfo_exists():return
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='ready':capture.configure(state='normal');notice.set(value)
                elif kind=='report':state['report']=value;notice.set(value['aviso']+' Controles visíveis: '+str(value['controles_visiveis'])+'.')
                else:notice.set(value)
        except queue.Empty:pass
        window.after(200,poll)
    window.bind('<Destroy>',lambda e:stop.set() if e.widget==window else None);state['capture']=capture;state['open']=open_button;state['notice']=notice;app.shift_inspection=state;poll()

if __name__=='__main__':
    from types import SimpleNamespace
    root=tk.Tk();root.withdraw();app=SimpleNamespace(root=root);open_inspection(app)
    app.shift_inspection['window'].bind('<Destroy>',lambda e:root.destroy() if e.widget==app.shift_inspection['window'] else None,add='+');root.mainloop()
