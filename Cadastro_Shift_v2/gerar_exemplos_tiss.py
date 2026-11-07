"""Fixtures inteiramente fictícias; códigos de teste não representam cadastro Shift real."""
from pathlib import Path
import json,io
import pymupdf
from PIL import Image

VALUES={2:'00000111',3:'00000222',4:'07/11/2026',5:'00000555',6:'31/12/2099',7:'00000777',8:'0000087654',9:'31/12/2099',10:'PESSOA FICTICIA ALFA',13:'000001313',15:'DRA EXEMPLO SINTETICA',16:'CRM',17:'0012345',18:'GO',22:'07/11/2026'}
LABELS={2:'Numero da guia no prestador',3:'Numero da guia principal',4:'Data da autorizacao',5:'Senha de autorizacao',6:'Validade da senha',7:'Numero da guia atribuido pela operadora',8:'Numero da carteira',9:'Validade da carteira',10:'Nome do beneficiario',13:'Codigo do contratado solicitante',15:'Nome do profissional solicitante',16:'Conselho profissional',17:'Numero do conselho',18:'UF',22:'Data da solicitacao'}
NAMES=['Hemograma','Glicose','TSH','Creatinina','Colesterol total']
CODES=['90000001','90000002','90000003','90000004','90000005']


def make_guide(path,blank=False,zero=False,repeated=False,multipage=False,other=False,crm_bad=False,variant='IPASGO',unknown=False,material=False):
 values=dict(VALUES)
 if blank:
  for k in [4,5,6,7]:values[k]=''
 if other:values[10]='PESSOA FICTICIA BETA';values[8]='0000099999'
 if crm_bad:values[17]='ILEGIVEL'
 d=pymupdf.open();p=d.new_page(width=1100,height=1100)
 p.insert_text((35,30),'GUIA SP/SADT - '+variant+' - DOCUMENTO FICTICIO',fontsize=13)
 p.insert_text((35,50),'Nascimento: 01/02/1995   Fonte pagadora: '+variant+'   Regime atendimento: AMBULATORIAL',fontsize=12)
 p.insert_text((35,70),'Etiqueta de controle: 0000999988',fontsize=11)
 for i,n in enumerate(values):
  x=[35,390,745][i%3];y=105+(i//3)*58
  p.insert_text((x,y),str(n)+' - '+LABELS[n],fontsize=10)
  if values[n]:p.insert_text((x,y+23),values[n],fontsize=14)
 def table(page,y,section,indices):
  page.insert_text((35,y),'PROCEDIMENTOS '+section,fontsize=13)
  for x,label in [(35,'25 - Codigo'),(225,'26 - Descricao'),(680,'27 - Qtd solicitada'),(855,'28 - Qtd autorizada')]+([(1000,'Material')] if material else []):page.insert_text((x,y+25),label,fontsize=11)
  for j,i in enumerate(indices):
   for x,text in [(35,'90009999' if unknown and i==0 else CODES[i]),(225,'Exame ficticio desconhecido' if unknown and i==0 else NAMES[i]),(680,'1'),(855,'' if blank else '0' if zero and i==0 else '1')]+([(1000,'EDTA' if i==0 else 'Soro')] if material else []):
    if text:page.insert_text((x,y+55+j*29),text,fontsize=13)
 table(p,450,'SOLICITADOS',range(3 if multipage else 5))
 if multipage:
  p=d.new_page(width=1100,height=1100);table(p,60,'SOLICITADOS',range(3,5))
 if repeated:table(p,725,'EXECUTADOS',range(5))
 d.save(path,deflate=True);d.close()
 return values


def make_order(path,other=False):
 d=pymupdf.open();p=d.new_page(width=850,height=700)
 text='PEDIDO MEDICO\nPaciente: '+('PESSOA FICTICIA BETA' if other else 'PESSOA FICTICIA ALFA')+'\nNascimento: 01/02/1995\nCarteira: 0000087654\nMedico: DRA EXEMPLO SINTETICA\nConselho: CRM\nNumero conselho: 0012345\nUF conselho: GO\nExames:\n'
 text+='\n'.join(f'{name} | 1 | {code}' for name,code in zip(NAMES,CODES))
 if other:text=text.replace('Carteira: 0000087654','Carteira: 0000099999')
 p.insert_text((40,50),text,fontsize=16);d.save(path);d.close()


def catalog():
 return [{'nome':name,'codigo_shift':'','tuss':code,'sinonimos':[],'material':'','fixture':True} for name,code in zip(NAMES,CODES)]


def main(out=None):
 out=Path(out) if out else Path(__file__).resolve().parent/'exemplos_tiss';out.mkdir(exist_ok=True)
 cases=[('01_completa',{}),('02_sem_autorizacao',{'blank':True}),('03_autorizada_zero',{'zero':True}),('04_duas_tabelas',{'repeated':True}),('06_multipagina',{'multipage':True}),('07_outro_paciente',{'other':True}),('10_crm_ilegivel',{'crm_bad':True}),('11_unimed',{'variant':'UNIMED'}),('09_exame_desconhecido',{'unknown':True}),('12_material',{'material':True})]
 for name,opts in cases:make_guide(out/(name+'.pdf'),**opts)
 make_order(out/'05_pedido.pdf')
 with pymupdf.open(out/'05_pedido.pdf') as d:
  im=Image.open(io.BytesIO(d[0].get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png')))
  for angle in [0,90,180,270]:im.rotate(angle,expand=True).save(out/f'05_pedido_{angle}.png')
  im.rotate(2,expand=True,fillcolor='white').save(out/'05_pedido_inclinado.png')
 with pymupdf.open(out/'01_completa.pdf') as d:
  im=Image.open(io.BytesIO(d[0].get_pixmap(matrix=pymupdf.Matrix(2,2)).tobytes('png')));im.save(out/'01_completa.png')
  buf=io.BytesIO();im.save(buf,format='PNG');pdf=pymupdf.open();p=pdf.new_page(width=1100,height=1100);p.insert_image(p.rect,stream=buf.getvalue());pdf.save(out/'01_escaneada.pdf',deflate=True);pdf.close()
 (out/'catalogo_ficticio.json').write_text(json.dumps(catalog(),ensure_ascii=False,indent=2)+'\n')
 (out/'esperado_campos.json').write_text(json.dumps(VALUES,ensure_ascii=False,indent=2)+'\n')
 (out/'LEIA-ME.txt').write_text('TODOS OS DADOS E CODIGOS SAO FICTICIOS. Nao sao codigos internos do Shift nem regras homologadas de operadoras. Importe o catalogo ficticio apenas para conferir estes exemplos. Quantidade zero/ausente nao constitui autorizacao.\n')
 return out

if __name__=='__main__':main()
