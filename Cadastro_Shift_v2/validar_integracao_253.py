"""Validação repetível de interface e RPA; gera apenas documentos sintéticos."""
import argparse
import json
import os
from pathlib import Path
import sys
import unittest


def main(output=None, screenshots=False):
    output = Path(output) if output else Path(__file__).resolve().parent / 'docs'
    output.mkdir(parents=True, exist_ok=True)
    os.environ['SHIFT_GUI_TESTS'] = '1'; os.environ['SHIFT_BROWSER_TESTS'] = '1'
    if screenshots: os.environ['SHIFT_VALIDATION_OUTPUT'] = str(output)
    from tests import test_handoff_253, test_training_253
    test_handoff_253.ROWS.clear()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in [test_handoff_253, test_training_253])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    rows = test_handoff_253.ROWS
    report = {'ambiente': 'LOCAL_SOMENTE_SINTETICOS', 'producao_validada': False,
              'testes': result.testsRun, 'erros': len(result.errors), 'falhas_testes': len(result.failures), 'ignorados': len(result.skipped),
              'verificacoes': len(rows), 'passaram': sum(r['passou'] for r in rows), 'falharam': sum(not r['passou'] for r in rows),
              'valores_esperados_e_encontrados': rows}
    (output / 'INTEGRACAO_COMPLETA_2_5_3.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result.wasSuccessful() and not result.skipped and bool(rows) and report['falharam'] == 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--saida'); parser.add_argument('--capturas', action='store_true')
    args = parser.parse_args(); sys.exit(0 if main(args.saida, args.capturas) else 1)
