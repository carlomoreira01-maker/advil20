import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from treinamento_integrado import initialize_training, create_training


class Training253(unittest.TestCase):
    def test_reabrir_treinamento_preserva_exemplos_e_base_existente(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'treino'; files, manifest = initialize_training(base)
            (base / 'anotacao_local.txt').write_text('NOTA FICTICIA', encoding='utf-8')
            files2, manifest2 = initialize_training(base)
            self.assertEqual((files, manifest), (files2, manifest2))
            self.assertEqual((base / 'anotacao_local.txt').read_text(), 'NOTA FICTICIA')
            self.assertTrue(all(hashlib.sha256((files / name).read_bytes()).hexdigest() == sha for name, sha in manifest.items()))
    def test_recusa_pasta_com_dados_sem_marcador_de_treinamento(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / 'arquivo_local.txt'; original.write_text('PRESERVAR', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'contém dados'): initialize_training(tmp)
            self.assertEqual(original.read_text(), 'PRESERVAR')
            self.assertFalse((Path(tmp) / 'catalogo.json').exists())


@unittest.skipUnless(os.getenv('SHIFT_GUI_TESTS') == '1', 'Requer Tk local')
class TrainingGUI253(unittest.TestCase):
    def test_iniciador_usa_interface_real_base_separada_e_perfil_ficticio_sem_aprovar(self):
        import tkinter as tk
        with tempfile.TemporaryDirectory() as tmp:
            root = tk.Tk(); app = create_training(root, Path(tmp) / 'treino')
            try:
                root.update(); self.assertIn('TREINAMENTO', root.title())
                with patch('tkinter.filedialog.askopenfilenames', return_value=[str(app.training_files / '01_um_paciente.pdf')]):
                    app.workspace.import_buttons['single'].invoke()
                end = time.monotonic() + 60
                while app.busy and time.monotonic() < end: root.update(); time.sleep(.01)
                self.assertFalse(app.busy); self.assertEqual(len(app.cases.get_children()), 1)
                self.assertEqual(app.selected_profile['id'], 'FICTICIO')
                self.assertFalse(app.models['guia']['pages_reviewed'])
                self.assertFalse(app.workspace.final_confirm.get())
                self.assertIsNone(app.store.get(app.cid)[3])
                other = Path(tmp) / 'fora_do_treino.pdf'; other.write_bytes(b'FORA DO TREINAMENTO')
                with self.assertRaisesRegex(ValueError, 'somente os exemplos'): app.import_scans([other], mode='single')
            finally: app.store.db.close(); root.destroy()
