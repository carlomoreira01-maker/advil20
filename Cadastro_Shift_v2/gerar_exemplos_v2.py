"""Gera apenas documentos sintéticos para testar a versão 2."""
import io
from pathlib import Path
import pymupdf
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'exemplos_v2'
BASE='''Paciente: Pessoa Sintetica Alfa
Nascimento: 01/02/1995
Fonte pagadora: Convenio Ficticio
Operadora: Operadora Sintetica
Guia: TESTE-001
Medico: Dra. Exemplo
Validade: 31/12/2099
Status: AUTORIZADO
'''

def text_pdf(path,text):
    d=pymupdf.open();p=d.new_page();p.insert_text((35,40),text,fontsize=12);d.save(path);d.close()
def scan(text):
    im=Image.new('RGB',(1900,1500),'white');draw=ImageDraw.Draw(im)
    font=None
    for name in ['DejaVuSans.ttf','arial.ttf']:
        try:font=ImageFont.truetype(name,34);break
        except OSError:pass
    font=font or ImageFont.load_default(size=34)
    draw.multiline_text((65,55),text,fill='black',font=font,spacing=18);return im

def main():
    OUT.mkdir(exist_ok=True)
    text=BASE+'Exames:\nHemograma | 1 | DEMO-HEM\nGlicose | 2 | DEMO-GLI\n'
    text_pdf(OUT/'01_pedido_digital.pdf',text)
    im=scan(text);im.save(OUT/'01_guia.png');im.save(OUT/'01_guia.jpg',quality=94)
    stream=io.BytesIO();im.save(stream,format='PNG');d=pymupdf.open();p=d.new_page(width=760,height=600);p.insert_image(p.rect,stream=stream.getvalue());d.save(OUT/'01_guia_escaneada.pdf');d.close()
    tablebase=BASE.replace('Pessoa Sintetica Alfa','Pessoa Sintetica Beta').replace('TESTE-001','TESTE-002')
    for filename,quantity in [('02_pedido_tabela.pdf','2'),('02_guia_divergente.pdf','4')]:
        d=pymupdf.open();p=d.new_page();p.insert_text((35,40),tablebase,fontsize=11)
        for x,t in [(35,'Codigo'),(165,'Descricao'),(370,'Qtd')]:p.insert_text((x,195),t,fontsize=11)
        for y,row in [(220,['DEMO-HEM','Hemograma','1']),(250,['DEMO-GLI','Glicose',quantity])]:
            for x,t in zip([35,165,370],row):p.insert_text((x,y),t,fontsize=11)
        d.save(OUT/filename);d.close()
    d=pymupdf.open(OUT/'01_pedido_digital.pdf');p=d.new_page();p.insert_text((35,40),'Exames:\nTSH | 1 | DEMO-TSH',fontsize=12);d.save(OUT/'03_pedido_multipagina.pdf');d.close()
    Image.new('RGB',(1000,1000),'white').save(OUT/'04_ilegivel.png')
    text_pdf(OUT/'05_guia_outro_paciente.pdf',text.replace('Pessoa Sintetica Alfa','Pessoa Sintetica Gama'))
    (OUT/'lote.csv').write_text('pedido;guia\n01_pedido_digital.pdf;01_guia_escaneada.pdf\n02_pedido_tabela.pdf;02_guia_divergente.pdf\n',encoding='utf-8')
if __name__=='__main__':main()
