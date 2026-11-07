"""Células por palavras e coordenadas, sem depender das linhas globais do OCR."""
import re
from difflib import get_close_matches
from statistics import median
from functools import lru_cache
from core import norm
from ocr_processing import union_box

# Campos adjacentes também delimitam regiões, mesmo quando não são extraídos.
LABELS={
2:r'(?:N\S*\s+(?:DA\s+)?)?GUIA\s+(?:(?:NO|DO|DA)\s+)?PRESTADOR',
3:r'(?:N\S*\s+(?:DA\s+)?)?GUIA\s+PRINCIPAL',
4:r'DATA\s+(?:(?:DA|DE)\s+)?AUTORIZACAO',5:r'SENHA(?:\s+DE\s+AUTORIZACAO)?',
6:r'(?:DATA\s+(?:DE\s+)?)?VALIDADE\s+(?:(?:DA|DE)\s+)?SENHA',
7:r'(?:N\S*\s+(?:DA\s+)?)?GUIA\s+(?:ATRIBUID[AO]\s+)?(?:(?:PELA|DA)\s+)?OPERADORA',
8:r'(?:N\S*\s+(?:DA\s+)?)?CARTEIRA',9:r'(?:DATA\s+(?:DE\s+)?)?VALIDADE\s+(?:(?:DA|DE)\s+)?CARTEIRA',
10:r'NOME\s+(?:(?:DO|DA)\s+)?BENEFICIARIO',11:r'(?:CARTAO\s+NACIONAL\s+DE\s+SAUDE|CNS)',
12:r'ATENDIMENTO\s+A\s+RN',13:r'CODIGO\s+(?:(?:(?:DO|DA)\s+)?CONTRATADO(?:\s+SOLICITANTE)?(?:\s+NA\s+OPERADORA)?|NA\s+OPERADORA)',
14:r'NOME\s+(?:(?:DO|DA)\s+)?CONTRATADO',15:r'NOME\s+(?:(?:DO|DA)\s+)?PROFISSIONAL(?:\s+SOLICITANTE)?',
16:r'CONSELHO(?:\s+PROFISSIONAL)?',17:r'N\S*\s+(?:(?:DO|DA|NO)\s+)?CONSELHO(?:\s+PROFISSIONAL)?',18:r'UF',19:r'CODIGO\s+CBO|CBO',
20:r'CARATER\s+(?:DE\s+)?ATENDIMENTO',21:r'CARATER\s+(?:DE\s+)?ATENDIMENTO',22:r'DATA\s+(?:(?:DA|DE)\s+)?SOLICITACAO',
23:r'INDICACAO\s+CLINICA',24:r'TIPO\s+(?:DE\s+)?ATENDIMENTO',
25:r'CODIGO(?:\s+(?:DO\s+)?PROCEDIMENTO)?',26:r'DESCRICAO(?:\s+(?:DO\s+)?PROCEDIMENTO)?',
27:r'(?:QUANTIDADE|QTD\.?|QTDE\.?|QT\.?)(?:\s+SOL\S*)?',28:r'(?:QUANTIDADE|QTD\.?|QTDE\.?|QT\.?)(?:\s+AUT\S*)?',
29:r'CODIGO\s+(?:(?:DO|DA)\s+)?CONTRATADO',30:r'NOME\s+(?:(?:DO|DA)\s+)?CONTRATADO',
31:r'CODIGO\s+CNES',32:r'TIPO\s+(?:DE\s+)?ATENDIMENTO',33:r'INDICACAO\s+(?:DE\s+)?ACIDENTE',
34:r'TIPO\s+(?:DE\s+)?CONSULTA',35:r'MOTIVO\s+(?:DE\s+)?ENCERRAMENTO',
36:r'DATA',37:r'HORA',38:r'HORA',39:r'TABELA',40:r'CODIGO',41:r'DESCRICAO',42:r'QUANTIDADE|QTD\.?|QTDE\.?|QT\.?',
}


def words_of(page):
 return [w for line in page['lines'] for w in line.get('words',[]) if len(w['text'])<=80]


def rows(words):
 """Agrupa pela linha de base. Rótulos pequenos não absorvem os valores abaixo."""
 out=[]
 for w in sorted(words,key=lambda w:(w['box'][3],w['box'][0])):
  b=w['box'];h=max(1,b[3]-b[1]);best=None
  for row in reversed(out):
   if b[3]-row['base']>max(3,h*.55):break
   if abs(b[3]-row['base'])<=max(1.5,min(h,row['h'])*.65):best=row;break
  if best is None:best={'base':b[3],'h':h,'words':[]};out.append(best)
  best['words'].append(w)
  substantial=[x for x in best['words'] if x['box'][3]-x['box'][1]>1.5] or best['words']
  best['base']=median(x['box'][3] for x in substantial)
  best['h']=median(x['box'][3]-x['box'][1] for x in substantial)
 for row in out:row['words'].sort(key=lambda w:w['box'][0])
 return out


@lru_cache(maxsize=2048)
def header_token(text):
 token=norm(text).strip(':.|')
 # Tiny form labels are often joined by OCR. Expand only known LABELS;
 # patient names, identifiers and procedure values are never fuzzy-corrected.
 compact=re.sub(r'[^A-Z]','',token)
 fused={'NOMEDOBENEFICIARIO':'NOME DO BENEFICIARIO','NOMEBENEFICIARIO':'NOME BENEFICIARIO',
        'NUMERODACARTEIRA':'NUMERO DA CARTEIRA','NDACARTEIRA':'NUMERO DA CARTEIRA',
        'NUMERODOCONSELHO':'NUMERO DO CONSELHO','NUMERONOCONSELHO':'NUMERO NO CONSELHO',
        'CONSELHOPROFISSIONAL':'CONSELHO PROFISSIONAL','NOMEDOPROFISSIONALSOLICITANTE':'NOME DO PROFISSIONAL SOLICITANTE'}
 if compact in fused:return fused[compact]
 if re.fullmatch(r'(?:QT|QTD|QTDE|QUANTIDADE)SOL(?:IC|ICITADA|ICITADO)?',compact):return 'QT SOLICITADA'
 if re.fullmatch(r'(?:QT|QTD|QTDE|QUANTIDADE)AUT(?:OR|ORIZADA|ORIZADO)?',compact):return 'QT AUTORIZADA'
 vocabulary='CODIGO NUMERO NOME SOLICITANTE BENEFICIARIO PROFISSIONAL CONSELHO PROCEDIMENTO DESCRICAO QUANTIDADE SOLICITADA AUTORIZADA AUTORIZACAO SOLICITACAO VALIDADE CARTEIRA CONTRATADO PRESTADOR OPERADORA PRINCIPAL'.split()
 if token in vocabulary:return token
 if len(token)>=4 and token.isalpha():
  matches=get_close_matches(token,vocabulary,n=1,cutoff=.72)
  if matches:return matches[0]
 return token


def anchors(page):
 words=words_of(page);found=[]
 # Seed at each number, collect only nearby words on its baseline, not the
 # pre-grouped OCR line (which can include a beneficiary value on the next row).
 for seed in words:
  match=re.fullmatch(r'(\d{1,2})(?:[-.)](.*))?',norm(seed['text']))
  if not match or int(match[1]) not in LABELS:continue
  suffix=match[2] or '';num=int(match[1]);b=seed['box'];h=max(2,b[3]-b[1]);cy=(b[1]+b[3])/2
  near=sorted([w for w in words if w is not seed and w['box'][0]>=b[2]-.5 and
               abs((w['box'][1]+w['box'][3])/2-cy)<=max(2,h*.65) and
               w['box'][3]-w['box'][1]<=h*1.75],key=lambda w:w['box'][0])
  # Stop at the next numbered label, so values cannot become label words.
  segment=[]
  for w in near:
   if segment and re.fullmatch(r'\d{1,2}[-.)]',norm(w['text'])):break
   segment.append(w)
  while segment and not re.search(r'[A-Za-zÀ-ÿ]',segment[0]['text']):segment.pop(0)
  tokens=([header_token(suffix)] if re.search(r'[A-Z]',suffix) else [])+[header_token(w['text']) for w in segment]
  text=' '.join(tokens).strip(' -:')
  m=re.match(LABELS[num]+r'(?=\s|:|$)',text)
  # A legible printed number plus an unambiguous prefix remains an anchor
  # when a tiny-font suffix is damaged. This is only a label rule.
  if not m and num in [10,15]:m=re.match(r'NOME(?=\s|$)',text)
  if not m:continue
  label=[seed];length=len(header_token(suffix)) if re.search(r'[A-Z]',suffix) else 0
  for w in segment:
   token=header_token(w['text']);token_start=length+(1 if length else 0)
   if token_start>=m.end():break
   label.append(w);length=token_start+len(token)
  box=union_box(label,False)
  found.append({'num':num,'x':b[0],'y':box[1],'bottom':box[3],'height':max(2,box[3]-box[1]),'header':label,'label_box':box})
 # The printed field number may be missing in OCR: recover by a distinctive
 # label, never by a bare digit or assumed page position.
 for row in rows(words):
  ws=row['words']
  for i,w in enumerate(ws):
   if not re.match(r'^(?:N\S*|VALIDADE|DATA|SENHA|CONSELHO|UF|INDICACAO|CODIGO|QT\s+SOLICITADA|QT\s+AUTORIZADA)$',header_token(w['text'])):continue
   if any(w in a['header'] for a in found):continue
   text=' '.join(header_token(x['text']) for x in ws[i:i+10])
   for num in [2,3,4,5,6,7,8,9,10,14,15,16,17,18,19,22,23,25,27,28]:
    if num in [27,28] and not re.match(r'QT\s+'+('SOL' if num==27 else 'AUT'),text):continue
    m=re.match(LABELS[num]+r'(?=\s|:|$)',text)
    if not m and num==10 and header_token(w['text'])=='NOME' and not re.match(r'NOME\s+SOCIAL',text) and any(a['num'] in [8,9] and abs(a['y']-w['box'][1])<7 for a in found):m=re.match('NOME',text)
    if not m:continue
    label=[];length=0
    for x in ws[i:]:
     if length>=m.end():break
     label.append(x);length+=len(header_token(x['text']))+(1 if length else 0)
    if any(abs(a['x']-w['box'][0])<5 and abs(a['y']-w['box'][1])<5 for a in found):break
    box=union_box(label,False)
    x=box[0]-max(5,(box[3]-box[1])*2) if num in [27,28] else box[0]
    found.append({'num':num,'x':x,'y':box[1],'bottom':box[3],'height':max(2,box[3]-box[1]),'header':label,'label_box':box,'number_inferred_from_label':True});break
 found=[a for a in found if not (a['num']==25 and a.get('number_inferred_from_label') and
        not any(b['num']==26 and abs(b['y']-a['y'])<8 for b in found))]
 # In a verified numbered 26-description header, adjacent printed 25/27/28
 # remain reliable column boundaries even when their tiny label is damaged.
 for description in list(found):
  if description['num']!=26:continue
  for w in words:
   m=re.fullmatch(r'(25|27|28)[-.)]?',norm(w['text']))
   if not m or abs(w['box'][1]-description['y'])>7:continue
   number=int(m[1])
   if (number==25 and w['box'][0]>=description['x']) or (number in [27,28] and w['box'][0]<=description['x']):continue
   if any(a['num']==number and abs(a['y']-description['y'])<8 for a in found):continue
   b=w['box'];found.append({'num':number,'x':b[0],'y':b[1],'bottom':b[3],'height':max(2,b[3]-b[1]),'header':[w],'label_box':list(b),'column_number_verified':True})
 width=max([page.get('size',[0,0])[0]]+[w['box'][2] for w in words])+1
 for a in found:
  same=[b for b in found if b is not a and b['x']>a['x']+4 and abs(b['y']-a['y'])<=max(4,min(a['height'],b['height'])*.9)]
  a['right']=min((b['x']-2 for b in same),default=width)
  for w in words:
   if w['box'][0]>a['x']+8 and abs(w['box'][1]-a['y'])<max(4,a['height']*.7) and re.fullmatch(r'11[-.)]',norm(w['text'])):
    a['right']=min(a['right'],w['box'][0]-2)
 return sorted(found,key=lambda a:(a['y'],a['x']))


def cell_words(page,a,aa):
 words=words_of(page);h=a['height']
 nxt=min((b['y'] for b in aa if b['y']>a['bottom']+1 and b['x']<a['right'] and b['right']>a['x']+2),default=a['bottom']+h*7)
 limit=min(nxt-1,a['bottom']+h*7)
 label_ids={id(w) for b in aa for w in b['header']}
 left=a['x']-max(3,h*(3 if a.get('number_inferred_from_label') else .8))
 below=[w for w in words if id(w) not in label_ids and left<=(w['box'][0]+w['box'][2])/2<a['right'] and
        w['box'][1]>=a['bottom']-.5 and w['box'][1]<limit]
 # A value can be beside the label (e.g. field 2 in the top right corner).
 lb=a['label_box'];inline=[w for w in words if id(w) not in label_ids and lb[2]+1<=w['box'][0]<a['right'] and
        abs((w['box'][1]+w['box'][3])/2-(lb[1]+lb[3])/2)<=max(3,h*.65)]
 if a['num']!=2 and inline and min(w['box'][0] for w in inline)-lb[2]>max(12,h*4):inline=[]
 return (inline or below) if a['num']==2 else (below or inline)


def table_rows(page,aa,document):
 from ocr_processing import source_box
 words=words_of(page);result=[];executed=[]
 starts=[a for a in aa if a['num'] in [25,40]]
 for start in starts:
  h=start['height'];heads=[a for a in aa if a['num'] in [25,26,27,28,40,41,42] and abs(a['y']-start['y'])<max(7,h*1.1)]
  description=next((a for a in heads if a['num'] in [26,41]),None)
  if description is None:continue
  # A generic execution table can repeat the 25-28 header numbers. Its title
  # determines its role; executed quantity never supplies authorization.
  preceding=[r for r in rows(words) if r['base']<start['y'] and re.search(r'(PROCEDIMENTOS|EXAMES).*(EXECUTADOS|REALIZADOS|SOLICITADOS|AUTORIZADOS)',norm(' '.join(w['text'] for w in r['words'])))]
  title=norm(' '.join(w['text'] for w in preceding[-1]['words'])) if preceding else ''
  execution=start['num']==40 or bool(re.search('EXECUTADOS|REALIZADOS',title))
  cols=[(start['x'],'codigo'),(description['x'],'descricao')]
  for a in heads:
   if a['num'] in [27,28,42]:cols.append((a['x'],{27:'quantidade_solicitada',28:'quantidade_autorizada',42:'quantidade_executada'}[a['num']]))
  for w in words:
   if norm(w['text']).strip(':.') in ['MATERIAL','AMOSTRA'] and abs(w['box'][1]-start['y'])<max(8,h):cols.append((w['box'][0],'material'))
  cols.sort();top=max(a['bottom'] for a in heads)
  # Any following numbered field/header ends this table.
  stop=min((a['y'] for a in aa if a['y']>top+2 and a['num'] not in [25,26,27,28]),default=max(w['box'][3] for w in words)+1)
  titles=[r for r in rows(words) if r['base']>top+4 and re.search(r'DADOS.*(?:EXECUTANTE|EXECUCAO)|PROCEDIMENTOS.*(?:EXECUTADOS|REALIZADOS)',norm(' '.join(w['text'] for w in r['words'])))]
  if titles:stop=min(stop,min(min(w['box'][1] for w in r['words']) for r in titles))
  following=min((a['y'] for a in starts if a['y']>top+2),default=stop);stop=min(stop,following)
  codewords=[w for w in words if top<w['box'][1]<stop and start['x']-5<=w['box'][0]<description['x']-3 and re.fullmatch(r'(?:\d{4,12}|[A-Z][A-Z0-9._/-]{1,39})',norm(w['text']))]
  # A damaged/blank code must not hide a legible procedure description. A
  # description row with a quantity in its own column is retained without
  # inventing a code. Name/catalogue validation still occurs in comparison.
  desc_right=min((x for x,k in cols if x>description['x']),default=float('inf'))
  desc_words=[w for w in words if top<w['box'][1]<stop and description['x']-4<=w['box'][0]<desc_right-4]
  qty_words=[w for w in words if top<w['box'][1]<stop and any(x-4<=w['box'][0] for x,k in cols if k.startswith('quantidade')) and re.fullmatch(r'\d{1,3}',w['text'])]
  codewords=[w for w in codewords if re.search(r'\d',w['text']) or any(
      abs((q['box'][1]+q['box'][3]-w['box'][1]-w['box'][3])/2)<max(3,w['box'][3]-w['box'][1]) for q in qty_words)]
  for r in rows(desc_words):
   ws=r['words'];cy=sum((w['box'][1]+w['box'][3])/2 for w in ws)/len(ws)
   h=max(w['box'][3]-w['box'][1] for w in ws)
   if not any(re.search('[A-Za-zÀ-ÿ]',w['text']) for w in ws):continue
   if any(abs((w['box'][1]+w['box'][3])/2-cy)<max(3,h) for w in codewords):continue
   if not any(abs((w['box'][1]+w['box'][3])/2-cy)<max(3,h*.8) for w in qty_words):continue
   codewords.append({'text':'','box':list(ws[0]['box']),'confidence':min(w['confidence'] for w in ws),'missing_code':True})
  codewords.sort(key=lambda w:w['box'][1])
  for i,codeword in enumerate(codewords):
   b=codeword['box'];height=max(3,b[3]-b[1]);cy=(b[1]+b[3])/2
   nexttop=codewords[i+1]['box'][1] if i+1<len(codewords) else min(stop,b[3]+height*2.6)
   bottom=(b[3]+nexttop)/2 if i+1<len(codewords) else nexttop
   selected=[w for w in words if cy-height*.9<=(w['box'][1]+w['box'][3])/2<bottom and start['x']-5<=w['box'][0]]
   cells={k:[] for _,k in cols}
   for w in selected:
    options=[(x,k) for x,k in cols if w['box'][0]>=x-4]
    if options:cells[options[-1][1]].append(w)
   # Code's region excludes row index / table code before the actual TUSS.
   cells['codigo']=[] if codeword.get('missing_code') else [codeword]
   text={k:' '.join(w['text'] for row in rows(ws) for w in row['words']).strip() for k,ws in cells.items()}
   if not text.get('descricao'):continue
   origin={'page':page['number'],'box':union_box(selected),'document':document.get('file'),'snippet':' '.join(w['text'] for w in selected)}
   row={**text,**origin,'confidence':min(w['confidence'] for w in selected),'reviewed':False,'raw':origin['snippet'],'notes':[],'section':'executados' if execution else 'solicitados','origins':[], 'material':text.get('material','')}
   desc_rows=rows(cells['descricao'])
   row['origins']=[{**origin,'box':union_box(r['words']),'snippet':' '.join(w['text'] for w in r['words'])} for r in desc_rows] or [dict(origin)]
   for key in ['quantidade_solicitada','quantidade_autorizada','quantidade_executada']:
    qty=re.sub(r'\s+','',text.get(key,''));ws=cells.get(key,[])
    row[key]=qty if re.fullmatch(r'\d{1,3}',qty) and ws and min(w['confidence'] for w in ws)>=80 else ''
   row['cell_origins']={k:{**origin,'box':union_box(ws),'snippet':' '.join(w['text'] for w in ws),'confidence':min(w['confidence'] for w in ws)} for k,ws in cells.items() if ws}
   row['quantidade']=row['quantidade_autorizada']
   if not row.get('codigo'):row['notes'].append('Código não identificado; conferir a linha e o catálogo aprovado.')
   if row['quantidade_autorizada'] in ['', '0']:row['notes'].append('Quantidade autorizada ausente, zero ou ilegível. Conferir; não presumir autorização.')
   (executed if execution else result).append(row)
 return result,executed
