"""Identificação livre/carimbo impresso separado dos campos estruturados do solicitante."""
import copy,re
from core import norm
from tiss import UFS,empty_field
from tiss_geometry import rows,words_of
from ocr_processing import union_box


def free_identification(document):
    result={k:empty_field(document.get('file')) for k in ['Conselho','Número conselho','UF conselho','Medico']}
    observations=[]
    states='|'.join(sorted(UFS))
    pattern=re.compile(r'\b(?P<council>CRM|CRO|COREN|CRBM|CRF|CREFITO|CRP|CRN|CRFA)\b\s*[:/-]?\s*'
                       r'(?:(?P<before>'+states+r')\b\s*[:/-]?\s*)?'
                       r'(?P<number>\d(?:[\d .]*\d)?)(?:\s*[-/]?\s*(?P<after>'+states+r')\b)?')
    for page in document['pages']:
        from prescription_layout import stamped_names
        for value,line in stamped_names(page):
            observations.append({'Medico':{'value':value,'document':document.get('file'),'page':page['number'],
                'box':union_box(line.get('words',[])) or line['box'],'confidence':line['confidence'],
                'snippet':line['text'],'origin_type':'nome_no_carimbo_impresso','reviewed':False,'candidates':[]}})
        for line in rows(words_of(page)):
            words=line['words'];text=norm(' '.join(w['text'] for w in words))
            for match in pattern.finditer(text):
                number=re.sub(r'[ .]','',match['number'])
                if not 2<=len(number)<=12:continue
                values={'Conselho':match['council'],'Número conselho':number,'UF conselho':match['before'] or match['after'] or ''}
                # A free-form stamp is traceable as such, never as a numbered cell.
                src={'document':document.get('file'),'page':page['number'],'box':union_box(words),
                     'confidence':min(w['confidence'] for w in words),'snippet':text,
                     'origin_type':'identificacao_livre_ou_carimbo','reviewed':False,'candidates':[]}
                observations.append({k:{**copy.deepcopy(src),'value':v} for k,v in values.items() if v})
    for key in result:
        candidates=[o[key] for o in observations if key in o]
        if not candidates:continue
        if len({c['value'] for c in candidates})==1 and all(c['confidence']>=65 for c in candidates):result[key]=candidates[0]
        else:result[key].update(candidates=candidates,diagnostic='Identificação livre/carimbo com leituras divergentes ou incompletas; conferir origem.')
    return result


def reconcile(structured,free,issues):
    for key,alternative in free.items():
        current=structured[key]
        if not alternative['value']:continue
        from prescription_layout import doctor_name
        equivalent=(doctor_name(current['value'])==doctor_name(alternative['value'])) if key=='Medico' else current['value']==alternative['value']
        if current['value'] and not equivalent:
            structured[key]={**empty_field(current.get('document')),'candidates':[copy.deepcopy(current),copy.deepcopy(alternative)],
                'diagnostic':'Campo estruturado e identificação livre/carimbo divergem; conferir ambas as origens.'}
            issues.append('Solicitante: '+key+' diverge entre campo estruturado e identificação livre/carimbo.')
        elif current['value']:current.setdefault('corroborating_origins',[]).append(copy.deepcopy(alternative))
        elif not current.get('candidates'):structured[key]=copy.deepcopy(alternative)
