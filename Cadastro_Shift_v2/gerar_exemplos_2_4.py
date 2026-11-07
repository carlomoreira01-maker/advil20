"""Documentos sintéticos para importação única e células densas; nenhum dado real."""
from pathlib import Path
import io
import pymupdf
from PIL import Image
from gerar_exemplos_tiss import make_order,make_guide,VALUES,CODES,NAMES,LABELS


def dense_guide(path,blank=False,zero=False,missing=False):
 d=pymupdf.open();p=d.new_page(width=825,height=578)
 p.insert_text((35,18),'GUIA SP/SADT - IPASGO - DOCUMENTO INTEIRAMENTE FICTICIO',fontsize=8)
 def field(n,x,y,right,value=None,inline=False):
  label=str(n)+' - '+LABELS.get(n,{11:'Cartao Nacional de Saude',14:'Nome do contratado',19:'Codigo CBO'}[n] if n in [11,14,19] else '')
  p.insert_text((x,y),label,fontsize=5)
  if value is None:value=VALUES.get(n,'')
  if value:
   vx=x+pymupdf.get_text_length(label,fontsize=5)+4 if inline else x
   p.insert_text((vx,y if inline else y+9),value,fontsize=7)
 field(2,560,30,815,inline=True);field(3,35,43,815)
 for n,x,right in [(4,35,145),(5,145,300),(6,300,430),(7,430,815)]:field(n,x,65,right,'' if blank else None)
 for n,x,right in [(8,35,230),(9,230,325),(10,325,575),(11,575,815)]:field(n,x,98,right)
 field(13,35,130,230);field(14,230,130,815,'LABORATORIO FICTICIO')
 for n,x,right in [(15,35,155),(16,310,415),(17,415,545),(18,545,590),(19,590,815)]:field(n,x,155,right,'225125' if n==19 else None)
 field(22,145,185,815)
 p.insert_text((35,210),'PROCEDIMENTOS SOLICITADOS',fontsize=6)
 for x,text in [(70,'25 - Codigo do procedimento'),(190,'26 - Descricao'),(690,'27 - Qt solicitada'),(750,'28 - Qt autorizada')]:p.insert_text((x,223),text,fontsize=5)
 for i,(code,name) in enumerate(zip(CODES,NAMES)):
  if missing and i==4:continue
  for x,text in [(80,code),(190,name),(725,'1'),(785,'' if blank else '0' if zero and i==0 else '1')]:
   if text:p.insert_text((x,238+i*13),text,fontsize=7)
 p.insert_text((35,350),'PROCEDIMENTOS EXECUTADOS',fontsize=6)
 for x,text in [(70,'40 - Codigo'),(190,'41 - Descricao'),(690,'42 - Quantidade')]:p.insert_text((x,365),text,fontsize=5)
 for i,(code,name) in enumerate(zip(CODES,NAMES)):
  for x,text in [(80,code),(190,name),(725,'1')]:p.insert_text((x,380+i*13),text,fontsize=7)
 p.insert_text((35,520),'Nascimento: 01/02/1995    Fonte pagadora: IPASGO    Regime atendimento: AMBULATORIAL',fontsize=8)
 d.save(path,deflate=True);d.close()


def combine(path,files):
 out=pymupdf.open()
 for file in files:
  with pymupdf.open(file) as part:out.insert_pdf(part)
 out.save(path,deflate=True);out.close()


def raster(source,dest,angle=0):
 with pymupdf.open(source) as pdf:
  out=pymupdf.open()
  for page in pdf:
   im=Image.open(io.BytesIO(page.get_pixmap(matrix=pymupdf.Matrix(3,3)).tobytes('png'))).rotate(angle,expand=True)
   buf=io.BytesIO();im.save(buf,format='PNG');p=out.new_page(width=im.width/3,height=im.height/3);p.insert_image(p.rect,stream=buf.getvalue())
  out.save(dest,deflate=True);out.close()


def main(out=None):
 out=Path(out) if out else Path(__file__).resolve().parent/'exemplos_2_4';out.mkdir(exist_ok=True)
 make_order(out/'pedido_alfa.pdf');make_order(out/'pedido_beta.pdf',other=True)
 make_guide(out/'guia_alfa.pdf');make_guide(out/'guia_beta.pdf',other=True)
 dense_guide(out/'guia_densa.pdf');dense_guide(out/'guia_sem_autorizacao.pdf',blank=True)
 dense_guide(out/'guia_zero.pdf',zero=True);dense_guide(out/'guia_exame_ausente.pdf',missing=True)
 raster(out/'guia_densa.pdf',out/'guia_90_escaneada.pdf',90)
 combine(out/'01_pedido_e_guia.pdf',[out/'pedido_alfa.pdf',out/'guia_densa.pdf'])
 combine(out/'02_guia_antes_pedido.pdf',[out/'guia_densa.pdf',out/'pedido_alfa.pdf'])
 combine(out/'03_quatro_paginas_misturadas.pdf',[out/'guia_beta.pdf',out/'pedido_alfa.pdf',out/'guia_alfa.pdf',out/'pedido_beta.pdf'])
 combine(out/'04_guia_girada_e_pedido.pdf',[out/'guia_90_escaneada.pdf',out/'pedido_alfa.pdf'])
 (out/'LEIA-ME.txt').write_text('TODOS os dados sao ficticios. Códigos 90000001 a 90000005 são identificadores sintéticos, não códigos oficiais. Catálogo e perfil de teste em exemplos_tiss são apenas para demonstração. Não importar na produção.\n',encoding='utf-8')
 return out

if __name__=='__main__':main()
