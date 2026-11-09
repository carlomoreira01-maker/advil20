"""Inicia o aplicativo existente em uma base separada, inteiramente fictícia."""
import hashlib
import json
from pathlib import Path

from gerar_exemplos_250 import main as generate_examples
from gerar_exemplos_tiss import catalog
from lis_simulado import CODES

ROOT = Path(__file__).resolve().parent
MARKER = 'TREINAMENTO_INTEGRADO_SOMENTE_FICTICIO'


def training_profile():
    return {'id': 'FICTICIO', 'nome': 'Treinamento fictício — sem validade no laboratório',
            'fonte_pagadora': 'IPASGO', 'tipo_atendimento': 'AMBULATORIAL',
            'procedimentos': list(CODES), 'homologado': True,
            'aprovado_por': 'RESPONSAVEL FICTICIO', 'aprovado_em': '2026-11-09',
            'exige_autorizacao': True,
            'mapeamento': {'Matrícula': 'Carteira', 'Guia': 'Guia prestador',
                           'Senha/Autorização': 'Senha autorização', 'Guia principal': 'Guia principal',
                           'Guia operadora': 'Guia operadora'},
            'obrigatorios': ['Matrícula', 'Guia', 'Senha/Autorização', 'Guia operadora'], 'valores_tecnicos': {}}


def initialize_training(data):
    data = Path(data); marker = data / '.somente_ficticio'
    if data.exists() and any(data.iterdir()) and (not marker.exists() or marker.read_text(encoding='utf-8') != MARKER):
        raise ValueError('A pasta escolhida já contém dados. O treinamento exige uma pasta separada e não altera uma instalação existente.')
    data.mkdir(parents=True, exist_ok=True); marker.write_text(MARKER, encoding='utf-8')
    files = data / 'exemplos'
    if not (files / 'manifesto_sha256.json').is_file(): generate_examples(files)
    manifest = json.loads((files / 'manifesto_sha256.json').read_text(encoding='utf-8'))
    cat = catalog()
    for row in cat: row['codigo_shift'] = 'SIM-LAB-' + row['tuss']
    if not (data / 'catalogo.json').exists(): (data / 'catalogo.json').write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding='utf-8')
    if not (data / 'perfis_pagadores.json').exists(): (data / 'perfis_pagadores.json').write_text(json.dumps([training_profile()], ensure_ascii=False, indent=2), encoding='utf-8')
    return files, manifest


def create_training(root, data=None):
    import copy
    from tkinter import ttk, filedialog
    from app import App
    from workbench import create_workbench
    data = Path(data) if data is not None else ROOT / 'dados_treinamento_integrado'
    files, manifest = initialize_training(data)

    class TrainingApp(App):
        def import_scans(self, paths=None, reprocess=None, mode=None):
            if paths is None:
                paths = filedialog.askopenfilenames(parent=self.root, title='Escolha um PDF inteiramente fictício',
                                                    initialdir=str(files), filetypes=[('Exemplos PDF', '*.pdf')])
            if not paths: return
            try: hashes = [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths]
            except OSError: raise ValueError('Exemplo fictício indisponível. Selecione os arquivos da pasta de treinamento.') from None
            if any(h not in manifest.values() for h in hashes):
                raise ValueError('Este iniciador aceita somente os exemplos gerados para treinamento. Abra INICIAR_WINDOWS.bat para sua rotina local.')
            return super().import_scans(paths, reprocess, mode)

        def open_case(self, cid, restore_diagnostics=True):
            super().open_case(cid, restore_diagnostics)
            if self.store.get(cid)[2] != 'PREPARADO' and self.selected_profile is None:
                self.selected_profile = copy.deepcopy(training_profile())
                self.show_comparison()

    app = create_workbench(root, data, base_class=TrainingApp)
    root.title('TREINAMENTO FICTÍCIO | Cadastro Assistido Shift')
    banner = ttk.Label(root, text='TREINAMENTO — dados e códigos fictícios, base separada da rotina', padding=8)
    banner.pack(fill='x', before=app.workspace.frame)
    app.workspace.notice.set('Importe 01_um_paciente.pdf da pasta de exemplos que será aberta. Confira as páginas e os dados; depois prepare e simule o pré-cadastro fictício. Informe seu nome / revisor. Nenhuma conferência é aprovada automaticamente.')
    app.training_files = files
    return app


if __name__ == '__main__':
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    try:
        app = create_training(root)
        root.mainloop()
    except Exception:
        messagebox.showerror('Treinamento não iniciado', 'Não foi possível abrir a base separada de treinamento. Preserve suas pastas e confira as instruções em ATUALIZAR_PARA_2_5_3.txt.')
        root.destroy()
