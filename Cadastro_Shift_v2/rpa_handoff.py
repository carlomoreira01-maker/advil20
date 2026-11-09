"""Entrega de um pré-cadastro conferido ao LIS fictício, sem adaptador de produção."""
import copy
import hashlib
import json
import re
from pathlib import Path

from core import digest, norm
from document_integrity import verified_sources
from engine_v2 import compare_models, review_errors
from lis_simulado import Simulation, approve


def _snapshot_hash(envelope):
    return digest({k: v for k, v in envelope.items() if k != 'snapshot_hash'})


def validate_handoff(envelope):
    if not isinstance(envelope, dict) or envelope.get('tipo') != 'PRE_CADASTRO_PARA_LIS_FICTICIO' or envelope.get('permite_producao') is not False:
        raise ValueError('Esta integração aceita somente o pré-cadastro fictício de demonstração.')
    if envelope.get('snapshot_hash') != _snapshot_hash(envelope):
        raise ValueError('A entrega ao simulador foi alterada. Reabra o pré-cadastro e confira novamente.')
    files = envelope.get('files')
    if not isinstance(files, list) or not files:
        raise ValueError('Documentos originais do atendimento não disponíveis.')
    attachments = []
    for item in files:
        try:
            path = Path(item['path'])
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except (KeyError, TypeError, OSError):
            raise ValueError('Documento original indisponível. Restaure o backup antes de simular.') from None
        if actual != item.get('sha256'):
            raise ValueError('Documento alterado após a conferência. A simulação foi bloqueada.')
        attachments.append({'name': path.name, 'sha256': actual})
    # Reutiliza o mesmo validador que protegerá a gravação no servidor local.
    if not isinstance(envelope.get('document_roles'), dict):
        raise ValueError('Pedido e guia precisam de associação explícita aos documentos originais.')
    state = Simulation(envelope['data'], envelope['approval'], attachments,
                       document_roles=envelope.get('document_roles'))
    state.db.close()
    return attachments


def build_handoff(store, cid, catalog, *, expected_revision, reviewer, checks,
                  synthetic_confirmed=False):
    if synthetic_confirmed is not True:
        raise ValueError('Marque que os dados e documentos são inteiramente fictícios. Use os exemplos de treinamento.')
    obj, rev, status, output = store.get(cid)
    if type(expected_revision) is not int or rev != expected_revision:
        raise ValueError('O atendimento mudou. Reabra o pré-cadastro e confira a revisão atual.')
    if status != 'PREPARADO' or not output:
        raise ValueError('Conclua a conferência e prepare o pré-cadastro validado antes de simular este atendimento. O rascunho continua disponível.')
    if output.get('tipo') != 'PRE_CADASTRO_LOCAL_NAO_ENVIADO' or output.get('os_real') is not None or output.get('revisao') != rev or output.get('caso') != cid:
        raise ValueError('Resultado local incompatível com a revisão do atendimento.')
    if digest(catalog) != output.get('catalogo_hash') or digest(obj['models']) != digest(output.get('conferencia')):
        raise ValueError('Dados ou catálogo mudaram após a preparação. Não será utilizada uma aprovação antiga.')
    models = obj['models']
    result = compare_models(models['pedido'], models['guia'], catalog)
    if result['pendencias'] or review_errors(models):
        raise ValueError('Ainda existem pendências de conferência. Resolva-as antes de iniciar a simulação.')
    guide = models['guia']; fields = guide['fields']; profile = guide.get('payer_profile') or {}
    if profile.get('id') != 'FICTICIO' or norm(profile.get('fonte_pagadora', '')) != 'IPASGO':
        raise ValueError('O simulador exige o perfil FICTICIO dos exemplos. Perfis reais não são convertidos automaticamente.')
    if norm(fields['Conselho']['value']) != 'CRM':
        raise ValueError('Confira o conselho profissional. O médico deste simulador é o CRM fictício dos exemplos.')
    from prescription_layout import doctor_name
    if doctor_name(fields['Medico']['value']) != doctor_name('DRA EXEMPLO SINTETICA'):
        raise ValueError('O nome do solicitante diverge do médico fictício cadastrado. Confira nome, conselho, número e UF.')
    mapped = result['payer_mapping']['values']
    destinations = {'guide': 'Guia', 'main_guide': 'Guia principal',
                    'operator_guide': 'Guia operadora', 'password': 'Senha/Autorização'}
    if any(key not in mapped for key in ['Matrícula', *destinations.values()]):
        raise ValueError('O perfil precisa mapear explicitamente matrícula, guias e autorização. Não será escolhido um número por semelhança.')
    exams = []
    for row in result['exames']:
        code = row.get('tuss', '')
        if row.get('codigo_shift') != 'SIM-LAB-' + code:
            raise ValueError('Use o catálogo fictício SIM-LAB dos exemplos. Códigos reais do laboratório não são enviados ao treinamento.')
        quantity = str(row['pedido'])
        if not quantity.isdigit():
            raise ValueError('Confira a quantidade de cada procedimento antes de simular.')
        exams.append({'code': code, 'quantity': int(quantity)})
    patient = {'nome': fields['Paciente']['value'], 'carteira': mapped['Matrícula']}
    birth = models['pedido']['fields']['Nascimento']['value'] or fields['Nascimento']['value']
    if birth: patient['nascimento'] = birth
    data = {'patient': patient, 'case_id': cid, 'payer': 'FONTE-FICTICIA',
            **{key: mapped[dest] for key, dest in destinations.items()},
            'crm': fields['Número conselho']['value'], 'uf': fields['UF conselho']['value'], 'exams': exams}
    sources = verified_sources(obj['docs'], store.data_dir)
    roles = {}
    for role in ['pedido', 'guia']:
        doc = obj['docs'][role]
        originals = doc.get('original_sources') or ([doc] if doc.get('local_path') and not doc.get('scan_batch') else [])
        roles[role] = sorted({s['sha256'] for s in originals if s['sha256'] in sources})
    envelope = {'tipo': 'PRE_CADASTRO_PARA_LIS_FICTICIO', 'permite_producao': False,
                'caso': cid, 'revision': rev, 'output_hash': digest(output),
                'data': data, 'approval': approve(data, reviewer, checks),
                'files': [{'path': str(path), 'sha256': sha} for sha, path in sorted(sources.items())],
                'document_roles': roles,
                'mapping': {'ambiente': 'SIMULADOR_LOCAL', 'perfil_origem': profile['id'],
                            'fonte_origem': profile['fonte_pagadora'], 'fonte_destino': 'FONTE-FICTICIA',
                            'procedimentos': [{'tuss': r['tuss'], 'codigo_interno_ficticio': r['codigo_shift']} for r in result['exames']]}}
    envelope['snapshot_hash'] = _snapshot_hash(envelope)
    validate_handoff(envelope)
    return copy.deepcopy(envelope)


def record_result(store, envelope, result):
    """Rastreia a demonstração separadamente, sem marcar envio ou O.S. real."""
    if envelope.get('snapshot_hash') != _snapshot_hash(envelope):
        raise ValueError('A revisão entregue ao simulador foi alterada.')
    if not isinstance(result, dict) or result.get('ficticio') is not True or result.get('os_real') is not None or not re.fullmatch(r'OS-SIM-[a-f0-9]{8}', result.get('os_simulada', '')):
        raise ValueError('Resultado incompatível com o simulador fictício.')
    with store.db:
        store.db.execute('BEGIN IMMEDIATE')
        _, rev, status, output = store.get(envelope['caso'])
        if status != 'PREPARADO' or rev != envelope['revision'] or digest(output) != envelope['output_hash']:
            raise ValueError('O atendimento mudou. A demonstração não será atribuída a outra revisão.')
        store.db.execute('CREATE TABLE IF NOT EXISTS integracao_simulada(caso TEXT,revision INTEGER,entrega_hash TEXT,resultado TEXT,PRIMARY KEY(caso,revision))')
        store.db.execute('INSERT INTO integracao_simulada VALUES(?,?,?,?)',
                         (envelope['caso'], rev, envelope['snapshot_hash'], json.dumps(result, ensure_ascii=False)))
        store.audit(envelope['caso'], 'RPA_SIMULADA', {'revisao': rev})
