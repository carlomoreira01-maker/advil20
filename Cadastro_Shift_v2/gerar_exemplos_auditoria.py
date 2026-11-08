"""Gabaritos e PDFs exclusivamente fictícios para auditoria 2.4.4."""
from pathlib import Path
import json,pymupdf
from gerar_exemplos_tiss import make_guide,VALUES,NAMES,CODES
from gerar_exemplos_2_4 import combine,raster

PATIENT='PESSOA FICTICIA DE OLIVEIRA DOS SANTOS'

def order(path,structured=False):
    pdf=pymupdf.open();p=pdf.new_page(width=1100,height=1100)
    lines=['PEDIDO MEDICO - DOCUMENTO FICTICIO','Paciente: '+PATIENT,'Nascimento: 01/02/1995','Carteira: 0000087654','Medico: DRA EXEMPLO SINTETICA','Conselho: CRM','Numero conselho: 0012345','UF conselho: GO','Exames:']
    lines += [f'{name} | 1 | {code}' for name,code in zip(NAMES,CODES)]
    p.insert_text((35,50),'\n'.join(lines),fontsize=14)
    if structured:
        p.insert_text((35,470),'10 - Nome do beneficiario',fontsize=10);p.insert_text((35,492),PATIENT,fontsize=12)
        p.insert_text((35,540),'15 - Nome do profissional solicitante',fontsize=10);p.insert_text((35,562),'DRA EXEMPLO SINTETICA',fontsize=12)
    pdf.save(path,deflate=True);pdf.close()


def guide(path,crm='0012345',split=False,wrap=False,uf='GO',blank=False,zero=False,multipage=False,other=False,stamp=''):
    original=path.with_name(path.stem+'_base.pdf');make_guide(original,blank=blank,zero=zero,multipage=multipage,other=other)
    with pymupdf.open(original) as pdf:
        p=pdf[0]
        for rect in [(30,15,1090,35),(742,225,1095,250),(30,320,380,387),(388,345,740,385)]:p.add_redact_annot(pymupdf.Rect(rect))
        if blank:p.add_redact_annot(pymupdf.Rect(388,110,740,145))
        p.apply_redactions()
        p.insert_text((35,29),'GUIA DE SERVICO PROFISSIONAL / SERVICO AUXILIAR DE DIAGNOSTICO E TERAPIA',fontsize=11)
        p.insert_text((745,244),'PESSOA FICTICIA BETA' if other else PATIENT,fontsize=10)
        p.insert_text((35,337),'17 - Numero no' if wrap else '17 - Numero no conselho',fontsize=10)
        if wrap:p.insert_text((35,350),'conselho',fontsize=10)
        if crm:p.insert_text((35,375 if wrap else 360),' '.join(crm) if split else crm,fontsize=12)
        if uf:p.insert_text((390,360),uf,fontsize=14)
        p.insert_text((745,395),'19 - Codigo CBO',fontsize=10);p.insert_text((745,418),'225125',fontsize=12)
        if stamp:p.insert_text((35,1050),stamp,fontsize=14)
        if multipage:pdf[1].insert_text((35,30),'CONTINUACAO DA GUIA - DOCUMENTO FICTICIO',fontsize=12)
        pdf.save(path,deflate=True)
    original.unlink()


def main(out=None):
    out=Path(out) if out else Path(__file__).resolve().parent/'exemplos_auditoria';out.mkdir(parents=True,exist_ok=True)
    order(out/'pedido.pdf');guide(out/'guia.pdf',wrap=True,split=True);guide(out/'guia_continuacao.pdf',multipage=True,wrap=True,split=True)
    pdf=pymupdf.open();p=pdf.new_page();p.insert_text((35,50),'DOCUMENTO COMPLEMENTAR FICTICIO\nPaciente: PESSOA\nAnexo administrativo sem identificadores adicionais.',fontsize=14);pdf.save(out/'complementar.pdf');pdf.close()
    combine(out/'01_quatro_paginas.pdf',[out/'pedido.pdf',out/'guia_continuacao.pdf',out/'complementar.pdf'])
    combine(out/'02_ordem_invertida.pdf',[out/'guia.pdf',out/'pedido.pdf'])
    combine(out/'03_nome_composto.pdf',[out/'pedido.pdf',out/'guia.pdf'])
    guide(out/'04_crm_go.pdf',split=True,wrap=True)
    guide(out/'05_guia_incompleta.pdf',blank=True)
    combine(out/'14_nao_aplicavel.pdf',[out/'pedido.pdf',out/'05_guia_incompleta.pdf'])
    guide(out/'guia_zero.pdf',zero=True);combine(out/'06_quantidades.pdf',[out/'pedido.pdf',out/'guia_zero.pdf'])
    guide(out/'guia_ilegivel.pdf',crm='ILEGIVEL');combine(out/'07_conferencia.pdf',[out/'pedido.pdf',out/'guia_ilegivel.pdf'])
    guide(out/'guia_outro.pdf',other=True);combine(out/'08_conflito.pdf',[out/'pedido.pdf',out/'guia_outro.pdf'])
    pdf=pymupdf.open();p=pdf.new_page();p.insert_text((35,45),'DOCUMENTO FICTICIO SEM TIPO\nPaciente: PESSOA FICTICIA ALFA\nInformacao administrativa sobre exame.',fontsize=14);pdf.save(out/'09_incerto.pdf');pdf.close()
    order(out/'10_pedido_estruturado.pdf',structured=True)
    for i,crm in enumerate(['12','00123','0012345','0001234567'],1):guide(out/f'crm_tamanho_{i}.pdf',crm=crm,split=i%2==0,wrap=True)
    guide(out/'11_sem_uf.pdf',uf='');guide(out/'12_carimbo_divergente.pdf',stamp='CRM/GO 0099999 - CARIMBO FICTICIO')
    raster(out/'04_crm_go.pdf',out/'13_guia_girada.pdf',90)
    (out/'GABARITO.json').write_text(json.dumps({'somente_dados_ficticios':True,'paciente':PATIENT,'campos':{**{str(k):v for k,v in VALUES.items()},'10':PATIENT,'19':'225125'},'tipos_quatro_paginas':['pedido','guia','continuação de guia','outro'],'crm_tamanhos':['12','00123','0012345','0001234567'],'exames':[{'codigo':c,'descricao':n,'solicitada':'1','autorizada':'1'} for c,n in zip(CODES,NAMES)]},ensure_ascii=False,indent=2)+'\n')
    (out/'LEIA-ME.txt').write_text('TODOS OS NOMES, NUMEROS, CODIGOS E DOCUMENTOS SAO FICTICIOS.\nUse 01_quatro_paginas.pdf no modo Um atendimento - varias paginas. O PDF 08_conflito.pdf deve bloquear a confirmacao. O caso 07_conferencia.pdf exige corrigir o CRM ilegiveI no original ficticio para 0012345, salvar e conferir. O catalogo/perfil ficticio dos testes nao deve ser usado em producao.\n',encoding='utf-8')
    return out

if __name__=='__main__':main()
