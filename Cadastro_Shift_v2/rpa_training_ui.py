"""Treinamento fictício explícito; nunca recebe os documentos da ficha selecionada."""
import queue,threading,tkinter as tk
from tkinter import ttk
from lis_simulado import APPROVALS,approve,demo_data

def open_training(app):
    old=getattr(app,'rpa_training',None)
    if old and old['window'].winfo_exists():old['window'].lift();return
    from rpa_simulada import SimulatedRPA
    window=tk.Toplevel(app.root);window.title('Treinamento RPA — somente demonstração');window.geometry('780x620')
    data=demo_data();stop=threading.Event();events=queue.Queue()
    ttk.Label(window,text='Treinamento local de cadastro no LIS fictício',font=('Segoe UI',16,'bold'),padding=15).pack(anchor='w')
    ttk.Label(window,text='Usa documentos gerados pelo próprio programa. A ficha selecionada na rotina não é enviada ao simulador.',wraplength=720,padding=10).pack(fill='x')
    summary=tk.Text(window,height=8,wrap='word');summary.pack(fill='x',padx=15);summary.insert('1.0','Paciente: '+data['patient']['nome']+'\nNascimento: '+data['patient']['nascimento']+'\nCarteira: '+data['patient']['carteira']+'\nFonte: '+data['payer']+'\nMédica: DRA EXEMPLO SINTETICA — CRM 0012345/GO\nGuia: 00000111 — autorização fictícia: 00000555\nCinco procedimentos fictícios, quantidade 1; pedido e guia sintéticos.');summary.configure(state='disabled')
    checks={}
    for key,label in zip(APPROVALS,['Identidade','Fonte pagadora','Médico','Exames e quantidades','Autorização']):
        checks[key]=tk.BooleanVar();ttk.Checkbutton(window,text='Conferi '+label,variable=checks[key]).pack(anchor='w',padx=15)
    notice=tk.StringVar(value='Informe Seu nome / revisor no painel. Confirme os cinco grupos e inicie o treino.');ttk.Label(window,textvariable=notice,wraplength=720,padding=12).pack(fill='x')
    def start():
        try:approval=approve(data,app.actor.get(),{k:v.get() for k,v in checks.items()})
        except ValueError as exc:notice.set(str(exc));return
        start_button.configure(state='disabled');notice.set('Abrindo o navegador. Confirme o paciente encontrado e, depois do preenchimento, confira e autorize a O.S. fictícia.')
        def work():
            rpa=None
            try:
                rpa=SimulatedRPA(data,approval,app.data/'rpa_treinamento.sqlite3');result=rpa.interactive(stop);events.put('Treino concluído: '+result['os_simulada']+'. As etiquetas são apenas uma prévia no navegador.')
                while not stop.wait(.2) and not rpa.page.is_closed():rpa.page.wait_for_timeout(100)
            except Exception:events.put('Treino encerrado ou bloqueado. Se o navegador não abriu, execute INSTALAR_SIMULACAO_RPA.bat. Confira também identidade, anexos e duplicidade; a mesma guia não pode gerar duas O.S. fictícias. Feche esta janela e abra Treinamento RPA novamente se precisar reiniciar.')
            finally:
                if rpa:rpa.close()
        threading.Thread(target=work,daemon=True).start()
    start_button=ttk.Button(window,text='Iniciar RPA com dados fictícios conferidos',command=start);start_button.pack(pady=8)
    ttk.Button(window,text='Encerrar treinamento',command=lambda:(stop.set(),window.destroy())).pack(pady=5)
    state={'window':window,'checks':checks,'start':start_button,'notice':notice}
    def poll():
        if not window.winfo_exists():return
        try:
            while True:notice.set(events.get_nowait())
        except queue.Empty:pass
        state['poll_id']=window.after(200,poll)
    def destroyed(event):
        if event.widget!=window:return
        stop.set()
        if state.get('poll_id'):
            try:window.after_cancel(state['poll_id'])
            except tk.TclError:pass
    window.bind('<Destroy>',destroyed);poll()
    app.rpa_training=state
