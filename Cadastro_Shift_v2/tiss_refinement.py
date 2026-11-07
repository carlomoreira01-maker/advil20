"""Conciliação conservadora: campos/quantidades exigem concordância entre releituras."""
import copy
from collections import defaultdict
from core import norm
from identity_evidence import names_compatible


def merge_anchor_fallbacks(page,found):
    result=list(found)
    for a in page.get('_anchor_fallbacks',[]):
        if not any(b['num']==a['num'] and abs(b['y']-a['y'])<=max(5,a['height']*1.5) for b in result):result.append(copy.deepcopy(a))
    for a in result:
        a['right']=min(a['right'],min((b['x']-2 for b in result if b['x']>a['x']+4 and abs(b['y']-a['y'])<=max(4,min(a['height'],b['height'])*.9)),default=a['right']))
    return result


def alternatives(document,page,extract):
    from engine_v2 import group_lines
    from tiss_geometry import words_of,anchors
    base=words_of(page);fallback=anchors(page)
    result=[]
    for reading in page.get('regional_readings',[]):
        ws=reading['words']
        if not ws:continue
        # Use the same region bounds after normalization; all boxes are in the
        # corrected reading coordinates, source boxes still refer to original.
        x0,y0,x1,y1=reading['bounds']
        alternate={k:v for k,v in page.items() if k not in ['regional_readings','_anchor_fallbacks']}
        alternate.update(lines=group_lines(ws),_anchor_fallbacks=[a for a in fallback if y0<=a['y']<y1])
        model=extract({'file':document.get('file'),'pages':[alternate]})
        result.append((reading,model))
    return result


def reconcile_fields(fields,page,variants,issues):
    from tiss import SCHEMA,empty_field
    for number,(key,kind) in SCHEMA.items():
        observations=[]
        for reading,model in variants:
            candidate=model['fields'][key]
            if number in reading['targets'] and candidate['value'] and (candidate['confidence'] or 0)>=80:
                observations.append((reading['id'],candidate))
        groups=defaultdict(list)
        for reading_id,candidate in observations:groups[norm(candidate['value'])].append((reading_id,candidate))
        agreed=[entries for entries in groups.values() if len({rid for rid,_ in entries})>=2]
        old=fields[key]
        foreign=[c for c in old.get('candidates',[]) if c.get('page') not in [None,page['number']]]
        if old.get('page') not in [None,page['number']] or foreign:continue
        if not agreed:
            if observations and not old['value']:
                old['candidates'].extend(copy.deepcopy(c) for _,c in observations)
                src=observations[0][1]
                for k in ['page','box','snippet','document']:old[k]=copy.deepcopy(src.get(k))
                old['diagnostic']='Leitura regional isolada; conferir origem antes de utilizar.'
            elif observations and old['value'] and (old.get('confidence') or 0)<80 and all(norm(c['value'])!=norm(old['value']) for _,c in observations):
                src=copy.deepcopy(old);old.update(value='',candidates=[src,*[copy.deepcopy(c) for _,c in observations]],diagnostic='Leitura principal fraca diverge da região; conferir origem.')
                issues.append('Campo '+key+' com leituras locais divergentes; conferir origem.')
            continue
        entries=max(agreed,key=lambda entries:(len(entries),min(c['confidence'] for _,c in entries)))
        candidate=copy.deepcopy(entries[0][1]);value=candidate['value']
        if old['value'] and norm(old['value'])!=norm(value):
            if kind=='name' and names_compatible(old['value'],value):
                if len(old['value'].split())>=len(value.split()):
                    old['regional_agreements']=len(entries);continue
            else:
                fields[key]={**empty_field(document=old.get('document')), 'page':page['number'],'box':candidate['box'],
                    'snippet':candidate['snippet'],'candidates':[copy.deepcopy(old),candidate],
                    'diagnostic':'Leituras locais divergentes; comparar as origens. Nenhum valor escolhido por suposição.'}
                issues.append('Campo '+key+' com leituras locais divergentes; conferir origem.');continue
        if old['value'] and norm(old['value'])==norm(value):
            old['regional_agreements']=len(entries);continue
        candidate.update(origin_type='campo_estruturado_ocr_regional',regional_agreements=len(entries),
                         confidence=min(c['confidence'] for _,c in entries),reviewed=False,
                         diagnostic='Valor confirmado por segmentações locais concordantes; conferir no original.')
        if old.get('candidates'):candidate['reading_history']=copy.deepcopy(old['candidates'])
        fields[key]=candidate


def reconcile_exams(exams,page,variants,issues):
    for row in exams:
        if row['page']!=page['number'] or not row.get('codigo'):continue
        for key in ['quantidade_solicitada','quantidade_autorizada']:
            observations=[]
            for reading,model in variants:
                if reading['family']!='table':continue
                matching=[e for e in model['exams'] if e['codigo']==row['codigo'] and e.get('section')=='solicitados']
                if len(matching)!=1:continue
                e=matching[0];value=e.get(key,'');origin=e.get('cell_origins',{}).get(key,{})
                if value.isdigit() and origin.get('confidence',0)>=80:observations.append((reading['id'],value,origin))
            groups=defaultdict(list)
            for rid,value,src in observations:groups[value].append((rid,src))
            agreed=[(value,entries) for value,entries in groups.items() if len({rid for rid,_ in entries})>=2]
            if not agreed:
                if observations and not row.get(key):row.setdefault('quantity_candidates',{})[key]=[{'value':v,**copy.deepcopy(src)} for _,v,src in observations]
                continue
            value,entries=max(agreed,key=lambda x:len(x[1]));old=row.get(key,'')
            if old and old!=value:
                row[key]='';row.setdefault('quantity_candidates',{})[key]=[{'value':old,**row.get('cell_origins',{}).get(key,{})},{'value':value,**copy.deepcopy(entries[0][1])}]
                row['notes'].append('Quantidade com leituras locais divergentes; não presumir autorização.')
                issues.append('Quantidade em tabela com leituras locais divergentes; conferir origem.')
            elif not old:
                row[key]=value;origin=copy.deepcopy(entries[0][1]);origin.update(reading_method='OCR local em região',regional_agreements=len(entries));row.setdefault('cell_origins',{})[key]=origin
        row['quantidade']=row.get('quantidade_autorizada','')
        if row['quantidade'].isdigit() and int(row['quantidade'])>0:
            row['notes']=[n for n in row['notes'] if not n.startswith('Quantidade autorizada ausente')]
