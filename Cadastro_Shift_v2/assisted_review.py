"""Conferência guiada local. Checkboxes humanos não dispensam validadores clínicos."""
import copy,tkinter as tk
from tkinter import ttk,messagebox
from engine_v2 import FIELDS,compare_models


class ReviewAssistant:
    def __init__(self,app):
        self.app=app;self.cid=app.cid;self.window=tk.Toplevel(app.root)
        self.window.title('Conferir atendimento — passo a passo');self.window.geometry('1080x760');self.window.minsize(850,600)
        self.window.transient(app.root)
        ttk.Label(self.window,text='1. Veja e identifique as páginas → 2. Confira dados e exames → 3. Salve e prepare',font=('Segoe UI',12,'bold'),padding=10).pack(fill='x')
        metadata=ttk.Frame(self.window,padding=8);metadata.pack(fill='x')
        ttk.Label(metadata,text='Revisor:').grid(row=0,column=0,sticky='w');actor=ttk.Entry(metadata,textvariable=app.actor,width=28);actor.grid(row=0,column=1,sticky='ew',padx=5)
        ttk.Label(metadata,text='Motivo da conferência:').grid(row=1,column=0,sticky='w');reason=ttk.Entry(metadata,textvariable=app.review_reason);reason.grid(row=1,column=1,sticky='ew',padx=5)
        metadata.columnconfigure(1,weight=1);self.entries={'actor':actor,'reason':reason}
        self.message=tk.StringVar(value='Comece vendo todas as páginas. Confira os tipos e a identidade antes de marcar os dados.')
        ttk.Label(self.window,textvariable=self.message,wraplength=1000,padding=8,foreground='#173d52').pack(fill='x')
        actions=ttk.Frame(self.window,padding=6);actions.pack(fill='x')
        for text,fn in [('Ver páginas / corrigir tipos',self.pages),('Confirmar páginas e identidade',self.confirm_pages),('Corrigir campos na tela principal',self.fields),('Atualizar esta conferência',self.refresh)]:
            button=ttk.Button(actions,text=text,command=lambda f=fn:self.run(f));button.pack(side='left',padx=3)
            if fn==self.confirm_pages:self.confirm_pages_button=button
        tabs=ttk.Notebook(self.window);tabs.pack(fill='both',expand=True,padx=8)
        data=ttk.Frame(tabs);exams=ttk.Frame(tabs);alerts=ttk.Frame(tabs);tabs.add(data,text='Dados que serão conferidos');tabs.add(exams,text='Exames solicitados e autorizados');tabs.add(alerts,text='Alertas que exigem leitura')
        self.summary=tk.Text(data,wrap='word',height=10,state='disabled');self.summary.pack(fill='both',expand=True)
        self.exam_table=ttk.Treeview(exams,columns=('role','name','code','requested','authorized','review'),show='headings')
        for key,title,width in [('role','Documento',90),('name','Exame impresso',270),('code','Código lido',100),('requested','Solicitada',90),('authorized','Autorizada / pedido',120),('review','Conferido',80)]:self.exam_table.heading(key,text=title);self.exam_table.column(key,width=width)
        scroll=ttk.Scrollbar(exams,orient='vertical',command=self.exam_table.yview);self.exam_table.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.exam_table.pack(fill='both',expand=True)
        ttk.Button(exams,text='Editar o exame selecionado',command=lambda:self.run(self.edit_exam)).pack(pady=4)
        self.alert_text=tk.Text(alerts,wrap='word',height=10,state='disabled');self.alert_text.pack(fill='both',expand=True)
        checks=ttk.LabelFrame(self.window,text='Marque somente depois de comparar com os originais',padding=7);checks.pack(fill='x',padx=8,pady=5)
        self.data_checks={};self.exam_checks={};self.alert_check=tk.BooleanVar()
        for i,role in enumerate(['pedido','guia']):
            self.data_checks[role]=tk.BooleanVar();self.exam_checks[role]=tk.BooleanVar()
            ttk.Checkbutton(checks,text='Conferi todos os dados do '+role+', inclusive ausências',variable=self.data_checks[role]).grid(row=i,column=0,sticky='w',padx=4)
            ttk.Checkbutton(checks,text='Conferi todos os exames do '+role+' e possíveis linhas não reconhecidas',variable=self.exam_checks[role]).grid(row=i,column=1,sticky='w',padx=4)
        ttk.Checkbutton(checks,text='Li os alertas da aba acima e conferi a resolução no original; o motivo está informado nesta tela',variable=self.alert_check).grid(row=2,column=0,columnspan=2,sticky='w')
        footer=ttk.Frame(self.window,padding=8);footer.pack(fill='x')
        self.final_check=tk.BooleanVar();ttk.Checkbutton(footer,text='Confirmo paciente, documentos, exames e autorização',variable=self.final_check,command=self.update_prepare).pack(anchor='w')
        self.save_button=ttk.Button(footer,text='SALVAR CONFERÊNCIA E VER RESULTADO',command=lambda:self.run(self.save));self.save_button.pack(side='left',padx=4)
        self.prepare_button=ttk.Button(footer,text='Preparar pré-cadastro local',command=lambda:self.run(self.prepare));self.prepare_button.pack(side='right',padx=4)
        def blocked_prepare_click(event):
            if str(self.prepare_button['state'])!='disabled':return
            if not app.metadata_ready(self.entries):self.message.set(app.review_hint.get())
            elif not self.saved:self.message.set('Primeiro confira as abas e clique em SALVAR CONFERÊNCIA E VER RESULTADO.')
            elif app.comparison_errors:self.message.set('Pré-cadastro bloqueado por:\n'+'\n'.join(app.comparison_errors[:6]))
            else:self.message.set('Marque a confirmação final do paciente, documentos, exames e autorização.')
            return 'break'
        self.prepare_button.bind('<Button-1>',blocked_prepare_click)
        ttk.Button(footer,text='Configuração pendente do laboratório',command=lambda:self.run(self.configuration)).pack(side='left',padx=4)
        self.saved=False;self.last_revision=app.rev;self.refresh();self.window.grab_set()
        self.traces=[(variable,variable.trace_add('write',self.invalidate)) for variable in [app.actor,app.review_reason,*self.data_checks.values(),*self.exam_checks.values(),self.alert_check]]
        def closed(event):
            if event.widget==self.window:
                for variable,token in self.traces:
                    try:variable.trace_remove('write',token)
                    except tk.TclError:pass
        self.window.bind('<Destroy>',closed,add='+')
    def run(self,fn):
        try:
            if self.app.cid!=self.cid:raise ValueError('O atendimento mudou. Feche e abra a conferência novamente.')
            fn()
        except Exception as exc:self.message.set(str(exc))
    def invalidate(self,*args):
        if not self.window.winfo_exists():return
        self.saved=False;self.final_check.set(False);self.update_prepare()
    def show(self):
        self.window.deiconify();self.window.lift();self.window.grab_set();self.refresh()
    def hide(self):self.window.grab_release();self.window.withdraw()
    def pages(self):
        self.hide();self.app.tabs.select(self.app.page_tab if self.app.page_panel.items else self.app.doc_tab);self.app.status.set('Veja todas as páginas. Se necessário, corrija o tipo abaixo da página. Depois clique em CONFERIR ATENDIMENTO para voltar.')
    def fields(self):
        self.hide();self.app.manual_correction();self.app.status.set('Corrija os campos e depois clique em CONFERIR ATENDIMENTO para voltar. As alterações ainda precisam ser salvas.')
    def confirm_pages(self):
        if not self.app.metadata_ready(self.entries):self.message.set(self.app.review_hint.get());return
        self.app.confirm_case_pages();self.refresh()
        if not any(m.get('association_pending') or m.get('classification_pending') for m in self.app.models.values()):self.message.set('Páginas confirmadas. Confira as abas de dados, exames e alertas e marque as caixas abaixo.')
    def refresh(self):
        app=self.app;models=app.collect();text=[];alert_lines=[]
        self.confirm_pages_button.configure(state='normal' if app.views['pedido'].doc.get('scan_batch') else 'disabled')
        if app.rev!=self.last_revision or (self.saved and app.dirty()):
            self.invalidate()
            for var in [*self.data_checks.values(),*self.exam_checks.values(),self.alert_check]:var.set(False)
            self.last_revision=app.rev
        for role,m in models.items():
            text.append(role.upper()+' — '+str(len(app.views[role].doc['pages']))+' páginas')
            core={'Paciente','Medico','Conselho','Número conselho','UF conselho'}
            if role=='guia' and m.get('tiss'):
                core.update(['Fonte pagadora','Regime atendimento'])
                if (m.get('payer_profile') or {}).get('exige_autorizacao',True):core.update(['Guia prestador','Senha autorização','Validade senha'])
            shown={k for k,f in m['fields'].items() if k in core or f['value'] or f.get('candidates') or f.get('not_applicable')}
            text.extend(key+': '+(field['value'] or ('Não se aplica (perfil)' if field.get('not_applicable') else 'Não identificado')) for key,field in m['fields'].items() if key in shown)
            absent=[key for key in m['fields'] if key not in shown]
            if absent:text.append('Demais campos não identificados (confira as ausências): '+', '.join(absent)+'.')
            text.append('')
            alert_lines.extend(role.upper()+': '+issue['message'] for issue in m['issues'])
        app.set_text(self.summary,'\n'.join(text));app.set_text(self.alert_text,'\n\n'.join(alert_lines) or 'Sem alertas de leitura.')
        self.exam_table.delete(*self.exam_table.get_children())
        for role,m in models.items():
            for i,e in enumerate(m['exams']):self.exam_table.insert('','end',iid=role+':'+str(i),values=(role,e['descricao'],e['codigo'],e.get('quantidade_solicitada',e.get('quantidade','')),e.get('quantidade_autorizada','') if role=='guia' else e.get('quantidade',''),'Sim' if e['reviewed'] else 'Não'))
        self.update_prepare()
    def edit_exam(self):
        selection=self.exam_table.selection()
        if not selection:raise ValueError('Selecione um exame na tabela.')
        role,index=selection[0].split(':');self.app.exam_tables[role].selection_set(index);self.app.edit_exam(role)
        editor=self.app.exam_editor['window']
        def closed(event):
            if event.widget==editor and self.window.winfo_exists():self.invalidate();self.refresh();self.window.grab_set()
        editor.bind('<Destroy>',closed,add='+')
    def save(self):
        app=self.app
        if not app.metadata_ready(self.entries):self.message.set(app.review_hint.get());return
        app.restore_seen_pages()
        missing=[role for role,view in app.views.items() if not view.doc['pages'] or len(view.seen)!=len(view.doc['pages'])]
        if missing:raise ValueError('Primeiro veja todas as páginas de '+', '.join(missing)+'. Use Ver páginas / corrigir tipos.')
        if any(m.get('association_pending') or m.get('classification_pending') or m.get('identity_conflict') for m in app.models.values()):raise ValueError('Confirme os tipos de páginas e a identidade antes de concluir. Conflitos devem ser corrigidos, não aprovados.')
        if not all(v.get() for v in [*self.data_checks.values(),*self.exam_checks.values(),self.alert_check]):raise ValueError('Confira as três abas e marque os dados, exames e alertas que você verificou. Essas confirmações são obrigatórias.')
        for role,model in app.models.items():
            app.page_checks[role].set(True)
            for field in app.field_checks[role].values():field.set(True)
            for exam in model['exams']:exam['reviewed']=True
            for issue in model['issues']:issue.update(reviewed=True,reason=app.review_reason.get().strip())
            app.render_rows(role)
        if not app.save():return
        self.saved=True;self.last_revision=app.rev;self.final_check.set(False);self.refresh()
        if app.comparison_errors:
            self.message.set('CONFERÊNCIA SALVA. O pré-cadastro ainda está bloqueado por:\n'+'\n'.join(app.comparison_errors[:6])+'\nCorrija os dados ou solicite a configuração ao responsável do laboratório.')
        else:self.message.set('CONFERÊNCIA SALVA SEM PENDÊNCIAS. Marque a confirmação final e clique em Preparar pré-cadastro local.')
    def update_prepare(self):
        ready=self.saved and self.final_check.get() and not self.app.comparison_errors and not self.app.dirty() and self.app.store.get(self.cid)[2]!='PREPARADO'
        self.prepare_button.configure(state='normal' if ready else 'disabled')
    def configuration(self):
        errors=compare_models(self.app.collect()['pedido'],self.app.collect()['guia'],self.app.catalog)['pendencias']
        self.hide()
        if any('catálogo' in e.lower() or 'código interno' in e.lower() for e in errors):self.app.catalog_window()
        else:self.app.payer_window()
    def prepare(self):
        if not self.saved or not self.final_check.get():raise ValueError('Salve a conferência e marque a confirmação final antes de preparar.')
        self.app.confirm.set(True);self.app.prepare();self.message.set('PRÉ-CADASTRO LOCAL PREPARADO. Nada foi enviado ao Shift.');self.prepare_button.configure(state='disabled')
