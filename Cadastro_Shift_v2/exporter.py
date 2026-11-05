import html
import json


def export_order(order, folder):
    if order.get('modo') != 'DEMONSTRACAO' or order.get('os_real') is not None:
        raise ValueError('Somente demonstração permitida.')
    identifier = order['os_simulada']
    if not identifier.startswith('DEMO-') or not identifier[5:].isalnum():
        raise ValueError('Identificador DEMO inválido.')
    esc = lambda value: html.escape(str(value), quote=True)
    labels = []
    for exam in order['exames']:
        labels.append('<article><h2>DEMONSTRAÇÃO</h2><strong>NÃO USAR EM AMOSTRAS REAIS</strong><p>' + esc(order['paciente']['Paciente']) + '</p><p>' + esc(exam['nome']) + ' · ' + esc(exam['codigo_shift']) + '</p><p>' + esc(exam['material']) + '</p><small>SEM CÓDIGO DE BARRAS · SEM IDENTIFICAÇÃO OFICIAL</small></article>')
    page = '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>DEMONSTRAÇÃO</title><style>body{font:16px Arial;background:#f5f7fa;padding:30px}article{border:3px dashed #a22;background:white;padding:20px;margin:15px;max-width:520px}h2{color:#a22}</style><h1>Etiquetas fictícias — DEMONSTRAÇÃO</h1><p>Somente visualização. Não identificar amostras.</p>' + ''.join(labels) + '</html>'
    folder.mkdir(parents=True, exist_ok=True)
    paths = [folder / (identifier + '.json'), folder / (identifier + '_etiquetas_DEMO.html')]
    paths[0].write_text(json.dumps(order, indent=2, ensure_ascii=False), encoding='utf-8')
    paths[1].write_text(page, encoding='utf-8')
    return paths
