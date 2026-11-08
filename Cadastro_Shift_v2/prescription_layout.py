"""Sinais de pedido impresso/carimbado, sem depender de título ou catálogo interno."""
import re
from core import norm
from tiss_geometry import rows,words_of

# Apenas evidência lexical: nunca fornece código, quantidade ou substitui descrição.
TERMS=('HEMOGRAMA','GLICOSE','GLICEMIA','TSH','T4 LIVRE','CREATININA','UREIA',
       'COLESTEROL','TRIGLICERIDES','TRIGLICERIDEOS','FERRITINA','VITAMINA B12',
       'VITAMINA D','HEMOGLOBINA GLICADA','EAS','URINA TIPO 1','UROCULTURA')
STAMP=re.compile(r'\b(?:CRM|CRO|COREN|CRBM|CRF)\s*[:/-]?\s*(?:[A-Z]{2}\s*[:/-]?\s*)?\d(?:[\d .]*\d)?\b')


def evidence(page,catalog=()):
    lines=page.get('lines',[]);text=norm(page.get('text',''))
    terms=set(TERMS)|{norm(s) for r in catalog for s in [r['nome'],*r.get('sinonimos',[])]}
    stamp=[l for l in lines if STAMP.search(norm(l['text']))]
    stop=min((l['box'][1] for l in lines if re.match(r'^(?:DR[.]?|DRA[.]?|ASSINATURA|CARIMBO)\s',norm(l['text']))),default=float('inf'))
    stop=min(stop,min((l['box'][1] for l in stamp),default=float('inf')))
    exam_lines=[];recognized=set();numbered=0
    for line in lines:
        n=norm(line['text'])
        if line['box'][1]>=stop:continue
        if re.match(r'^(?:PACIENTE|NOME|NASCIMENTO|CARTEIRA|MATRICULA|CPF|CNS|MEDICO|CONVENIO|OPERADORA|ENDERECO|TELEFONE)\b',n):continue
        numbered_row=bool(re.match(r'^\s*(?:[-•]|\d{1,2}[.)])\s*[A-Z]',n))
        named={t for t in terms if re.search(r'\b'+re.escape(t)+r'\b',n)}
        if not numbered_row and not named:continue
        if not re.search(r'[A-Z]',n):continue
        if re.match(r'^(?:SOLICITO|EXAMES|PROCEDIMENTOS|REQUISICAO)\s*:?$',n):continue
        exam_lines.append(line);recognized.update(named);numbered+=numbered_row
    patient=bool(re.search(r'\b(?:PACIENTE|NOME DO PACIENTE)\s*[:=-]?\s+[A-Z]',text))
    intention=bool(re.search(r'\b(?:SOLICITO|REQUISITO|EXAMES|REQUISICAO)\b',text))
    excluded=bool(re.search(r'\b(?:ATESTADO|RECEITUARIO|RECEITA MEDICA|LAUDO|TERMO DE CONSENTIMENTO|RESULTADOS? DE EXAMES?)\b',text))
    supported=patient and bool(stamp) and not excluded and (len(recognized)>=2 or (intention and numbered>=2))
    return {'supported':supported,'exam_lines':exam_lines,'stamp_lines':stamp,
            'recognized_terms':len(recognized),'reason':'Paciente, lista de exames e identificação profissional legível em carimbo; sem estrutura de guia de autorização.'}


def doctor_name(value):
    return re.sub(r'^DR(?:A)?[.]?\s+','',norm(value)).strip()


def stamped_names(page):
    lines=page.get('lines',[]);stamps=[l for l in lines if STAMP.search(norm(l['text']))];found=[]
    for stamp in stamps:
        candidates=[]
        for line in lines:
            n=norm(line['text']);h=max(3,line['box'][3]-line['box'][1])
            if not re.match(r'^DR(?:A)?[.]?\s+[A-Z]',n):continue
            if not 0<=stamp['box'][1]-line['box'][1]<=h*5:continue
            if abs(line['box'][0]-stamp['box'][0])>h*5:continue
            value=re.sub(r'^DR(A)?[.]?\s+',lambda m:'DRA ' if m[1] else 'DR ',n)
            if len(doctor_name(value).split())<2 or re.search(r'\d',value):continue
            candidates.append((stamp['box'][1]-line['box'][1],value,line))
        if candidates:found.append(min(candidates,key=lambda c:c[0])[1:])
    return found
