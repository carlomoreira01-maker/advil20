"""Miniaturas locais de TODAS as páginas, inclusive complementares e desconhecidas."""
import copy
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from reader import preview


class PagePanel(ttk.Frame):
    def __init__(self,parent,view_class):
        super().__init__(parent)
        self.seen_ids=set();self.items=[];self.selected_id=None;self.photos=[]
        self.info=tk.StringVar(value='Importe um escaneamento para visualizar suas páginas.')
        ttk.Label(self,textvariable=self.info,wraplength=950,padding=6).pack(fill='x')
        panes=ttk.Panedwindow(self,orient='horizontal');panes.pack(fill='both',expand=True)
        left=ttk.Frame(panes,width=190);right=ttk.Frame(panes);panes.add(left,weight=1);panes.add(right,weight=6)
        canvas=tk.Canvas(left,width=180,highlightthickness=0);scroll=ttk.Scrollbar(left,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set);canvas.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        self.thumbs=ttk.Frame(canvas);canvas.create_window(0,0,window=self.thumbs,anchor='nw')
        self.thumbs.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        self.viewer=view_class(right,'Página original · classificação individual');self.viewer.pack(fill='both',expand=True)
        self.viewer.on_page=self.opened
        self.buttons=[]
    def clear(self):
        self.items=[];self.seen_ids=set();self.selected_id=None;self.photos=[];self.buttons=[]
        for w in self.thumbs.winfo_children():w.destroy()
        self.viewer.doc=None;self.viewer.path=None;self.viewer.canvas.delete('all');self.viewer.info.set('')
    def load(self,batch,group,data):
        from PIL import ImageTk
        self.items=[copy.deepcopy(i) for i in batch['pages'] if i['group']==group]
        self.seen_ids=set();self.photos=[];self.buttons=[]
        for widget in self.thumbs.winfo_children():widget.destroy()
        doc={'file':group,'pages':[]}
        for index,item in enumerate(self.items):
            source=batch['sources'][item['source']];page=copy.deepcopy(next(p for p in source['pages'] if p['number']==item['page']))
            path=Path(data)/'documentos'/(source['sha256']+Path(source['file']).suffix.lower())
            page['source']={'path':str(path),'page':item['page'],'sha256':source['sha256'],'file':source['file']}
            page['number']=index+1;doc['pages'].append(page)
            text=f'Página {item["page"]}\n{item["kind"]}'
            try:
                im,_=preview(path,item['page']-1);im.thumbnail((140,145));photo=ImageTk.PhotoImage(im);self.photos.append(photo)
                button=ttk.Button(self.thumbs,text=text,image=photo,compound='top',command=lambda i=index:self.select(i))
            except (ValueError,OSError):
                button=ttk.Button(self.thumbs,text=text+'\nPrévia indisponível',command=lambda i=index:self.select(i))
            button.pack(fill='x',padx=3,pady=4);self.buttons.append(button)
        self.viewer.load(doc)
        if self.items:self.select(0)
        self.info.set(f'{group} · {len(self.items)} páginas preservadas. Clique nas miniaturas e confira tipo, identificação e origem.')
    def select(self,index):
        if not 0<=index<len(self.items):return
        self.viewer.index=index;self.viewer.box=None;self.viewer.render()
    def opened(self,index):
        if not 0<=index<len(self.items):return
        self.selected_id=self.items[index]['id'];self.seen_ids.add(self.selected_id)
        item=self.items[index]
        self.info.set(f'{item["group"]} · Página original {item["page"]} · Tipo: {item["kind"]}. Use Corrigir página / agrupamento para alterar.')
