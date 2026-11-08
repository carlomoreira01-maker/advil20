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
NOT_APPLICABLE='Não se aplica (perfil)'
IMPORT_MODES={'single':'Um atendimento — várias páginas','multiple':'Vários pacientes — verificar identificação'}


class DocumentView(ttk.Frame):
    def __init__(self,parent,title):
        super().__init__(parent)
        self.path=None;self.doc=None;self.index=0;self.zoom=1.;self.box=None
        self.seen=set();self.rotation_offset=0
        self.on_page=None
        bar=ttk.Frame(self);bar.pack(fill='x')
        ttk.Label(bar,text=title,font=('Segoe UI',11,'bold')).pack(side='left')
        for text,fn in [('<',lambda:self.move(-1)),('>',lambda:self.move(1)),('-',lambda:self.scale(.8)),('+',lambda:self.scale(1.25))]:ttk.Button(bar,text=text,width=3,command=fn).pack(side='left',padx=1)
        ttk.Button(bar,text='Girar',width=5,command=self.rotate).pack(side='left',padx=2)
        self.info=tk.StringVar();ttk.Label(self,textvariable=self.info).pack(anchor='w')
        frame=ttk.Frame(self);frame.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(frame,bg='#dfe6eb',highlightthickness=0)
        vy=ttk.Scrollbar(frame,orient='vertical',command=self.canvas.yview);hx=ttk.Scrollbar(frame,orient='horizontal',command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vy.set,xscrollcommand=hx.set)
        self.canvas.grid(row=0,column=0,sticky='nsew');vy.grid(row=0,column=1,sticky='ns');hx.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
    def load(self,doc):
        self.doc=doc;self.path=doc.get('local_path');self.index=0;self.zoom=1.;self.box=None;self.seen=set();self.rotation_offset=0;self.render()
    def move(self,delta):
        if self.doc:self.index=max(0,min(len(self.doc['pages'])-1,self.index+delta));self.box=None;self.render()
    def rotate(self):
        self.rotation_offset=(self.rotation_offset+90)%360;self.render()
    def scale(self,factor):
        self.zoom=max(.3,min(4,self.zoom*factor));self.render()
    def locate(self,page,box):
        if not self.doc or not page:return
        self.index=max(0,min(len(self.doc['pages'])-1,int(page)-1));self.box=box;self.render()
    def render(self):
        if not self.doc:return
        self.canvas.delete('all')
        if not self.doc['pages']:
            self.info.set('Documento não identificado neste atendimento')
            self.canvas.create_text(15,15,text='Abra Identificar documentos para corrigir a classificação.',anchor='nw');return
        p=self.doc['pages'][self.index];self.seen.add(self.index+1)
        source=p.get('source',{});path=source.get('path',self.path);source_index=source.get('page',self.index+1)-1
        angle=(int(p.get('orientation',0))+self.rotation_offset)%360
        self.info.set(f'Página {self.index+1}/{len(self.doc["pages"])} · original {source_index+1} · {p["method"]} · Rotação {angle}° · Zoom {round(self.zoom*100)}%')
        try:
            if not path or Path(path).suffix.lower()=='.txt':
                self.canvas.create_text(15,15,text=p['text'],anchor='nw',font=('Consolas',11),width=700)
            else:
                from PIL import ImageTk
                im,_=preview(path,source_index)
                if angle:im=im.rotate(angle,expand=True)
                base=min(1,540/max(1,im.width));factor=base*self.zoom
                im=im.resize((max(1,int(im.width*factor)),max(1,int(im.height*factor))))
                self.photo=ImageTk.PhotoImage(im);self.canvas.create_image(0,0,image=self.photo,anchor='nw')
                if self.box:
                    from document_geometry import rotated_box
                    size=list(reversed(p['size'])) if angle in [90,270] else p['size']
                    sx=im.width/size[0];sy=im.height/size[1];b=rotated_box(self.box,p['size'],angle)
                    self.canvas.create_rectangle(b[0]*sx,b[1]*sy,b[2]*sx,b[3]*sy,outline='#dc5b12',width=3)
                    self.canvas.yview_moveto(max(0,b[1]*sy-40)/max(1,im.height))
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))
            if self.on_page:self.on_page(self.index)
        except Exception as exc:self.canvas.create_text(10,10,text='Não foi possível exibir original: '+str(exc),anchor='nw',width=480)


class App:
    def __init__(self,root,data=DATA,demo=False):
        self.root=root;self.data=Path(data);self.data.mkdir(parents=True,exist_ok=True)
        (self.data/'documentos').mkdir(exist_ok=True)
        self.store=CaseStore(self.data/'cadastro_local.sqlite3')
        self.catalog_path=self.data/'catalogo.json'
        self.catalog=catalog_load(self.catalog_path) if self.catalog_path.exists() else catalog_load(ROOT/'catalogo_demo.json') if demo else []
        self.selected_profile=None;self.pending_imports={};self.demo=demo;self.stage_diagnostics={}
        self.cid=None;self.models=None;self.busy=False;self.events=queue.Queue();self.loading=False
        self.ocr_settings_path=settings_file() if self.data.resolve()==DATA.resolve() else self.data/'configuracao_ocr.json'
        self.ocr_request=0;self.ocr_dialog=None;self.ocr_health=None
        self.import_sequence=0
        root.report_callback_exception=self.callback_failure
        root.title('Cadastro Assistido Shift · versão 2.4.5 · Local');root.geometry('1450x950');root.minsize(1100,760)
        st=ttk.Style();st.theme_use('clam');st.configure('TButton',padding=6);st.configure('Treeview',rowheight=28)
        tk.Label(root,text='CADASTRO ASSISTIDO SHIFT  |  2.4.5',font=('Segoe UI',19,'bold'),bg='#173d52',fg='white',anchor='w',padx=18,pady=12).pack(fill='x')
        ttk.Label(root,text='Importar escaneamento → Identificar documentos → Extrair dados → Comparar exames → Conferir → Preparar cadastro',font=('Segoe UI',11,'bold'),padding=8).pack(fill='x')
        ttk.Label(root,text='Processamento local | Revisão humana obrigatória | Pré-cadastro não enviado ao Shift',padding=(10,0)).pack(anchor='w')
        bar=ttk.Frame(root,padding=8);bar.pack(fill='x')
        ttk.Label(bar,text='Revisor:').pack(side='left');self.actor=tk.StringVar(value='');self.actor_entry=ttk.Entry(bar,textvariable=self.actor,width=20);self.actor_entry.pack(side='left',padx=5)
        st.configure('Accent.TButton',font=('Segoe UI',11,'bold'),padding=(12,10))
        self.import_scan_button=ttk.Button(bar,text='IMPORTAR ESCANEAMENTO',style='Accent.TButton',command=lambda:self.guard(self.import_scans));self.import_scan_button.pack(side='left',padx=3)
        ttk.Button(bar,text='Identificar documentos',command=lambda:self.guard(self.classification_window)).pack(side='left',padx=3)
        self.examples_button=ttk.Button(bar,text='Exemplos fictícios',command=lambda:self.guard(self.examples));self.examples_button.pack(side='left',padx=3)
        config_button=ttk.Menubutton(bar,text='Configurações e ferramentas');config_button.pack(side='right',padx=5)
        menu=tk.Menu(config_button,tearoff=False);config_button.configure(menu=menu)
        for title,fn in [('Catálogo do laboratório',self.catalog_window),('Fontes pagadoras',self.payer_window),('Diagnóstico e configuração OCR',self.ocr_settings_window),('Importar par separado (legado)',self.import_pair),('Importar lote CSV (legado)',self.import_csv),('Simulação local fictícia',self.simulation_window),('DEMO v1',self.legacy)]:menu.add_command(label=title,command=lambda f=fn:self.guard(f))
        mode_bar=ttk.Frame(root,padding=(8,0));mode_bar.pack(fill='x')
        ttk.Label(mode_bar,text='Modo de importação:').pack(side='left')
        self.import_mode=tk.StringVar(value=IMPORT_MODES['single'])
        ttk.Combobox(mode_bar,textvariable=self.import_mode,values=list(IMPORT_MODES.values()),state='readonly',width=48).pack(side='left',padx=6)
        self.ocr_status=tk.StringVar(value='OCR: verificando mecanismo e idiomas…')
        self.ocr_status_label=tk.Label(root,textvariable=self.ocr_status,anchor='w',fg='#865400',padx=10,wraplength=1100)
        self.ocr_status_label.pack(fill='x')
        panes=ttk.Panedwindow(root,orient='horizontal');panes.pack(fill='both',expand=True,padx=8)
        sidebar=ttk.Frame(panes,width=210);main=ttk.Frame(panes);panes.add(sidebar,weight=1);panes.add(main,weight=7)
        ttk.Label(sidebar,text='PACIENTES NA FILA',padding=6).pack()
        self.assisted_button=ttk.Button(sidebar,text='CONFERIR ATENDIMENTO',style='Accent.TButton',command=lambda:self.guard(self.assisted_review));self.assisted_button.pack(fill='x',pady=5)
        self.cases=ttk.Treeview(sidebar,columns=('nome','etapa','exames','pendencias'),show='headings',selectmode='browse')
        for c,t,w in [('nome','Paciente',140),('etapa','Etapa',115),('exames','Exames',55),('pendencias','Pend.',50)]:self.cases.heading(c,text=t);self.cases.column(c,width=w)
        self.cases.pack(fill='both',expand=True);self.cases.bind('<<TreeviewSelect>>',self.select)
        ttk.Button(sidebar,text='Auditoria local',command=lambda:self.guard(self.audit_window)).pack(fill='x',pady=6)
        ttk.Button(sidebar,text='Interno sem guia externa',command=lambda:self.guard(self.import_internal)).pack(fill='x',pady=3)
        ttk.Button(sidebar,text='Reprocessar leitura',command=lambda:self.guard(self.reanalyze_case)).pack(fill='x',pady=3)
        self.tabs=ttk.Notebook(main);self.tabs.pack(fill='both',expand=True)
        self.doc_tab=ttk.Frame(self.tabs);self.review_container=ttk.Frame(self.tabs);self.out_tab=ttk.Frame(self.tabs,padding=8)
        from page_panel import PagePanel
        self.page_tab=ttk.Frame(self.tabs);self.tabs.add(self.page_tab,text='Páginas do atendimento')
        self.page_panel=PagePanel(self.page_tab,DocumentView);self.page_panel.pack(fill='both',expand=True)
        page_actions=ttk.Frame(self.page_tab,padding=5);page_actions.pack(fill='x')
        self.page_kind=tk.StringVar(value='pedido')
        old_on_page=self.page_panel.viewer.on_page
        def page_selected(index):
            old_on_page(index)
            if 0<=index<len(self.page_panel.items):self.page_kind.set(self.page_panel.items[index]['kind'])
        self.page_panel.viewer.on_page=page_selected
        ttk.Label(page_actions,text='Tipo da página selecionada:').pack(side='left')
        ttk.Combobox(page_actions,textvariable=self.page_kind,values=['pedido','guia','continuação de pedido','continuação de guia','outro','incerto'],state='readonly',width=24).pack(side='left',padx=4)
        self.page_type_button=ttk.Button(page_actions,text='Corrigir tipo',command=lambda:self.guard(self.correct_page_type));self.page_type_button.pack(side='left',padx=3)
        self.group_confirm_button=ttk.Button(page_actions,text='Confirmar páginas e identidade',command=lambda:self.guard(self.confirm_case_pages));self.group_confirm_button.pack(side='left',padx=3)
        ttk.Button(self.page_tab,text='Corrigir página / agrupamento',command=lambda:self.guard(self.classification_window)).pack(pady=5)
        self.tabs.add(self.doc_tab,text='1 · Originais lado a lado');self.tabs.add(self.review_container,text='2 · Comparar e conferir');self.tabs.add(self.out_tab,text='3 · Pré-cadastro')
        self.diagnostic_tab=ttk.Frame(self.tabs,padding=8)
        self.tabs.add(self.diagnostic_tab,text='Diagnóstico de leitura')
        ttk.Label(self.diagnostic_tab,text='Diagnóstico técnico local: sem nomes, caminhos ou conteúdo clínico.\n'
                  'Campos “Não identificado” precisam de conferência. Use Origem para ver página e trecho.',
                  wraplength=850).pack(anchor='w',pady=8)
        self.diagnostic_table=ttk.Treeview(self.diagnostic_tab,
            columns=('doc','page','executed','method','chars','failure','parse','ui'),show='headings')
        for c,t,w in [('doc','Documento / tipo',180),('page','Página',60),('executed','Leitura executada',120),
                      ('method','Método / idiomas',260),('chars','Caracteres',90),('failure','Leitura',220),('parse','Interpretação',170),('ui','Interface',140)]:
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
        for k,title in [('pedido','Pedido médico'),('guia','Guia SP/SADT · conferir autorização')]:
            self.views[k]=DocumentView(originals,title);originals.add(self.views[k],weight=1)
        self.origin_text=tk.Text(self.doc_tab,height=3,wrap='word',state='disabled')
        self.origin_text.pack(fill='x')
        ttk.Button(self.doc_tab,text='Ir para conferência estruturada →',command=lambda:self.tabs.select(self.review_container)).pack(pady=6)
        self.compare_table=ttk.Treeview(self.review_tab,columns=('nome','code','lido','p','g','pp','pg','status'),show='headings',height=4)
        for c,t,w in [('nome','Exame',170),('code','Interno',75),('lido','Código lido',90),('p','Pedido',55),('g','Guia',55),('pp','Pág. pedido',70),('pg','Pág. guia',70),('status','Comparação',190)]:self.compare_table.heading(c,text=t);self.compare_table.column(c,width=w)
        self.compare_table.pack(fill='x')
        self.blockers=tk.Text(self.review_tab,height=3,wrap='word',fg='#a43224',state='disabled');self.blockers.pack(fill='x',pady=5)
        pending_frame=ttk.Frame(self.review_tab);pending_frame.pack(fill='x')
        self.pending_table=ttk.Treeview(pending_frame,columns=('message','action'),show='headings',height=3)
        self.pending_table.heading('message',text='O que falta para concluir');self.pending_table.column('message',width=650)
        self.pending_table.heading('action',text='Como resolver');self.pending_table.column('action',width=180)
        pending_scroll=ttk.Scrollbar(pending_frame,orient='vertical',command=self.pending_table.yview)
        self.pending_table.configure(yscrollcommand=pending_scroll.set);pending_scroll.pack(side='right',fill='y')
        self.pending_table.pack(fill='x',expand=True);self.pending_table.bind('<Double-1>',lambda e:self.guard(self.navigate_pending))
        self.pending_button=ttk.Button(self.review_tab,text='Resolver pendência selecionada →',command=lambda:self.guard(self.navigate_pending));self.pending_button.pack(anchor='w',pady=3)
        self.na_button=ttk.Button(self.review_tab,text='Aplicar não aplicáveis do perfil',command=lambda:self.guard(self.apply_not_applicable));self.na_button.pack(anchor='w',pady=2)
        self.forms=ttk.Notebook(self.review_tab);self.forms.pack(fill='both',expand=True)
        self.field_vars={};self.field_checks={};self.exam_tables={};self.page_checks={};self.alert_tables={};self.field_tabs={};self.field_entries={}
        for kind,title in [('pedido','Pedido'),('guia','Guia')]:
            frame=ttk.Frame(self.forms,padding=5);self.forms.add(frame,text=title)
            field_tabs=ttk.Notebook(frame);field_tabs.pack(fill='x');self.field_tabs[kind]=field_tabs
            groups={name:ttk.Frame(field_tabs,padding=5) for name in ['Paciente','Guia TISS','Médico e atendimento']}
            for name,group in groups.items():field_tabs.add(group,text=name)
            counts={name:0 for name in groups};self.field_entries[kind]={};self.field_vars[kind]={};self.field_checks[kind]={}
            for key in FIELDS:
                category='Paciente' if key in ['Paciente','Nascimento','Fonte pagadora','Operadora','Carteira','Validade carteira','CPF','CNS'] else 'Médico e atendimento' if key in ['Medico','Conselho','Número conselho','UF conselho','CBO','Código solicitante','Data solicitação','Indicação clínica','Regime atendimento','Data execução'] else 'Guia TISS'
                fields=groups[category];i=counts[category];counts[category]+=1
                col=(i%2)*4;r=i//2
                ttk.Label(fields,text=key+' (legado)' if key in ['Guia','Validade'] else key).grid(row=r,column=col,sticky='w',padx=3)
                var=tk.StringVar();check=tk.BooleanVar();self.field_vars[kind][key]=var;self.field_checks[kind][key]=check
                ent=ttk.Entry(fields,textvariable=var,width=28);self.field_entries[kind][key]=ent;ent.grid(row=r,column=col+1,sticky='ew',padx=3,pady=2)
                ttk.Checkbutton(fields,text='Conferido',variable=check,command=self.review_changed).grid(row=r,column=col+2)
                ttk.Button(fields,text='Origem',command=lambda k=kind,f=key:self.locate_field(k,f)).grid(row=r,column=col+3)
                var.trace_add('write',lambda *_,k=kind,f=key:self.changed_field(k,f))
            ttk.Label(frame,text='Exames: selecione uma linha para editar ou conferir. Quantidade nunca é presumida.').pack(anchor='w',pady=5)
            table=ttk.Treeview(frame,columns=('desc','code','sol','q','mat','src','ok'),show='headings',height=4)
            for c,t,w in [('desc','Descrição',190),('code','Código lido',100),('sol','Solicitada',65),('q','Aut./Qtd.',65),('mat','Material lido',120),('src','Origem / leitura',170),('ok','Conferido',70)]:table.heading(c,text=t);table.column(c,width=w)
            table.pack(fill='both',expand=True);table.bind('<Double-1>',lambda e,k=kind:self.guard(lambda:self.edit_exam(k)))
            self.exam_tables[kind]=table
            actions=ttk.Frame(frame);actions.pack(fill='x')
            for label,fn in [('Editar / conferir',lambda k=kind:self.edit_exam(k)),('Adicionar exame',lambda k=kind:self.edit_exam(k,True)),('Excluir linha',lambda k=kind:self.delete_exam(k)),('Ver origem',lambda k=kind:self.locate_exam(k))]:ttk.Button(actions,text=label,command=lambda f=fn:self.guard(f)).pack(side='left',padx=2)
            alerts=ttk.Treeview(frame,columns=('msg','ok'),show='headings',height=2);alerts.heading('msg',text='Alertas de cobertura — duplo clique para registrar resolução');alerts.heading('ok',text='Resolvido');alerts.column('msg',width=650);alerts.column('ok',width=70);alerts.pack(fill='x',pady=4);alerts.bind('<Double-1>',lambda e,k=kind:self.guard(lambda:self.resolve_issue(k)));self.alert_tables[kind]=alerts
            v=tk.BooleanVar();self.page_checks[kind]=v;ttk.Checkbutton(frame,text='Conferi visualmente TODAS as páginas e os dados ausentes deste documento',variable=v,command=lambda k=kind:self.check_pages(k)).pack(anchor='w')
        actions=ttk.Frame(self.review_container,padding=5);actions.grid(row=2,column=0,columnspan=2,sticky='ew')
        metadata=ttk.Frame(actions);metadata.pack(fill='x',pady=(0,5))
        ttk.Label(metadata,text='Motivo da conferência:').pack(side='left')
        self.review_reason=tk.StringVar(value='Conferência dos campos e exames com os originais')
        self.reason_entry=ttk.Entry(metadata,textvariable=self.review_reason);self.reason_entry.pack(side='left',fill='x',expand=True,padx=5)
        self.review_hint=tk.StringVar(value='Preencha Revisor no topo e confira o motivo antes de salvar.')
        ttk.Label(metadata,textvariable=self.review_hint,foreground='#a43224',wraplength=260).pack(side='right')
        self.prepare_help_button=ttk.Button(metadata,text='Por que está bloqueado?',command=lambda:self.guard(self.explain_prepare));self.prepare_help_button.pack(side='right',padx=4)
        controls=ttk.Frame(actions);controls.pack(fill='x')
        actions=controls
        ttk.Button(actions,text='Corrigir manualmente',command=lambda:self.guard(self.manual_correction)).pack(side='left')
        ttk.Button(actions,text='Conferir campos vistos',command=lambda:self.guard(self.review_fields)).pack(side='left')
        self.save_review_button=ttk.Button(actions,text='Salvar correções e comparar',command=lambda:self.guard(self.save));self.save_review_button.pack(side='left')
        self.confirm=tk.BooleanVar();ttk.Checkbutton(actions,text='Conferi o paciente e os documentos',variable=self.confirm).pack(side='left',padx=6)
        self.prepare_button=ttk.Button(actions,text='Preparar pré-cadastro >',command=lambda:self.guard(self.prepare));self.prepare_button.pack(side='right')
        def blocked_prepare_click(event):
            if str(self.prepare_button['state'])=='disabled':self.guard(self.explain_prepare);return 'break'
        self.prepare_button.bind('<Button-1>',blocked_prepare_click)
        self.output=tk.Text(self.out_tab,state='disabled',wrap='word');self.output.pack(fill='both',expand=True)
        ttk.Button(self.out_tab,text='Salvar pré-cadastro JSON',command=lambda:self.guard(self.export)).pack(pady=8)
        self.status=tk.StringVar(value='Clique em IMPORTAR ESCANEAMENTO. A leitura começa automaticamente.')
        ttk.Label(root,textvariable=self.status,padding=8).pack(fill='x')
        self.refresh();self.poll_id=root.after(150,self.poll)
        root.bind('<Destroy>',self.cancel_poll,add='+')
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.check_ocr()
        self.confirm.trace_add('write',lambda *_:self.update_prepare_state())
        self.actor.trace_add('write',lambda *_:self.update_prepare_state())
        self.review_reason.trace_add('write',lambda *_:self.review_changed())
        self.prepare_button.configure(state='disabled')
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
    def case_stage(self,models,status):
        if status=='PREPARADO':return 'Pronto para pré-cadastro'
        if any(m.get('identity_conflict') for m in models.values()):return 'Conflito de identidade'
        if any(m.get('association_pending') for m in models.values()):return 'Agrupamento provisório'
        errors=compare_models(models['pedido'],models['guia'],self.catalog)['pendencias']
        if any('diverg' in e.lower() or 'Não autorizado' in e for e in errors):return 'Divergência de autorização'
        if errors:return 'Informações incompletas'
        return 'Aguardando conferência' if review_errors(models) else 'Pronto para pré-cadastro'
    def payer_window(self):
        from payer_mapping import load_profiles,map_payer,validate_profile,DESTINATIONS,SOURCES
        path=self.data/'perfis_pagadores.json'
        try:profiles=load_profiles(path) if path.exists() else []
        except ValueError:profiles=[]
        window=tk.Toplevel(self.root);window.title('Fontes pagadoras · configuração local')
        ttk.Label(window,text='Regras precisam de aprovação da equipe. Interno, IPASGO e outros têm escopos separados.\nNunca reutilize senha, matrícula e números de guia como se fossem o mesmo campo.',padding=12).pack()
        picker=ttk.Combobox(window,state='readonly',width=75);picker.pack(fill='x',padx=12)
        result=tk.Text(window,height=12,width=90);result.pack(fill='both',expand=True,padx=12)
        def refresh():picker['values']=[p['nome'] for p in profiles]
        def persist():path.write_text(json.dumps(profiles,ensure_ascii=False,indent=2),encoding='utf-8');refresh()
        def load():
            file=filedialog.askopenfilename(parent=window,title='Perfis homologados JSON',filetypes=[('Perfis','*.json')])
            if not file:return
            try:profiles[:]=load_profiles(file);persist()
            except Exception as exc:messagebox.showerror('Perfil inválido',str(exc),parent=window)
        def choose():
            if picker.current()<0:return
            self.selected_profile=copy.deepcopy(profiles[picker.current()]);self.confirm.set(False)
            if self.models:
                mapping=map_payer(self.collect()['guia'],self.selected_profile)
                result.delete('1.0','end');result.insert('1.0',json.dumps(mapping,ensure_ascii=False,indent=2));self.show_comparison()
        def edit():
            old=profiles[picker.current()] if picker.current()>=0 else {}
            editor=tk.Toplevel(window);editor.title('Definir perfil de atendimento')
            variables={}
            for i,(key,label) in enumerate([('id','Identificador do perfil'),('nome','Nome do perfil'),('fonte_pagadora','Fonte pagadora (como no documento)'),('tipo_atendimento','Tipo/regime de atendimento'),('procedimentos','Códigos abrangidos separados por ; (* só se aprovado)'),('aprovado_por','Responsável pela aprovação'),('aprovado_em','Data da aprovação AAAA-MM-DD')]):
                value=';'.join(old.get(key,[])) if key=='procedimentos' else old.get(key,'')
                var=tk.StringVar(value=value);variables[key]=var
                ttk.Label(editor,text=label).grid(row=i,column=0,sticky='w',padx=8,pady=3);ttk.Entry(editor,textvariable=var,width=55).grid(row=i,column=1,columnspan=2,sticky='ew',padx=8)
            authorization=tk.BooleanVar(value=old.get('exige_autorizacao',True));approved=tk.BooleanVar(value=old.get('homologado',False))
            ttk.Checkbutton(editor,text='Este escopo exige autorização',variable=authorization).grid(row=7,column=0,columnspan=2,sticky='w')
            ttk.Checkbutton(editor,text='Equipe responsável homologou este escopo e mapeamento',variable=approved).grid(row=8,column=0,columnspan=3,sticky='w')
            mapping={};required={};defaults={};default_checks={}
            ttk.Label(editor,text='Campo no Shift').grid(row=9,column=0);ttk.Label(editor,text='Origem no documento').grid(row=9,column=1);ttk.Label(editor,text='Padrão técnico / aprovação individual').grid(row=9,column=3)
            for i,dest in enumerate(sorted(DESTINATIONS),10):
                ttk.Label(editor,text=dest).grid(row=i,column=0,sticky='w',padx=8)
                var=tk.StringVar(value=old.get('mapeamento',{}).get(dest,''));mapping[dest]=var
                ttk.Combobox(editor,textvariable=var,state='readonly',values=['',*sorted(SOURCES)],width=25).grid(row=i,column=1,padx=4)
                required[dest]=tk.BooleanVar(value=dest in old.get('obrigatorios',[]));ttk.Checkbutton(editor,text='Obrigatório',variable=required[dest]).grid(row=i,column=2)
                defaults[dest]=tk.StringVar(value=old.get('valores_tecnicos',{}).get(dest,{}).get('valor',''))
                ttk.Entry(editor,textvariable=defaults[dest],width=18).grid(row=i,column=3)
                default_checks[dest]=tk.BooleanVar(value=dest in old.get('valores_tecnicos',{}));ttk.Checkbutton(editor,text='Padrão aprovado',variable=default_checks[dest]).grid(row=i,column=4)
            def save_profile():
                try:
                    item={key:var.get().strip() for key,var in variables.items()};item['procedimentos']=[x.strip() for x in item['procedimentos'].split(';') if x.strip()]
                    item.update(homologado=approved.get(),exige_autorizacao=authorization.get(),mapeamento={d:v.get() for d,v in mapping.items() if v.get()},obrigatorios=[d for d,v in required.items() if v.get()],valores_tecnicos={})
                    item['campos_nao_aplicaveis']=[k.strip() for k in na_fields.get().split(';') if k.strip()]
                    for dest,var in defaults.items():
                        if var.get().strip():
                            if not default_checks[dest].get():raise ValueError('Padrão técnico só pode ser salvo com aprovação explícita.')
                            item['valores_tecnicos'][dest]={'valor':var.get().strip(),'aprovado_por':item['aprovado_por'],'aprovado_em':item['aprovado_em']}
                    item=validate_profile(item)
                    index=next((i for i,p in enumerate(profiles) if p['id']==item['id']),None)
                    if index is None:profiles.append(item);index=len(profiles)-1
                    else:profiles[index]=item
                    persist();picker.current(index);editor.destroy()
                except Exception as exc:messagebox.showerror('Configuração não salva',str(exc),parent=editor)
            na_fields=tk.StringVar(value=';'.join(old.get('campos_nao_aplicaveis',[])))
            ttk.Label(editor,text='Campos não aplicáveis aprovados (separar por ;)').grid(row=19,column=0,columnspan=2)
            ttk.Entry(editor,textvariable=na_fields,width=55).grid(row=19,column=2,columnspan=3)
            ttk.Button(editor,text='Salvar perfil local',command=save_profile).grid(row=20,column=0,columnspan=5,pady=10)
            self.profile_editor={'window':editor,'variables':variables,'mapping':mapping,'required':required,'authorization':authorization,'approved':approved,'save':save_profile}
        bar=ttk.Frame(window,padding=10);bar.pack(fill='x')
        for title,fn in [('Novo / editar perfil',edit),('Importar perfis JSON',load),('Aplicar ao atendimento',choose)]:ttk.Button(bar,text=title,command=fn).pack(side='left',padx=5)
        self.payer_manager={'window':window,'edit':edit,'choose':choose,'picker':picker};refresh()
    def import_internal(self):
        from internal_workflow import build_internal
        if not self.selected_profile:raise ValueError('Selecione primeiro um perfil interno homologado em Fontes pagadoras.')
        file=filedialog.askopenfilename(title='Pedido do atendimento interno',filetypes=[('Documento','*.pdf *.png *.jpg *.txt')])
        if not file:return
        document=read_document(file,settings_path=self.ocr_settings_path);model=parse_document(document,self.catalog)
        raw=Path(file).read_bytes();dest=self.data/'documentos'/(document['sha256']+Path(file).suffix.lower());dest.write_bytes(raw);document['local_path']=str(dest.resolve())
        doc,guide=build_internal(document,model,self.selected_profile)
        cid=self.store.add({'pedido':document,'guia':doc},{'pedido':model,'guia':guide},self.actor.get())
        self.refresh();self.cases.selection_set(cid);self.open_case(cid);self.tabs.select(self.review_container)
    def simulation_window(self):
        from simulador import start_simulator
        import webbrowser
        if not getattr(self,'simulator',None):self.simulator=start_simulator()
        webbrowser.open(self.simulator.url)
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
        if event.widget==self.root and getattr(self,'compare_after',None):
            self.root.after_cancel(self.compare_after);self.compare_after=None
    def set_text(self,w,text):
        w.configure(state='normal');w.delete('1.0','end');w.insert('1.0',text);w.configure(state='disabled')
    def changed_field(self,kind,key):
        if not self.loading:
            self.field_checks[kind][key].set(False);self.review_changed()
    def review_changed(self):
        if self.loading or not self.models:return
        self.confirm.set(False)
        if getattr(self,'compare_after',None):self.root.after_cancel(self.compare_after)
        self.compare_after=self.root.after(180,self.live_comparison)
    def live_comparison(self):
        self.compare_after=None
        if self.models and not self.loading:self.show_comparison()
    def update_prepare_state(self):
        if not hasattr(self,'prepare_button'):return
        ready=bool(self.cid and self.models and not getattr(self,'comparison_errors',[True]) and self.confirm.get()
                   and self.actor.get().strip() and self.review_reason.get().strip() and not self.dirty() and self.store.get(self.cid)[2]!='PREPARADO')
        self.prepare_button.configure(state='normal' if ready else 'disabled')
    def manual_correction(self):
        if not self.models:raise ValueError('Selecione um atendimento na fila.')
        self.tabs.select(self.review_container)
        self.status.set('Edite os campos e exames abaixo. Confira os originais, salve as correções e compare novamente.')
        self.field_entries['pedido']['Paciente'].focus_set()
    def metadata_ready(self,entries=None):
        entries=entries or {'actor':self.actor_entry,'reason':self.reason_entry}
        for key,variable,label in [('actor',self.actor,'Revisor'),('reason',self.review_reason,'Motivo da conferência')]:
            if not variable.get().strip():
                message='Preencha '+label+'. O campo está destacado nesta tela.'
                self.review_hint.set(message);self.status.set(message)
                if entries[key] is self.reason_entry:self.tabs.select(self.review_container)
                entries[key].winfo_toplevel().lift()
                ttk.Style().configure('Missing.TEntry',fieldbackground='#fff0dc')
                entries[key].configure(style='Missing.TEntry');entries[key].focus_force()
                return False
            entries[key].configure(style='TEntry')
        self.review_hint.set('Revisor e motivo preenchidos. Salve a conferência após revisar os documentos.')
        return True
    def explain_prepare(self):
        self.tabs.select(self.review_container)
        if not self.metadata_ready():return
        if self.dirty():
            self.status.set('Há alterações não salvas. Clique em Salvar correções e comparar.');self.save_review_button.focus_force();return
        self.show_comparison()
        if self.comparison_errors:
            self.status.set('O pré-cadastro está bloqueado pelas pendências listadas. Use CONFERIR ATENDIMENTO para seguir os passos.')
            return self.assisted_review()
        self.status.set('Marque a confirmação final do paciente e dos documentos para liberar Preparar pré-cadastro.')
    def assisted_review(self):
        if not self.cid:raise ValueError('Importe um escaneamento ou selecione um atendimento.')
        from assisted_review import ReviewAssistant
        current=getattr(self,'review_assistant',None)
        if current and current.window.winfo_exists() and current.cid==self.cid:current.show();return
        if current and current.window.winfo_exists():current.window.destroy()
        self.review_assistant=ReviewAssistant(self)
    def _save_pages(self,batch,seen):
        from scan_import import save_batch
        selected_page=self.page_panel.selected_id
        cid=self.cid;cids=save_batch(self.store,batch,self.catalog,self.actor.get(),replace=True)
        cid=cid if cid in cids else cids[0]
        self.refresh();self.cases.selection_set(cid);self.open_case(cid)
        self.page_panel.seen_ids.update(seen.intersection({i['id'] for i in self.page_panel.items}))
        selected_index=next((i for i,p in enumerate(self.page_panel.items) if p['id']==selected_page),None)
        if selected_index is not None:self.page_panel.select(selected_index)
        self.restore_seen_pages()
    def restore_seen_pages(self):
        for view in self.views.values():
            for i,page in enumerate(view.doc['pages'],1):
                src=page.get('source',{})
                if src.get('sha256','')+':'+str(src.get('page')) in self.page_panel.seen_ids:view.seen.add(i)
    def correct_page_type(self):
        if not self.cid or not self.page_panel.selected_id:raise ValueError('Selecione uma página nas miniaturas.')
        if not self.metadata_ready():return
        if self.dirty() and not self.save():return
        from scan_import import load_batch
        obj=self.store.get(self.cid)[0];batch=load_batch(self.store,obj['docs']['pedido']['scan_batch'])
        item=next(i for i in batch['pages'] if i['id']==self.page_panel.selected_id)
        item.update(kind=self.page_kind.get(),classification_origin='manual',reviewed=True,reason=self.review_reason.get().strip())
        seen=set(self.page_panel.seen_ids);self._save_pages(batch,seen);self.tabs.select(self.page_tab)
        self.status.set('Tipo da página corrigido. A ficha e a comparação foram atualizadas; confirme as páginas e a identidade.')
    def confirm_case_pages(self):
        if not self.cid:raise ValueError('Selecione um atendimento.')
        if not self.metadata_ready():return
        if self.dirty() and not self.save():return
        from scan_import import load_batch,confirm_group
        obj=self.store.get(self.cid)[0];batch_id=obj['docs']['pedido'].get('scan_batch')
        if not batch_id:raise ValueError('Atendimento legado: confira os originais lado a lado.')
        batch=load_batch(self.store,batch_id);group=obj['docs']['pedido']['scan_group'];seen=set(self.page_panel.seen_ids)
        items=[i for i in batch['pages'] if i['group']==group]
        if any(i['id'] not in seen for i in items):raise ValueError('Abra todas as miniaturas antes de confirmar as páginas e a identidade.')
        if not messagebox.askyesno('Conferir páginas e identidade','Confirma o tipo de TODAS as páginas, a finalidade dos complementares e os identificadores da mesma pessoa?\nConflitos e páginas incertas continuam bloqueados.'):return
        for item in items:
            if item['kind']=='outro':item.update(reviewed=True,reason=self.review_reason.get().strip())
        confirm_group(batch,group,self.actor.get(),self.review_reason.get(),seen)
        self._save_pages(batch,seen);self.tabs.select(self.review_container)
        self.status.set('Páginas e identidade confirmadas. Clique em CONFERIR ATENDIMENTO para revisar os dados e os exames.')
    def review_fields(self):
        if not self.models:raise ValueError('Selecione um atendimento.')
        k=['pedido','guia'][self.forms.index(self.forms.select())]
        if not self.page_checks[k].get():raise ValueError('Abra todas as páginas e marque a conferência visual deste documento antes de conferir seus campos.')
        if not messagebox.askyesno('Conferência humana dos campos','Confirma que comparou TODOS os campos deste documento com o original, inclusive os não identificados?\nAusências essenciais continuarão bloqueando o pré-cadastro.'):
            return
        for var in self.field_checks[k].values():var.set(True)
        self.review_changed()
    def collect(self):
        if not self.models:raise ValueError('Selecione um paciente.')
        m=copy.deepcopy(self.models)
        if self.selected_profile:m['guia']['payer_profile']=copy.deepcopy(self.selected_profile)
        for k in m:
            for f in FIELDS:
                value=self.field_vars[k][f].get().strip()
                value='' if value.casefold()==UNIDENTIFIED.casefold() else value
                if value==NOT_APPLICABLE and m[k]['fields'][f].get('not_applicable'):value=''
                elif m[k]['fields'][f].get('not_applicable'):m[k]['fields'][f].pop('not_applicable')
                if value!=m[k]['fields'][f]['value']:
                    m[k]['fields'][f]['origin_type']='correcao_manual';m[k]['fields'][f]['confidence']=None
                    m[k]['fields'][f]['candidates']=[]
                m[k]['fields'][f]['value']=value
                m[k]['fields'][f]['reviewed']=self.field_checks[k][f].get()
            m[k]['pages_reviewed']=self.page_checks[k].get()
        return m
    def dirty(self):
        if not self.cid:return False
        obj=self.store.get(self.cid)[0]
        metadata=obj.get('review_metadata')
        return digest(self.collect())!=digest(obj['models']) or bool(metadata and metadata!={'revisor':self.actor.get().strip(),'motivo':self.review_reason.get().strip()})
    def refresh(self):
        self.cases.delete(*self.cases.get_children())
        for cid,cur,status in self.store.db.execute('SELECT id,current,status FROM casos_v2 ORDER BY rowid'):
            if status=='RECLASSIFICADO':continue
            models=json.loads(cur)['models'];name=models['pedido'].get('scan_patient_name') or models['pedido']['fields']['Paciente']['value'] or models['guia']['fields']['Paciente']['value'] or 'Identidade pendente'
            count=len(models['pedido']['exams']) or len(models['guia']['exams'])
            errors=compare_models(models['pedido'],models['guia'],self.catalog)['pendencias']+review_errors(models)
            self.cases.insert('','end',iid=cid,values=(name,self.case_stage(models,status),count,len(errors)))
        for token,state in self.pending_imports.items():
            if not self.cases.exists(token):self.cases.insert('','end',iid=token,values=('Atendimento em leitura',state))
    def select(self,event=None):
        s=self.cases.selection()
        if not s or s[0] in self.pending_imports or s[0]==self.cid:return
        if self.cid and self.dirty():
            if not messagebox.askyesno('Conferência não salva','Descartar as alterações não salvas e abrir o outro paciente?'):
                self.cases.selection_set(self.cid);return
        self.open_case(s[0])
    def open_case(self,cid,restore_diagnostics=True):
        self.cid=cid;obj,self.rev,status,out=self.store.get(cid);self.models=copy.deepcopy(obj['models']);self.selected_profile=self.models['guia'].get('payer_profile');self.loading=True
        if obj.get('review_metadata'):self.review_reason.set(obj['review_metadata']['motivo'])
        # Saved absolute paths can change after copying dados_v2 to a new folder.
        for doc in obj['docs'].values():
            for page in doc['pages']:
                src=page.get('source')
                if src:
                    local=self.data/'documentos'/(src['sha256']+Path(src['file']).suffix.lower())
                    if local.is_file():src['path']=str(local)
            local=self.data/'documentos'/(doc['sha256']+Path(doc['file']).suffix.lower())
            if local.is_file():doc['local_path']=str(local)
        self.set_text(self.origin_text,'Selecione Origem em um campo ou exame para localizar sua fonte.')
        try:
            for k in self.models:
                if restore_diagnostics:
                    d=obj['docs'][k]
                    self.update_diagnostic('Caso selecionado · '+k,document_diagnostics(d),d.get('document_type',UNIDENTIFIED))
                for f in FIELDS:
                    field=self.models[k]['fields'][f]
                    self.field_vars[k][f].set(field['value'] or (NOT_APPLICABLE if field.get('not_applicable') else UNIDENTIFIED))
                    self.field_checks[k][f].set(self.models[k]['fields'][f]['reviewed'])
                self.page_checks[k].set(self.models[k]['pages_reviewed']);self.views[k].load(obj['docs'][k]);self.render_rows(k)
        finally:self.loading=False
        batch_id=obj['docs']['pedido'].get('scan_batch')
        if batch_id:
            from scan_import import load_batch
            self.page_panel.load(load_batch(self.store,batch_id),obj['docs']['pedido']['scan_group'],self.data)
        else:
            self.page_panel.clear();self.page_panel.info.set('Atendimento legado: originais disponíveis na aba lado a lado.')
        self.confirm.set(False);self.show_comparison()
        self.set_text(self.output,json.dumps(out,ensure_ascii=False,indent=2) if out else 'Pré-cadastro ainda não preparado. Conclua a conferência.')
        self.status.set(f'Revisão {self.rev} · {status}')
    def render_rows(self,k):
        t=self.exam_tables[k];t.delete(*t.get_children())
        for i,e in enumerate(self.models[k]['exams']):t.insert('','end',iid=str(i),values=(e['descricao'],e['codigo'],e.get('quantidade_solicitada',''),e.get('quantidade_solicitada',e['quantidade']) if k=='pedido' else e['quantidade'],e['material'],f'Pág. {e["page"] or "manual"} · '+('INCERTO' if e['confidence'] is not None and e['confidence']<80 else 'Conferir original'), 'Sim' if e['reviewed'] else 'Não'))
        t=self.alert_tables[k];t.delete(*t.get_children())
        for i,a in enumerate(self.models[k]['issues']):t.insert('','end',iid=str(i),values=(a['message'],'Sim' if a['reviewed'] else 'Não'))
    def show_comparison(self):
        m=self.collect();self.analysis=compare_models(m['pedido'],m['guia'],self.catalog)
        t=self.compare_table;t.delete(*t.get_children())
        for r in self.analysis['exames']:t.insert('','end',values=(r['nome'],r['codigo_shift'] or UNIDENTIFIED,r.get('codigo_lido',r.get('tuss','')),r['pedido'],r['guia'],r['pagina_pedido'],r['pagina_guia'],r['situacao']))
        errors=self.analysis['pendencias']+review_errors(m)
        self.comparison_errors=errors
        self.blockers.configure(fg='#a43224' if errors else '#24633d')
        self.set_text(self.blockers,('Há '+str(len(errors))+' verificações pendentes. Selecione uma linha abaixo e clique em Resolver pendência.\n'+'\n'.join('• '+e for e in errors[:3])) if errors else 'Conferência salva sem pendências. Marque a confirmação final e prepare o pré-cadastro.')
        from review_workflow import review_plan,ACTION_LABELS
        self.pending_steps=review_plan(m,self.analysis)
        self.pending_table.delete(*self.pending_table.get_children())
        for i,step in enumerate(self.pending_steps):self.pending_table.insert('','end',iid=str(i),values=(step['message'],ACTION_LABELS[step['action']]))
        self.pending_button.configure(state='normal' if self.pending_steps else 'disabled')
        if self.pending_steps:self.pending_table.selection_set('0')
        elif self.dirty():self.set_text(self.blockers,'Conferência preenchida. Clique em Salvar correções e comparar antes de confirmar o paciente.')
        self.update_prepare_state()
    def navigate_pending(self):
        if not self.models:raise ValueError('Selecione um atendimento.')
        selected=self.pending_table.selection()
        if not selected:raise ValueError('Selecione uma pendência na lista.')
        step=self.pending_steps[int(selected[0])];action=step['action'];role=step['role']
        if action=='classify':return self.classification_window()
        if action=='profile':return self.payer_window()
        if action=='catalog':return self.catalog_window()
        self.tabs.select(self.review_container);self.forms.select(0 if role=='pedido' else 1)
        if action=='pages':
            view=self.views[role]
            if not view.doc['pages']:
                self.status.set('Documento ausente. Abra Identificar documentos e corrija o tipo das páginas.');return self.classification_window()
            page=next((i for i in range(1,len(view.doc['pages'])+1) if i not in view.seen),1)
            view.locate(page,None);self.tabs.select(self.doc_tab)
            self.status.set('Veja todas as páginas e depois marque a conferência visual do '+role+'.');return
        if action=='field':
            field=step['field'];entry=self.field_entries[role][field]
            self.field_tabs[role].select(entry.master);entry.focus_set()
            self.root.update_idletasks()
            y=entry.winfo_rooty()-self.review_tab.winfo_rooty()
            self.review_canvas.yview_moveto(max(0,y-100)/max(1,self.review_tab.winfo_height()))
            self.status.set('Confira '+field+' com o original; edite se necessário e marque Conferido.')
        elif action=='exam':
            index=step['index']
            if index is not None:self.exam_tables[role].selection_set(str(index))
            self.edit_exam(role,new=index is None)
        elif action=='issue':
            self.alert_tables[role].selection_set(str(step['index']));self.resolve_issue(role)
    def apply_not_applicable(self):
        if not self.models:raise ValueError('Selecione um atendimento.')
        from payer_mapping import mark_not_applicable
        model=copy.deepcopy(self.collect()['guia'])
        mark_not_applicable(model,self.selected_profile)
        if not messagebox.askyesno('Conferir regra homologada','Confirma que os campos não se aplicam ao atendimento e que não há informação correspondente no original?'):return
        self.models['guia']=model
        self.loading=True
        try:
            for key,field in model['fields'].items():
                if field.get('not_applicable'):self.field_vars['guia'][key].set(NOT_APPLICABLE);self.field_checks['guia'][key].set(False)
        finally:self.loading=False
        self.confirm.set(False);self.show_comparison()
    def locate_field(self,k,f):
        if not self.models:return
        src=self.models[k]['fields'][f]
        if not src['value'] and src.get('candidates'):return self.candidate_window(k,f)
        self.locate_source(k,f,src)
    def candidate_window(self,k,f):
        source=self.models[k]['fields'][f]
        candidates=[{**{key:copy.deepcopy(source.get(key)) for key in ['page','box','snippet','document','confidence']},**copy.deepcopy(c)} for c in source.get('candidates',[]) if c.get('value')]
        if not candidates:return self.locate_source(k,f,source)
        window=tk.Toplevel(self.root);window.title('Conferir leituras · '+f);window.geometry('900x340')
        ttk.Label(window,text='Leituras locais diferentes não são aprovação. Compare cada origem e escolha somente o valor conferido no documento.',wraplength=850,padding=8).pack(fill='x')
        table=ttk.Treeview(window,columns=('valor','pagina','confianca','metodo'),show='headings',height=7)
        for key,title,width in [('valor','Valor lido',370),('pagina','Página original',110),('confianca','Confiança OCR',110),('metodo','Leitura',230)]:table.heading(key,text=title);table.column(key,width=width)
        table.pack(fill='both',expand=True,padx=8)
        for i,c in enumerate(candidates):table.insert('','end',iid=str(i),values=(c['value'],c.get('source_document',{}).get('page',c.get('page')),c.get('confidence',''),c.get('origin_type','Leitura local')))
        table.selection_set('0')
        def selected():
            if not table.selection():raise ValueError('Selecione uma leitura para conferir.')
            return candidates[int(table.selection()[0])]
        def show():self.locate_source(k,f,selected())
        def choose():
            c=copy.deepcopy(selected())
            if f in ['Conselho','UF conselho'] and c.get('origin_type')=='codigo_impresso_nao_mapeado':
                raise ValueError('Código numérico sem correspondência homologada. Informe o conselho/UF confirmado na conferência.')
            c.update(reviewed=False,origin_type='escolha_humana_de_leitura',confidence=None,candidates=[])
            self.models[k]['fields'][f]=c;self.field_vars[k][f].set(c['value']);self.field_checks[k][f].set(False)
            self.confirm.set(False);self.show_comparison();window.destroy()
        buttons=ttk.Frame(window,padding=7);buttons.pack(fill='x')
        ttk.Button(buttons,text='Ver página da leitura',command=lambda:self.guard(show)).pack(side='left',padx=4)
        ttk.Button(buttons,text='Usar valor para conferir',command=lambda:self.guard(choose)).pack(side='left',padx=4)
        self.candidate_editor={'window':window,'table':table,'show':show,'choose':choose}
    def locate_source(self,k,f,src):
        conf=src.get('confidence');self.status.set(f'{f}: página {src.get("page") or "não localizada"}; confiança OCR {conf if conf is not None else "não disponível"}. '+src.get('diagnostic','Conferir o valor no original.'))
        target=k
        if src.get('document') and self.views[k].doc.get('file')!=src['document']:
            target=next((name for name,view in self.views.items() if view.doc and view.doc.get('file')==src['document']),k)
        self.views[target].locate(src['page'],src['box']);self.tabs.select(self.doc_tab)
        physical=src.get('source_document',{})
        self.set_text(self.origin_text,
            f'Origem de {f}: {target} · {physical.get("file",src.get("document") or "Original")} · Página original: {physical.get("page",src["page"]) or "não localizada"}\n'
            +src.get('diagnostic','Conferir original.')+'\nTrecho: '+(src.get('snippet') or 'Não identificado'))
    def locate_exam(self,k):
        s=self.exam_tables[k].selection()
        if s:
            e=self.models[k]['exams'][int(s[0])];self.views[k].locate(e['page'],e['box']);self.tabs.select(self.doc_tab)
            physical=e.get('source_document',{})
            self.set_text(self.origin_text,f'Origem do exame: {k} · {physical.get("file",e.get("document") or "Original")} · Página original: {physical.get("page",e["page"])}\nTrecho: {e.get("snippet",e.get("raw",""))}')
    def edit_exam(self,k,new=False):
        if not self.models:raise ValueError('Selecione um paciente.')
        s=self.exam_tables[k].selection()
        if not new and not s:raise ValueError('Selecione um exame.')
        idx=len(self.models[k]['exams']) if new else int(s[0])
        old={'descricao':'','codigo':'','quantidade':'','material':'','page':None,'box':None,'confidence':None,'reviewed':False,'raw':'','notes':['Inclusão manual']} if new else self.models[k]['exams'][idx]
        w=tk.Toplevel(self.root);w.title('Conferir exame · '+k);w.transient(self.root);w.grab_set();variables={}
        for i,(key,label) in enumerate([('descricao','Descrição'),('codigo','Código lido (interno ou TUSS)'),('quantidade_solicitada','Quantidade solicitada (TISS)'),('quantidade','Quantidade autorizada / quantidade do pedido'),('material','Material lido'),('page','Página de origem')]):
            initial=old.get('quantidade_solicitada',old.get('quantidade')) if k=='pedido' and key=='quantidade' else old.get(key)
            ttk.Label(w,text=label).grid(row=i,column=0,padx=10,pady=6,sticky='w');v=tk.StringVar(value=str(initial or ''));variables[key]=v;ttk.Entry(w,textvariable=v,width=48,state='disabled' if k=='pedido' and key=='quantidade_solicitada' else 'normal').grid(row=i,column=1,padx=10)
        ttk.Label(w,text='\n'.join(old.get('notes',[])) or 'Compare a linha com o original.',wraplength=500).grid(row=6,column=0,columnspan=2,padx=10,pady=8)
        checked=tk.BooleanVar(value=old['reviewed'])
        for v in variables.values():v.trace_add('write',lambda *_:checked.set(False))
        ttk.Checkbutton(w,text='Conferi este exame no documento original',variable=checked).grid(row=7,column=0,columnspan=2)
        def commit():
            try:
                e={**old,**{key:v.get().strip() for key,v in variables.items()},'reviewed':checked.get()}
                if not e['descricao']:raise ValueError('Informe a descrição.')
                if e['quantidade'] and (not e['quantidade'].isdigit() or not 0<=int(e['quantidade'])<=999):raise ValueError('Quantidade deve ficar vazia ou ser de 0 a 999; vazio e zero não autorizam.')
                if k=='pedido':e['quantidade_solicitada']=e['quantidade']
                elif e.get('quantidade_solicitada') and (not e['quantidade_solicitada'].isdigit() or not 0<=int(e['quantidade_solicitada'])<=999):raise ValueError('Quantidade solicitada deve ser de 0 a 999 ou ficar vazia para conferência.')
                if not e['page'].isdigit() or not 1<=int(e['page'])<=len(self.views[k].doc['pages']):raise ValueError('Indique uma página válida do documento.')
                e['page']=int(e['page'])
                physical=self.views[k].doc['pages'][e['page']-1].get('source')
                if physical:e['source_document']=copy.deepcopy(physical)
                if self.models[k].get('tiss'):e['quantidade_autorizada']=e['quantidade']
                if e['page']!=old['page']:e['box']=None
                if any(e.get(key)!=old.get(key) for key in variables):e['origin_type']='correcao_manual';e['confidence']=None
                if new:self.models[k]['exams'].append(e)
                else:self.models[k]['exams'][idx]=e
                self.confirm.set(False);self.render_rows(k);self.show_comparison();w.destroy()
            except Exception as exc:messagebox.showerror('Conferir exame',str(exc),parent=w)
        button=ttk.Button(w,text='Aplicar à conferência',command=commit);button.grid(row=8,column=0,columnspan=2,pady=12)
        self.exam_editor={'window':w,'variables':variables,'checked':checked,'button':button}
    def delete_exam(self,k):
        s=self.exam_tables[k].selection()
        if s:
            reason=simpledialog.askstring('Excluir linha','Motivo da exclusão (por exemplo: rodapé reconhecido como exame):')
            if not reason:return
            e=self.models[k]['exams'].pop(int(s[0]));self.models[k].setdefault('removed_exams',[]).append({'exam':copy.deepcopy(e),'reason':reason})
            self.models[k]['issues'].append({'message':'Linha excluída: '+e['raw'],'reviewed':True,'reason':reason});self.render_rows(k);self.confirm.set(False);self.show_comparison()
    def resolve_issue(self,k):
        s=self.alert_tables[k].selection()
        if not s:return
        issue=self.models[k]['issues'][int(s[0])]
        reason=simpledialog.askstring('Conferência do alerta',issue['message']+'\n\nDescreva o que conferiu/corrigiu no original:',initialvalue=issue['reason'])
        if reason and reason.strip():issue.update(reviewed=True,reason=reason.strip());self.confirm.set(False);self.render_rows(k);self.show_comparison()
    def check_pages(self,k):
        if not self.models:self.page_checks[k].set(False);return
        for n,page in enumerate(self.views[k].doc['pages'],1):
            src=page.get('source',{})
            if src.get('sha256','')+':'+str(src.get('page')) in self.page_panel.seen_ids:self.views[k].seen.add(n)
        if self.page_checks[k].get() and len(self.views[k].seen)!=len(self.views[k].doc['pages']):
            self.page_checks[k].set(False);messagebox.showinfo('Páginas pendentes','Abra todas as páginas deste documento na aba Originais antes de confirmar.')
        self.review_changed()
    def save(self):
        if not self.metadata_ready():return False
        m=self.collect()
        reason=self.review_reason.get().strip()
        self.store.save(self.cid,m,self.actor.get(),reason,self.rev);self.rev+=1;self.models=m;self.confirm.set(False);[self.render_rows(k) for k in self.models];self.show_comparison();self.refresh();self.status.set(f'Conferência salva · revisão {self.rev}')
        return True
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
    def import_scans(self,paths=None,reprocess=None,mode=None):
        from scan_import import read_scan
        if self.cid and self.dirty():raise ValueError('Salve as correções antes de importar ou reprocessar.')
        if paths is None:
            paths=filedialog.askopenfilenames(title='IMPORTAR ESCANEAMENTO · pedido e guia juntos ou em qualquer ordem',filetypes=[('Escaneamentos','*.pdf *.png *.jpg *.jpeg')])
        if not paths:return
        if self.busy:raise ValueError('Aguarde a leitura terminar.')
        self.busy=True;self.pending_imports={'escaneamento-em-leitura':'Aguardando leitura'};self.refresh()
        self.progress=tk.Toplevel(self.root);self.progress.title('Leitura local do escaneamento');self.progress.transient(self.root);self.progress.grab_set()
        self.progress.protocol('WM_DELETE_WINDOW',lambda:None)
        self.scan_progress=tk.StringVar(value='Classificando cada página localmente…')
        ttk.Label(self.progress,textvariable=self.scan_progress,padding=20,wraplength=470).pack()
        self.progress_indicator=ttk.Progressbar(self.progress,mode='indeterminate',length=350);self.progress_indicator.pack(padx=20,pady=15);self.progress_indicator.start()
        cat=copy.deepcopy(self.catalog)
        mode=(reprocess.get('mode','multiple') if reprocess else mode or next(k for k,v in IMPORT_MODES.items() if v==self.import_mode.get()))
        def worker():
            try:
                batch=read_scan(paths,self.data,cat,settings_path=self.ocr_settings_path,mode=mode,
                    progress=lambda i,total,text:self.events.put(('scan_progress',text)))
                if reprocess:
                    from scan_import import merge_reprocessed
                    merge_reprocessed(batch,reprocess)

                self.events.put(('scan_batch',batch,bool(reprocess)))
            except Exception as exc:self.events.put(('error',safe_failure(exc)))
            finally:self.events.put(('done',))
        threading.Thread(target=worker,daemon=True).start()
    def classification_window(self):
        from scan_import import load_batch,save_batch,KINDS,confirm_group,assess_group,apply_identity_edits
        from identity_evidence import IDENTIFIERS
        if not self.cid:raise ValueError('Importe um escaneamento ou selecione um atendimento.')
        if self.dirty():raise ValueError('Salve as correções antes de alterar a classificação das páginas.')
        obj=self.store.get(self.cid)[0];batch_id=obj['docs']['pedido'].get('scan_batch')
        if not batch_id:raise ValueError('Atendimento legado: use os originais lado a lado ou importe pelo modo de escaneamento.')
        batch=load_batch(self.store,batch_id);seen=set(self.page_panel.seen_ids)
        w=tk.Toplevel(self.root);w.title('Identificar documentos e confirmar agrupamento');w.geometry('1250x930')
        ttk.Label(w,text='Cada página pertence a uma ficha provisória. Revise desconhecidos, mova páginas ou corrija a identificação lida.\nConflitos não são liberados por confirmação. Para corrigir OCR, compare com o original e registre o motivo.',padding=8).pack(fill='x')
        table=ttk.Treeview(w,columns=('arquivo','pagina','tipo','atendimento','paciente'),show='headings',height=5)
        for key,title,width in [('arquivo','Original',210),('pagina','Página',55),('tipo','Tipo',160),('atendimento','Atendimento',150),('paciente','Identificação lida',250)]:table.heading(key,text=title);table.column(key,width=width)
        table.pack(fill='x',padx=8)
        editor=ttk.Frame(w,padding=6);editor.pack(fill='x')
        kind=tk.StringVar();group=tk.StringVar();reason=tk.StringVar();reviewed=tk.BooleanVar();state=tk.StringVar()
        ttk.Label(editor,text='Tipo:').grid(row=0,column=0);ttk.Combobox(editor,textvariable=kind,values=KINDS,state='readonly',width=24).grid(row=0,column=1)
        ttk.Label(editor,text='Mover para atendimento:').grid(row=0,column=2)
        group_picker=ttk.Combobox(editor,textvariable=group,width=26);group_picker.grid(row=0,column=3)
        ttk.Label(editor,text='Motivo / identificadores conferidos:').grid(row=1,column=0,columnspan=2)
        ttk.Entry(editor,textvariable=reason,width=66).grid(row=1,column=2,columnspan=3,sticky='ew')
        ttk.Checkbutton(editor,text='Conferi o tipo e os dados desta página no original',variable=reviewed).grid(row=2,column=0,columnspan=4,sticky='w')
        identity_vars={}
        identity_frame=ttk.LabelFrame(editor,text='Corrigir identificação desta página (sem alterar o PDF)',padding=4);identity_frame.grid(row=3,column=0,columnspan=5,sticky='ew')
        for index,key in enumerate(['Paciente',*IDENTIFIERS]):
            ttk.Label(identity_frame,text=key).grid(row=index//3*2,column=index%3,sticky='w')
            var=tk.StringVar();identity_vars[key]=var;ttk.Entry(identity_frame,textvariable=var,width=35).grid(row=index//3*2+1,column=index%3,padx=5,sticky='ew')
        ttk.Label(editor,textvariable=state,wraplength=1150,foreground='#9a3525').grid(row=4,column=0,columnspan=5,sticky='w',pady=3)
        view=DocumentView(w,'Página selecionada · original preservado');view.pack(fill='both',expand=True,padx=8)
        def refresh():
            table.delete(*table.get_children());group_picker.configure(values=list(dict.fromkeys(i['group'] for i in batch['pages'])))
            for i,item in enumerate(batch['pages']):
                source=batch['sources'][item['source']]
                table.insert('','end',iid=str(i),values=(source['file'],item['page'],item['kind'],item['group'],item['model']['fields']['Paciente']['value'] or UNIDENTIFIED))
        def current():
            selection=table.selection()
            if not selection:raise ValueError('Selecione uma página.')
            return int(selection[0]),batch['pages'][int(selection[0])]
        def select(event=None):
            if not table.selection():return
            index,item=current();kind.set(item['kind']);group.set(item['group']);reason.set(item['reason']);reviewed.set(item['reviewed'])
            for key,var in identity_vars.items():var.set(item['model']['fields'].get(key,{}).get('value',''))
            members=[p for p in batch['pages'] if p['group']==item['group']];assessment=assess_group(members)
            state.set(' · '.join(assessment['errors']) or f'{len(members)} páginas neste atendimento. A confirmação do agrupamento exige visualizar todas e conferir os identificadores.')
            source=batch['sources'][item['source']];page=copy.deepcopy(next(p for p in source['pages'] if p['number']==item['page']))
            local=self.data/'documentos'/(source['sha256']+Path(source['file']).suffix.lower())
            page['source']={'path':str(local),'page':item['page']};view.load({**source,'pages':[page]});seen.add(item['id'])
        def apply():
            index,item=current()
            if not reason.get().strip() or not reviewed.get() or not group.get().strip():raise ValueError('Informe atendimento, motivo e confirmação da página.')
            edits={k:v.get().strip() for k,v in identity_vars.items()}
            if any(edits[k]!=item['model']['fields'].get(k,{}).get('value','') for k in edits):
                apply_identity_edits(item,edits,self.actor.get(),reason.get().strip())
            item.update(kind=kind.get(),classification_origin='manual',group=group.get().strip(),reason=reason.get().strip(),reviewed=True)
            refresh();table.selection_set(str(index))
        def approve():
            index,item=current()
            confirm_group(batch,item['group'],self.actor.get(),reason.get(),seen)
            state.set('Agrupamento conferido nesta revisão. Salve a classificação para atualizar a ficha e conferir os campos/exames.')
        def regroup():
            index,item=current()
            if not reason.get().strip():raise ValueError('Informe por que deseja reunir as páginas deste PDF.')
            source=item['source'];name='Provisório PDF '+str(list(batch['sources']).index(source)+1)
            for page in batch['pages']:
                if page['source']==source:page['group']=name
            batch['mode']='single';batch['group_reviews']={};refresh();table.selection_set(str(index));select()
        def save():
            if not self.actor.get().strip():raise ValueError('Informe seu nome no campo Revisor da janela principal.')
            if not messagebox.askyesno('Salvar classificação','Atualizar as fichas com esta classificação e identificação?\nAs revisões anteriores serão preservadas e os campos precisarão de conferência.',parent=w):return
            cids=save_batch(self.store,batch,self.catalog,self.actor.get(),replace=True)
            self.refresh();self.cases.selection_set(cids[0]);self.open_case(cids[0]);self.tabs.select(self.review_container);w.destroy()
        buttons=ttk.Frame(editor);buttons.grid(row=5,column=0,columnspan=5,sticky='w',pady=4)
        for title,fn in [('Aplicar à página',apply),('Reunir páginas deste PDF',regroup),('Confirmar agrupamento',approve),('Salvar classificação e extrair dados',save)]:ttk.Button(buttons,text=title,command=lambda f=fn:self.guard(f)).pack(side='left',padx=3)
        table.bind('<<TreeviewSelect>>',select);refresh()
        selected=next((i for i,p in enumerate(batch['pages']) if p['id']==self.page_panel.selected_id),0)
        if batch['pages']:table.selection_set(str(selected));select()
        self.classification_editor={'window':w,'table':table,'kind':kind,'group':group,'reason':reason,'reviewed':reviewed,'identity':identity_vars,'apply':apply,'save':save,'confirm':approve,'regroup':regroup,'batch':batch,'seen':seen,'state':state}
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
        if not self.catalog:
            self.catalog=catalog_load(ROOT/'catalogo_demo.json');self.status.set('Modo de exemplos: catálogo fictício carregado somente nesta sessão.')
        self.import_pairs([(ROOT/'exemplos'/f'{i}_pedido.txt',ROOT/'exemplos'/f'{i}_guia.txt') for i in ['01','02','03']])
    def reanalyze_case(self):
        if not self.cid:raise ValueError('Selecione um atendimento na fila.')
        if self.dirty():raise ValueError('Salve a conferência atual antes de reanalisar.')
        if not self.actor.get().strip():raise ValueError('Informe o revisor antes de reanalisar.')
        obj,revision,status,_=self.store.get(self.cid)
        if status=='PREPARADO':raise ValueError('Pré-cadastro já preparado; reanálise bloqueada para preservar a conferência.')
        batch_id=obj['docs']['pedido'].get('scan_batch') or obj['docs']['guia'].get('scan_batch')
        if batch_id:
            from scan_import import load_batch
            batch=load_batch(self.store,batch_id)
            paths=[self.data/'documentos'/(sha+Path(src['file']).suffix.lower()) for sha,src in batch['sources'].items()]
            if any(not p.is_file() for p in paths):raise ValueError('Restaure os originais na pasta dados_v2/documentos.')
            if messagebox.askyesno('Reprocessar leitura','Ler novamente todas as páginas deste escaneamento? Os campos precisarão de nova conferência. O histórico será preservado.'):
                self.import_scans(paths,reprocess=batch)
            return
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
        for number in range(1,len(pairs)+1):self.pending_imports[f'pendente-{sequence}-{number}']='Aguardando leitura'
        self.refresh()
        self.busy=True;self.status.set('Lendo localmente. OCR pode levar alguns minutos…');cat=copy.deepcopy(self.catalog)
        self.progress=tk.Toplevel(self.root);self.progress.title('Leitura local em andamento');self.progress.transient(self.root);self.progress.grab_set();self.progress.protocol('WM_DELETE_WINDOW',lambda:None)
        ttk.Label(self.progress,text='Lendo os documentos neste computador…\nAguarde a conclusão do lote.',padding=25).pack()
        indicator=ttk.Progressbar(self.progress,mode='indeterminate',length=330);self.progress_indicator=indicator;indicator.pack(padx=25,pady=15);indicator.start()
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
                        self.events.put(('interpretation',f'Lote {sequence} · Par {number} · {k}',models[k]['interpretation']))
                        if d['document_type']!=k:
                            models[k]['issues'].append({'message':'Tipo do documento não confirmado como '+k+'. Confira o original.',
                                                       'reviewed':False,'reason':''})
                    self.events.put(('progress',f'pendente-{sequence}-{number}','Leitura concluída'))
                    self.events.put(('reanalyzed',reanalysis,docs,models) if reanalysis else ('case',docs,models,f'pendente-{sequence}-{number}'))
            except Exception as exc:self.events.put(('error',safe_failure(exc)))
            finally:self.events.put(('done',))
        threading.Thread(target=run,daemon=True).start()
    def update_diagnostic(self,label,rows,result):
        table=self.diagnostic_table
        for item in table.get_children():
            if table.item(item,'values')[0]==label:table.delete(item)
        if not rows:
            table.insert('','end',values=(label,'—','Em andamento' if result=='Lendo…' else 'Falhou',
                                        '—',0,result,'Aguardando','Aguardando'));return
        for row in rows:
            method=row['method']+(' · '+row['languages'] if row['languages'] else '')
            table.insert('','end',values=(label,row['page'],'Sim' if row['executed'] else 'Não',
                method,row['characters'],
                'FALHA: '+row['detail'] if row['failed'] else 'Lido · tipo: '+result,'Aguardando','Aguardando'))
    def record_interpretation(self,label,result):
        self.stage_diagnostics[label]={'ocr':True,'interpretation':copy.deepcopy(result),'ui':None}
        for item in self.diagnostic_table.get_children():
            values=list(self.diagnostic_table.item(item,'values'))
            if values[0]==label:
                values[6]=f"{result['fields_found']} campos / {result['exams_found']} exames" if result['fields_found'] or result['exams_found'] else 'FALHA: nenhum campo/exame'
                self.diagnostic_table.item(item,values=values)
    def record_ui_stage(self,success):
        # Only counts/status in technical records; field contents remain in the case.
        if success:
            success=all(self.field_vars[k][f].get()==(v['value'] or (NOT_APPLICABLE if v.get('not_applicable') else UNIDENTIFIED))
                        for k,m in self.models.items() for f,v in m['fields'].items())
        for label,result in self.stage_diagnostics.items():
            if result['ui'] is None:
                result['ui']=success
                for item in self.diagnostic_table.get_children():
                    values=list(self.diagnostic_table.item(item,'values'))
                    if values[0]==label:values[7]='Preenchida' if success else 'FALHA na atualização';self.diagnostic_table.item(item,values=values)
    def poll(self):
        try:
            while True:
                item=self.events.get_nowait()
                if item[0]=='scan_progress':
                    self.scan_progress.set(item[1]);self.status.set(item[1]);self.pending_imports['escaneamento-em-leitura']='Lendo e identificando páginas';self.refresh()
                elif item[0]=='scan_batch':
                    from scan_import import save_batch
                    batch,replace=item[1:];cids=save_batch(self.store,batch,self.catalog,self.actor.get(),replace=replace)
                    self.pending_imports.clear();self.refresh()
                    if cids:
                        self.cases.selection_set(cids[0]);self.open_case(cids[0]);self.tabs.select(self.review_container)
                        for k,model in self.models.items():self.record_interpretation('Caso selecionado · '+k,model['interpretation'])
                        self.record_ui_stage(True)
                elif item[0]=='case':
                    try:
                        cid=self.store.add(item[1],item[2],self.actor.get());
                        if len(item)>3:self.pending_imports.pop(item[3],None)
                        self.refresh();self.cases.selection_set(cid);self.open_case(cid,restore_diagnostics=False);self.tabs.select(self.review_container)
                        self.record_ui_stage(True)
                    except Exception as exc:
                        self.record_ui_stage(False);messagebox.showwarning('Importação',safe_failure(exc))
                elif item[0]=='reanalyzed':
                    info,docs,models=item[1:]
                    self.store.save(info['cid'],models,self.actor.get(),'Reanálise local após configuração OCR',
                                    info['revision'],documents=docs)
                    self.refresh();self.cases.selection_set(info['cid']);self.open_case(info['cid'],restore_diagnostics=False)
                    self.tabs.select(self.review_container)
                elif item[0]=='diagnostic':self.update_diagnostic(*item[1:])
                elif item[0]=='interpretation':self.record_interpretation(*item[1:])
                elif item[0]=='progress':self.pending_imports[item[1]]=item[2];self.refresh()
                elif item[0]=='ocr_health':self.finish_ocr_check(*item[1:])
                elif item[0]=='error':messagebox.showwarning('Documento não importado',item[1])
                else:
                    self.busy=False;self.pending_imports.clear();self.progress_indicator.stop();self.progress.grab_release();self.progress.destroy()
                    self.status.set('Leitura encerrada. Clique em CONFERIR ATENDIMENTO. Revisor e motivo ficam visíveis antes de salvar.');self.refresh()
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
        if getattr(self,'simulator',None):self.simulator.close()
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
