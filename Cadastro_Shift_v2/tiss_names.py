"""Nomes impressos dentro de uma célula: conserva prenome e sobrenome espaçados."""
import re
from statistics import median
from core import norm
from tiss_geometry import rows

BAD=re.compile(r'\d|\b(?:BENEFICIARIO|PROFISSIONAL|CONTRATADO|CONSELHO|NOME SOCIAL|PROCEDIMENTOS|EXECUTADOS|SOLICITADOS|SOLICITANTE|DADOS DO|DADOS DA|ASSINATURA)\b')


def name_words(region):
    lines=[]
    for row in rows(region):
        chunks=[];chunk=[]
        for word in row['words']:
            if chunk and word['box'][0]-chunk[-1]['box'][2]>max(18,(word['box'][3]-word['box'][1])*3):
                chunks.append(chunk);chunk=[]
            chunk.append(word)
        if chunk:chunks.append(chunk)
        plausible=[c for c in chunks if re.search('[A-Z]',norm(' '.join(w['text'] for w in c))) and not BAD.search(norm(' '.join(w['text'] for w in c)))]
        if not plausible:continue
        first=plausible[0];height=median(w['box'][3]-w['box'][1] for w in first)
        # Administrative text in a neighboring unrecognized column is usually
        # a smaller font. A horizontal gap alone must never delete a first name.
        selected=[]
        for c in plausible:
            if abs(median(x['box'][3]-x['box'][1] for x in c)-height)>max(1,height*.18):continue
            if selected and len(c)==1 and len(c[0]['text'])==1 and c[0]['box'][0]-selected[-1]['box'][2]>max(18,height*6):continue
            selected.extend(c)
        if selected:lines.append(selected)
    starts=[ws for ws in lines if len(norm(' '.join(w['text'] for w in ws)).split())>=2]
    if not starts:return []
    first=min(starts,key=lambda ws:(round(ws[0]['box'][1]/5),ws[0]['box'][0]));result=list(first)
    height=max(w['box'][3]-w['box'][1] for w in first)
    for ws in lines:
        if ws is first:continue
        same_font=abs(median(w['box'][3]-w['box'][1] for w in ws)-median(w['box'][3]-w['box'][1] for w in first))<=max(.75,height*.18)
        if same_font and abs(ws[0]['box'][0]-first[0]['box'][0])<height*2 and 2<ws[0]['box'][1]-first[0]['box'][1]<height*2.5:result.extend(ws)
    return result
