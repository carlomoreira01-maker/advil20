import os,unittest
from pathlib import Path

@unittest.skipUnless(os.getenv('SHIFT_BROWSER_TESTS')=='1','Teste de navegador opcional: SHIFT_BROWSER_TESTS=1')
class BrowserSimulation(unittest.TestCase):
 def setUp(self):
  from simulador import start_simulator
  from playwright.sync_api import sync_playwright
  self.server=start_simulator();self.play=sync_playwright().start()
  self.browser=self.play.chromium.launch(executable_path='/usr/bin/chromium',headless=True,chromium_sandbox=True)
  self.page=self.browser.new_page();self.page.goto(self.server.url)
 def tearDown(self):self.browser.close();self.play.stop();self.server.close()
 def test_fluxo_ficticio_com_revisao_e_bloqueio_duplicidade(self):
  p=self.page;p.locator('#search').click();p.locator('#identity').check();p.locator('#confirm').click()
  p.wait_for_function("document.querySelector('#status').textContent.includes('Identidade confirmada')")
  p.locator('#doctor').click();p.wait_for_function("document.querySelector('#status').textContent.includes('Solicitante fictício')")
  p.locator('#files').set_input_files([{'name':'pedido_ficticio.txt','mimeType':'text/plain','buffer':b'FICTICIO'}, {'name':'guia_ficticia.txt','mimeType':'text/plain','buffer':b'FICTICIO'}])
  p.locator('#review').check();p.locator('#prepare').click()
  p.wait_for_function("document.querySelector('#status').textContent.includes('OS-SIM-')")
  self.assertIn('"os_real": null',p.locator('#status').inner_text())
  p.locator('#prepare').click();p.wait_for_function("document.querySelector('#status').textContent.includes('bloqueada')")
 def test_nome_isolado_e_sem_confirmacao_nao_processam(self):
  p=self.page;p.locator('#nascimento').fill('');p.locator('#carteira').fill('');p.locator('#search').click()
  p.wait_for_function("document.querySelector('#status').textContent.includes('bloqueada')")
  p.locator('#prepare').click();self.assertNotIn('OS-SIM-',p.locator('#status').inner_text())
 def test_alterar_identidade_revoga_confirmacao(self):
  p=self.page;p.locator('#search').click();p.locator('#identity').check();p.locator('#confirm').click()
  p.wait_for_function("document.querySelector('#status').textContent.includes('Identidade confirmada')")
  p.locator('#carteira').fill('0000099999');self.assertFalse(p.locator('#identity').is_checked())
  p.locator('#prepare').click();p.wait_for_function("document.querySelector('#status').textContent.includes('bloqueada')")
