"""Somente tempos, métodos e contagens; nenhum conteúdo ou identificador clínico."""
import json,tkinter as tk
from tkinter import ttk
def show_times(app):
    if not app.cid:raise ValueError('Selecione um atendimento já analisado.')
    from scan_import import load_batch
    obj=app.store.get(app.cid)[0];batch_id=obj['docs']['pedido'].get('scan_batch')
    if not batch_id:raise ValueError('Tempos disponíveis para novas importações de escaneamentos.')
    timing=load_batch(app.store,batch_id).get('timing',{})
    window=tk.Toplevel(app.root);window.title('Tempos de leitura local');text=tk.Text(window,width=100,height=25);text.pack(fill='both',expand=True)
    text.insert('1.0',json.dumps(timing,ensure_ascii=False,indent=2) if timing else 'Reprocesse a leitura para medir os tempos desta versão.');text.configure(state='disabled')
