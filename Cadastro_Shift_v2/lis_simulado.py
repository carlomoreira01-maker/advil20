"""LIS exclusivo de treinamento. Só aceita os pacientes/códigos sintéticos definidos aqui."""
import hashlib,json,sqlite3,threading,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from core import digest

APPROVALS=('identidade','fonte_pagadora','medico','exames','autorizacao')
PATIENTS=[{'id':'SIM-P1','nome':'PESSOA FICTICIA DE OLIVEIRA','nascimento':'01/02/1995','carteira':'0000087654'},
          {'id':'SIM-P2','nome':'PESSOA FICTICIA DOS SANTOS','nascimento':'03/04/1990','carteira':'0000099999'}]
CODES=['90000001','90000002','90000003','90000004','90000005']

def demo_data():
    return {'patient':{k:v for k,v in PATIENTS[0].items() if k!='id'},'case_id':'DEMO-ATENDIMENTO-1',
        'payer':'FONTE-FICTICIA','guide':'00000111','main_guide':'00000222','operator_guide':'00000777','password':'00000555',
        'crm':'0012345','uf':'GO','exams':[{'code':c,'quantity':1} for c in CODES]}

def approve(data,reviewer,checks):
    if not reviewer.strip() or not all(checks.get(k) is True for k in APPROVALS):raise ValueError('Confira identidade, fonte pagadora, médico, exames e autorização e informe o revisor.')
    return {'reviewer':reviewer.strip(),'checks':dict(checks),'data_hash':digest(data)}

class Simulation:
    def __init__(self,data,approval,attachments,db_path=':memory:'):
        if approval.get('data_hash')!=digest(data) or not approval.get('reviewer') or not all(approval.get('checks',{}).get(k) is True for k in APPROVALS):raise ValueError('Dados alterados ou aprovação humana incompleta.')
        query={k:v for k,v in data.get('patient',{}).items() if v}
        if len(query)<2:raise ValueError('Dados faltantes: informe pelo menos dois identificadores do paciente; dados restantes podem ser reutilizados do cadastro confirmado.')
        if not set(query)<={'nome','nascimento','carteira'}:raise ValueError('Identificador desconhecido.')
        matches=[p for p in PATIENTS if all(p[k]==v for k,v in query.items())]
        if len(matches)!=1 or data.get('payer')!='FONTE-FICTICIA' or data.get('crm')!='0012345' or data.get('uf')!='GO':raise ValueError('Simulador aceita somente o cadastro fictício conhecido. Dados reais são bloqueados.')
        if any(data.get(k)!=demo_data()[k] for k in ['guide','main_guide','operator_guide','password']):raise ValueError('Use apenas as guias e autorizações fictícias do treinamento.')
        exams=data.get('exams',[])
        if not data.get('case_id') or not exams or len({e['code'] for e in exams})!=len(exams) or any(e.get('code') not in CODES or type(e.get('quantity')) is not int or not 1<=e['quantity']<=99 for e in exams):raise ValueError('Procedimentos/quantidades fictícios inválidos.')
        self.data=json.loads(json.dumps(data));self.approval=approval;self.patient=matches[0];self.nonce=uuid.uuid4().hex;self.selected=False;self.order=None
        if len(attachments)!=2 or len({a.get('name') for a in attachments})!=2 or any(len(a.get('sha256',''))!=64 for a in attachments):raise ValueError('Dois anexos fictícios identificados por SHA-256 são obrigatórios.')
        self.attachments=attachments;self.lock=threading.Lock();self.db=sqlite3.connect(db_path,check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS os_demo(caso TEXT UNIQUE,chave TEXT UNIQUE,resultado TEXT)');self.db.commit()
    def search(self,query):
        if sum(bool(query.get(k)) for k in ['nome','nascimento','carteira'])<2:raise ValueError('Informe pelo menos dois identificadores.')
        return [p for p in PATIENTS if all(p[k]==v for k,v in query.items() if v)]
    def select(self,request):
        matches=self.search(request.get('query',{}))
        if not request.get('reviewed') or len(matches)!=1 or matches[0]!=self.patient or request.get('id')!=self.patient['id']:raise ValueError('Confira a correspondência única do cadastro existente.')
        self.selected=True;return {'selected':True,'id':self.patient['id']}
    def create(self,request):
        actual=json.loads(json.dumps(request.get('data',{})));expected=json.loads(json.dumps(self.data))
        for value in [actual,expected]:value['patient']={k:v for k,v in value.get('patient',{}).items() if v}
        if not self.selected or request.get('final') is not True or actual!=expected:raise ValueError('Confirmação humana final e dados aprovados sem alterações são obrigatórios.')
        if request.get('attachments')!=self.attachments:raise ValueError('Anexe os dois documentos sintéticos íntegros.')
        key=digest([self.patient['id'],self.data['payer'],self.data['guide']])
        with self.lock:
            if self.db.execute('SELECT 1 FROM os_demo WHERE caso=? OR chave=?',(self.data['case_id'],key)).fetchone():raise ValueError('Possível duplicidade: atendimento ou guia já processados na simulação.')
            result={'os_simulada':'OS-SIM-'+uuid.uuid4().hex[:8],'os_real':None,'patient_id':self.patient['id'],'doctor_id':'SIM-M1','ficticio':True,'labels':['DEMONSTRAÇÃO SEM VALIDADE — '+e['code'] for e in self.data['exams']]}
            with self.db:self.db.execute('INSERT INTO os_demo VALUES(?,?,?)',(self.data['case_id'],key,json.dumps(result)))
            self.order=result;return result

def start_lis(data,approval,attachments,db_path=':memory:'):
    state=Simulation(data,approval,attachments,db_path)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,value,status=200):
            raw=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if self.path!='/':self.send_error(404);return
            raw=(Path(__file__).parent/'simulador_web/lis.html').read_text().replace('__NONCE__',state.nonce).encode()
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_POST(self):
            host='127.0.0.1:'+str(self.server.server_port)
            if self.headers.get('Host')!=host or self.headers.get('Origin') not in [None,'http://'+host] or self.headers.get('X-Demo-Session')!=state.nonce:self.send_error(403);return
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0<length<100000:raise ValueError('Tamanho inválido.')
                q=json.loads(self.rfile.read(length))
                if self.path=='/search':result=state.search(q)
                elif self.path=='/select':result=state.select(q)
                elif self.path=='/order':result=state.create(q)
                else:self.send_error(404);return
                self.reply(result)
            except (ValueError,KeyError,TypeError):self.reply({'error':'Operação bloqueada: confira dados aprovados, identidade, anexos ou possível duplicidade.'},400)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    class Running:
        url='http://127.0.0.1:'+str(server.server_port)
        def close(self):server.shutdown();server.server_close();state.db.close()
    running=Running();running.state=state;return running
