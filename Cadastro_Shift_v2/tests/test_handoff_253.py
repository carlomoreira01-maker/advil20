"""Do PDF importado pela interface ao navegador: somente pacientes sintéticos."""
import copy
import hashlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from core import digest
from engine_v2 import CaseStore
from gerar_exemplos_250 import main, PATIENTS, CLINICAL, EXECUTOR, PRIORITY
from gerar_exemplos_tiss import catalog, VALUES
from lis_simulado import APPROVALS, Simulation, approve, demo_data
from rpa_handoff import build_handoff, validate_handoff, record_result
from scan_import import read_scan, save_batch, confirm_group
from tests.test_mapping_sim import profile

ROWS = []


def prepared(base, source, *, name=None, doctor=None, prepare=True):
    cat = catalog()
    for row in cat: row['codigo_shift'] = 'SIM-LAB-' + row['tuss']
    batch = read_scan([source], base, cat, mode='single')
    confirm_group(batch, 'Atendimento 1', 'REVISOR FICTICIO', 'Conferência fictícia', {p['id'] for p in batch['pages']})
    store = CaseStore(Path(base) / 'base.sqlite3')
    cid = save_batch(store, batch, cat, 'REVISOR FICTICIO')[0]
    obj, rev, _, _ = store.get(cid); models = obj['models']
    models['guia']['payer_profile'] = profile()
    for m in models.values():
        if name: m['fields']['Paciente']['value'] = name
        if doctor: m['fields']['Medico']['value'] = doctor
        m['pages_reviewed'] = True
        for f in m['fields'].values(): f['reviewed'] = True
        for e in m['exams']: e['reviewed'] = True
        for i in m['issues']: i.update(reviewed=True, reason='Conferência fictícia')
    store.save(cid, models, 'REVISOR FICTICIO', 'Conferência fictícia', rev)
    if prepare: store.prepare(cid, cat, 'REVISOR FICTICIO', rev + 1, digest(cat), True)
    return store, cid, cat, rev + 1


class Handoff253(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory(); cls.files = main(cls.fixtures.name)
    @classmethod
    def tearDownClass(cls): cls.fixtures.cleanup()
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store, self.cid, self.cat, self.rev = prepared(self.tmp.name, self.files / '01_um_paciente.pdf')
    def tearDown(self): self.store.db.close(); self.tmp.cleanup()
    def build(self, **kwargs):
        args = {'expected_revision': self.rev, 'reviewer': 'REVISOR FICTICIO',
                'checks': {k: True for k in APPROVALS}, 'synthetic_confirmed': True}
        args.update(kwargs)
        return build_handoff(self.store, self.cid, self.cat, **args)
    def test_entrega_valores_aprovados_e_um_pdf_integral_para_duas_funcoes(self):
        envelope = self.build(); data = envelope['data']
        expected = demo_data(); expected['case_id'] = self.cid
        self.assertEqual(data, expected)
        self.assertFalse(envelope['permite_producao'])
        self.assertEqual(len(envelope['files']), 1)
        sha = envelope['files'][0]['sha256']
        self.assertEqual(envelope['document_roles'], {'pedido': [sha], 'guia': [sha]})
        self.assertEqual(hashlib.sha256(Path(envelope['files'][0]['path']).read_bytes()).hexdigest(), sha)
    def test_rascunho_nao_substitui_pre_cadastro_validado(self):
        self.store.db.execute("UPDATE casos_v2 SET status='CONFERIR',output=NULL WHERE id=?", (self.cid,)); self.store.db.commit()
        with self.assertRaisesRegex(ValueError, 'Conclua a conferência'): self.build()
    def test_revisao_antiga_nao_e_aprovada(self):
        with self.assertRaisesRegex(ValueError, 'mudou'): self.build(expected_revision=self.rev - 1)
    def test_catalogo_alterado_nao_reutiliza_aprovacao(self):
        self.cat[0]['codigo_shift'] = 'OUTRO-CODIGO-FICTICIO'
        with self.assertRaisesRegex(ValueError, 'catálogo mudaram'): self.build()
    def test_cinco_confirmacoes_e_revisor_sao_obrigatorios(self):
        for key in APPROVALS:
            checks = {k: k != key for k in APPROVALS}
            with self.subTest(grupo=key), self.assertRaises(ValueError): self.build(checks=checks)
        with self.assertRaises(ValueError): self.build(reviewer='')
    def test_confirmacao_explicita_de_dados_ficticios(self):
        with self.assertRaisesRegex(ValueError, 'inteiramente fictícios'): self.build(synthetic_confirmed=False)
    def test_original_alterado_depois_da_preparacao_bloqueia(self):
        e = self.build(); Path(e['files'][0]['path']).write_bytes(b'ALTERACAO INTEIRAMENTE FICTICIA')
        with self.assertRaisesRegex(ValueError, 'alterada'): self.build()
        with self.assertRaisesRegex(ValueError, 'alterado'): validate_handoff(e)
    def test_dados_mutados_no_transporte_bloqueiam(self):
        e = self.build(); e['data']['guide'] = 'NUMERO DIFERENTE FICTICIO'
        with self.assertRaisesRegex(ValueError, 'alterada'): validate_handoff(e)
    def test_paciente_fora_do_treinamento_nao_cai_em_demonstracao_generica(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, cid, cat, rev = prepared(tmp, self.files / '01_um_paciente.pdf', name='OUTRA PESSOA INTEIRAMENTE FICTICIA')
            try:
                with self.assertRaisesRegex(ValueError, 'fictício conhecido'):
                    build_handoff(s, cid, cat, expected_revision=rev, reviewer='REVISOR FICTICIO', checks={k: True for k in APPROVALS}, synthetic_confirmed=True)
            finally: s.db.close()
    def test_anexo_unico_precisa_comprovar_as_duas_funcoes(self):
        data = demo_data(); approval = approve(data, 'REVISOR FICTICIO', {k: True for k in APPROVALS})
        attachments = [{'name': 'documento.pdf', 'sha256': '0' * 64}]
        for roles in [None, {'pedido': ['0' * 64]}, {'pedido': ['0' * 64], 'guia': ['1' * 64]}, {'pedido': [], 'guia': ['0' * 64]}]:
            with self.subTest(roles=roles), self.assertRaises(ValueError): Simulation(data, approval, attachments, document_roles=roles)
    def test_registro_da_simulacao_preserva_pre_cadastro_e_log_sem_dados_pessoais(self):
        e = self.build(); before = self.store.get(self.cid)
        result = {'os_simulada': 'OS-SIM-1234abcd', 'ficticio': True, 'os_real': None}
        record_result(self.store, e, result)
        self.assertEqual(self.store.get(self.cid), before)
        rows = self.store.db.execute('SELECT caso,revision FROM integracao_simulada').fetchall()
        self.assertEqual(rows, [(self.cid, self.rev)])
        audit = str(self.store.db.execute("SELECT detalhe FROM audit_v2 WHERE acao='RPA_SIMULADA'").fetchall())
        for value in ['PESSOA', '0012345', '0000087654']: self.assertNotIn(value, audit)
    def test_resultado_real_nao_pode_ser_marcado_como_simulacao(self):
        with self.assertRaises(ValueError): record_result(self.store, self.build(), {'os_simulada': 'OS-SIM-1234abcd', 'os_real': 'REAL-FICTICIO', 'ficticio': True})
    def test_nome_do_medico_divergente_nao_seleciona_so_pelo_crm(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, cid, cat, rev = prepared(tmp, self.files / '01_um_paciente.pdf', doctor='DRA OUTRA PESSOA FICTICIA')
            try:
                with self.assertRaisesRegex(ValueError, 'nome do solicitante'):
                    build_handoff(s, cid, cat, expected_revision=rev, reviewer='REVISOR FICTICIO', checks={k: True for k in APPROVALS}, synthetic_confirmed=True)
            finally: s.db.close()


@unittest.skipUnless(os.getenv('SHIFT_BROWSER_TESTS') == '1', 'Requer navegador local')
class BrowserHandoff253(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gerar_exemplos_2_4 import combine
        cls.fixtures = tempfile.TemporaryDirectory(); cls.files = main(cls.fixtures.name)
        combine(cls.files / 'um_paciente_b.pdf', [cls.files / 'pedido_b.pdf', cls.files / 'guia_b.pdf'])
    @classmethod
    def tearDownClass(cls): cls.fixtures.cleanup()
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.store = None; self.rpa = None
    def tearDown(self):
        if self.rpa: self.rpa.close()
        if self.store: self.store.db.close()
        self.tmp.cleanup()
    def open(self, file='01_um_paciente.pdf'):
        from rpa_simulada import SimulatedRPA
        self.store, self.cid, cat, rev = prepared(self.tmp.name, self.files / file)
        self.envelope = build_handoff(self.store, self.cid, cat, expected_revision=rev, reviewer='REVISOR FICTICIO', checks={k: True for k in APPROVALS}, synthetic_confirmed=True)
        self.rpa = SimulatedRPA.from_handoff(self.envelope, db_path=Path(self.tmp.name) / 'demo.sqlite3', headless=True)
    def confirm(self):
        self.rpa.search_patient(); p = self.rpa.page
        p.locator('#identity').check(); p.locator('#select').click(); p.wait_for_function('window.identityConfirmed===true')
        self.rpa.fill_order(); p.locator('#final').check()
    def test_segundo_paciente_nao_recebe_anexos_ou_identidade_do_primeiro(self):
        self.open('um_paciente_b.pdf'); self.confirm()
        self.assertEqual(self.rpa.page.locator('#nome').input_value(), PATIENTS[1])
        self.assertEqual(self.rpa.page.locator('#carteira').input_value(), '0000099999')
        self.assertEqual(self.rpa.submit_after_human()['patient_id'], 'SIM-P2')
        self.assertEqual(self.rpa.page.evaluate('window.attachments')[0]['sha256'], self.envelope['files'][0]['sha256'])
    def test_reabrir_pre_cadastro_nao_gera_segunda_os_ficticia(self):
        from rpa_simulada import SimulatedRPA
        self.open(); self.confirm(); first = self.rpa.submit_after_human(); self.rpa.close()
        self.rpa = SimulatedRPA.from_handoff(self.envelope, db_path=Path(self.tmp.name) / 'demo.sqlite3', headless=True)
        self.confirm()
        with self.assertRaisesRegex(ValueError, 'bloqueada'): self.rpa.submit_after_human()
        self.assertIsNone(first['os_real']); self.assertIsNone(self.rpa.server.state.order)
    def test_cancelamento_antes_e_depois_da_confirmacao_impede_gravacao(self):
        import threading
        self.open(); cancel = threading.Event(); cancel.set()
        with patch.object(self.rpa, 'search_patient', side_effect=AssertionError('Não pesquisar após cancelar')):
            with self.assertRaisesRegex(ValueError, 'encerrado'): self.rpa.interactive(cancel)
        cancel.clear(); self.confirm(); original = self.rpa.fill_order
        def fill_and_cancel():
            original(); self.rpa.page.locator('#final').check(); self.rpa.page.evaluate('window.humanFinal=true'); cancel.set()
        with patch.object(self.rpa, 'search_patient', return_value=None), patch.object(self.rpa, 'fill_order', side_effect=fill_and_cancel):
            with self.assertRaisesRegex(ValueError, 'encerrado'): self.rpa.interactive(cancel)
        self.assertIsNone(self.rpa.server.state.order)


@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS') == '1' and os.getenv('SHIFT_BROWSER_TESTS') == '1', 'Requer Tk e navegador locais')
class IntegratedHandoff253(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = tempfile.TemporaryDirectory(); cls.files = main(cls.fixtures.name)
    @classmethod
    def tearDownClass(cls): cls.fixtures.cleanup()
    def setUp(self):
        import tkinter as tk
        from workbench import create_workbench
        self.tmp = tempfile.TemporaryDirectory(); self.root = tk.Tk()
        self.app = create_workbench(self.root, Path(self.tmp.name) / 'dados')
        self.ui = self.app.workspace; self.app.catalog = catalog(); self.root.update()
        for row in self.app.catalog: row['codigo_shift'] = 'SIM-LAB-' + row['tuss']
    def tearDown(self):
        state = getattr(self.app, 'rpa_case_simulation', None)
        if state:
            state['stop'].set()
            end = time.monotonic() + 15
            while state['busy'] and time.monotonic() < end: self.root.update(); time.sleep(.01)
        self.app.store.db.close(); self.root.destroy(); self.tmp.cleanup()
    def check(self, name, expected, actual):
        ROWS.append({'teste': self.id().split('.')[-1], 'verificacao': name, 'esperado': expected, 'encontrado': actual, 'passou': expected == actual})
        self.assertEqual(actual, expected, name)
    def wait(self, predicate, timeout=60):
        end = time.monotonic() + timeout
        while not predicate() and time.monotonic() < end: self.root.update(); time.sleep(.01)
        self.assertTrue(predicate(), 'Ação da interface não concluiu no tempo previsto')
        self.root.update()
    def prepare_ui(self, file='01_um_paciente.pdf'):
        with patch('app.filedialog.askopenfilenames', return_value=[str(self.files / file)]):
            self.ui.import_buttons['single'].invoke(); self.wait(lambda: not self.app.busy)
        self.check('Um atendimento por PDF', 1, len(self.app.cases.get_children()))
        self.app.actor.set('REVISOR FICTICIO')
        if file == '05_leitura_incerta.pdf':
            self.ui.go(2); entry = self.ui.inputs['Número conselho']; entry.delete(0, 'end'); entry.insert(0, '0012345')
            self.ui.save_corrections_button.invoke(); self.root.update()
            self.check('Correção manual persistida', '0012345', self.app.store.get(self.app.cid)[0]['models']['guia']['fields']['Número conselho']['value'])
        self.ui.go(1)
        for b in self.ui.page_panel.buttons: b.invoke(); self.root.update()
        self.check('Classificação por página', ['pedido', 'guia'], [p['kind'] for p in self.ui.page_panel.items])
        with patch('app.messagebox.askyesno', return_value=True): self.ui.confirm_pages_button.invoke()
        self.app.selected_profile = profile(); self.ui.compare_button.invoke(); self.ui.go(4)
        self.ui.data_review.set(True); self.ui.exams_review.set(True); self.ui.validate_button.invoke(); self.root.update()
        self.check('Pendências após conferência', [], self.app.comparison_errors)
        self.ui.final_confirm.set(True); self.ui.prepare_button.invoke(); self.root.update()
        self.check('Pré-cadastro preparado', 'PREPARADO', self.app.store.get(self.app.cid)[2])
    def run_browser_as_human(self, rpa, cancel, run_interactive):
        p = rpa.page
        with self.assertRaises(ValueError): rpa.fill_order()
        with self.assertRaises(ValueError): rpa.submit_after_human()
        # Somente o papel humano é automatizado pelo teste. O orquestrador real
        # pesquisa, aguarda, preenche, aguarda a autorização e submete a O.S.
        p.evaluate('''() => {
            window.testHumanStage=0;
            window.testHumanTimer=setInterval(()=>{
                const e=id=>document.getElementById(id);
                if(window.testHumanStage===0 && e('patient').textContent.includes('SIM-P1')){
                    e('identity').click();e('select').click();window.testHumanStage=1;
                }
                if(window.testHumanStage===1 && window.identityConfirmed &&
                   e('doctor_result').textContent.includes('SIM-M1') && window.attachments.length===1){
                    e('final').click();e('authorize').click();window.testHumanStage=2;
                }
            },80);
        }''')
        result = run_interactive(rpa, cancel)
        p.evaluate('clearInterval(window.testHumanTimer)')
        self.check('Cadastro encontrado', True, 'SIM-P1' in p.locator('#patient').inner_text())
        self.check('Confirmação e autorização pelos botões reais', 2, p.evaluate('window.testHumanStage'))
        data = self.app.rpa_case_simulation['handoff']['data']
        for key in ['case_id', 'payer', 'guide', 'main_guide', 'operator_guide', 'password', 'crm', 'uf']:
            self.check('Navegador: ' + key, data[key], p.locator('#' + key).input_value())
        for key in ['nome', 'nascimento', 'carteira']:
            self.check('Navegador: paciente/' + key, data['patient'][key], p.locator('#' + key).input_value())
        self.check('Procedimentos no navegador', ['90000001;1', '90000002;1', '90000003;1', '90000004;1', '90000005;1'], p.locator('#exams').input_value().splitlines())
        e = self.app.rpa_case_simulation['handoff']; files = [{'name': Path(f['path']).name, 'sha256': f['sha256']} for f in e['files']]
        self.check('Anexo original integral e íntegro', files, p.evaluate('window.attachments'))
        self.check('Um PDF, duas funções', 1, len(rpa.paths))
        self.check('O.S. real', None, result['os_real'])
        self.check('Etiquetas fictícias no navegador', 5, p.locator('.label').count())
        output_dir = os.getenv('SHIFT_VALIDATION_OUTPUT')
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            p.screenshot(path=str(Path(output_dir) / (self.id().split('.')[-1] + '.png')), full_page=True)
        cancel.set()
        return result
    def finish(self):
        from rpa_simulada import SimulatedRPA
        output_dir = os.getenv('SHIFT_VALIDATION_OUTPUT')
        if output_dir:
            from PIL import ImageGrab
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            self.root.update()
            x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
            ImageGrab.grab(bbox=(x, y, x + self.root.winfo_width(), y + self.root.winfo_height())).save(Path(output_dir) / 'PRE_CADASTRO_INTEGRADO_2_5_3.png')
        self.ui.simulate_case_button.invoke(); self.root.update(); state = self.app.rpa_case_simulation
        state['start'].invoke(); self.root.update(); self.check('Documentos fictícios precisam ser confirmados', None, state['handoff'])
        for v in state['checks'].values(): v.set(True)
        state['synthetic'].set(True)
        original = SimulatedRPA.from_handoff; interactive = SimulatedRPA.interactive
        def headless(envelope, **kwargs): return original(envelope, headless=True, **kwargs)
        def human(rpa, cancel=None): return self.run_browser_as_human(rpa, cancel, interactive)
        with patch.object(SimulatedRPA, 'from_handoff', side_effect=headless), patch.object(SimulatedRPA, 'interactive', human), patch('gerar_exemplos_250.main', side_effect=AssertionError('Não substituir documentos por exemplos')):
            state['start'].invoke(); self.wait(lambda: not state['busy'], timeout=90)
            self.check('Resultado da integração vinculado ao caso', True, bool(state['result']))
        self.check('Pré-cadastro continua local', None, self.app.store.get(self.app.cid)[3]['os_real'])
        self.check('Uma simulação registrada', 1, self.app.store.db.execute('SELECT COUNT(*) FROM integracao_simulada').fetchone()[0])
        self.check('PDF preservado, sem criar segunda ficha', 1, len(self.app.cases.get_children()))
    def test_importar_conferir_preparar_e_automatizar_no_navegador(self):
        from tiss import SCHEMA
        self.prepare_ui()
        expected = {**VALUES, 10: PATIENTS[0], 23: CLINICAL, 30: EXECUTOR}
        for number in [*PRIORITY, 16]:
            key = SCHEMA[number][0]; w = self.ui.inputs[key]
            self.check('Campo ' + str(number) + ' preenchido na interface', expected[number], w.get('1.0', 'end-1c') if number == 23 else w.get())
            field = self.app.models['guia']['fields'][key]
            self.check('Campo ' + str(number) + ' página original', 2, field['source_document']['page'])
            self.check('Campo ' + str(number) + ' região original', True, bool(field['box']))
        self.finish()
    def test_corrigir_crm_manualmente_antes_de_entregar_ao_navegador(self):
        self.prepare_ui('05_leitura_incerta.pdf'); self.finish()
    def test_fechar_janelas_cancela_atualizacoes_agendadas(self):
        from rpa_training_ui import open_training
        from shift_inspection_ui import open_inspection
        self.prepare_ui(); self.ui.simulate_case_button.invoke(); self.root.update()
        windows = [self.app.rpa_case_simulation]
        open_training(self.app); windows.append(self.app.rpa_training)
        open_inspection(self.app); windows.append(self.app.shift_inspection)
        for state in windows:
            timer = state['poll_id']; self.assertIn(timer, self.root.tk.call('after', 'info'))
            state['window'].destroy(); self.root.update()
            self.assertNotIn(timer, self.root.tk.call('after', 'info'))


if __name__ == '__main__': unittest.main()
