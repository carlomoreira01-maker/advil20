"""Interface principal em etapas sobre os controladores existentes; tudo local."""
import copy,json,tkinter as tk
from pathlib import Path
from tkinter import ttk,filedialog,messagebox,font as tkfont
from engine_v2 import FIELDS,compare_models,review_errors,digest
from priority_fields import PRIORITY,state_label,source_role
from draft_workflow import build_draft,save_draft,load_draft

PHASES=['Início','Documentos','Dados identificados','Exames','Pré-cadastro']
KIND_LABELS={'pedido':'Pedido médico','guia':'Guia de autorização / SP-SADT','continuação de pedido':'Continuação de pedido','continuação de guia':'Continuação de guia','outro':'Documento complementar','incerto':'Tipo não identificado'}
COLORS={'bg':'#f5f7fb','ink':'#1e293b','muted':'#64748b','blue':'#2457d6','line':'#dde4ee'}


def create_workbench(root,data=None,base_class=None):
    if base_class is None:
        from app import App
        base_class=App
    class Workbench(base_class):
        def __init__(self):
            self.workspace=None
            if data is None:super().__init__(root)
            else:super().__init__(root,data)
            self.old_actor_entry=self.actor_entry;self.old_reason_entry=self.reason_entry
            self.workspace=Workspace(self)
            self.actor_entry=self.workspace.actor_entry;self.reason_entry=self.workspace.reason_entry
        def refresh(self):
            super().refresh()
            if self.workspace:self.workspace.refresh_home()
        def open_case(self,cid,restore_diagnostics=True):
            super().open_case(cid,restore_diagnostics)
            if self.workspace:
                draft=load_draft(self.store,cid)
                if draft:
                    self.loading=True
                    try:
                        self.models=copy.deepcopy(draft['models'])
                        for role,model in self.models.items():
                            for key in FIELDS:
                                self.field_vars[role][key].set(model['fields'][key]['value'] or 'Não identificado')
                                self.field_checks[role][key].set(model['fields'][key]['reviewed'])
                            self.page_checks[role].set(model['pages_reviewed']);self.render_rows(role)
                        if draft.get('metadata'):self.review_reason.set(draft['metadata'].get('motivo',self.review_reason.get()))
                    finally:self.loading=False
                    self.show_comparison()
                self.workspace.bind_case()
        def show_comparison(self):
            super().show_comparison()
            if self.workspace:self.workspace.refresh_detail()
        def changed_field(self,kind,key):
            super().changed_field(kind,key)
            if self.workspace and not self.loading:self.workspace.invalidate_review()
        def metadata_ready(self,entries=None):
            if self.workspace and entries is None:
                if self.workspace.advanced:
                    entries={'actor':self.old_actor_entry,'reason':self.old_reason_entry}
                    if not self.review_reason.get().strip():self.tabs.select(self.review_container)
                elif not self.review_reason.get().strip():self.workspace.go(4)
            valid=super().metadata_ready(entries)
            if not valid and self.workspace:self.workspace.notice.set(self.review_hint.get())
            return valid
        def locate_source(self,role,key,src):
            if not self.workspace or self.workspace.advanced:return super().locate_source(role,key,src)
            self.workspace.source_dialog(role,key,src)
        def guard(self,fn):
            if not self.workspace or self.workspace.advanced:return super().guard(fn)
            try:
                if self.busy:raise ValueError('A análise está em andamento. Aguarde a leitura terminar.')
                return fn()
            except Exception as exc:
                self.workspace.notice.set(str(exc));self.status.set(str(exc))
        def close(self):
            if self.busy:
                messagebox.showinfo('Análise em andamento','Aguarde a leitura terminar antes de fechar.');return
            if self.workspace and self.cid and self.dirty() and self.store.get(self.cid)[2]!='PREPARADO':
                self.workspace.save_current_draft(quiet=True)
            if getattr(self,'simulator',None):self.simulator.close()
            self.store.db.close();self.root.destroy()
        def preserve_navigation(self):
            if not self.workspace or not self.cid:return False
            if self.store.get(self.cid)[2]=='PREPARADO':return digest(self.collect())==digest(self.store.get(self.cid)[0]['models'])
            self.workspace.save_current_draft(quiet=True)
            draft=load_draft(self.store,self.cid)
            return bool(draft and digest(draft['models'])==digest(self.collect()))
    return Workbench()


class Workspace:
    def __init__(self,app):
        self.app=app;self.root=app.root;self.phase=0;self.advanced=False;self.bound_cid=None;self.bound_revision=None;self.binding=False
        self.legacy_pack=[(w,w.pack_info()) for w in self.root.winfo_children() if w.winfo_manager()=='pack']
        for w,_ in self.legacy_pack:w.pack_forget()
        self.root.title('Cadastro Assistido Shift 2.5.2 | Processamento local')
        self.root.geometry(f'{min(1280,self.root.winfo_screenwidth()-50)}x{min(840,self.root.winfo_screenheight()-80)}');self.root.minsize(1000,640)
        families={f.casefold():f for f in tkfont.families(self.root)}
        self.font=next((families[f.casefold()] for f in ['Segoe UI','DejaVu Sans','Liberation Sans','Noto Sans','Nimbus Sans L'] if f.casefold() in families),tkfont.nametofont('TkDefaultFont').actual('family'))
        style=ttk.Style();style.configure('Clean.TFrame',background=COLORS['bg']);style.configure('Card.TFrame',background='white')
        style.configure('Clean.TLabel',background=COLORS['bg'],foreground=COLORS['ink'],font=(self.font,11))
        style.configure('Title.TLabel',background=COLORS['bg'],foreground=COLORS['ink'],font=(self.font,20,'bold'))
        style.configure('Muted.TLabel',background=COLORS['bg'],foreground=COLORS['muted'],font=(self.font,10))
        style.configure('Card.TLabel',background='white',foreground=COLORS['ink'],font=(self.font,11))
        style.configure('TButton',background='white',foreground=COLORS['ink'],bordercolor=COLORS['line'],lightcolor='white',darkcolor='white',relief='flat',font=(self.font,10),padding=(12,8))
        style.map('TButton',background=[('active','#edf2ff')],bordercolor=[('active',COLORS['blue'])])
        style.configure('Primary.TButton',background=COLORS['blue'],foreground='white',font=(self.font,11,'bold'),padding=(16,10),bordercolor=COLORS['blue'])
        style.map('Primary.TButton',background=[('active','#1945af')]);style.configure('Nav.TButton',padding=(12,9),font=(self.font,10))
        style.configure('Clean.Treeview',rowheight=32,font=(self.font,10),background='white',fieldbackground='white',borderwidth=0)
        style.configure('Clean.Treeview.Heading',font=(self.font,10,'bold'),padding=8)
        style.configure('Clean.TNotebook',background=COLORS['bg'],borderwidth=0);style.configure('Clean.TNotebook.Tab',font=(self.font,11),padding=(16,10))
        style.map('Clean.TNotebook.Tab',background=[('selected','white')],foreground=[('selected',COLORS['blue'])])
        style.configure('Attention.TEntry',fieldbackground='#fff4db')
        self.frame=ttk.Frame(self.root,style='Clean.TFrame',padding=18);self.frame.pack(fill='both',expand=True)
        header=ttk.Frame(self.frame,style='Clean.TFrame');header.pack(fill='x')
        ttk.Label(header,text='Cadastro Assistido Shift',style='Title.TLabel').pack(side='left')
        ttk.Label(header,text='2.5.2  |  Local e assistido',style='Muted.TLabel').pack(side='left',padx=14)
        more=ttk.Menubutton(header,text='Mais opções');more.pack(side='right');menu=tk.Menu(more,tearoff=False);more.configure(menu=menu)
        for title,fn in [('Configurar leitor OCR',app.ocr_settings_window),('Catálogo do laboratório',app.catalog_window),('Perfis de fontes pagadoras',app.payer_window),('Diagnóstico e conferência detalhada',self.show_advanced),('Histórico local',app.audit_window),('Tempos de leitura',lambda:__import__('reading_diagnostics').show_times(app)),('Exemplos fictícios',self.examples),('Simulador local',app.simulation_window),('Treinamento RPA — LIS fictício',lambda:__import__('rpa_training_ui').open_training(app)),('Inspecionar Shift — somente leitura',lambda:__import__('shift_inspection_ui').open_inspection(app))]:menu.add_command(label=title,command=lambda f=fn:app.guard(f))
        reviewer=ttk.Frame(self.frame,style='Clean.TFrame');reviewer.pack(fill='x',pady=(10,12))
        ttk.Label(reviewer,text='Seu nome / revisor',style='Clean.TLabel').pack(side='left');self.actor_entry=ttk.Entry(reviewer,textvariable=app.actor,width=28);self.actor_entry.pack(side='left',padx=8)
        self.case_title=tk.StringVar(value='Importe documentos para começar.');ttk.Label(reviewer,textvariable=self.case_title,style='Muted.TLabel').pack(side='right')
        nav=ttk.Frame(self.frame,style='Clean.TFrame');nav.pack(fill='x');self.nav_buttons=[]
        for i,name in enumerate(PHASES):
            b=ttk.Button(nav,text=str(i+1)+'  '+name,style='Nav.TButton',command=lambda n=i:app.guard(lambda:self.go(n)));b.pack(side='left',padx=(0,7));self.nav_buttons.append(b)
        self.notice=tk.StringVar(value='Escolha um paciente ou vários pacientes e importe PDF, JPG ou PNG. A leitura é automática.')
        ttk.Label(self.frame,textvariable=self.notice,style='Muted.TLabel',wraplength=1150).pack(fill='x',pady=(10,12))
        self.body=ttk.Frame(self.frame,style='Clean.TFrame');self.body.pack(fill='both',expand=True)
        self.panels=[ttk.Frame(self.body,style='Clean.TFrame') for _ in PHASES]
        self.make_home();self.make_documents();self.make_data();self.make_exams();self.make_preview()
        footer=ttk.Frame(self.frame,style='Clean.TFrame');footer.pack(fill='x',pady=(12,0))
        self.back_button=ttk.Button(footer,text='Voltar',command=lambda:app.guard(lambda:self.go(max(0,self.phase-1))));self.back_button.pack(side='left')
        self.save_corrections_button=ttk.Button(footer,text='Salvar correções',command=lambda:app.guard(self.save_corrections));self.save_corrections_button.pack(side='left',padx=8)
        self.reprocess_button=ttk.Button(footer,text='Reprocessar leitura',command=lambda:app.guard(self.reprocess));self.reprocess_button.pack(side='left')
        self.next_button=ttk.Button(footer,text='Continuar',style='Primary.TButton',command=lambda:app.guard(self.continue_flow));self.next_button.pack(side='right')
        self.legacy_return=ttk.Button(self.root,text='Voltar ao painel simples',style='Primary.TButton',command=self.hide_advanced)
        app.status.trace_add('write',lambda *_:self.read_status());self.refresh_home();self.go(0)
    def run(self,fn):return self.app.guard(fn)
    def read_status(self):
        status=self.app.status.get()
        if self.app.busy:self.notice.set(status)
        elif status.startswith('Análise cancelada'):self.notice.set(status)
        elif status.startswith('Leitura encerrada'):
            conflict=self.app.models and any(m.get('identity_conflict') for m in self.app.models.values())
            self.notice.set('Leitura concluída com conflito de identificação. As páginas permanecem juntas provisoriamente; confira os identificadores e separe as páginas antes de confirmar.' if conflict else 'Leitura concluída. Confira as páginas e os dados identificados. Você já pode abrir e salvar o rascunho de pré-cadastro.')
    def card(self,parent,title):
        box=ttk.Frame(parent,style='Card.TFrame',padding=14);ttk.Label(box,text=title,style='Card.TLabel',font=(self.font,12,'bold')).pack(anchor='w',pady=(0,8));return box
    def table(self,parent,columns,height=8):
        area=ttk.Frame(parent);area.pack(fill='both',expand=True)
        tree=ttk.Treeview(area,columns=[c[0] for c in columns],show='headings',style='Clean.Treeview',height=height)
        for key,title,width in columns:tree.heading(key,text=title);tree.column(key,width=width,minwidth=55)
        v=ttk.Scrollbar(area,orient='vertical',command=tree.yview);h=ttk.Scrollbar(area,orient='horizontal',command=tree.xview);tree.configure(yscrollcommand=v.set,xscrollcommand=h.set)
        tree.grid(row=0,column=0,sticky='nsew');v.grid(row=0,column=1,sticky='ns');h.grid(row=1,column=0,sticky='ew');area.rowconfigure(0,weight=1);area.columnconfigure(0,weight=1);return tree
    def make_home(self):
        panel=self.panels[0];metrics=ttk.Frame(panel,style='Clean.TFrame');metrics.pack(fill='x',pady=(0,14));self.metrics=[]
        for title in ['Documentos analisados','Atendimentos para conferência','Com pendências']:
            c=self.card(metrics,title);c.pack(side='left',fill='both',expand=True,padx=(0,10));v=tk.StringVar(value='0');ttk.Label(c,textvariable=v,style='Card.TLabel',font=(self.font,24,'bold')).pack(anchor='w');self.metrics.append(v)
        self.scope_tabs=ttk.Notebook(panel,style='Clean.TNotebook');self.scope_tabs.pack(fill='both',expand=True);self.scope=tk.StringVar(value='single');self.import_buttons={};self.queues={}
        self.advanced_grouping=tk.BooleanVar(value=False)
        for scope,title,description in [('single','Cadastro de um paciente','Cada PDF mantém todas as suas páginas em um atendimento provisório. Conflitos exigem revisão.'),('multiple','Cadastro de vários pacientes','Selecione vários PDFs: cada arquivo gera seu próprio atendimento provisório. PDFs diferentes não são reunidos.')]:
            frame=ttk.Frame(self.scope_tabs,padding=14);self.scope_tabs.add(frame,text=title)
            ttk.Label(frame,text=description,wraplength=1050).pack(anchor='w',pady=(0,10));b=ttk.Button(frame,text='Importar documentos',style='Primary.TButton',command=lambda s=scope:self.run(lambda:self.import_documents(s)));b.pack(anchor='w',pady=(0,12));self.import_buttons[scope]=b
            tree=self.table(frame,[('patient','Atendimento / paciente',330),('stage','Situação',250),('exams','Exames',90),('pending','Pendências',110)])
            tree.bind('<<TreeviewSelect>>',lambda e,t=tree:self.choose_from(t));tree.bind('<Double-1>',lambda e:self.run(lambda:self.go(1)));self.queues[scope]=tree
            if scope=='multiple':
                ttk.Checkbutton(frame,text='Avançado: este PDF contém vários pacientes — propor separação por identificadores',variable=self.advanced_grouping).pack(anchor='w',pady=4)
                self.batch_drafts_button=ttk.Button(frame,text='Salvar rascunhos dos atendimentos',command=lambda:self.run(self.save_batch_drafts));self.batch_drafts_button.pack(anchor='w',pady=(8,0))
        self.scope_tabs.bind('<<NotebookTabChanged>>',lambda e:self.scope.set('single' if self.scope_tabs.index(self.scope_tabs.select())==0 else 'multiple'))
    def make_documents(self):
        panel=self.panels[1]
        ttk.Label(panel,text='Veja as páginas e confira o tipo de documento. Uma guia não substitui um pedido ausente.',style='Clean.TLabel').pack(anchor='w',pady=(0,8))
        from page_panel import PagePanel
        DocumentView=type(self.app.views['pedido'])
        self.page_panel=PagePanel(panel,DocumentView);self.page_panel.pack(fill='both',expand=True);self.app.page_panel=self.page_panel
        self.document_kind=tk.StringVar(value=KIND_LABELS['pedido'])
        old=self.page_panel.viewer.on_page
        def selected(i):
            old(i)
            if 0<=i<len(self.page_panel.items):
                item=self.page_panel.items[i];self.app.page_kind.set(item['kind']);self.document_kind.set(KIND_LABELS[item['kind']]);self.page_panel.viewer.info.set('Página '+str(item['page'])+' do arquivo original — '+KIND_LABELS[item['kind']])
        self.page_panel.viewer.on_page=selected
        actions=ttk.Frame(panel,style='Clean.TFrame');actions.pack(fill='x',pady=8)
        ttk.Label(actions,text='Tipo da página',style='Clean.TLabel').pack(side='left');ttk.Combobox(actions,textvariable=self.document_kind,values=list(KIND_LABELS.values()),state='readonly',width=29).pack(side='left',padx=8)
        self.correct_type_button=ttk.Button(actions,text='Corrigir tipo',command=lambda:self.run(self.correct_type));self.correct_type_button.pack(side='left')
        self.move_button=ttk.Button(actions,text='Mover página',command=lambda:self.run(self.move_page));self.move_button.pack(side='left',padx=8)
        review_actions=ttk.Frame(panel,style='Clean.TFrame');review_actions.pack(fill='x')
        ttk.Button(review_actions,text='Identificação por página',command=lambda:self.run(self.page_identity)).pack(side='left')
        self.regroup_pdf_button=ttk.Button(review_actions,text='Reunir páginas deste PDF',command=lambda:self.run(self.regroup_pdf));self.regroup_pdf_button.pack(side='left',padx=8)
        self.confirm_pages_button=ttk.Button(review_actions,text='Confirmar páginas e identidade',command=lambda:self.run(self.app.confirm_case_pages));self.confirm_pages_button.pack(side='right')
    def make_data(self):
        panel=self.panels[2];ttk.Label(panel,text='Corrija somente o que precisar. Os números são mantidos como texto, incluindo zeros à esquerda.',style='Clean.TLabel').pack(anchor='w',pady=(0,8))
        self.correct_information_button=ttk.Button(panel,text='Corrigir informação',command=lambda:self.run(self.focus_information));self.correct_information_button.pack(anchor='w',pady=(0,8))
        canvas=tk.Canvas(panel,bg=COLORS['bg'],highlightthickness=0);scroll=ttk.Scrollbar(panel,orient='vertical',command=canvas.yview);canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        self.data_canvas=canvas
        self.data_area=ttk.Frame(canvas,style='Clean.TFrame');wid=canvas.create_window(0,0,window=self.data_area,anchor='nw');canvas.bind('<Configure>',lambda e:canvas.itemconfigure(wid,width=e.width));self.data_area.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        self.data_area.columnconfigure(0,weight=1);self.data_area.columnconfigure(1,weight=1)
        self.inputs={};self.origin_buttons={};self.field_roles={};self.field_states={};self.state_widgets={};self.clinical_var=None
        groups=[('Paciente',[10,8],0,0),('Autorização e guia',[2,3,7,5],1,0),('Solicitante e atendimento',[15,16,17,18,23,30],0,1)]
        for title,nums,row,col in groups:
            card=self.card(self.data_area,title);card.grid(row=row,column=col,rowspan=2 if col else 1,sticky='nsew',padx=(0,10),pady=(0,10));fields=ttk.Frame(card,style='Card.TFrame');fields.pack(fill='both',expand=True);fields.columnconfigure(1,weight=1)
            for i,n in enumerate(nums):
                _,key,label=next(x for x in PRIORITY if x[0]==n);r=i*2
                ttk.Label(fields,text=label+' ('+str(n)+')',style='Card.TLabel').grid(row=r,column=0,sticky='w',padx=(0,8),pady=4)
                if n==23:
                    widget=tk.Text(fields,height=3,width=30,wrap='word',font=(self.font,10),borderwidth=1,relief='solid');widget.bind('<KeyRelease>',self.clinical_changed)
                else:widget=ttk.Entry(fields,width=25)
                widget.grid(row=r,column=1,sticky='ew',pady=4);self.inputs[key]=widget
                origin=ttk.Button(fields,text='Origem',command=lambda k=key:self.run(lambda:self.origin(k)));origin.grid(row=r,column=2,padx=(5,0));self.origin_buttons[key]=origin
                state=tk.StringVar();self.field_states[key]=state;status=ttk.Label(fields,textvariable=state,style='Card.TLabel',font=(self.font,9),foreground=COLORS['muted']);status.grid(row=r+1,column=1,columnspan=2,sticky='w');self.state_widgets[key]=status
        self.extra_toggle=ttk.Button(self.data_area,text='Mostrar dados complementares: nascimento, fonte e atendimento',command=self.toggle_extra);self.extra_toggle.grid(row=2,column=0,columnspan=2,sticky='w',pady=5)
        extra=self.card(self.data_area,'Dados complementares');extra.grid(row=3,column=0,columnspan=2,sticky='ew',padx=(0,10));extra.grid_remove();self.extra_card=extra;self.extra_visible=False;self.extra_inputs={}
        row=ttk.Frame(extra,style='Card.TFrame');row.pack(fill='x')
        for key,label in [('Nascimento','Nascimento'),('Fonte pagadora','Fonte pagadora'),('Regime atendimento','Regime de atendimento'),('Validade senha','Validade da senha')]:
            cell=ttk.Frame(row,style='Card.TFrame');cell.pack(side='left',fill='x',expand=True,padx=4);ttk.Label(cell,text=label,style='Card.TLabel').pack(anchor='w');entry=ttk.Entry(cell,width=20);entry.pack(fill='x');self.extra_inputs[key]=entry
    def make_exams(self):
        panel=self.panels[3];ttk.Label(panel,text='Exames identificados nos documentos. Quantidade vazia ou zero não significa autorização.',style='Clean.TLabel').pack(anchor='w',pady=(0,10))
        self.exam_table=self.table(panel,[('name','Exame',300),('code','Código TUSS / lido',150),('requested','Solicitada',105),('authorized','Autorizada',105),('state','Comparação',270)])
        bar=ttk.Frame(panel,style='Clean.TFrame');bar.pack(fill='x',pady=8);self.exam_role=tk.StringVar(value='guia')
        ttk.Label(bar,text='Documento para corrigir:',style='Clean.TLabel').pack(side='left');ttk.Combobox(bar,textvariable=self.exam_role,values=['pedido','guia'],state='readonly',width=12).pack(side='left',padx=8)
        self.edit_exam_button=ttk.Button(bar,text='Corrigir exame',command=lambda:self.run(self.edit_exam));self.edit_exam_button.pack(side='left')
        ttk.Button(bar,text='Adicionar exame',command=lambda:self.run(lambda:self.add_exam())).pack(side='left',padx=8)
        self.compare_button=ttk.Button(bar,text='Comparar exames',style='Primary.TButton',command=lambda:self.run(self.compare));self.compare_button.pack(side='right')
    def toggle_extra(self):
        self.extra_visible=not self.extra_visible
        self.extra_card.grid() if self.extra_visible else self.extra_card.grid_remove()
        self.extra_toggle.configure(text='Ocultar dados complementares' if self.extra_visible else 'Mostrar dados complementares: nascimento, fonte e atendimento')
    def make_preview(self):
        outer=self.panels[4];self.preview_canvas=tk.Canvas(outer,bg=COLORS['bg'],highlightthickness=0)
        scrollbar=ttk.Scrollbar(outer,orient='vertical',command=self.preview_canvas.yview);self.preview_canvas.configure(yscrollcommand=scrollbar.set);scrollbar.pack(side='right',fill='y');self.preview_canvas.pack(fill='both',expand=True)
        panel=ttk.Frame(self.preview_canvas,style='Clean.TFrame');self.preview_area=panel;window=self.preview_canvas.create_window(0,0,window=panel,anchor='nw')
        self.preview_canvas.bind('<Configure>',lambda e:self.preview_canvas.itemconfigure(window,width=e.width));panel.bind('<Configure>',lambda e:self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox('all')))
        self.preview_title=tk.StringVar(value='Rascunho de pré-cadastro');self.preview_subtitle=tk.StringVar(value='Pode ser aberto e salvo com pendências. Não cria cadastro, autorização ou O.S. no Shift.')
        ttk.Label(panel,textvariable=self.preview_title,style='Title.TLabel').pack(anchor='w');ttk.Label(panel,textvariable=self.preview_subtitle,style='Muted.TLabel',wraplength=1000).pack(anchor='w',pady=(4,10))
        self.preview_summary=tk.Text(panel,height=5,wrap='word',font=(self.font,10),relief='flat',state='disabled');self.preview_summary.pack(fill='x',pady=(0,10))
        self.pending_table=self.table(panel,[('message','O que ainda precisa de atenção',700),('action','Próxima ação',230)],height=5)
        self.resolve_pending_button=ttk.Button(panel,text='Resolver pendência selecionada',command=lambda:self.run(self.resolve_pending));self.resolve_pending_button.pack(anchor='w',pady=5)
        self.review_options=ttk.Frame(panel,style='Clean.TFrame');self.review_options.pack(fill='x')
        metadata=ttk.Frame(self.review_options,style='Clean.TFrame');metadata.pack(fill='x',pady=5);ttk.Label(metadata,text='Motivo da conferência',style='Clean.TLabel').pack(side='left');self.reason_entry=ttk.Entry(metadata,textvariable=self.app.review_reason);self.reason_entry.pack(side='left',fill='x',expand=True,padx=8)
        self.data_review=tk.BooleanVar();self.exams_review=tk.BooleanVar();self.final_confirm=tk.BooleanVar()
        for text,var in [('Conferi os dados e as ausências com os documentos',self.data_review),('Conferi exames, quantidades e alertas apresentados',self.exams_review),('Confirmo a identidade e a autorização deste atendimento',self.final_confirm)]:ttk.Checkbutton(self.review_options,text=text,variable=var).pack(anchor='w',pady=2)
        bar=ttk.Frame(panel,style='Clean.TFrame');bar.pack(fill='x',pady=8);self.preview_actions=bar
        self.save_draft_button=ttk.Button(bar,text='Salvar rascunho',command=lambda:self.run(self.save_current_draft));self.save_draft_button.pack(side='left')
        ttk.Button(bar,text='Exportar rascunho JSON',command=lambda:self.run(self.export_draft)).pack(side='left',padx=8)
        self.validate_button=ttk.Button(bar,text='Salvar conferência',command=lambda:self.run(self.save_review));self.validate_button.pack(side='left')
        self.prepare_button=ttk.Button(bar,text='Preparar pré-cadastro validado',style='Primary.TButton',command=lambda:self.run(self.prepare));self.prepare_button.pack(side='right')
        self.prepared_actions=ttk.Frame(panel,style='Clean.TFrame');ttk.Button(self.prepared_actions,text='Exportar pré-cadastro validado',style='Primary.TButton',command=lambda:self.run(self.app.export)).pack(side='right')
    def go(self,n):
        if n and not self.app.cid:self.notice.set('Importe documentos ou selecione um atendimento na fila.');n=0
        if self.app.cid and self.clinical_var:self.clinical_changed()
        self.phase=n
        for panel in self.panels:panel.pack_forget()
        self.panels[n].pack(fill='both',expand=True)
        for i,b in enumerate(self.nav_buttons):b.configure(style='Primary.TButton' if i==n else 'Nav.TButton')
        self.back_button.configure(text='Início' if n==0 else 'Voltar') if hasattr(self,'back_button') else None
        if hasattr(self,'next_button'):self.next_button.configure(text='Salvar rascunho de pré-cadastro' if n==4 else 'Ver rascunho' if n==3 else 'Continuar')
        if n==4:self.refresh_detail()
    def continue_flow(self):
        if self.phase==4 and self.app.cid and self.app.store.get(self.app.cid)[2]=='PREPARADO':return self.app.export()
        if self.phase==4:return self.save_current_draft()
        self.go(self.phase+1)
    def focus_information(self):
        if not self.app.cid:raise ValueError('Selecione um atendimento.')
        from priority_fields import field_state
        models=self.app.collect()
        key=next((key for key in self.inputs if field_state(models[self.field_roles[key]]['fields'][key])=='uncertain'),'Paciente')
        widget=self.inputs[key];self.go(2);self.root.update_idletasks()
        height=max(1,self.data_area.winfo_reqheight());self.data_canvas.yview_moveto(max(0,(widget.winfo_rooty()-self.data_area.winfo_rooty()-25)/height));widget.focus_set()
        if key!='Indicação clínica':widget.selection_range(0,'end')
        self.notice.set('Edite o campo selecionado ou clique no dado que deseja corrigir. Depois use Salvar correções; o rascunho também pode ser salvo com pendências.')
    def import_documents(self,scope):
        self.scope.set(scope)
        if self.app.cid and self.app.dirty():self.save_current_draft(quiet=True)
        self.app.import_scans(mode='multiple' if scope=='multiple' and self.advanced_grouping.get() else 'single')
        if self.app.busy:self.notice.set('Lendo documentos localmente. Cada página será analisada e associada por identificação.')
    def choose_from(self,tree):
        selection=tree.selection()
        if not selection or selection[0]==self.app.cid:return
        self.run(lambda:self.choose_case(selection[0]))
    def choose_case(self,cid):
        if self.app.busy:return
        if self.app.cid and self.app.dirty() and self.app.store.get(self.app.cid)[2]!='PREPARADO':self.save_current_draft(quiet=True)
        self.app.cases.selection_set(cid);self.app.open_case(cid)
    def refresh_home(self):
        app=self.app;rows=[];sources=set();ready=0;pending=0
        for cid in app.cases.get_children():
            if cid in app.pending_imports:continue
            vals=app.cases.item(cid,'values');rows.append((cid,vals));obj=app.store.get(cid)[0]
            for d in obj['docs'].values():
                for src in d.get('original_sources',[]):sources.add(src['sha256'])
                if d.get('pages') and not d.get('scan_batch'):sources.add(d['sha256'])
            ready+=any(m['interpretation']['fields_found'] or m['interpretation']['exams_found'] for m in obj['models'].values());pending+=int(vals[3])>0
        for tree in self.queues.values():
            old=tree.selection();tree.delete(*tree.get_children())
            for cid,vals in rows:tree.insert('','end',iid=cid,values=vals)
            if app.cid and tree.exists(app.cid):tree.selection_set(app.cid)
        for var,value in zip(self.metrics,[len(sources),ready,pending]):var.set(str(value))
    def bind_case(self):
        app=self.app;new_patient=self.bound_cid!=app.cid;changed=new_patient or self.bound_revision!=app.rev;self.bound_cid=app.cid;self.bound_revision=app.rev;self.binding=True
        prepared=app.store.get(app.cid)[2]=='PREPARADO'
        has_guide=bool(app.views['guia'].doc['pages']);role='guia' if has_guide else 'pedido'
        try:
            for key,widget in self.inputs.items():
                selected=source_role({'models':app.models,'docs':{k:v.doc for k,v in app.views.items()}},key)
                self.field_roles[key]=selected;var=app.field_vars[selected][key]
                if key=='Indicação clínica':
                    widget.configure(state='normal');self.clinical_var=var;widget.delete('1.0','end');widget.insert('1.0','' if var.get()=='Não identificado' else var.get());widget.configure(state='disabled' if prepared else 'normal')
                else:widget.configure(textvariable=var,state='readonly' if prepared else 'normal')
            for key,widget in self.extra_inputs.items():widget.configure(textvariable=app.field_vars['pedido' if key=='Nascimento' and app.views['pedido'].doc['pages'] else role][key],state='readonly' if prepared else 'normal')
            if changed:
                self.data_review.set(all(m['pages_reviewed'] and all(f['reviewed'] for f in m['fields'].values()) for m in app.models.values()))
                self.exams_review.set(all(all(e['reviewed'] for e in m['exams']) and all(i['reviewed'] for i in m['issues']) for m in app.models.values()));self.final_confirm.set(False)
        finally:self.binding=False
        name=app.models[self.field_roles['Paciente']]['fields']['Paciente']['value'] or 'Identificação pendente';self.case_title.set(name)
        self.refresh_detail()
        if new_patient:self.go(1)
    def clinical_changed(self,event=None):
        if self.binding or not self.clinical_var:return
        value=self.inputs['Indicação clínica'].get('1.0','end-1c')
        if value!=self.clinical_var.get() and not (not value and self.clinical_var.get()=='Não identificado'):self.clinical_var.set(value)
    def invalidate_review(self):
        if self.binding:return
        self.data_review.set(False);self.final_confirm.set(False)
    def refresh_detail(self):
        app=self.app
        if not app.cid or not app.models:return
        models=app.collect()
        from priority_fields import field_state
        for key,var in self.field_states.items():
            field=models[self.field_roles.get(key,'guia')]['fields'][key];var.set(state_label(field));uncertain=field_state(field)=='uncertain'
            self.state_widgets[key].configure(foreground='#a25e08' if uncertain else COLORS['muted'])
            if key!='Indicação clínica':self.inputs[key].configure(style='Attention.TEntry' if uncertain else 'TEntry')
        result=compare_models(models['pedido'],models['guia'],app.catalog);self.comparison_rows=result['exames']
        self.exam_table.delete(*self.exam_table.get_children())
        for i,r in enumerate(self.comparison_rows):self.exam_table.insert('','end',iid=str(i),values=(r['nome'],r.get('codigo_lido') or r.get('tuss') or 'Não identificado',r['pedido'],r['guia'],'Correspondem — conferir' if r['situacao']=='Conferir' else r['situacao']))
        obj=app.store.get(app.cid)[0];preview=build_draft({**obj,'models':models},app.catalog,app.cid,app.rev);self.preview=preview
        prepared=app.store.get(app.cid)[2]=='PREPARADO';self.preview_title.set('Pré-cadastro validado — demonstração' if prepared else 'Rascunho de pré-cadastro')
        self.preview_subtitle.set('Conferência concluída e resultado salvo localmente. Nenhuma O.S. real foi criada.' if prepared else 'Pode ser aberto e salvo com pendências. Não cria cadastro, autorização ou O.S. no Shift.')
        for widget in [self.pending_table.master,self.resolve_pending_button,self.review_options,self.preview_actions,self.prepared_actions]:widget.pack_forget()
        self.preview_summary.configure(height=10 if prepared else 5)
        if prepared:
            self.prepared_actions.pack(fill='x',pady=8);self.preview_canvas.yview_moveto(0)
        else:
            self.pending_table.master.pack(fill='both',expand=True);self.resolve_pending_button.pack(anchor='w',pady=5);self.review_options.pack(fill='x');self.preview_actions.pack(fill='x',pady=8)
        if prepared and self.phase==4:self.next_button.configure(text='Exportar pré-cadastro validado')
        title=['Paciente: '+(preview['campos']['Paciente']['valor'] or 'Não identificado'),'Fonte pagadora: '+(models['guia']['fields']['Fonte pagadora']['value'] or 'Não identificada'),
               'Documentos: '+', '.join(role for role,present in preview['documentos_presentes'].items() if present),'Exames reconhecidos: '+str(len(result['exames']))]
        for key in ['Guia prestador','Guia principal','Guia operadora','Senha autorização','Medico','Contratado executante']:
            if preview['campos'][key]['valor']:title.append(preview['campos'][key]['rotulo']+': '+preview['campos'][key]['valor'])
        app.set_text(self.preview_summary,'\n'.join(title))
        self.pending_items=[]
        for message in preview['pendencias']:
            action='dados'
            if any(t in message.lower() for t in ['catálogo','código interno']):action='catálogo'
            elif any(t in message.lower() for t in ['perfil','escopo']):action='perfil'
            elif any(t in message.lower() for t in ['páginas','identidade','documento não identificado','classificação']):action='documentos'
            elif any(t in message.lower() for t in ['quantidade','procedimento','exame']):action='exames'
            self.pending_items.append((message,action))
        for role,m in models.items():
            for issue in m['issues']:
                if not issue['reviewed']:self.pending_items.append((role.capitalize()+': '+issue['message'],'conferir alerta'))
        self.pending_table.delete(*self.pending_table.get_children())
        for i,(message,action) in enumerate(self.pending_items):self.pending_table.insert('','end',iid=str(i),values=(message,action.capitalize()))
        if self.pending_items:self.pending_table.selection_set('0')
    def origin(self,key):self.app.locate_field(self.field_roles[key],key)
    def source_dialog(self,role,key,src):
        DocumentView=type(self.app.views['pedido'])
        if src.get('document'):
            role=next((k for k,v in self.app.views.items() if v.doc and v.doc.get('file')==src['document']),role)
        window=tk.Toplevel(self.root);window.title('Origem da informação — '+key);window.geometry('850x700')
        ttk.Label(window,text='Documento original preservado. '+src.get('diagnostic','Confira o valor destacado.'),padding=10,wraplength=800).pack(fill='x')
        viewer=DocumentView(window,'Fonte da informação');viewer.pack(fill='both',expand=True);viewer.load(self.app.views[role].doc);viewer.locate(src.get('page'),src.get('box'));self.source_view=viewer
        excerpt=tk.Text(window,height=4,wrap='word');excerpt.pack(fill='x');excerpt.insert('1.0',src.get('snippet') or 'Campo sem leitura localizada.');excerpt.configure(state='disabled')
    def edit_exam(self):
        selection=self.exam_table.selection()
        if not selection:raise ValueError('Selecione um exame na tabela.')
        from engine_v2 import resolve_exam
        from core import norm
        row=self.comparison_rows[int(selection[0])];role=self.exam_role.get();matches=[]
        for i,e in enumerate(self.app.models[role]['exams']):
            cat,_=resolve_exam(e,self.app.catalog)
            if (cat and cat['nome']==row['nome']) or (e['codigo'] and e['codigo']==row.get('codigo_lido',row.get('tuss',''))) or norm(e['descricao'])==norm(row['nome']):matches.append(i)
        if len(matches)!=1:raise ValueError('Selecione o documento correto. Se houver linhas repetidas, use a conferência detalhada em Mais opções.')
        self.app.exam_tables[role].selection_set(str(matches[0]));self.app.edit_exam(role);self.after_exam_edit()
    def add_exam(self):
        role=self.exam_role.get()
        if not self.app.views[role].doc['pages']:raise ValueError('Esse documento não foi encontrado. Não é possível criar um pedido a partir da guia.')
        self.app.edit_exam(role,new=True);self.after_exam_edit()
    def after_exam_edit(self):
        editor=self.app.exam_editor['window']
        def closed(event):
            if event.widget==editor:self.exams_review.set(False);self.final_confirm.set(False);self.refresh_detail()
        editor.bind('<Destroy>',closed,add='+')
    def compare(self):self.clinical_changed();self.app.show_comparison();self.notice.set('Comparação atualizada. Divergências e campos pendentes permanecem visíveis.');self.refresh_detail()
    def correct_type(self):
        self.app.page_kind.set(next(k for k,v in KIND_LABELS.items() if v==self.document_kind.get()));self.app.correct_page_type()
    def save_corrections(self):
        if not self.app.cid:raise ValueError('Selecione um atendimento.')
        self.clinical_changed()
        if self.app.save():self.notice.set('Correções salvas. Você pode continuar para o rascunho mesmo com pendências.');self.bind_case()
    def save_current_draft(self,quiet=False):
        if not self.app.cid:
            if quiet:return
            raise ValueError('Selecione um atendimento.')
        self.clinical_changed();result=save_draft(self.app.store,self.app.cid,self.app.collect(),self.app.catalog,expected_revision=self.app.rev,metadata={'motivo':self.app.review_reason.get()})
        if not quiet:self.notice.set('Rascunho salvo localmente com '+str(len(result['pendencias']))+' pendências. Nada foi enviado ao Shift.')
        return result
    def save_review(self):
        if not self.app.metadata_ready():return
        if not self.data_review.get() or not self.exams_review.get():raise ValueError('Confira os dados, exames e alertas e marque as duas confirmações antes de salvar a conferência.')
        self.app.restore_seen_pages()
        for role,m in self.app.models.items():
            if self.app.views[role].doc['pages']:
                if not m['pages_reviewed'] and len(self.app.views[role].seen)!=len(self.app.views[role].doc['pages']):raise ValueError('Veja todas as páginas em Documentos antes de confirmar a conferência.')
                self.app.page_checks[role].set(True)
            for v in self.app.field_checks[role].values():v.set(True)
            for e in m['exams']:e['reviewed']=True
            for issue in m['issues']:issue.update(reviewed=True,reason=self.app.review_reason.get().strip())
        if self.app.save():self.notice.set('Conferência salva. O rascunho mostra as pendências que ainda impedem a preparação validada.');self.refresh_detail()
    def save_batch_drafts(self):
        saved=0
        for cid in self.queues['multiple'].get_children():
            obj,revision,status,_=self.app.store.get(cid)
            if status=='PREPARADO':continue
            if cid==self.app.cid:self.save_current_draft(quiet=True)
            else:
                draft=load_draft(self.app.store,cid);save_draft(self.app.store,cid,draft['models'] if draft else obj['models'],self.app.catalog,expected_revision=revision,metadata=(draft or {}).get('metadata'))
            saved+=1
        self.notice.set(str(saved)+' rascunhos salvos. Cada atendimento exige conferência individual; nenhum cadastro foi enviado ao Shift.')
    def prepare(self):
        self.go(4)
        if self.app.store.get(self.app.cid)[2]=='PREPARADO':self.notice.set('Este pré-cadastro já foi preparado localmente. O resultado original permanece preservado.');return
        if not self.app.metadata_ready():return
        self.app.show_comparison()
        if self.app.dirty():raise ValueError('Salve as correções e a conferência antes de preparar. O rascunho continua acessível.')
        if self.app.comparison_errors:raise ValueError('Resolva as pendências listadas para preparar. Você pode salvar e exportar o rascunho agora.')
        if not self.final_confirm.get():raise ValueError('Marque a confirmação de identidade e autorização antes de preparar o pré-cadastro.')
        self.app.confirm.set(True);self.app.prepare();self.notice.set('Pré-cadastro validado preparado LOCALMENTE. Nenhuma O.S. real foi criada.');self.refresh_home();self.bind_case()
    def export_draft(self):
        draft=self.save_current_draft();file=filedialog.asksaveasfilename(title='Salvar rascunho local',defaultextension='.json',initialfile='rascunho_local.json',filetypes=[('JSON','*.json')])
        if file:Path(file).write_text(json.dumps(draft,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');self.notice.set('Rascunho exportado com os avisos de pendência. Não foi enviado ao Shift.')
    def resolve_pending(self):
        selected=self.pending_table.selection()
        if not selected:raise ValueError('Selecione uma pendência.')
        _,action=self.pending_items[int(selected[0])]
        if action=='catálogo':return self.app.catalog_window()
        if action=='perfil':return self.app.payer_window()
        self.go({'documentos':1,'dados':2,'exames':3,'conferir alerta':4}[action])
        self.notice.set('Confira a pendência e corrija a informação. A preparação validada continua protegida.')
    def reprocess(self):
        if not self.app.cid:raise ValueError('Selecione um atendimento.')
        if not self.app.metadata_ready():return
        if self.app.dirty() and not self.app.save():return
        self.app.reanalyze_case()
    def page_identity(self):
        if self.app.dirty() and not self.app.save():return
        self.app.classification_window()
    def move_page(self):
        if not self.app.cid or not self.page_panel.selected_id:raise ValueError('Selecione uma página nas miniaturas.')
        from scan_import import load_batch
        obj=self.app.store.get(self.app.cid)[0];batch=load_batch(self.app.store,obj['docs']['pedido']['scan_batch']);item=next(i for i in batch['pages'] if i['id']==self.page_panel.selected_id)
        w=tk.Toplevel(self.root);w.title('Mover página para outro atendimento');w.geometry('580x260')
        ttk.Label(w,text='Escolha o atendimento. As páginas e identificadores serão verificados novamente.',padding=12,wraplength=530).pack(fill='x')
        target=tk.StringVar(value=item['group']);ttk.Combobox(w,textvariable=target,values=list(dict.fromkeys(i['group'] for i in batch['pages'])),width=52).pack(padx=12,pady=8)
        ttk.Label(w,text='Seu nome e motivo da conferência devem estar preenchidos no painel.').pack(pady=5)
        def commit():
            if not self.app.metadata_ready():return
            if not target.get().strip():raise ValueError('Informe o atendimento de destino.')
            if self.app.dirty() and not self.app.save():return
            item['group']=target.get().strip();self.app._save_pages(batch,set(self.page_panel.seen_ids));self.notice.set('Página movida. Confirme novamente os tipos e a identidade; conflitos continuam bloqueados.');w.destroy()
        button=ttk.Button(w,text='Mover página',style='Primary.TButton',command=lambda:self.run(commit));button.pack(pady=12);self.move_editor={'window':w,'target':target,'button':button}
    def regroup_pdf(self):
        if not self.app.cid or not self.page_panel.selected_id:raise ValueError('Selecione uma página do PDF nas miniaturas.')
        if not self.app.metadata_ready():return
        if self.app.dirty() and not self.app.save():return
        from scan_import import load_batch
        obj=self.app.store.get(self.app.cid)[0];batch=load_batch(self.app.store,obj['docs']['pedido']['scan_batch']);selected=next(i for i in batch['pages'] if i['id']==self.page_panel.selected_id)
        if not messagebox.askyesno('Reunir provisoriamente','Manter todas as páginas deste PDF no mesmo atendimento provisório? Conflitos continuarão impedindo a confirmação.'):return
        for item in batch['pages']:
            if item['source']==selected['source']:item['group']=selected['group']
        batch['group_reviews']={};self.app._save_pages(batch,set(self.page_panel.seen_ids));self.notice.set('Páginas do PDF reunidas provisoriamente. Confira identidade e classificação; conflitos não são aprovados.')
    def examples(self):self.show_advanced();self.app.examples()
    def show_advanced(self):
        self.frame.pack_forget();self.advanced=True
        for w,info in self.legacy_pack:
            info={k:v for k,v in info.items() if k!='in'};w.pack(**info)
        self.legacy_return.pack(side='bottom',fill='x')
    def hide_advanced(self):
        for w,_ in self.legacy_pack:w.pack_forget()
        self.legacy_return.pack_forget();self.advanced=False;self.frame.pack(fill='both',expand=True);self.bind_case() if self.app.cid else self.go(0)
