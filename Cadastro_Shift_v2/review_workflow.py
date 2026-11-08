"""Pendências com ações concretas; não altera nem dispensa as validações do cadastro."""


def review_plan(models,comparison):
    steps=[]
    def add(message,action,role='guia',field=None,index=None):
        item={'message':message,'action':action,'role':role,'field':field,'index':index}
        if item not in steps:steps.append(item)
    for role,model in models.items():
        if model.get('classification_pending') or model.get('association_pending') or model.get('identity_conflict'):
            add('Conferir tipos, páginas e identidade do agrupamento.','classify',role)
        if not model['pages_reviewed']:add('Visualizar todas as páginas e marcar a conferência do '+role+'.','pages',role)
        unchecked=[k for k,v in model['fields'].items() if not v['reviewed']]
        if unchecked:add(str(len(unchecked))+' campos do '+role+' ainda sem conferência (inclusive ausências).','field',role,unchecked[0])
        for i,exam in enumerate(model['exams']):
            if not exam['reviewed']:add('Conferir exame '+str(i+1)+' do '+role+'.','exam',role,index=i)
        for i,issue in enumerate(model['issues']):
            if not issue['reviewed'] or not issue['reason'].strip():add('Registrar resolução: '+issue['message'],'issue',role,index=i)
    for message in comparison['pendencias']:
        low=message.lower()
        if any(word in low for word in ['catálogo','código interno','sinônimo']):add(message,'catalog');continue
        if any(word in low for word in ['perfil','fonte pagadora','tipo de atendimento','escopo']):add(message,'profile');continue
        if 'identidade' in low:
            if any(m.get('scan_group') for m in models.values()):add(message,'classify');continue
            add(message,'field','pedido','Paciente');continue
        role='pedido' if 'no pedido' in low or low.startswith('pedido:') else 'guia'
        field=next((key for key in sorted(models[role]['fields'],key=len,reverse=True) if key.lower() in low),None)
        if field:add(message,'field',role,field)
        elif 'médico' in low:add(message,'field',role,'Medico')
        else:add(message,'exam',role,index=0 if models[role]['exams'] else None)
    return steps


ACTION_LABELS={'classify':'Identificar páginas','pages':'Ver páginas','field':'Conferir campo',
               'exam':'Conferir exame','issue':'Resolver alerta','catalog':'Configurar catálogo','profile':'Selecionar perfil'}
