"""Regressões 2.4.2: exclusivamente pessoas, códigos e documentos fictícios."""
from pathlib import Path
import pymupdf
from gerar_exemplos_tiss import make_guide,make_order,VALUES
from gerar_exemplos_2_4 import combine,raster


def main(out=None):
    out=Path(out) if out else Path(__file__).resolve().parent/'exemplos_2_4_2';out.mkdir(exist_ok=True)
    make_order(out/'pedido_ficticio.pdf');make_guide(out/'guia_continuacao_original.pdf',multipage=True)
    with pymupdf.open(out/'guia_continuacao_original.pdf') as pdf:
        n=list(VALUES).index(10);x=[35,390,745][n%3];y=105+(n//3)*58+23
        pdf[0].add_redact_annot(pymupdf.Rect(x-1,y-17,x+320,y+5));pdf[0].apply_redactions()
        pdf[0].insert_text((x,y),'PESSOA FICTICIA',fontsize=14)
        pdf[1].insert_text((35,30),'CONTINUACAO DA GUIA - DOCUMENTO FICTICIO',fontsize=12)
        pdf.save(out/'guia_e_continuacao.pdf',deflate=True)
    extra=pymupdf.open();p=extra.new_page(width=850,height=700)
    p.insert_text((40,50),'DOCUMENTO COMPLEMENTAR FICTICIO\nPaciente: PESSOA\nAnexo administrativo sem identificadores adicionais.\nSomente para teste local.',fontsize=15)
    extra.save(out/'complementar_ficticio.pdf');extra.close()
    combine(out/'01_um_atendimento_quatro_paginas.pdf',[out/'pedido_ficticio.pdf',out/'guia_e_continuacao.pdf',out/'complementar_ficticio.pdf'])
    make_guide(out/'guia_outro_paciente.pdf',other=True)
    combine(out/'02_identificadores_incompativeis.pdf',[out/'pedido_ficticio.pdf',out/'guia_outro_paciente.pdf'])
    raster(out/'01_um_atendimento_quatro_paginas.pdf',out/'03_quatro_paginas_escaneadas.pdf',90)
    for filename,wide,neighbor in [('04_nome_espacado.pdf',True,False),('05_coluna_vizinha.pdf',False,True)]:
        pdf=pymupdf.open();p=pdf.new_page(width=1000,height=350)
        for x,y,text in [(30,40,'10 - Nome do beneficiario'),(30,120,'15 - Nome do profissional solicitante'),(30,145,'MEDICO FICTICIO')]:p.insert_text((x,y),text,fontsize=12)
        if wide:
            p.insert_text((30,65),'PRIMEIRO',fontsize=12);p.insert_text((220,65),'SEGUNDO TERCEIRO',fontsize=12)
        else:
            p.insert_text((30,65),'PRIMEIRO SEGUNDO TERCEIRO',fontsize=12)
            p.insert_text((600,65),'CONTROLE 999999',fontsize=9)
        pdf.save(out/filename);pdf.close()
    (out/'LEIA-ME.txt').write_text('TODOS OS DADOS SAO FICTICIOS. O primeiro PDF tem pedido, guia com nome parcial, continuacao sem identidade e documento complementar. Importe no modo Um atendimento - varias paginas: deve aparecer uma ficha provisoria com quatro miniaturas. O segundo PDF contem conflito proposital e NAO pode ter agrupamento confirmado. Nenhum codigo representa cadastro Shift real.\n',encoding='utf-8')
    return out

if __name__=='__main__':main()
