"""Simulação funcional em loopback, dados fictícios, sem credenciais ou acesso ao Shift."""
import json,threading,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from core import norm,digest

class SimulatedShift:
 def __init__(self):
  self.patients=[{'id':'SIM-P1','nome':'PESSOA FICTICIA ALFA','nascimento':'01/02/1995','carteira':'0000087654'},
                 {'id':'SIM-P2','nome':'PESSOA FICTICIA ALFA','nascimento':'03/04/1990','carteira':'0000099999'}]
  self.doctors=[{'id':'SIM-M1','nome':'DRA EXEMPLO SINTETICA','crm':'0012345','uf':'GO'}]
  self.confirmed={};self.orders={}
 def search(self,query):
  keys=[k for k in ['nome','nascimento','carteira'] if query.get(k)]
  if len(keys)<2:raise ValueError('Pesquisa requer dois identificadores; nome isolado não basta.')
  return [p for p in self.patients if all(norm(p[k])==norm(query[k]) for k in keys)]
 def confirm(self,query,patient_id,reviewed):
  matches=self.search(query)
  if not reviewed or len(matches)!=1 or matches[0]['id']!=patient_id:raise ValueError('Identidade ambígua ou não conferida.')
  token=uuid.uuid4().hex;self.confirmed[token]=patient_id;return token
 def doctor(self,crm,uf):
  matches=[d for d in self.doctors if d['crm']==crm and d['uf']==norm(uf)]
  if len(matches)!=1:raise ValueError('Solicitante não encontrado. Não cadastrar automaticamente.')
  return matches[0]
 def create_patient(self,patient,approved=False):
  if not approved or not all(patient.get(k) for k in ['nome','nascimento','carteira']):raise ValueError('Novo paciente exige dados suficientes e aprovação explícita.')
  if any(p['carteira']==patient['carteira'] or (norm(p['nome'])==norm(patient['nome']) and p['nascimento']==patient['nascimento']) for p in self.patients):raise ValueError('Paciente já existente ou possível duplicidade.')
  record={**patient,'id':'SIM-P-'+uuid.uuid4().hex[:8]};self.patients.append(record);return record
 def prepare(self,data):
  if not data.get('reviewed') or data.get('token') not in self.confirmed:raise ValueError('Revisão humana e identidade confirmada são obrigatórias.')
  doctor=self.doctor(data.get('crm',''),data.get('uf',''))
  if not data.get('case_id') or not data.get('payer') or not data.get('guide'):raise ValueError('Atendimento, fonte pagadora e guia obrigatórios nesta simulação.')
  if not data.get('exams') or any(e.get('code') not in ['90000001','90000002','90000003','90000004','90000005'] or not isinstance(e.get('quantity'),int) or e['quantity']<=0 for e in data['exams']):raise ValueError('Procedimentos fictícios/quantidades inválidos.')
  if data['case_id'] in self.orders:raise ValueError('Atendimento já processado na simulação.')
  if len(data.get('attachments',[]))!=2:raise ValueError('Anexe pedido e autorização fictícios.')
  result={'os_simulada':'OS-SIM-'+uuid.uuid4().hex[:8],'os_real':None,'ficticio':True,'patient_id':self.confirmed[data['token']],
          'doctor_id':doctor['id'],'case_id':data['case_id'],'labels':'SOMENTE ETIQUETAS FICTÍCIAS; nenhuma impressão oficial'}
  self.orders[data['case_id']]=result;return result


def start_simulator():
 state=SimulatedShift()
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def send_json(self,value,status=200):
   data=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  def do_GET(self):
   if self.path!='/':self.send_error(404);return
   content=(Path(__file__).parent/'simulador_web/index.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
  def do_POST(self):
   # Reject foreign browser origins; no service binds outside loopback.
   if self.headers.get('Host') not in ['127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)]:self.send_error(403);return
   if self.headers.get('Origin') not in [None,'http://'+self.headers.get('Host','')]:self.send_error(403);return
   try:
    length=int(self.headers.get('Content-Length',0))
    if not 0<length<=65536:raise ValueError('Requisição inválida.')
    data=json.loads(self.rfile.read(length))
    if self.path=='/search':result=state.search(data)
    elif self.path=='/confirm':result={'token':state.confirm(data['query'],data['patient_id'],data.get('reviewed'))}
    elif self.path=='/doctor':result=state.doctor(data['crm'],data['uf'])
    elif self.path=='/new-patient':result=state.create_patient(data.get('patient',{}),data.get('approved',False))
    elif self.path=='/prepare':result=state.prepare(data)
    else:self.send_error(404);return
    self.send_json(result)
   except (ValueError,KeyError,TypeError):self.send_json({'error':'Operação bloqueada: confira identidade, revisão, dados fictícios ou duplicidade.'},400)
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
 class Running:
  url='http://127.0.0.1:'+str(server.server_port)
  def close(self):server.shutdown();server.server_close()
 return Running()

if __name__=='__main__':
 import webbrowser,time
 running=start_simulator();webbrowser.open(running.url)
 try:
  while True:time.sleep(1)
 except KeyboardInterrupt:running.close()
