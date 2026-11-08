"""Classificação por página; estrutura TISS não equivale a autorização concedida."""
import re
from core import norm
from tiss_geometry import anchors


def classify_page(page):
    text=norm(page.get('text',''))
    aa=anchors(page);numbers={a['num'] for a in aa}
    request=bool(re.search(r'\b(?:PEDIDO MEDICO|SOLICITACAO DE EXAMES|REQUISICAO DE EXAMES)\b',text))
    guide=bool(re.search(r'\b(?:GUIA DE AUTORIZACAO|GUIA AUTORIZADA|GUIA (?:DE )?(?:SP\s*/\s*SADT|SP-SADT))\b',text))
    long_title=bool(re.search(r'GUIA DE SERVICO PROFISSIONAL',text) and re.search(r'SERVICO AUXILIAR DE DIAGNOSTICO',text))
    administration=bool(re.search(r'\b(?:RECIBO|COMPROVANTE|RESULTADO DE EXAME|DOCUMENTO COMPLEMENTAR)\b',text))
    beneficiary=bool(numbers & {8,9,10})
    requester=bool(numbers & {13,15,16,17,18})
    procedures={25,26}<=numbers and any(abs(a['y']-b['y'])<max(8,a['height']) for a in aa if a['num']==25 for b in aa if b['num']==26)
    authorization=bool(numbers & {2,3,4,5,6,7})
    partial_structure={8,10,15}<=numbers
    structure=(beneficiary and requester and (authorization or procedures) and len(numbers)>=5) or partial_structure
    evidence=[]
    if request:evidence.append('Título explícito de pedido médico.')
    if guide or long_title:evidence.append('Título de guia SP/SADT/autorização.')
    if structure:evidence.append('Conjunto coerente de células TISS de carteira, beneficiário e solicitante/guia/procedimentos.')
    if procedures:evidence.append('Colunas de código e descrição alinhadas.')
    if re.search(r'\b(?:REGISTRO )?ANS\b',text):evidence.append('Rótulo ANS presente.')
    if request and (guide or long_title):kind='incerto'
    elif request:kind='pedido'
    elif guide or long_title or structure:kind='guia'
    elif procedures and re.search(r'PROCEDIMENTOS (?:SOLICITADOS|AUTORIZADOS)',text):kind='continuação de guia'
    elif administration:kind='outro'
    else:
        # Sem título, exige vários sinais. Nome/palavra EXAME isolados não bastam.
        patient=bool(re.search(r'\b(?:PACIENTE|NOME DO PACIENTE)\s*[:=-]',text))
        doctor=bool(re.search(r'\b(?:MEDICO|SOLICITANTE|CRM)\b',text))
        intention=bool(re.search(r'\b(?:SOLICITO|REQUISITO|SOLICITACAO|REQUISICAO)\b',text))
        listing=bool(re.search(r'\b(?:EXAMES|PROCEDIMENTOS)\b',text))
        kind='pedido' if patient and doctor and intention and listing else 'incerto'
        if kind=='pedido':evidence.append('Paciente, solicitante, intenção de solicitação e lista de exames.')
    if re.search(r'\bCONTINUA(?:CAO)?\b',text) and kind in ['pedido','guia']:kind='continuação de '+kind
    return {'kind':kind,'uncertain':kind=='incerto','evidence':evidence,
            'reason':' '.join(evidence) if evidence else 'Classificação incerta: confira o tipo desta página no original.'}


def document_type(document):
    kinds={classify_page(p)['kind'].replace('continuação de ','') for p in document['pages']}
    return next(iter(kinds)) if len(kinds)==1 and kinds<={'pedido','guia'} else 'Não identificado'
