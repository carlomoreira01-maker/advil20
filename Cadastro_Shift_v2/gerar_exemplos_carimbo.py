"""Pedidos impressos e carimbos azuis fictícios, sem dados de pessoas reais."""
from pathlib import Path
import json,pymupdf
from gerar_exemplos_tiss import make_guide,NAMES
from gerar_exemplos_2_4 import combine,raster


def order(path,stamp=True,heading='',quantities=True):
    pdf=pymupdf.open();p=pdf.new_page(width=650,height=850)
    lines=[(35,45,heading or 'CLINICA FICTICIA - SOMENTE TESTE'),(35,105,'Paciente PESSOA FICTICIA ALFA'),(35,135,'Nascimento 01/02/1995'),(35,165,'Carteira 0000087654')]
    lines += [(50,240+i*35,f'{i+1}. {name}'+(' Qtd: 1' if quantities else '')) for i,name in enumerate(NAMES)]
    if stamp:lines += [(300,640,'Dra. EXEMPLO SINTETICA'),(300,665,'CRM-GO 0012345')]
    for x,y,t in lines:p.insert_text((x,y),t,fontsize=14,color=(0,0,.45) if y>600 else (0,0,0))
    pdf.save(path,deflate=True);pdf.close()


def main(out=None):
    out=Path(out) if out else Path(__file__).resolve().parent/'exemplos_carimbo';out.mkdir(parents=True,exist_ok=True)
    order(out/'pedido_carimbo.pdf');order(out/'pedido_sem_carimbo.pdf',stamp=False);order(out/'consentimento_carimbo.pdf',heading='TERMO DE CONSENTIMENTO FICTICIO');order(out/'receita_carimbo.pdf',heading='RECEITA MEDICA FICTICIA');order(out/'pedido_sem_quantidades.pdf',quantities=False)
    make_guide(out/'guia.pdf');make_guide(out/'guia_zero.pdf',zero=True);make_guide(out/'guia_continuacao.pdf',multipage=True)
    with pymupdf.open(out/'guia.pdf') as pdf:
        pdf[0].insert_text((35,1040),'Dra. EXEMPLO SINTETICA\nCRM-GO 0012345',fontsize=12);pdf.save(out/'guia_com_carimbo.pdf',deflate=True)
    extra=pymupdf.open();p=extra.new_page();p.insert_text((35,50),'DOCUMENTO COMPLEMENTAR FICTICIO\nPaciente PESSOA\nAnexo administrativo para teste.',fontsize=14);extra.save(out/'complementar.pdf');extra.close()
    combine(out/'01_pedido_carimbo_e_guia.pdf',[out/'pedido_carimbo.pdf',out/'guia.pdf'])
    combine(out/'02_guia_antes_pedido.pdf',[out/'guia_com_carimbo.pdf',out/'pedido_carimbo.pdf'])
    combine(out/'03_quatro_paginas.pdf',[out/'pedido_carimbo.pdf',out/'guia_continuacao.pdf',out/'complementar.pdf'])
    combine(out/'04_autorizada_zero.pdf',[out/'pedido_carimbo.pdf',out/'guia_zero.pdf'])
    raster(out/'pedido_carimbo.pdf',out/'05_pedido_girado.pdf',90)
    (out/'GABARITO.json').write_text(json.dumps({'somente_ficticios':True,'paciente':'PESSOA FICTICIA ALFA','medico':'DRA EXEMPLO SINTETICA','conselho':'CRM','numero':'0012345','uf':'GO','exames':NAMES,'quantidade':'1','quantidade_ausente':'','tipos_duas_paginas':['pedido','guia'],'tipos_quatro_paginas':['pedido','guia','continuação de guia','outro']},ensure_ascii=False,indent=2)+'\n')
    (out/'LEIA-ME.txt').write_text('SOMENTE DADOS FICTICIOS. 01 contem pedido sem titulo, com carimbo, e guia. 03 contem quatro paginas do mesmo paciente ficticio. 04 tem autorizacao zero e deve bloquear o preparo. 05 e pedido escaneado girado. Consentimento/receita com CRM nao devem virar pedido so por conter carimbo. Nenhum codigo interno do Shift e fornecido por estes documentos.\n')
    return out

if __name__=='__main__':main()
