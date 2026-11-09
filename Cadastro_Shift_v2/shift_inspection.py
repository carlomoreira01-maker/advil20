"""Inspeção estrutural local e sem valores. Não preenche nem envia formulários."""
import re,unicodedata
from urllib.parse import urlsplit

SHIFT_HOST='sh.labsaudeonline.com.br'
SHIFT_LOGIN='https://sh.labsaudeonline.com.br/main/auth/login?returnUrl=%2Fapp'
ALIASES={
 'paciente':('paciente','nomepaciente','nomedopaciente','patient','patientname','beneficiario','nomebeneficiario','nomedobeneficiario'),
 'nascimento':('nascimento','datanascimento','birthdate','dateofbirth'),
 'carteira':('carteira','numerocarteira','numerodacarteira','carteirinha','matricula','membershipnumber'),
 'fonte_pagadora':('fontepagadora','convenio','convenioid','payer','payerid'),
 'guia_prestador':('guiaprestador','guianoprestador','numeroguia','guia','guidenumber'),
 'guia_principal':('guiaprincipal','mainguide'),
 'guia_operadora':('guiaoperadora','operatorguide'),
 'autorizacao':('autorizacao','senhaautorizacao','authorization'),
 'medico':('medico','medicosolicitante','solicitante','physician','doctor'),
 'conselho_numero':('crm','numeroconselho','registrationnumber'),
 'conselho_uf':('uf','ufconselho','registrationstate'),
 'procedimentos':('procedimentos','procedimento','exames','exame','procedure','procedurecode'),
 'quantidade':('quantidade','quantity','qtd'),
}
def compact(value):
    return re.sub('[^a-z]','',unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower())

def semantic(value):
    text=compact(value)
    return next((field for field,aliases in ALIASES.items() if text in aliases),None)

def safe_attribute(value):
    """Só aliases técnicos conhecidos ou IDs de framework; nunca dados arbitrários."""
    if not isinstance(value,str) or len(value)>80:return None
    if semantic(value):return value if re.fullmatch(r'[A-Za-z_-]+',value) else None
    if re.fullmatch(r'mat-(?:input|select|checkbox)-\d{1,4}',value):return value
    for prefix in ['txt','edt','cmb','ddl','input','select']:
        if value.lower().startswith(prefix) and semantic(value[len(prefix):]):
            return value if re.fullmatch(r'[A-Za-z_-]+',value) else None
    return None

def inspect_structure(page,expected_host=SHIFT_HOST):
    """Somente controles visíveis, sem value, HTML, textos, cookies ou URLs privadas."""
    if urlsplit(page.url).hostname!=expected_host:raise ValueError('A inspeção só funciona no domínio autorizado do Shift. Retorne à tela do sistema.')
    records=[];login=False;count=0
    for frame_index,frame in enumerate(page.frames):
        if urlsplit(frame.url).hostname!=expected_host:continue
        controls=frame.evaluate('''() => Array.from(document.querySelectorAll('input,select,textarea,[role="combobox"]')).filter(e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden').map(e=>({tag:e.tagName.toLowerCase(),type:e.type||'',id:e.getAttribute('id')||'',name:e.getAttribute('name')||'',control:e.getAttribute('formcontrolname')||'',testid:e.getAttribute('data-testid')||'',role:e.getAttribute('role')||'',label:e.getAttribute('aria-label')||Array.from(e.labels||[]).map(l=>l.textContent).join(' ')}))''')
        count+=len(controls)
        if any(c['type']=='password' for c in controls):login=True;continue
        for ordinal,c in enumerate(controls):
            if c['type'] in ['password','hidden','file']:continue
            hints={semantic(c.get(k,'')) for k in ['id','name','control','testid','label']};hints.discard(None)
            selectors=[]
            for key,attribute in [('id','id'),('name','name'),('control','formcontrolname'),('testid','data-testid')]:
                value=safe_attribute(c.get(key,''))
                if value:selectors.append({'css':'['+attribute+'="'+value+'"]','estavel':not value.startswith('mat-')})
            records.append({'frame':frame_index,'ordem':ordinal,'tag':c['tag'] if c['tag'] in ['input','select','textarea','div','span','button'] else 'controle',
                'tipo':c['type'] if c['type'] in ['text','number','date','checkbox','radio','email','tel','search','select-one','select-multiple','textarea',''] else 'outro',
                'campos_possiveis':sorted(hints),'seletores_candidatos':selectors,'homologado':False})
    if login:records=[]
    return {'tipo':'INSPECAO_ESTRUTURAL_SEM_VALORES','dominio':expected_host,'login_visivel':login,'autenticacao_verificada':False,
        'controles_visiveis':count,'controles':records,'permite_gravacao':False,
        'aviso':'Conclua o login manualmente antes de inspecionar a tela autorizada.' if login else 'Candidatos estruturais para revisão técnica. Não comprovam autenticação, campos homologados ou automação pronta.'}
