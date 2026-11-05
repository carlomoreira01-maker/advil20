"""Contrato futuro; não importa Playwright, não abre navegador, não acessa o LIS."""


class ShiftRPA:
    def enviar(self, *_args, **_kwargs):
        raise RuntimeError('Integração desativada. Exige projeto separado, homologação e aprovação específica.')
