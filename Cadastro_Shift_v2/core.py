"""Domínio DEMO: sem rede, sem integrações e sem códigos clínicos reais."""
import hashlib
import json
import re
import sqlite3
import unicodedata
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

MODE = 'DEMONSTRACAO'
FIELDS = ['Paciente', 'Nascimento', 'Convenio', 'Guia', 'Medico', 'Validade', 'Status']


def norm(s):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', s.upper()) if not unicodedata.combining(c)).split())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def catalog_load(path):
    rows = json.loads(Path(path).read_text(encoding='utf-8'))
    seen = set()
    for r in rows:
        if not r['codigo_shift'].startswith('DEMO-') or r.get('tuss'):
            raise ValueError('Nesta versão, somente códigos DEMO- e TUSS vazio são permitidos.')
        if r['codigo_shift'] in seen or not r['nome'] or not r['material']:
            raise ValueError('Catálogo inválido: código repetido ou campo obrigatório vazio.')
        seen.add(r['codigo_shift'])
        if not isinstance(r['sinonimos'], list):
            raise ValueError('Sinônimos precisam ser uma lista.')
    if not rows:
        raise ValueError('Catálogo vazio.')
    return rows


def parse(text):
    """Parser conservador do modelo sintético. Não interpreta prosa nem manuscritos."""
    fields, exams, errors, in_exams = {}, [], [], False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if norm(line) in ('DEMONSTRACAO', 'PEDIDO MEDICO', 'GUIA AUTORIZADA'):
            continue
        if norm(line) == 'EXAMES:':
            in_exams = True
            continue
        if in_exams:
            parts = [v.strip() for v in line.split('|')]
            if len(parts) != 3 or not parts[1].isdigit() or not 1 <= int(parts[1]) <= 99:
                errors.append('Linha de exame inválida: ' + line)
            else:
                exams.append({'texto': parts[0], 'quantidade': int(parts[1]), 'codigo': parts[2]})
            continue
        if ':' in line:
            key, val = line.split(':', 1)
            known = next((k for k in FIELDS if norm(k) == norm(key)), None)
            if known and known not in fields:
                fields[known] = val.strip()
            else:
                errors.append('Campo desconhecido ou repetido: ' + key)
        else:
            errors.append('Texto fora do modelo: ' + line)
    if 'DEMONSTRACAO' not in [norm(l) for l in text.splitlines()]:
        errors.append('Falta a marca DEMONSTRAÇÃO em linha própria.')
    if not exams:
        errors.append('Nenhum exame estruturado encontrado.')
    return {'campos': fields, 'exames': exams, 'erros': errors}


def resolve(exam, catalog):
    candidates = [r for r in catalog if norm(exam['texto']) in {norm(x) for x in [r['nome'], *r['sinonimos']]}]
    if len(candidates) != 1:
        return None, 'Exame desconhecido ou ambíguo: ' + exam['texto']
    row = candidates[0]
    if exam['codigo'] != row['codigo_shift']:
        return None, 'Código ausente ou divergente: ' + exam['texto']
    return row, None


def compare(pedido, guia, catalog, today=None):
    p, g = parse(pedido), parse(guia)
    errors = ['Pedido: ' + e for e in p['erros']] + ['Guia: ' + e for e in g['erros']]
    for key in ['Paciente', 'Convenio', 'Guia', 'Medico']:
        for title, obj in [('Pedido', p), ('Guia', g)]:
            if not obj['campos'].get(key):
                errors.append(f'{title}: falta {key}.')
        if norm(p['campos'].get(key, '')) != norm(g['campos'].get(key, '')):
            errors.append(f'Divergência de {key}.')
    for obj in [p, g]:
        dob = obj['campos'].get('Nascimento', '')
        if dob:
            try:
                if datetime.strptime(dob, '%d/%m/%Y').date() > (today or date.today()):
                    raise ValueError()
            except ValueError:
                errors.append('Data de nascimento inválida.')
    if p['campos'].get('Nascimento', '') != g['campos'].get('Nascimento', ''):
        errors.append('Nascimento divergente ou presente somente em um documento.')
    try:
        if datetime.strptime(g['campos'].get('Validade', ''), '%d/%m/%Y').date() < (today or date.today()):
            errors.append('Guia vencida.')
    except ValueError:
        errors.append('Validade da guia ausente ou inválida.')
    if norm(g['campos'].get('Status', '')) != 'AUTORIZADO':
        errors.append('Status da guia não é AUTORIZADO.')
    maps = []
    for title, obj in [('Pedido', p), ('Guia', g)]:
        found = {}
        for exam in obj['exames']:
            row, error = resolve(exam, catalog)
            if error:
                errors.append(title + ': ' + error)
            else:
                code = row['codigo_shift']
                if code in found:
                    errors.append(title + ': exame repetido ' + code)
                found[code] = {**row, 'quantidade': exam['quantidade']}
        maps.append(found)
    rows = []
    for code in sorted(set(maps[0]) | set(maps[1])):
        a, b = maps[0].get(code), maps[1].get(code)
        ok = bool(a and b and a['quantidade'] == b['quantidade'])
        if not ok:
            errors.append('Exame ausente ou quantidade divergente: ' + code)
        rows.append({**(a or b), 'pedido': a['quantidade'] if a else 0, 'guia': b['quantidade'] if b else 0, 'situacao': 'Conferir' if ok else 'DIVERGENTE'})
    return {'paciente': p['campos'], 'guia': g['campos'], 'exames': rows, 'pendencias': errors, 'catalogo_hash': digest(catalog)}


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, source_key TEXT UNIQUE, original TEXT NOT NULL, current TEXT NOT NULL, revision INTEGER NOT NULL, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, case_id TEXT, action TEXT NOT NULL, detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, case_id TEXT UNIQUE REFERENCES cases(id), identity_key TEXT UNIQUE, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS case_revisions(case_id TEXT, revision INTEGER, payload TEXT, PRIMARY KEY(case_id,revision));
        ''')
        self.db.commit()

    def audit(self, actor, cid, action, detail):
        # Mesmo no DEMO v1: texto clínico/revisor ficam nos dados do caso, não em logs.
        safe={'evento':action}
        if isinstance(detail,dict):
            if 'antes' in detail:safe.update(antes='registro local do caso',depois='registro local do caso')
            if 'revisao_anterior' in detail:safe['revisao_anterior']=detail['revisao_anterior']
        self.db.execute('INSERT INTO audit(at,actor,case_id,action,detail) VALUES(?,?,?,?,?)', (datetime.now(timezone.utc).isoformat(), 'LOCAL', cid, action, json.dumps(safe, ensure_ascii=False)))

    def add(self, pedido, guia, actor, sources=None):
        key = digest([pedido, guia])
        cid = str(uuid.uuid4())
        obj = json.dumps({'pedido': pedido, 'guia': guia, 'fontes': sources or {}}, ensure_ascii=False)
        try:
            with self.db:
                self.db.execute('INSERT INTO cases VALUES(?,?,?,?,?,?)', (cid, key, obj, obj, 1, 'PENDENTE'))
                self.audit(actor, cid, 'IMPORTACAO', {'originais': json.loads(obj), 'hash': key})
        except sqlite3.IntegrityError as e:
            raise ValueError('Este par de documentos já foi importado.') from e
        return cid

    def list(self):
        return self.db.execute('SELECT id,current,revision,status FROM cases ORDER BY rowid').fetchall()

    def get(self, cid):
        row = self.db.execute('SELECT current,revision,status,original FROM cases WHERE id=?', (cid,)).fetchone()
        if row is None:
            raise ValueError('Caso inexistente.')
        return json.loads(row[0]), row[1], row[2], json.loads(row[3])

    def edit(self, cid, pedido, guia, actor, reason):
        if not actor.strip() or not reason.strip():
            raise ValueError('Informe revisor e motivo da alteração.')
        before, rev, status, _ = self.get(cid)
        if status == 'SIMULADO':
            raise ValueError('Caso já simulado: histórico preservado, edição bloqueada.')
        after = {**before, 'pedido': pedido, 'guia': guia}
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO case_revisions VALUES(?,?,?)', (cid,rev,json.dumps(before,ensure_ascii=False)))
            self.db.execute('INSERT INTO case_revisions VALUES(?,?,?)', (cid,rev+1,json.dumps({'dados':after,'revisor':actor,'motivo':reason},ensure_ascii=False)))
            self.db.execute('UPDATE cases SET current=?,revision=revision+1 WHERE id=?', (json.dumps(after, ensure_ascii=False), cid))
            self.audit(actor, cid, 'CORRECAO', {'motivo': reason, 'antes': before, 'depois': after, 'revisao_anterior': rev})

    def simulate(self, cid, catalog, actor, reviewed, expected_revision, expected_hash, today=None):
        if not actor.strip() or not reviewed:
            raise ValueError('Revisão humana obrigatória.')
        with self.db:
            # Lock before reading prevents simultaneous approval of stale data.
            self.db.execute('BEGIN IMMEDIATE')
            current, rev, status, _ = self.get(cid)
            if status == 'SIMULADO' or rev != expected_revision or digest(catalog) != expected_hash:
                raise ValueError('Caso já simulado ou revisão/catálogo mudou. Confira novamente.')
            result = compare(current['pedido'], current['guia'], catalog, today)
            if result['pendencias']:
                raise ValueError('Há pendências; simulação bloqueada.')
            identity = digest([norm(result['paciente']['Paciente']), result['paciente'].get('Nascimento', ''), norm(result['paciente']['Convenio']), norm(result['paciente']['Guia'])])
            oid = 'DEMO-' + uuid.uuid4().hex[:12].upper()
            payload = {'modo': MODE, 'os_simulada': oid, 'os_real': None, 'revisor': actor, 'revisao': rev, 'caso': cid, 'documentos_hash': digest(current), **result}
            try:
                self.db.execute('INSERT INTO orders VALUES(?,?,?,?)', (oid, cid, identity, json.dumps(payload, ensure_ascii=False)))
            except sqlite3.IntegrityError as e:
                raise ValueError('Possível duplicidade de paciente/convênio/guia. Bloqueado.') from e
            self.db.execute("UPDATE cases SET status='SIMULADO' WHERE id=?", (cid,))
            self.audit(actor, cid, 'REVISAO_E_SIMULACAO', payload)
            return payload

    def order(self, cid):
        row = self.db.execute('SELECT payload FROM orders WHERE case_id=?', (cid,)).fetchone()
        return json.loads(row[0]) if row else None
