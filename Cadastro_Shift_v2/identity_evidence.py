"""Evidências locais de identidade; nomes parciais não equivalem a confirmação."""
import re
from datetime import datetime,date
from core import norm

IDENTIFIERS=('Nascimento','Carteira','CPF','CNS')


def value(model,key):
    return norm(model.get('fields',{}).get(key,{}).get('value',''))


def identifier(key,text):
    text=norm(text)
    if not text:return ''
    if key=='Nascimento':
        try:
            parsed=datetime.strptime(text,'%d/%m/%Y').date()
            return parsed.isoformat() if parsed<=date.today() else ''
        except ValueError:return ''
    result=re.sub(r'[\s./-]','',text)
    if not re.fullmatch(r'[A-Z0-9]+',result) or not re.search(r'\d',result):return ''
    if key=='CPF' and len(result)!=11:return ''
    if key=='CNS' and len(result)!=15:return ''
    return result


def names_compatible(a,b):
    """Aceita fragmento contíguo realmente presente; nunca corrige letras ou junta nomes."""
    aa=norm(a).split();bb=norm(b).split()
    if not aa or not bb:return True
    short,long=(aa,bb) if len(aa)<=len(bb) else (bb,aa)
    return any(long[i:i+len(short)]==short for i in range(len(long)-len(short)+1))


def conflicts(a,b):
    result=[]
    if value(a,'Paciente') and value(b,'Paciente') and not names_compatible(value(a,'Paciente'),value(b,'Paciente')):result.append('Paciente')
    for key in IDENTIFIERS:
        x=identifier(key,value(a,key));y=identifier(key,value(b,key))
        if x and y and x!=y:result.append(key)
    return result


def compatible(a,b):
    if conflicts(a,b):return False
    common=[key for key in IDENTIFIERS if identifier(key,value(a,key)) and identifier(key,value(b,key))]
    names=[value(a,'Paciente'),value(b,'Paciente')]
    strong=any(k in common for k in ['Carteira','CPF','CNS'])
    return bool(common and all(names) and (strong or min(len(n.split()) for n in names)>=2))


def full_name(models):
    names=[value(m,'Paciente') for m in models if value(m,'Paciente')]
    if not names:return ''
    longest=max(names,key=lambda n:(len(n.split()),len(n)))
    if any(not names_compatible(n,longest) for n in names):return ''
    return longest
