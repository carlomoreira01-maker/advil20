"""Leitura geométrica conservadora de rótulos TISS/SP-SADT. Sem integração externa."""
import re
from datetime import datetime
from core import norm
from ocr_processing import union_box, source_box

SCHEMA={
 2:('Guia prestador','id'),3:('Guia principal','id'),4:('Data autorização','date'),
 5:('Senha autorização','id'),6:('Validade senha','date'),7:('Guia operadora','id'),
 8:('Carteira','id'),9:('Validade carteira','date'),10:('Paciente','name'),
 13:('Código solicitante','id'),15:('Medico','name'),16:('Conselho','council'),
 17:('Número conselho','number'),18:('UF conselho','uf'),19:('CBO','cbo'),22:('Data solicitação','date'),23:('Indicação clínica','text'),30:('Contratado executante','company')}
EXTRA_FIELDS=['Guia prestador','Guia principal','Data autorização','Senha autorização','Validade senha',
 'Guia operadora','Carteira','Validade carteira','Código solicitante','Conselho','Número conselho','UF conselho',
 'Data solicitação','Indicação clínica','Regime atendimento','Data execução','CBO','Contratado executante']
STARTS={2:'NUMERO GUIA',3:'NUMERO GUIA',4:'DATA',5:'SENHA',6:'VALIDADE',7:'NUMERO GUIA',8:'NUMERO CARTEIRA',
9:'VALIDADE',10:'NOME',13:'CODIGO',15:'NOME',16:'CONSELHO',17:'NUMERO',18:'UF',22:'DATA',
25:'CODIGO',26:'DESCRICAO',27:'QUANTIDADE QTD QTDE QTD.',28:'QUANTIDADE QTD QTDE QTD.'}
UFS=set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())


def empty_field(document=None):
 return {'value':'','page':None,'box':None,'confidence':None,'reviewed':False,'document':document,'snippet':'','candidates':[],'extraction_state':'not_found','located':False}


def valid(value,kind):
 if not value:return False
 if kind=='text':return bool(re.search(r'[A-Z]',value)) and len(value)<=1000
 if kind=='id':
  if re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}',value):return False
  return bool(re.fullmatch(r'[A-Z0-9][A-Z0-9./-]*',value)) and bool(re.search(r'\d',value))
 if kind=='number':return bool(re.fullmatch(r'\d+',value))
 if kind=='cbo':return bool(re.fullmatch(r'\d{6}',value))
 if kind=='company':return bool(re.search(r'[A-Z]',value)) and len(value)<=250
 if kind=='date':
  try:datetime.strptime(value,'%d/%m/%Y');return True
  except ValueError:return False
 if kind=='uf':return value in UFS
 if kind=='council':return value in {'CRM','CRO','COREN','CRBM','CRF','CREFITO','CRP','CRN','CRFA'}
 return len(value.split())>=2 and not re.search(r'\d',value) and not any(t in value for t in ['CONTRATADO','BENEFICIARIO','PROFISSIONAL','CONSELHO'])


from tiss_geometry import anchors, cell_words, table_rows, rows


def extract(document):
 fields={key:empty_field(document.get('file')) for key,_ in SCHEMA.values()}
 found_any=False;exams=[];executed=[];extra=[];issues=[];regions=[]
 for page in document['pages']:
  from tiss_refinement import merge_anchor_fallbacks
  aa=merge_anchor_fallbacks(page,anchors(page))
  detected=len(aa)>=2 and (any(a['num'] in [2,5,7,8,10,15] for a in aa) or 'SP/SADT' in norm(page.get('text','')) or {25,26}.issubset({a['num'] for a in aa}))
  if not detected:continue
  found_any=True
  procedure_top=min((a['y'] for a in aa if a['num'] in [25,26]),default=float('inf'))
  for a in aa:
   if a['num'] not in SCHEMA:continue
   if a['num']!=30 and a['y']>procedure_top:continue  # Campos do solicitante não vêm da seção executante.
   key,kind=SCHEMA[a['num']];region=cell_words(page,a,aa);candidate=None
   value_rows=rows(region)
   if a['num']==23:
    kept=[]
    for row in value_rows:
     if re.fullmatch(r'(?:PROCEDIMENTOS|EXAMES)\s+(?:SOLICITADOS|AUTORIZADOS|EXECUTADOS)|DADOS\s+DO\s+EXECUTANTE',norm(' '.join(w['text'] for w in row['words']))):break
     kept.append(row)
    value_rows=kept;region=[w for row in kept for w in row['words']]
   if not fields[key]['value']:
    fields[key].update(page=page['number'],box=union_box(region or a['header']),located=True,
        extraction_state='uncertain' if region else 'empty',tiss_number=a['num'],
        snippet=' '.join(w['text'] for w in a['header'])+' / '+' '.join(w['text'] for w in region),
        diagnostic='Região localizada, sem valor legível/validável; conferir original.')
   if a['num']==23 and region:regions.append({'field':23,'page':page['number'],'box':union_box(region)})
   if kind in ['name','company']:
    from tiss_names import name_words
    ws=name_words(region,company=kind=='company')
    value=norm(' '.join(w['text'] for w in ws)).strip(' :|')
    if valid(value,kind):candidate=(value,ws)

   elif kind=='text':
    ws=[w for row in value_rows for w in row['words']]
    value='\n'.join(' '.join(w['text'] for w in row['words']) for row in value_rows).strip()
    if valid(norm(value),kind):candidate=(value,ws)
   else:
    for r in value_rows:
     ws=r['words'];value=norm(' '.join(w['text'] for w in ws)).strip(' :|')
     if kind in ['id','number','date','cbo']:value=re.sub(r'\s+','',value)
     if kind=='number' and re.fullmatch(r'[0-9.]+',value):value=value.replace('.','')
     if valid(value,kind):candidate=(value,ws);break
     if kind in ['council','uf'] and value.isdigit():
      fields[key]['candidates'].append({'value':value,'page':page['number'],'box':union_box(ws),'origin_type':'codigo_impresso_nao_mapeado'})
      fields[key].update(page=page['number'],box=union_box(ws),confidence=min(w['confidence'] for w in ws),
          snippet=' '.join(w['text'] for w in a['header'])+' / '+value,origin_type='codigo_impresso_nao_mapeado',raw_code=value,
          diagnostic='Código numérico impresso sem mapeamento homologado; conferir conselho/UF.')
      issues.append('Código numérico de '+key+' exige mapeamento homologado ou conferência; não convertido automaticamente.')
   if candidate is None:continue
   value,ws=candidate;confidence=min(w['confidence'] for w in ws)
   src={'value':value,'document':document.get('file'),'page':page['number'],'box':union_box(ws),
        'confidence':confidence,'snippet':' '.join(w['text'] for w in a['header'])+' / '+' '.join(w['text'] for w in ws),
        'reviewed':False,'candidates':[],'tiss_number':a['num'],'located':True,'extraction_state':'identified','origin_type':'campo_estruturado','diagnostic':'Valor localizado na célula do rótulo.'}
   previous=fields[key]
   if previous['candidates'] or (previous['value'] and norm(previous['value'])!=value) or confidence<65:
    src['candidates']=previous['candidates']+([previous] if previous['value'] else [])+[dict(src)]
    src['value']='';src['extraction_state']='uncertain';issues.append('Campo '+key+' incerto ou conflitante; conferir origem.')
    src['diagnostic']='Confiança insuficiente ou valores conflitantes; conferir origem.'
   fields[key]=src
  requested,done=table_rows(page,aa,document)
  if page.get('regional_readings'):
   from tiss_refinement import alternatives,reconcile_fields,reconcile_exams
   variants=alternatives(document,page,extract)
   reconcile_fields(fields,page,variants,issues)
   reconcile_exams(requested,page,variants,issues)
  exams.extend(requested);executed.extend(done)
  for line in page['lines']:
   n=norm(line['text'])
   if re.search(r'\b(ETIQUETA|PROTOCOLO|CONTROLE|ATENDIMENTO)\b',n) or (aa and line['box'][1]<min(a['y'] for a in aa) and re.search(r'\b\d{5,}\b',n)):
    for code in re.findall(r'\b\d{3,}\b',n):extra.append({'value':code,'purpose':'não verificada','page':page['number'],'box':source_box(line),'snippet':line['text']})
 for e in exams:
  e['execution_occurrences']=[x for x in executed if x['codigo']==e['codigo'] and norm(x['descricao'])==norm(e['descricao'])]
 for row in executed:
  if not any(e['codigo']==row['codigo'] and norm(e['descricao'])==norm(row['descricao']) for e in exams):issues.append('Procedimento executado sem correspondente na solicitação; conferir original.')
 for field in fields.values():field.setdefault('diagnostic','Rótulo ou valor não localizado; conferir original.')
 return {'detected':found_any,'fields':fields,'exams':exams,'executed_exams':executed,'extra_numbers':extra,'issues':list(dict.fromkeys(issues)),
         'field_regions':regions,
         'layout_profile':'rótulos e células SP/SADT por coordenadas; homologação local pendente'}
