"""Auxiliar do instalador: evita código Python embutido nas aspas do PowerShell."""
import sys
from pathlib import Path


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    action = argv[0] if argv else ''
    if action == 'python':
        if not (3, 12) <= sys.version_info[:2] < (3, 15):
            return 3
        print(sys.executable)
        return 0
    from ocr_runtime import tesseract_exe, check_ocr_health, save_settings
    if action == 'localizar-ocr':
        exe = tesseract_exe()
        if not exe:
            return 3
        print(exe)
        return 0
    if action == 'selecionar-ocr':
        import tkinter as tk
        from tkinter import filedialog, messagebox
        root = tk.Tk(); root.withdraw()
        try:
            path = filedialog.askopenfilename(parent=root, title='Selecione o tesseract.exe instalado no computador',
                filetypes=[('Tesseract', 'tesseract.exe'), ('Executáveis', '*.exe')])
            if not path:
                return 3
            result = check_ocr_health(exe=path)
            if not result['ok']:
                messagebox.showerror('Verificação OCR', result['message'], parent=root)
                return 3
            save_settings(result['exe'])
            print(result['exe'])
            return 0
        finally:
            root.destroy()
    print('Comando auxiliar inválido.', file=sys.stderr)
    return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        from ocr_runtime import safe_failure
        print(safe_failure(exc), file=sys.stderr)
        sys.exit(1)
