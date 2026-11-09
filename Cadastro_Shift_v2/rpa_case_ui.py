"""Validação integrada de um atendimento fictício já conferido na interface."""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from lis_simulado import APPROVALS
from rpa_handoff import build_handoff, record_result


def open_case_simulation(app):
    old = getattr(app, 'rpa_case_simulation', None)
    if old and old['window'].winfo_exists():
        old['window'].lift()
        return
    if not app.cid:
        raise ValueError('Selecione um atendimento fictício já conferido.')
    cid, revision = app.cid, app.rev
    obj, _, status, _ = app.store.get(cid)
    if status != 'PREPARADO':
        raise ValueError('Prepare o pré-cadastro validado antes de simular este atendimento. O rascunho permanece acessível.')
    window = tk.Toplevel(app.root)
    window.title('Simular este pré-cadastro fictício')
    window.geometry('820x680')
    ttk.Label(window, text='Do atendimento conferido ao LIS fictício',
              font=('Segoe UI', 16, 'bold'), padding=15).pack(anchor='w')
    ttk.Label(window, text='Utiliza os valores e os arquivos originais deste pré-cadastro. '
              'Aceita somente os pacientes, o perfil FICTICIO e o catálogo SIM-LAB dos exemplos. '
              'O endereço do Shift real não é utilizado.', wraplength=760, padding=12).pack(fill='x')
    guide = obj['models']['guia']; f = guide['fields']
    summary = tk.Text(window, height=7, wrap='word')
    summary.pack(fill='x', padx=15)
    summary.insert('1.0', 'Paciente: ' + f['Paciente']['value'] + '\nCarteirinha: ' + f['Carteira']['value'] +
                   '\nGuia prestador: ' + f['Guia prestador']['value'] + '\nMédico: ' + f['Medico']['value'] +
                   '\nConselho: ' + f['Conselho']['value'] + ' ' + f['Número conselho']['value'] + '/' + f['UF conselho']['value'] +
                   '\nProcedimentos conferidos: ' + str(len(guide['exams'])))
    summary.configure(state='disabled')
    row = ttk.Frame(window); row.pack(fill='x', padx=15, pady=6)
    ttk.Label(row, text='Seu nome / revisor').pack(side='left')
    ttk.Entry(row, textvariable=app.actor, width=35).pack(side='left', padx=8)
    checks = {}
    for key, label in zip(APPROVALS, ['Identidade', 'Fonte pagadora do exemplo', 'Médico', 'Exames e quantidades', 'Autorização']):
        checks[key] = tk.BooleanVar()
        ttk.Checkbutton(window, text='Conferi ' + label, variable=checks[key]).pack(anchor='w', padx=15)
    synthetic = tk.BooleanVar()
    ttk.Checkbutton(window, text='Estes dados e documentos são inteiramente fictícios.',
                    variable=synthetic).pack(anchor='w', padx=15, pady=8)
    notice = tk.StringVar(value='Confirme os cinco grupos e o uso de documentos fictícios. O navegador solicitará novamente a confirmação do paciente e a autorização final.')
    ttk.Label(window, textvariable=notice, wraplength=760, padding=12).pack(fill='x')
    events, stop = queue.Queue(), threading.Event()
    state = {'window': window, 'checks': checks, 'synthetic': synthetic,
             'notice': notice, 'stop': stop, 'result': None, 'handoff': None, 'busy': False}

    def start():
        if state['busy']: return
        try:
            envelope = build_handoff(app.store, cid, app.catalog, expected_revision=revision,
                                      reviewer=app.actor.get(), checks={k: v.get() for k, v in checks.items()},
                                      synthetic_confirmed=synthetic.get())
        except ValueError as exc:
            notice.set(str(exc)); return
        state['handoff'] = envelope; state['busy'] = True
        start_button.configure(state='disabled')
        notice.set('Abrindo o LIS fictício com este pré-cadastro. No navegador, confirme o cadastro encontrado e confira os valores antes de autorizar a O.S. fictícia.')

        def worker():
            rpa = None
            try:
                from rpa_simulada import SimulatedRPA
                rpa = SimulatedRPA.from_handoff(envelope, db_path=app.data / 'rpa_treinamento.sqlite3')
                result = rpa.interactive(stop)
                events.put(('result', result))
                while not stop.is_set() and not rpa.page.is_closed():
                    rpa.page.wait_for_timeout(150)
            except ValueError as exc:
                events.put(('error', str(exc)))
            except Exception:
                events.put(('error', 'O navegador foi encerrado ou não está disponível. Execute INSTALAR_SIMULACAO_RPA.bat se necessário. Reabra esta janela para tentar novamente; confira também a proteção de duplicidade.'))
            finally:
                try:
                    if rpa: rpa.close()
                finally:
                    events.put(('finished', None))
        threading.Thread(target=worker, daemon=True).start()

    start_button = ttk.Button(window, text='Simular este pré-cadastro conferido', command=start)
    start_button.pack(pady=8)
    ttk.Button(window, text='Encerrar simulação', command=lambda: (stop.set(), window.destroy())).pack(pady=5)
    state['start'] = start_button

    def poll():
        if not window.winfo_exists(): return
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == 'result':
                    try:
                        record_result(app.store, state['handoff'], value)
                        state['result'] = value
                        notice.set('Integração fictícia concluída: ' + value['os_simulada'] +
                                   '. Foram utilizados os valores conferidos e os documentos deste atendimento. Nenhuma O.S. real foi criada.')
                    except Exception:
                        notice.set('O navegador concluiu a demonstração, mas não foi possível vinculá-la à revisão local. A gravação real continua indisponível; não repita o cadastro sem verificar a duplicidade.')
                elif kind == 'error': notice.set(value)
                elif kind == 'finished': state['busy'] = False
        except queue.Empty:
            pass
        state['poll_id'] = window.after(200, poll)

    def destroyed(event):
        if event.widget != window: return
        stop.set()
        if state.get('poll_id'):
            try: window.after_cancel(state['poll_id'])
            except tk.TclError: pass
    window.bind('<Destroy>', destroyed)
    app.rpa_case_simulation = state
    poll()
