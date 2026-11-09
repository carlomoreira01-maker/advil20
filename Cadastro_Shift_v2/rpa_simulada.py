"""Playwright separado: servidor próprio em loopback; nenhum endereço LIS configurável."""
import hashlib,os,shutil,tempfile
from pathlib import Path
from urllib.parse import urlsplit
from lis_simulado import start_lis,approve,demo_data

class SimulatedRPA:
    def __init__(self,data,approval,db_path=':memory:',headless=False):
        from gerar_exemplos_250 import main
        self.tmp=tempfile.TemporaryDirectory(prefix='shift_treino_');self.server=None;self.browser=None;self.play=None
        try:
            files=main(self.tmp.name);patient=data.get('patient',{});self.paths=[files/'pedido_a.pdf',files/'guia_completa.pdf'] if patient.get('carteira')=='0000087654' or patient.get('nome')=='PESSOA FICTICIA DE OLIVEIRA' else [files/'pedido_b.pdf',files/'guia_b.pdf']
            attachments=[{'name':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in self.paths]
            self.server=start_lis(data,approval,attachments,db_path);self.data=data
            from playwright.sync_api import sync_playwright
            self.play=sync_playwright().start();exe=os.getenv('SHIFT_CHROMIUM') or shutil.which('chromium')
            self.browser=self.play.chromium.launch(headless=headless,chromium_sandbox=True,**({'executable_path':exe} if exe else {}));self.context=self.browser.new_context()
            def route(request):
                u=urlsplit(request.request.url);base=urlsplit(self.server.url)
                request.continue_() if (u.scheme,u.hostname,u.port)==(base.scheme,base.hostname,base.port) else request.abort()
            self.context.route('**/*',route);self.page=self.context.new_page();self.page.goto(self.server.url)
        except Exception:self.close();raise
    def search_patient(self):
        for key,val in self.data['patient'].items():self.page.locator('#'+key).fill(val)
        self.page.locator('#search').click();self.page.wait_for_function("document.querySelector('#patient').textContent.includes('SIM-P')")
    def fill_order(self):
        if not self.server.state.selected:raise ValueError('Confirme manualmente a identidade no navegador antes de preencher a O.S.')
        p=self.page
        for key in ['case_id','guide','main_guide','operator_guide','password','crm','uf']:p.locator('#'+key).fill(self.data[key])
        p.locator('#payer').select_option(self.data['payer']);p.locator('#doctor').click()
        p.locator('#exams').fill('\n'.join(e['code']+';'+str(e['quantity']) for e in self.data['exams']))
        p.locator('#files').set_input_files([str(p) for p in self.paths]);p.wait_for_function("window.attachments && window.attachments.length===2")
    def submit_after_human(self):
        if not self.page.locator('#final').is_checked():raise ValueError('A confirmação final deve ser marcada pelo atendente.')
        self.page.locator('#result').evaluate("element=>element.textContent='Aguardando confirmação local…'")
        self.page.locator('#create').click();self.page.wait_for_function("document.querySelector('#result').textContent.includes('OS-SIM-') || document.querySelector('#result').textContent.includes('bloqueada')")
        if 'bloqueada' in self.page.locator('#result').inner_text().lower() or not self.server.state.order:raise ValueError('Simulação bloqueada. Confira dados e duplicidade.')
        self.page.locator('#labels').click();return self.server.state.order
    def interactive(self,cancel=None):
        import time
        def wait(expression):
            end=time.monotonic()+300
            while not self.page.evaluate(expression):
                if cancel is not None and cancel.is_set():raise ValueError('Treinamento encerrado.')
                if time.monotonic()>end:raise ValueError('Tempo de conferência encerrado. Inicie outro treinamento.')
                self.page.wait_for_timeout(150)
        self.search_patient();wait('window.identityConfirmed===true')
        self.fill_order();wait('window.humanFinal===true')
        result=self.submit_after_human();self.page.wait_for_timeout(1000);return result
    def close(self):
        if self.browser:self.browser.close();self.browser=None
        if self.play:self.play.stop();self.play=None
        if self.server:self.server.close();self.server=None
        self.tmp.cleanup()
