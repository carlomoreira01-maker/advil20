"""Aplicativo desktop Tkinter. Execute: python app.py"""
import csv
from datetime import datetime
import html
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from core import Store, catalog_load, compare, digest
from reader import read, preview

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'dados_demo'


class App:
    def __init__(self, root, data=DATA):
        self.root = root
        self.data = Path(data)
        self.data.mkdir(exist_ok=True)
        (self.data / 'documentos').mkdir(exist_ok=True)
        self.store = Store(self.data / 'demo.sqlite3')
        self.catalog = catalog_load(ROOT / 'catalogo_demo.json')
        self.cid = None
        self.analysis = None
        self.events = queue.Queue()
        self.busy = False
        root.title('Cadastro Assistido | DEMONSTRAÇÃO LOCAL')
        root.geometry('1280x850')
        root.minsize(1000, 700)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=7)
        style.configure('Treeview', rowheight=27)
        tk.Label(root, text='CADASTRO ASSISTIDO  /  DEMONSTRAÇÃO', bg='#123247', fg='white', font=('Arial', 19, 'bold'), anchor='w', padx=18, pady=13).pack(fill='x')
        tk.Label(root, text='Somente documentos fictícios • Sem conexão com o Shift • Sem impressão • Revisão humana por paciente', bg='#fff0c6', padx=15, pady=8, anchor='w').pack(fill='x')
        top = ttk.Frame(root, padding=8)
        top.pack(fill='x')
        ttk.Label(top, text='Nome do revisor:').pack(side='left')
        self.actor = tk.StringVar(value='Operador de demonstração')
        ttk.Entry(top, textvariable=self.actor, width=28).pack(side='left', padx=6)
        for label, cmd in [('Carregar 3 exemplos', self.examples), ('Importar um par', self.import_pair), ('Importar lote CSV', self.import_csv), ('Carregar catálogo', self.load_catalog)]:
            ttk.Button(top, text=label, command=lambda fn=cmd: self.guard(fn)).pack(side='left', padx=3)
        paned = ttk.Panedwindow(root, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10)
        left = ttk.Frame(paned, width=240)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=5)
        ttk.Label(left, text='FILA DE PACIENTES', font=('Arial', 11, 'bold')).pack(pady=8)
        self.cases = ttk.Treeview(left, columns=('nome', 'status'), show='headings', selectmode='browse')
        self.cases.heading('nome', text='Paciente')
        self.cases.heading('status', text='Etapa')
        self.cases.column('nome', width=155)
        self.cases.column('status', width=95)
        self.cases.pack(fill='both', expand=True)
        self.cases.bind('<<TreeviewSelect>>', self.select)
        ttk.Button(left, text='Ver auditoria', command=lambda: self.guard(self.audit_window)).pack(fill='x', pady=8)
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill='both', expand=True)
        docs = ttk.Frame(self.tabs, padding=8)
        self.review_tab = ttk.Frame(self.tabs, padding=8)
        self.output_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(docs, text='1 · Documentos e correções')
        self.tabs.add(self.review_tab, text='2 · Comparar e conferir')
        self.tabs.add(self.output_tab, text='3 · Pré-cadastro e etiquetas DEMO')
        ttk.Label(docs, text='Originais ficam preservados. Edite a transcrição para corrigir OCR; informe o motivo ao salvar.').pack(anchor='w')
        texts = ttk.Frame(docs)
        texts.pack(fill='both', expand=True)
        self.editors = {}
        for kind, label in [('pedido', 'Pedido médico'), ('guia', 'Guia de autorização')]:
            col = ttk.LabelFrame(texts, text=label, padding=5)
            col.pack(side='left', fill='both', expand=True, padx=3)
            ttk.Button(col, text='Ver original / páginas', command=lambda k=kind: self.guard(lambda: self.original(k))).pack(fill='x')
            t = tk.Text(col, wrap='word', width=42, font=('Consolas', 10), undo=True)
            t.pack(fill='both', expand=True)
            self.editors[kind] = t
        ttk.Button(docs, text='Salvar transcrição e comparar', command=lambda: self.guard(self.save_compare)).pack(pady=8)
        self.summary = tk.Text(self.review_tab, wrap='word', height=9, state='disabled')
        self.summary.pack(fill='x')
        cols = ('nome', 'codigo_shift', 'pedido', 'guia', 'material', 'situacao')
        self.exam_table = ttk.Treeview(self.review_tab, columns=cols, show='headings', height=7)
        for c, name in zip(cols, ['Exame', 'Código DEMO', 'Pedido', 'Guia', 'Material de exemplo', 'Situação']):
            self.exam_table.heading(c, text=name)
            self.exam_table.column(c, width=120 if c not in ('pedido', 'guia') else 50)
        self.exam_table.pack(fill='both', expand=True, pady=8)
        self.blockers = tk.Text(self.review_tab, height=8, wrap='word', state='disabled', fg='#a02424')
        self.blockers.pack(fill='both', expand=True)
        self.confirm = tk.BooleanVar(value=False)
        ttk.Checkbutton(self.review_tab, variable=self.confirm, text='Conferi os dois originais, identidade, códigos, quantidades e validade. Todos os dados são fictícios.').pack(anchor='w', pady=8)
        ttk.Button(self.review_tab, text='Revisar e SIMULAR ordem de serviço', command=lambda: self.guard(self.simulate)).pack(anchor='e')
        self.output = tk.Text(self.output_tab, wrap='word', state='disabled')
        self.output.pack(fill='both', expand=True)
        ttk.Button(self.output_tab, text='Exportar JSON e etiquetas HTML (sem imprimir)', command=lambda: self.guard(self.export)).pack(pady=8)
        self.status = tk.StringVar(value='Comece clicando em “Carregar 3 exemplos”.')
        ttk.Label(root, textvariable=self.status, padding=10).pack(fill='x')
        self.refresh()
        self.root.after(150, self.poll)

    def guard(self, fn):
        try:
            if self.busy:
                raise ValueError('Aguarde a conclusão da leitura.')
            fn()
        except Exception as exc:
            with self.store.db:
                self.store.audit(self.actor.get(), self.cid, 'ERRO', {'tipo': type(exc).__name__, 'mensagem': str(exc)[:500]})
            messagebox.showerror('Não foi possível concluir', str(exc))

    def text_set(self, widget, text):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')

    def refresh(self):
        self.cases.delete(*self.cases.get_children())
        for cid, cur, rev, status in self.store.list():
            name = compare(json.loads(cur)['pedido'], json.loads(cur)['guia'], self.catalog)['paciente'].get('Paciente', 'Não identificado')
            self.cases.insert('', 'end', iid=cid, values=(name, status))
        if self.cid and self.cases.exists(self.cid):
            self.cases.selection_set(self.cid)

    def select(self, event=None):
        selected = self.cases.selection()
        if not selected:
            return
        self.cid = selected[0]
        cur, rev, status, _ = self.store.get(self.cid)
        for kind, editor in self.editors.items():
            editor.delete('1.0', 'end')
            editor.insert('1.0', cur[kind])
        self.analyze()
        order = self.store.order(self.cid)
        self.text_set(self.output, json.dumps(order, ensure_ascii=False, indent=2) if order else 'Ainda não há pré-cadastro aprovado para este paciente.')

    def analyze(self):
        cur, self.rev, status, _ = self.store.get(self.cid)
        self.analysis = compare(cur['pedido'], cur['guia'], self.catalog)
        self.confirm.set(False)
        self.text_set(self.summary, 'DADOS INTERPRETADOS — comparar com os originais\n\n' + '\n'.join(f'{k}: {v or "Não informado"}' for k, v in self.analysis['paciente'].items()) + '\nNascimento ausente nos dois documentos exige atenção ao homônimo.\nTUSS: não configurado; códigos deste catálogo são exclusivamente fictícios.')
        self.exam_table.delete(*self.exam_table.get_children())
        for r in self.analysis['exames']:
            self.exam_table.insert('', 'end', values=tuple(r[k] for k in ('nome', 'codigo_shift', 'pedido', 'guia', 'material', 'situacao')))
        self.text_set(self.blockers, '\n'.join('• ' + p for p in self.analysis['pendencias']) or 'Nenhuma divergência estrutural. A correspondência textual não comprova autorização: conferir os originais.')
        self.status.set(f'Revisão {self.rev} | {status} | {len(self.analysis["pendencias"])} pendências')

    def save_compare(self):
        if not self.cid:
            raise ValueError('Selecione um paciente.')
        cur, _, _, _ = self.store.get(self.cid)
        values = {k: t.get('1.0', 'end-1c') for k, t in self.editors.items()}
        if any(values[k] != cur[k] for k in values):
            reason = simpledialog.askstring('Rastreabilidade', 'Qual o motivo da correção? Não use dados reais.')
            if not reason:
                return
            self.store.edit(self.cid, values['pedido'], values['guia'], self.actor.get(), reason)
        self.analyze()
        self.tabs.select(self.review_tab)
        self.refresh()

    def examples(self):
        pairs = [(ROOT/'exemplos'/f'{i}_pedido.txt', ROOT/'exemplos'/f'{i}_guia.txt') for i in ('01', '02', '03')]
        self.import_pairs(pairs)

    def import_pair(self):
        p = filedialog.askopenfilename(title='Escolha o pedido FICTÍCIO', filetypes=[('Documentos', '*.txt *.pdf *.png *.jpg *.jpeg')])
        if not p:
            return
        g = filedialog.askopenfilename(title='Escolha a guia do MESMO paciente fictício', filetypes=[('Documentos', '*.txt *.pdf *.png *.jpg *.jpeg')])
        if g:
            self.import_pairs([(Path(p), Path(g))])

    def import_csv(self):
        file = filedialog.askopenfilename(title='Escolha o manifesto de lote', filetypes=[('CSV', '*.csv')])
        if not file:
            return
        base = Path(file).parent.resolve()
        with open(file, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
        if not rows or len(rows) > 100:
            raise ValueError('Use entre 1 e 100 pares por lote.')
        pairs = []
        for row in rows:
            pair = []
            for k in ['pedido', 'guia']:
                p = (base / row[k]).resolve()
                if not p.is_relative_to(base):
                    raise ValueError('Caminhos do CSV precisam ficar na pasta do manifesto.')
                pair.append(p)
            pairs.append(tuple(pair))
        self.import_pairs(pairs)

    def import_pairs(self, pairs):
        self.busy = True
        self.status.set('Lendo documentos localmente… aguarde. Cada par representa um paciente.')
        def work():
            for p, g in pairs:
                try:
                    documents, sources = {}, {}
                    for kind, path in [('pedido', p), ('guia', g)]:
                        text, meta = read(path)
                        documents[kind] = text
                        target = self.data / 'documentos' / (meta['sha256'] + path.suffix.lower())
                        # Copia para auditoria o mesmo conteúdo cujo hash foi calculado.
                        raw = path.read_bytes()
                        import hashlib
                        if hashlib.sha256(raw).hexdigest() != meta['sha256']:
                            raise ValueError('Documento mudou durante a leitura. Importe novamente.')
                        target.write_bytes(raw)
                        sources[kind] = {**meta, 'copia': str(target.resolve())}
                    self.events.put(('case', documents, sources))
                except Exception as exc:
                    self.events.put(('error', f'{p.name} / {g.name}: {exc}'))
            self.events.put(('done',))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                item = self.events.get_nowait()
                if item[0] == 'case':
                    try:
                        docs, sources = item[1:]
                        self.cid = self.store.add(docs['pedido'], docs['guia'], self.actor.get(), sources)
                    except Exception as exc:
                        self.events.put(('error', str(exc)))
                elif item[0] == 'error':
                    with self.store.db:
                        self.store.audit(self.actor.get(), None, 'ERRO_IMPORTACAO', item[1])
                    messagebox.showwarning('Documento não importado', item[1])
                else:
                    self.busy = False
                    self.refresh()
                    self.select()
                    self.status.set('Leitura concluída. Selecione cada paciente e confira os documentos.')
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def load_catalog(self):
        file = filedialog.askopenfilename(title='Catálogo DEMO JSON', filetypes=[('JSON', '*.json')])
        if not file:
            return
        updated = catalog_load(file)
        with self.store.db:
            self.store.audit(self.actor.get(), None, 'CATALOGO_CARREGADO', {'antes': digest(self.catalog), 'depois': digest(updated), 'conteudo': updated})
        self.catalog = updated
        if self.cid:
            self.analyze()
        messagebox.showinfo('Catálogo', 'Catálogo carregado para esta sessão. Reiniciar restaura catalogo_demo.json.')

    def original(self, kind):
        if not self.cid:
            raise ValueError('Selecione um paciente.')
        _, _, _, original = self.store.get(self.cid)
        w = tk.Toplevel(self.root)
        w.title('ORIGINAL PRESERVADO — ' + kind)
        w.geometry('850x750')
        path = original.get('fontes', {}).get(kind, {}).get('copia')
        if not path or Path(path).suffix.lower() == '.txt':
            t = tk.Text(w, wrap='word')
            t.pack(fill='both', expand=True)
            self.text_set(t, original[kind])
            return
        from PIL import ImageTk
        label = ttk.Label(w)
        label.pack(fill='both', expand=True)
        page = [0]
        def render(delta=0):
            page[0] += delta
            im, total = preview(path, page[0])
            im.thumbnail((810, 650))
            label.photo = ImageTk.PhotoImage(im)
            label.configure(image=label.photo)
            prev.configure(state='normal' if page[0] else 'disabled')
            nxt.configure(state='normal' if page[0] + 1 < total else 'disabled')
            w.title(f'ORIGINAL {kind} — página {page[0]+1}/{total}')
        nav = ttk.Frame(w)
        nav.pack()
        prev = ttk.Button(nav, text='Anterior', command=lambda: self.guard(lambda: render(-1)))
        prev.pack(side='left')
        nxt = ttk.Button(nav, text='Próxima', command=lambda: self.guard(lambda: render(1)))
        nxt.pack(side='left')
        render()

    def simulate(self):
        if not self.cid:
            raise ValueError('Selecione e confira um paciente.')
        cur, _, _, _ = self.store.get(self.cid)
        if any(self.editors[k].get('1.0', 'end-1c') != cur[k] for k in self.editors):
            self.confirm.set(False)
            raise ValueError('Há correções sem salvar. Clique em Salvar transcrição e comparar.')
        order = self.store.simulate(self.cid, self.catalog, self.actor.get(), self.confirm.get(), self.rev, self.analysis['catalogo_hash'])
        self.text_set(self.output, json.dumps(order, indent=2, ensure_ascii=False))
        self.tabs.select(self.output_tab)
        self.refresh()

    def export(self):
        order = self.store.order(self.cid)
        if not order:
            raise ValueError('Conclua a revisão e a simulação deste paciente.')
        folder = filedialog.askdirectory(title='Pasta para arquivos fictícios')
        if not folder:
            return
        from exporter import export_order
        paths = export_order(order, Path(folder))
        with self.store.db:
            self.store.audit(self.actor.get(), self.cid, 'EXPORTACAO_DEMO', {'arquivos': [p.name for p in paths]})
        messagebox.showinfo('Arquivos criados', 'Pré-cadastro JSON e etiquetas HTML de DEMONSTRAÇÃO salvos. Nenhuma impressão foi enviada.')

    def audit_window(self):
        w = tk.Toplevel(self.root)
        w.title('Auditoria local — demonstração')
        w.geometry('1000x600')
        t = tk.Text(w, wrap='word')
        t.pack(fill='both', expand=True)
        rows = self.store.db.execute('SELECT at,actor,case_id,action,detail FROM audit ORDER BY id DESC LIMIT 200').fetchall()
        self.text_set(t, '\n\n'.join(' | '.join(str(x) for x in row) for row in rows))


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
