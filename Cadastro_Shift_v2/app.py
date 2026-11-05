"""Cadastro Assistido Shift v2 — aplicativo desktop inteiramente local."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import queue
import shutil
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from engine_v2 import (FIELDS, CaseStore, catalog_load, read_document, parse_document,
                       compare_models, review_errors, digest, document_diagnostics)
from ocr_runtime import (safe_failure, settings_file, load_settings, save_settings,
                         tesseract_exe, check_ocr_health)
from reader import preview

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'dados_v2'
UNIDENTIFIED='Não identificado'


class DocumentView(ttk.Frame):
    def __init__(self,parent,title):
        super().__init__(parent)
        self.path=None;self.doc=None;self.index=0;self.zoom=1.;self.box=None
        self.seen=set()
        bar=ttk.Frame(self);bar.pack(fill='x')
        ttk.Label(bar,text=title,font=('Segoe UI',11,'bold')).pack(side='left')
        for text,fn in [('<',lambda:self.move(-1)),('>',lambda:self.move(1)),('-',lambda:self.scale(.8)),('+',lambda:self.scale(1.25))]:ttk.Button(bar,text=text,width=3,command=fn).pack(side='left',padx=1)
        self.info=tk.StringVar();ttk.Label(self,textvariable=self.info).pack(anchor='w')
        frame=ttk.Frame(self);frame.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(frame,bg='#dfe6eb',highlightthickness=0)
        vy=ttk.Scrollbar(frame,orient='vertical',command=self.canvas.yview);hx=ttk.Scrollbar(frame,orient='horizontal',command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vy.set,xscrollcommand=hx.set)
        self.canvas.grid(row=0,column=0,sticky='nsew');vy.grid(row=0,column=1,sticky='ns');hx.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
    def load(self,doc):
        self.doc=doc;self.path=doc.get('local_path');self.index=0;self.zoom=1.;self.box=None;self.seen=set();self.render()
    def move(self,delta):
        if self.doc:self.index=max(0,min(len(self.doc['pages'])-1,self.index+delta));self.box=None;self.render()
    def scale(self,factor):
        self.zoom=max(.3,min(4,self.zoom*factor));self.render()
    def locate(self,page,box):
        if not self.doc or not page:return
        self.index=max(0,min(len(self.doc['pages'])-1,int(page)-1));self.box=box;self.render()
    def render(self):
        if not self.doc:return
        self.canvas.delete('all');p=self.doc['pages'][self.index];self.seen.add(self.index+1)
        self.info.set(f'Página {self.index+1}/{len(self.doc["pages"])} · {p["method"]} · Zoom {round(self.zoom*100)}%')
        try:
            if not self.path or Path(self.path).suffix.lower()=='.txt':
                self.canvas.create_text(15,15,text=p['text'],anchor='nw',font=('Consolas',11),width=700)
            else:
                from PIL import ImageTk
                im,_=preview(self.path,self.index)
                base=min(1,540/max(1,im.width));factor=base*self.zoom
                im=im.resize((max(1,int(im.width*factor)),max(1,int(im.height*factor))))
                self.photo=ImageTk.PhotoImage(im);self.canvas.create_image(0,0,image=self.photo,anchor='nw')
                if self.box:
                    sx=im.width/p['size'][0];sy=im.height/p['size'][1];b=self.box
                    self.canvas.create_rectangle(b[0]*sx,b[1]*sy,b[2]*sx,b[3]*sy,outline='#dc5b12',width=3)
                    self.canvas.yview_moveto(max(0,b[1]*sy-40)/max(1,im.height))
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        except Exception as exc:self.canvas.create_text(10,10,text='Não foi possível exibir original: '+str(exc),anchor='nw',width=480)


class App:
    def __init__(self,root,data=DATA):
        self.root=root;self.data=Path(data);self.data.mkdir(parents=True,exist_ok=True)
        (self.data/'documentos').mkdir(exist_ok=True)
        self.store=CaseStore(self.data/'cadastro_local.sqlite3')
        self.catalog_path=self.data/'catalogo.json'
        self.catalog=catalog_load(self.catalog_path if self.catalog_path.exists() else ROOT/'catalogo_demo.json')
        self.cid=None;self.models=None;self.busy=False;self.events=queue.Queue();self.loading=False
        self.ocr_settings_path=settings_file() if self.data.resolve()==DATA.resolve() else self.data/'configuracao_ocr.json'
        self.ocr_request=0;self.ocr_dialog=None;self.ocr_health=None
        self.import_sequence=0
        root.report_callback_exception=self.callback_failure
        root.title('Cadastro Assistido Shift · versão 2.2 · Local');root.geometry('1450x950');root.minsize(1100,760)
        st=ttk.Style();st.theme_use('clam');st.configure('TButton',padding=6);st.configure('Treeview',rowheight=28)
        tk.Label(root,text='CADASTRO ASSISTIDO SHIFT  |  2.2',font=('Segoe UI',19,'bold'),bg='#173d52',fg='white',anchor='w',padx=18,pady=12).pack(fill='x')
        ttk.Label(root,text='Importar > Ler > Comparar > Conferir > Preparar pré-cadastro',font=('Segoe UI',12,'bold'),padding=8).pack(fill='x')
        ttk.Label(root,text='Processamento local | Revisão humana obrigatória | Pré-cadastro não enviado ao Shift',padding=(10,0)).pack(anchor='w')
        bar=ttk.Frame(root,padding=8);bar.pack(fill='x')
        ttk.Label(bar,text='Revisor:').pack(side='left');self.actor=tk.StringVar(value='');ttk.Entry(bar,textvariable=self.actor,width=20).pack(side='left',padx=5)
        for title,fn in [('Importar e ler par',self.import_pair),('Importar lote CSV',self.import_csv),('3 exemplos',self.examples),('Catálogo',self.catalog_window),('Configurações OCR',self.ocr_settings_window),('DEMO v1',self.legacy)]:ttk.Button(bar,text=title,command=lambda f=fn:self.guard(f)).pack(side='left',padx=3)
        self.ocr_status=tk.StringVar(value='OCR: verificando mecanismo e idiomas…')
        self.ocr_status_label=tk.Label(root,textvariable=self.ocr_status,anchor='w',fg='#865400',padx=10,wraplength=1100)
        self.ocr_status_label.pack(fill='x')
        panes=ttk.Panedwindow(root,orient='horizontal');panes.pack(fill='both',expand=True,padx=8)
        sidebar=ttk.Frame(panes,width=210);main=ttk.Frame(panes);panes.add(sidebar,weight=1);panes.add(main,weight=7)
        ttk.Label(sidebar,text='PACIENTES NA FILA',padding=6).pack()
        self.cases=ttk.Treeview(sidebar,columns=('nome','etapa'),show='headings',selectmode='browse')
        for c,t,w in [('nome','Paciente',145),('etapa','Etapa',90)]:self.cases.heading(c,text=t);self.cases.column(c,width=w)
        self.cases.pack(fill='both',expand=True);self.cases.bind('<<TreeviewSelect>>',self.select)
        ttk.Button(sidebar,text='Auditoria local',command=lambda:self.guard(self.audit_window)).pack(fill='x',pady=6)
        ttk.Button(sidebar,text='Reanalisar documentos',command=lambda:self.guard(self.reanalyze_case)).pack(fill='x',pady=3)
        self.tabs=ttk.Notebook(main);self.tabs.pack(fill='both',expand=True)
        self.doc_tab=ttk.Frame(self.tabs);self.review_container=ttk.Frame(self.tabs);self.out_tab=ttk.Frame(self.tabs,padding=8)
        self.tabs.add(self.doc_tab,text='1 · Originais lado a lado');self.tabs.add(self.review_container,text='2 · Comparar e conferir');self.tabs.add(self.out_tab,text='3 · Pré-cadastro')
        self.diagnostic_tab=ttk.Frame(self.tabs,padding=8)
        self.tabs.add(self.diagnostic_tab,text='Diagnóstico de leitura')
        ttk.Label(self.diagnostic_tab,text='Diagnóstico técnico local: sem nomes, caminhos ou conteúdo clínico.\n'
                  'Campos “Não identificado” precisam de conferência. Use Origem para ver página e trecho.',
                  wraplength=850).pack(anchor='w',pady=8)
        self.diagnostic_table=ttk.Treeview(self.diagnostic_tab,
            columns=('doc','page','executed','method','chars','failure'),show='headings')
        for c,t,w in [('doc','Documento / tipo',180),('page','Página',60),('executed','Leitura executada',120),
                      ('method','Método / idiomas',260),('chars','Caracteres',90),('failure','Resultado',220)]:
            self.diagnostic_table.heading(c,text=t);self.diagnostic_table.column(c,width=w)
        scroll=ttk.Scrollbar(self.diagnostic_tab,orient='vertical',command=self.diagnostic_table.yview)
        self.diagnostic_table.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.diagnostic_table.pack(fill='both',expand=True)
        self.review_canvas=tk.Canvas(self.review_container,highlightthickness=0)
        vs=ttk.Scrollbar(self.review_container,orient='vertical',command=self.review_canvas.yview)
        hs=ttk.Scrollbar(self.review_container,orient='horizontal',command=self.review_canvas.xview)
        self.review_canvas.configure(yscrollcommand=vs.set,xscrollcommand=hs.set)
        self.review_canvas.grid(row=0,column=0,sticky='nsew');vs.grid(row=0,column=1,sticky='ns');hs.grid(row=1,column=0,sticky='ew')
        self.review_container.rowconfigure(0,weight=1);self.review_container.columnconfigure(0,weight=1)
        self.review_tab=ttk.Frame(self.review_canvas,padding=8)
        self.review_window=self.review_canvas.create_window(0,0,window=self.review_tab,anchor='nw')
        self.review_canvas.bind('<Configure>',self.resize_review)
        self.review_tab.bind('<Configure>',lambda e:self.review_canvas.configure(scrollregion=self.review_canvas.bbox('all')))
        originals=ttk.Panedwindow(self.doc_tab,orient='horizontal');originals.pack(fill='both',expand=True)
        self.views={}
        for k,title in [('pedido','Pedido médico'),('guia','Guia autorizada')]:
            self.views[k]=DocumentView(originals,title);originals.add(self.views[k],weight=1)
        self.origin_text=tk.Text(self.doc_tab,height=3,wrap='word',state='disabled')
        self.origin_text.pack(fill='x')
        ttk.Button(self.doc_tab,text='Ir para conferência estruturada →',command=lambda:self.tabs.select(self.review_container)).pack(pady=6)
        self.compare_table=ttk.Treeview(self.review_tab,columns=('nome','code','p','g','pp','pg','status'),show='headings',height=4)
        for c,t,w in [('nome','Exame',170),('code','Interno',90),('p','Pedido',55),('g','Guia',55),('pp','Pág. pedido',70),('pg','Pág. guia',70),('status','Comparação',160)]:self.compare_table.heading(c,text=t);self.compare_table.column(c,width=w)
        self.compare_table.pack(fill='x')
        self.blockers=tk.Text(self.review_tab,height=3,wrap='word',fg='#a43224',state='disabled');self.blockers.pack(fill='x',pady=5)
        self.forms=ttk.Notebook(self.review_tab);self.forms.pack(fill='both',expand=True)
        self.field_vars={};self.field_checks={};self.exam_tables={};self.page_checks={};self.alert_tables={}
        for kind,title in [('pedido','Pedido'),('guia','Guia')]:
            frame=ttk.Frame(self.forms,padding=5);self.forms.add(frame,text=title)
            fields=ttk.Frame(frame);fields.pack(fill='x');self.field_vars[kind]={};self.field_checks[kind]={}
            for i,key in enumerate(FIELDS):
                col=(i%2)*4;r=i//2
                ttk.Label(fields,text=key).grid(row=r,column=col,sticky='w',padx=3)
                var=tk.StringVar();check=tk.BooleanVar();self.field_vars[kind][key]=var;self.field_checks[kind][key]=check
                ent=ttk.Entry(fields,textvariable=var,width=28);ent.grid(row=r,column=col+1,sticky='ew',padx=3,pady=2)
                ttk.Checkbutton(fields,text='Conferido',variable=check).grid(row=r,column=col+2)
                ttk.Button(fields,text='Origem',command=lambda k=kind,f=key:self.locate_field(k,f)).grid(row=r,column=col+3)
                var.trace_add('write',lambda *_,k=kind,f=key:self.changed_field(k,f))
            ttk.Label(frame,text='Exames: selecione uma linha para editar ou conferir. Quantidade nunca é presumida.').pack(anchor='w',pady=5)
            table=ttk.Treeview(frame,columns=('desc','code','q','mat','src','ok'),show='headings',height=4)
            for c,t,w in [('desc','Descrição',190),('code','Código lido',100),('q','Qtd.',45),('mat','Material lido',120),('src','Origem / leitura',170),('ok','Conferido',70)]:table.heading(c,text=t);table.column(c,width=w)
            table.pack(fill='both',expand=True);table.bind('<Double-1>',lambda e,k=kind:self.guard(lambda:self.edit_exam(k)))
            self.exam_tables[kind]=table
            actions=ttk.Frame(frame);actions.pack(fill='x')
            for label,fn in [('Editar / conferir',lambda k=kind:self.edit_exam(k)),('Adicionar exame',lambda k=kind:self.edit_exam(k,True)),('Excluir linha',lambda k=kind:self.delete_exam(k)),('Ver origem',lambda k=kind:self.locate_exam(k))]:ttk.Button(actions,text=label,command=lambda f=fn:self.guard(f)).pack(side='left',padx=2)
            alerts=ttk.Treeview(frame,columns=('msg','ok'),show='headings',height=2);alerts.heading('msg',text='Alertas de cobertura — duplo clique para registrar resolução');alerts.heading('ok',text='Resolvido');alerts.column('msg',width=650);alerts.column('ok',width=70);alerts.pack(fill='x',pady=4);alerts.bind('<Double-1>',lambda e,k=kind:self.guard(lambda:self.resolve_issue(k)));self.alert_tables[kind]=alerts
            v=tk.BooleanVar();self.page_checks[kind]=v;ttk.Checkbutton(frame,text='Conferi visualmente TODAS as páginas e os dados ausentes deste documento',variable=v,command=lambda k=kind:self.check_pages(k)).pack(anchor='w')
        actions=ttk.Frame(self.review_container,padding=5);actions.grid(row=2,column=0,columnspan=2,sticky='ew')
        ttk.Button(actions,text='Salvar conferência e comparar',command=lambda:self.guard(self.save)).pack(side='left')
        self.confirm=tk.BooleanVar();ttk.Checkbutton(actions,text='Conferi o paciente e os documentos',variable=self.confirm).pack(side='left',padx=6)
        self.prepare_button=ttk.Button(actions,text='Preparar pré-cadastro >',command=lambda:self.guard(self.prepare));self.prepare_button.pack(side='right')
        self.output=tk.Text(self.out_tab,state='disabled',wrap='word');self.output.pack(fill='both',expand=True)
        ttk.Button(self.out_tab,text='Salvar pré-cadastro JSON',command=lambda:self.guard(self.export)).pack(pady=8)
        self.status=tk.StringVar(value='Escolha um pedido e a guia correspondente ou carregue os exemplos sintéticos.')
        ttk.Label(root,textvariable=self.status,padding=8).pack(fill='x')
        self.refresh();self.poll_id=root.after(150,self.poll)
        root.bind('<Destroy>',self.cancel_poll,add='+')
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.check_ocr()
    def check_ocr(self,exe=None,save=False):
        self.ocr_request+=1;request=self.ocr_request;self.ocr_health=None
        self.ocr_status.set('OCR: testando leitura local em português e inglês…')
        self.ocr_status_label.configure(fg='#865400')
        dialog=self.ocr_dialog
        if dialog and dialog['window'].winfo_exists():
            dialog['result'].set('Testando o executável, os idiomas e a leitura de uma imagem fictícia…')
            dialog['button'].configure(state='disabled')
        def run():
            result=check_ocr_health(exe=exe,settings_path=self.ocr_settings_path)
            # A gravação ocorre na thread principal, após conferir que esta é a
            # solicitação mais recente e que a janela continua aberta.
            self.events.put(('ocr_health',request,result,save,dialog))
        threading.Thread(target=run,daemon=True).start()
    def finish_ocr_check(self,request,result,save,dialog):
        if request!=self.ocr_request:return
        active=bool(dialog and dialog['window'].winfo_exists())
        if save and not active:
            self.check_ocr();return
        if save and result['ok'] and active:
            try:save_settings(result['exe'],self.ocr_settings_path)
            except Exception as exc:result={'ok':False,'message':safe_failure(exc),'languages':[]}
        self.ocr_health=result
        self.ocr_status.set(result['message'])
        self.ocr_status_label.configure(fg='#24633d' if result['ok'] else '#a43224')
        if active:
            dialog['button'].configure(state='normal')
            dialog['result'].set(result['message']+(' · Caminho salvo para os próximos usos.' if save and result['ok'] else ''))
            if result['ok']:dialog['path'].set(result['exe'])
    def ocr_settings_window(self):
        if self.ocr_dialog and self.ocr_dialog['window'].winfo_exists():
            self.ocr_dialog['window'].lift();return
        window=tk.Toplevel(self.root);window.title('Configurações OCR · somente neste computador')
        window.transient(self.root);window.grab_set()
        ttk.Label(window,text='Selecione o tesseract.exe instalado neste computador.\n'
                  'Os idiomas português e inglês já acompanham o programa na pasta tessdata.',padding=12).pack(anchor='w')
        try:selected=load_settings(self.ocr_settings_path).get('tesseract_path','')
        except ValueError:selected=''
        path=tk.StringVar(value=tesseract_exe(self.ocr_settings_path) or selected or '')
        ttk.Entry(window,textvariable=path,width=85).pack(fill='x',padx=12)
        result=tk.StringVar(value='O caminho só será salvo após um teste real de OCR aprovado.')
        ttk.Label(window,textvariable=result,wraplength=650,padding=12).pack(fill='x')
        bar=ttk.Frame(window,padding=12);bar.pack(fill='x')
        def choose():
            filename=filedialog.askopenfilename(parent=window,title='Selecione tesseract.exe',
                filetypes=[('Executável Tesseract','tesseract.exe'),('Executáveis','*.exe'),('Todos os arquivos','*')])
            if filename:path.set(filename);result.set('Caminho escolhido. Clique em Testar e salvar.')
        def auto():
            found=tesseract_exe(self.ocr_settings_path,include_saved=False)
            path.set(found or '')
            result.set('Executável localizado. Clique em Testar e salvar.' if found else
                       'Não localizado. Clique em Selecionar tesseract.exe e procure na sua pasta Downloads.')
        ttk.Button(bar,text='Selecionar tesseract.exe…',command=choose).pack(side='left',padx=3)
        ttk.Button(bar,text='Localizar automaticamente',command=auto).pack(side='left',padx=3)
        def test():
            value=path.get().strip().strip('"')
            if not value:result.set('Selecione primeiro o arquivo tesseract.exe.');return
            self.check_ocr(exe=value,save=True)
        button=ttk.Button(bar,text='Testar e salvar',command=test);button.pack(side='left',padx=3)
        ttk.Button(bar,text='Fechar',command=window.destroy).pack(side='left',padx=3)
        self.ocr_dialog={'window':window,'path':path,'result':result,'button':button,'choose':choose,'test':test,'auto':auto}
    def resize_review(self,event=None):
        self.review_canvas.itemconfigure(self.review_window,width=max(self.review_canvas.winfo_width(),self.review_tab.winfo_reqwidth()),height=max(self.review_canvas.winfo_height(),self.review_tab.winfo_reqheight()))
        self.review_canvas.configure(scrollregion=self.review_canvas.bbox('all'))
    def guard(self,fn):
        try:
            if self.busy:raise ValueError('Aguarde a leitura terminar.')
            fn()
        except Exception as exc:messagebox.showerror('Ação não concluída',str(exc))
    def callback_failure(self,exc_type,exc,tb):
        # Tkinter por padrão escreve tracebacks com possíveis caminhos pessoais no console.
        messagebox.showerror('Falha na interface',safe_failure(exc))
    def cancel_poll(self,event):
        if event.widget==self.root and self.poll_id:
            self.root.after_cancel(self.poll_id);self.poll_id=None
    def set_text(self,w,text):
        w.configure(state='normal');w.delete('1.0','end');w.insert('1.0',text);w.configure(state='disabled')
    def changed_field(self,kind,key):
        if not self.loading:self.field_checks[kind][key].set(False);self.confirm.set(False)
    def collect(self):
        if not self.models:raise ValueError('Selecione um paciente.')
        m=copy.deepcopy(self.models)
        for k in m:
            for f in FIELDS:
                value=self.field_vars[k][f].get().strip()
                m[k]['fields'][f]['value']='' if value.casefold()==UNIDENTIFIED.casefold() else value
                m[k]['fields'][f]['reviewed']=self.field_checks[k][f].get()
            m[k]['pages_reviewed']=self.page_checks[k].get()
        return m
    def dirty(self):
        return self.cid and digest(self.collect())!=digest(self.store.get(self.cid)[0]['models'])
    def refresh(self):
        self.cases.delete(*self.cases.get_children())
        for cid,cur,status in self.store.db.execute('SELECT id,current,status FROM casos_v2 ORDER BY rowid'):
            name=json.loads(cur)['models']['pedido']['fields']['Paciente']['value'] or 'Identidade pendente'
            self.cases.insert('','end',iid=cid,values=(name,status))
    def select(self,event=None):
        s=self.cases.selection()
        if not s or s[0]==self.cid:return
        if self.cid and self.dirty():
            if not messagebox.askyesno('Conferência não salva','Descartar as alterações não salvas e abrir o outro paciente?'):
                self.cases.selection_set(self.cid);return
        self.open_case(s[0])
    def open_case(self,cid,restore_diagnostics=True):
        self.cid=cid;obj,self.rev,status,out=self.store.get(cid);self.models=copy.deepcopy(obj['models']);self.loading=True
        self.set_text(self.origin_text,'Selecione Origem em um campo ou exame para localizar sua fonte.')
        try:
            for k in self.models:
                if restore_diagnostics:
                    d=obj['docs'][k]
                    self.update_diagnostic('Caso selecionado · '+k,document_diagnostics(d),d.get('document_type',UNIDENTIFIED))
                for f in FIELDS:
                    self.field_vars[k][f].set(self.models[k]['fields'][f]['value'] or UNIDENTIFIED)
                    self.field_checks[k][f].set(self.models[k]['fields'][f]['reviewed'])
                self.page_checks[k].set(self.models[k]['pages_reviewed']);self.views[k].load(obj['docs'][k]);self.render_rows(k)
        finally:self.loading=False
        self.confirm.set(False);self.prepare_button.configure(state='disabled' if status=='PREPARADO' else 'normal');self.show_comparison()
        self.set_text(self.output,json.dumps(out,ensure_ascii=False,indent=2) if out else 'Pré-cadastro ainda não preparado. Conclua a conferência.')
        self.status.set(f'Revisão {self.rev} · {status}')
    def render_rows(self,k):
        t=self.exam_tables[k];t.delete(*t.get_children())
        for i,e in enumerate(self.models[k]['exams']):t.insert('','end',iid=str(i),values=(e['descricao'],e['codigo'],e['quantidade'],e['material'],f'Pág. {e["page"] or "manual"} · '+('INCERTO' if e['confidence'] is not None and e['confidence']<80 else 'Conferir original'), 'Sim' if e['reviewed'] else 'Não'))
        t=self.alert_tables[k];t.delete(*t.get_children())
        for i,a in enumerate(self.models[k]['issues']):t.insert('','end',iid=str(i),values=(a['message'],'Sim' if a['reviewed'] else 'Não'))
    def show_comparison(self):
        m=self.collect();self.analysis=compare_models(m['pedido'],m['guia'],self.catalog)
        t=self.compare_table;t.delete(*t.get_children())
        for r in self.analysis['exames']:t.insert('','end',values=(r['nome'],r['codigo_shift'],r['pedido'],r['guia'],r['pagina_pedido'],r['pagina_guia'],r['situacao']))
        errors=self.analysis['pendencias']+review_errors(m)
        self.blockers.configure(fg='#a43224' if errors else '#24633d')
        self.set_text(self.blockers,'\n'.join('• '+e for e in errors) or 'Conferência salva sem pendências. Marque a confirmação final e prepare o pré-cadastro.')
    def locate_field(self,k,f):
        if not self.models:return
        src=self.models[k]['fields'][f]
        conf=src['confidence'];self.status.set(f'{f}: página {src["page"] or "não localizada"}; confiança OCR {conf if conf is not None else "não disponível"}. Texto digital também exige revisão.')
        self.views[k].locate(src['page'],src['box']);self.tabs.select(self.doc_tab)
        if src.get('snippet'):
            self.set_text(self.origin_text,
                f'Origem de {f}: {k} · Página: {src["page"]}\nTrecho: {src["snippet"]}')
    def locate_exam(self,k):
        s=self.exam_tables[k].selection()
        if s:
            e=self.models[k]['exams'][int(s[0])];self.views[k].locate(e['page'],e['box']);self.tabs.select(self.doc_tab)
            self.set_text(self.origin_text,f'Origem do exame: {k} · Página: {e["page"]}\nTrecho: {e.get("snippet",e.get("raw",""))}')
    def edit_exam(self,k,new=False):
        if not self.models:raise ValueError('Selecione um paciente.')
        s=self.exam_tables[k].selection()
        if not new and not s:raise ValueError('Selecione um exame.')
        idx=len(self.models[k]['exams']) if new else int(s[0])
        old={'descricao':'','codigo':'','quantidade':'','material':'','page':None,'box':None,'confidence':None,'reviewed':False,'raw':'','notes':['Inclusão manual']} if new else self.models[k]['exams'][idx]
        w=tk.Toplevel(self.root);w.title('Conferir exame · '+k);w.transient(self.root);w.grab_set();variables={}
        for i,(key,label) in enumerate([('descricao','Descrição'),('codigo','Código lido (interno ou TUSS)'),('quantidade','Quantidade'),('material','Material lido'),('page','Página de origem')]):
            ttk.Label(w,text=label).grid(row=i,column=0,padx=10,pady=6,sticky='w');v=tk.StringVar(value=str(old[key] or ''));variables[key]=v;ttk.Entry(w,textvariable=v,width=48).grid(row=i,column=1,padx=10)
        ttk.Label(w,text='\n'.join(old.get('notes',[])) or 'Compare a linha com o original.',wraplength=500).grid(row=5,column=0,columnspan=2,padx=10,pady=8)
        checked=tk.BooleanVar(value=old['reviewed'])
        for v in variables.values():v.trace_add('write',lambda *_:checked.set(False))
        ttk.Checkbutton(w,text='Conferi este exame no documento original',variable=checked).grid(row=6,column=0,columnspan=2)
        def commit():
            try:
                e={**old,**{key:v.get().strip() for key,v in variables.items()},'reviewed':checked.get()}
                if not e['descricao']:raise ValueError('Informe a descrição.')
                if not e['quantidade'].isdigit() or not 1<=int(e['quantidade'])<=999:raise ValueError('Quantidade deve ser de 1 a 999.')
                if not e['page'].isdigit() or not 1<=int(e['page'])<=len(self.views[k].doc['pages']):raise ValueError('Indique uma página válida do documento.')
                e['page']=int(e['page'])
                if e['page']!=old['page']:e['box']=None
                if new:self.models[k]['exams'].append(e)
                else:self.models[k]['exams'][idx]=e
                self.confirm.set(False);self.render_rows(k);self.show_comparison();w.destroy()
            except Exception as exc:messagebox.showerror('Conferir exame',str(exc),parent=w)
        ttk.Button(w,text='Aplicar à conferência',command=commit).grid(row=7,column=0,columnspan=2,pady=12)
    def delete_exam(self,k):
        s=self.exam_tables[k].selection()
        if s:
            reason=simpledialog.askstring('Excluir linha','Motivo da exclusão (por exemplo: rodapé reconhecido como exame):')
            if not reason:return
            e=self.models[k]['exams'].pop(int(s[0]));self.models[k]['issues'].append({'message':'Linha excluída: '+e['raw'],'reviewed':True,'reason':reason});self.render_rows(k);self.confirm.set(False);self.show_comparison()
    def resolve_issue(self,k):
        s=self.alert_tables[k].selection()
        if not s:return
        issue=self.models[k]['issues'][int(s[0])]
        reason=simpledialog.askstring('Conferência do alerta',issue['message']+'\n\nDescreva o que conferiu/corrigiu no original:',initialvalue=issue['reason'])
        if reason and reason.strip():issue.update(reviewed=True,reason=reason.strip());self.confirm.set(False);self.render_rows(k)
    def check_pages(self,k):
        if not self.models:self.page_checks[k].set(False);return
        if self.page_checks[k].get() and len(self.views[k].seen)!=len(self.views[k].doc['pages']):
            self.page_checks[k].set(False);messagebox.showinfo('Páginas pendentes','Abra todas as páginas deste documento na aba Originais antes de confirmar.')
        self.confirm.set(False)
    def save(self):
        m=self.collect()
        reason=simpledialog.askstring('Salvar conferência','Motivo / observação desta revisão:',initialvalue='Conferência dos campos e exames com os originais')
        if not reason:return
        self.store.save(self.cid,m,self.actor.get(),reason,self.rev);self.rev+=1;self.models=m;self.confirm.set(False);[self.render_rows(k) for k in self.models];self.show_comparison();self.refresh();self.status.set(f'Conferência salva · revisão {self.rev}')
    def prepare(self):
        if not self.cid:raise ValueError('Selecione um paciente.')
        if self.dirty():raise ValueError('Salve a conferência antes de preparar.')
        out=self.store.prepare(self.cid,self.catalog,self.actor.get(),self.rev,self.analysis['catalogo_hash'],self.confirm.get())
        self.set_text(self.output,json.dumps(out,ensure_ascii=False,indent=2));self.tabs.select(self.out_tab);self.prepare_button.configure(state='disabled');self.refresh();self.status.set('Pré-cadastro preparado localmente. Nada foi enviado ao Shift.')
    def export(self):
        if not self.cid:raise ValueError('Selecione um paciente.')
        out=self.store.get(self.cid)[3]
        if not out:raise ValueError('Prepare o pré-cadastro primeiro.')
        p=filedialog.asksaveasfilename(title='Salvar pré-cadastro local',defaultextension='.json',initialfile='pre_cadastro_'+self.cid[:8]+'.json',filetypes=[('JSON','*.json')])
        if p:Path(p).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');self.status.set('JSON salvo. Nenhum cadastro ou impressão enviado.')
    def import_pair(self):
        if self.cid and self.dirty():raise ValueError('Salve a conferência atual antes de importar novos documentos.')
        opts={'filetypes':[('Documentos','*.pdf *.png *.jpg *.jpeg *.txt')]}
        p=filedialog.askopenfilename(title='1. Pedido médico',**opts)
        if not p:return
        g=filedialog.askopenfilename(title='2. Guia do MESMO paciente',**opts)
        if g:self.import_pairs([(Path(p),Path(g))])
    def import_csv(self):
        if self.cid and self.dirty():raise ValueError('Salve a conferência atual antes de importar.')
        f=filedialog.askopenfilename(title='Lote CSV: colunas pedido;guia',filetypes=[('CSV','*.csv')])
        if not f:return
        self.import_pairs(load_manifest(f))
    def examples(self):
        if self.cid and self.dirty():raise ValueError('Salve a conferência antes de carregar exemplos.')
        self.import_pairs([(ROOT/'exemplos'/f'{i}_pedido.txt',ROOT/'exemplos'/f'{i}_guia.txt') for i in ['01','02','03']])
    def reanalyze_case(self):
        if not self.cid:raise ValueError('Selecione um atendimento na fila.')
        if self.dirty():raise ValueError('Salve a conferência atual antes de reanalisar.')
        if not self.actor.get().strip():raise ValueError('Informe o revisor antes de reanalisar.')
        obj,revision,status,_=self.store.get(self.cid)
        if status=='PREPARADO':raise ValueError('Pré-cadastro já preparado; reanálise bloqueada para preservar a conferência.')
        paths=[]
        for k in ['pedido','guia']:
            d=obj['docs'][k]
            local=self.data/'documentos'/(d['sha256']+Path(d['file']).suffix.lower())
            if not local.is_file():local=Path(d.get('local_path',''))
            if not local.is_file():raise ValueError('Original local ausente. Restaure a pasta dados_v2/documentos do backup.')
            paths.append(local)
        if not messagebox.askyesno('Reanalisar documentos',
            'Ler novamente os mesmos documentos após ajustar o OCR?\n'
            'A nova leitura substituirá os campos atuais e exigirá nova conferência. O histórico anterior será preservado.'):
            return
        self.import_pairs([paths],reanalysis={'cid':self.cid,'revision':revision,
            'files':{d['sha256']:d['file'] for d in obj['docs'].values()}})
    def import_pairs(self,pairs,reanalysis=None):
        if self.busy:raise ValueError('Aguarde a leitura terminar.')
        pairs=[(Path(p),Path(g)) for p,g in pairs]
        if not 1<=len(pairs)<=100:raise ValueError('Selecione entre 1 e 100 pares.')
        self.import_sequence+=1;sequence=self.import_sequence
        self.busy=True;self.status.set('Lendo localmente. OCR pode levar alguns minutos…');cat=copy.deepcopy(self.catalog)
        self.progress=tk.Toplevel(self.root);self.progress.title('Leitura local em andamento');self.progress.transient(self.root);self.progress.grab_set();self.progress.protocol('WM_DELETE_WINDOW',lambda:None)
        ttk.Label(self.progress,text='Lendo os documentos neste computador…\nAguarde a conclusão do lote.',padding=25).pack()
        indicator=ttk.Progressbar(self.progress,mode='indeterminate',length=330);indicator.pack(padx=25,pady=15);indicator.start()
        def run():
            try:
                for number,(p,g) in enumerate(pairs,1):
                    docs={};models={};failed=False
                    for k,path in [('pedido',p),('guia',g)]:
                        label=f'Lote {sequence} · Par {number} · {k}'
                        self.events.put(('diagnostic',label,[],'Lendo…'))
                        try:
                            d=read_document(path,settings_path=self.ocr_settings_path)
                            if reanalysis:d['file']=reanalysis['files'].get(d['sha256'],d['file'])
                            self.events.put(('diagnostic',label,document_diagnostics(d),d['document_type']))
                            raw=path.read_bytes()
                            if hashlib.sha256(raw).hexdigest()!=d['sha256']:raise ValueError('Arquivo mudou durante a leitura.')
                            dest=self.data/'documentos'/(d['sha256']+path.suffix.lower())
                            dest.write_bytes(raw);d['local_path']=str(dest.resolve());docs[k]=d
                        except Exception as exc:
                            failed=True
                            self.events.put(('diagnostic',label,[],safe_failure(exc)))
                            self.events.put(('error',safe_failure(exc)))
                    if failed:continue
                    # Troca segura somente quando AMBOS os títulos identificam a inversão.
                    if docs['pedido']['document_type']=='guia' and docs['guia']['document_type']=='pedido':
                        docs={'pedido':docs['guia'],'guia':docs['pedido']}
                    for k,d in docs.items():
                        models[k]=parse_document(d,cat)
                        if d['document_type']!=k:
                            models[k]['issues'].append({'message':'Tipo do documento não confirmado como '+k+'. Confira o original.',
                                                       'reviewed':False,'reason':''})
                    self.events.put(('reanalyzed',reanalysis,docs,models) if reanalysis else ('case',docs,models))
            except Exception as exc:self.events.put(('error',safe_failure(exc)))
            finally:self.events.put(('done',))
        threading.Thread(target=run,daemon=True).start()
    def update_diagnostic(self,label,rows,result):
        table=self.diagnostic_table
        for item in table.get_children():
            if table.item(item,'values')[0]==label:table.delete(item)
        if not rows:
            table.insert('','end',values=(label,'—','Em andamento' if result=='Lendo…' else 'Falhou',
                                        '—',0,result));return
        for row in rows:
            method=row['method']+(' · '+row['languages'] if row['languages'] else '')
            table.insert('','end',values=(label,row['page'],'Sim' if row['executed'] else 'Não',
                method,row['characters'],
                'FALHA: '+row['detail'] if row['failed'] else 'Lido · tipo: '+result))
    def poll(self):
        try:
            while True:
                item=self.events.get_nowait()
                if item[0]=='case':
                    try:
                        cid=self.store.add(item[1],item[2],self.actor.get());self.refresh();self.cases.selection_set(cid);self.open_case(cid,restore_diagnostics=False);self.tabs.select(self.review_container)
                    except Exception as exc:messagebox.showwarning('Importação',str(exc))
                elif item[0]=='reanalyzed':
                    info,docs,models=item[1:]
                    self.store.save(info['cid'],models,self.actor.get(),'Reanálise local após configuração OCR',
                                    info['revision'],documents=docs)
                    self.refresh();self.cases.selection_set(info['cid']);self.open_case(info['cid'],restore_diagnostics=False)
                    self.tabs.select(self.review_container)
                elif item[0]=='diagnostic':self.update_diagnostic(*item[1:])
                elif item[0]=='ocr_health':self.finish_ocr_check(*item[1:])
                elif item[0]=='error':messagebox.showwarning('Documento não importado',item[1])
                else:
                    self.busy=False;self.progress.grab_release();self.progress.destroy()
                    self.status.set('Leitura encerrada. Confira os campos e as falhas na aba Diagnóstico de leitura.');self.refresh()
        except queue.Empty:pass
        except Exception as exc:
            # Uma falha de atualização não deve interromper para sempre o consumo
            # da fila, deixando o modal e o estado busy presos.
            messagebox.showwarning('Falha ao atualizar a interface',safe_failure(exc))
        finally:self.poll_id=self.root.after(150,self.poll)
    def catalog_window(self):
        w=tk.Toplevel(self.root);w.title('Catálogo local configurável');w.geometry('950x540')
        ttk.Label(w,text='Catálogo de exemplo: substitua pelos códigos e materiais aprovados pelo laboratório. Duplo clique para editar.',padding=8).pack(fill='x')
        t=ttk.Treeview(w,columns=('name','code','tuss','syn','mat'),show='headings')
        for c,title in [('name','Exame'),('code','Interno'),('tuss','TUSS'),('syn','Sinônimos'),('mat','Material')]:t.heading(c,text=title);t.column(c,width=170)
        t.pack(fill='both',expand=True)
        def refresh():
            t.delete(*t.get_children())
            for i,r in enumerate(self.catalog):t.insert('','end',iid=str(i),values=(r['nome'],r['codigo_shift'],r.get('tuss') or '',', '.join(r['sinonimos']),r['material']))
        def install(rows):
            if self.cid and self.dirty():raise ValueError('Salve a conferência atual antes de alterar o catálogo.')
            temp=self.data/'catalogo_validar.json';temp.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8');valid=catalog_load(temp);temp.unlink()
            if not self.actor.get().strip():raise ValueError('Informe o revisor na tela principal.')
            with self.store.db:self.store.audit(None,'CATALOGO',{'revisor':self.actor.get(),'antes':self.catalog,'depois':valid})
            self.catalog_path.write_text(json.dumps(valid,ensure_ascii=False,indent=2),encoding='utf-8');self.catalog=valid
            if self.cid:
                for m in self.models.values():
                    for e in m['exams']:e['reviewed']=False
                self.confirm.set(False)
                for k in self.models:self.render_rows(k)
                self.show_comparison()
            refresh()
        def edit(new=False):
            s=t.selection()
            if not new and not s:return
            idx=len(self.catalog) if new else int(s[0]);row={} if new else self.catalog[idx]
            editw=tk.Toplevel(w);editw.title('Exame do catálogo');vs={}
            for i,(k,title) in enumerate([('nome','Nome'),('codigo_shift','Código interno'),('tuss','TUSS (opcional)'),('sinonimos','Sinônimos separados por ;'),('material','Material')]):
                ttk.Label(editw,text=title).grid(row=i,column=0,padx=8,pady=5);v=tk.StringVar(value='; '.join(row.get(k,[])) if k=='sinonimos' else row.get(k) or '');vs[k]=v;ttk.Entry(editw,textvariable=v,width=52).grid(row=i,column=1,padx=8)
            def done():
                r={**row,**{k:v.get().strip() for k,v in vs.items()}};r['sinonimos']=[s.strip() for s in r['sinonimos'].split(';') if s.strip()];r['tuss']=r['tuss'] or None
                rows=copy.deepcopy(self.catalog)
                if new:rows.append(r)
                else:rows[idx]=r
                install(rows);editw.destroy()
            ttk.Button(editw,text='Salvar catálogo',command=lambda:self.guard(done)).grid(row=5,column=0,columnspan=2,pady=12)
        def load():
            p=filedialog.askopenfilename(title='Catálogo JSON',filetypes=[('JSON','*.json')])
            if p:install(catalog_load(p))
        def equiv():
            s=t.selection()
            if not s:return
            code=simpledialog.askstring('Equivalência explícita','Código equivalente aprovado para este exame (não cria equivalência de quantidades):',parent=w)
            if not code:return
            reason=simpledialog.askstring('Aprovação da equivalência','Justificativa da aprovação:',parent=w)
            if not reason:return
            from datetime import datetime
            rows=copy.deepcopy(self.catalog);rows[int(s[0])].setdefault('equivalencias',[]).append({'codigo':code.strip(),'aprovada':True,'aprovado_por':self.actor.get().strip(),'aprovado_em':datetime.now().isoformat(),'justificativa':reason})
            install(rows)
        t.bind('<Double-1>',lambda e:self.guard(edit));bar=ttk.Frame(w);bar.pack(fill='x')
        for title,fn in [('Adicionar',lambda:edit(True)),('Editar',edit),('Importar JSON',load),('Aprovar código equivalente',equiv)]:ttk.Button(bar,text=title,command=lambda f=fn:self.guard(f)).pack(side='left',padx=5,pady=8)
        refresh()
    def audit_window(self):
        w=tk.Toplevel(self.root);w.title('Histórico local de conferências');t=tk.Text(w,wrap='word');t.pack(fill='both',expand=True)
        rows=self.store.db.execute('SELECT * FROM audit_v2 ORDER BY rowid DESC LIMIT 100').fetchall();self.set_text(t,'\n\n'.join(' | '.join(map(str,r)) for r in rows))
    def legacy(self):
        import app_v1
        w=tk.Toplevel(self.root);app_v1.App(w)
    def close(self):
        if self.busy:
            messagebox.showinfo('Leitura em andamento','Aguarde terminar antes de fechar.');return
        if self.cid and self.dirty() and not messagebox.askyesno('Alterações não salvas','Descartar a conferência não salva e fechar?'):return
        self.store.db.close();self.root.destroy()


def load_manifest(file):
    file=Path(file);base=file.parent.resolve()
    with file.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f,delimiter=';'))
    if not rows or len(rows)>100:raise ValueError('Lote deve ter entre 1 e 100 pares.')
    pairs=[];seen=set()
    for row in rows:
        pair=[]
        for k in ['pedido','guia']:
            value=row.get(k,'').strip()
            if not value:raise ValueError('CSV precisa das colunas pedido;guia preenchidas.')
            path=(base/value).resolve()
            if not path.is_relative_to(base) or not path.is_file():raise ValueError('Arquivo inexistente ou fora da pasta do lote: '+value)
            if path in seen:raise ValueError('Um documento foi associado a mais de um par. Confira o CSV.')
            seen.add(path);pair.append(path)
        pairs.append(tuple(pair))
    return pairs


if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
