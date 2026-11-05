"""Documentos exclusivamente fictícios para demonstrar a correção, sem rede."""
from pathlib import Path
import io
import pymupdf
from gerar_exemplos_v2 import BASE, scan, text_pdf


def main():
    out=Path(__file__).resolve().parent/'exemplos_correcao';out.mkdir(exist_ok=True)
    body=BASE+'Exames:\nHemograma | 1 | DEMO-HEM\nGlicose | 2 | DEMO-GLI\n'
    text_pdf(out/'01_pedido_digital.pdf','PEDIDO MEDICO\n'+body.replace(': ','  '))
    image=scan('GUIA DE AUTORIZACAO\n'+body)
    image.save(out/'02_guia_escaneada.png');image.save(out/'02_guia_escaneada.jpg')
    stream=io.BytesIO();image.save(stream,format='PNG')
    doc=pymupdf.open();page=doc.new_page(width=760,height=600)
    page.insert_image(page.rect,stream=stream.getvalue())
    doc.save(out/'02_guia_escaneada.pdf',deflate=True);doc.close()
    text_pdf(out/'03_guia_divergente.pdf','GUIA DE AUTORIZACAO\n'+body.replace('Glicose | 2','Glicose | 4'))
    (out/'LEIA-ME.txt').write_text('Dados inteiramente fictícios.\nImporte 01_pedido_digital.pdf e 02_guia_escaneada.png (ou JPG/PDF).\nOs campos devem aparecer após a leitura. Compare com 03_guia_divergente.pdf para verificar o bloqueio de quantidade divergente.\nNenhuma preparação dispensa conferência humana.\n',encoding='utf-8')

if __name__=='__main__':main()
