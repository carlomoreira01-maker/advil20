"""Contrato futuro; não importa Playwright, não abre navegador, não acessa o LIS."""


class ShiftRPA:
    def enviar(self, *_args, **_kwargs):
        raise RuntimeError('Gravação em produção ainda não homologada. Use Inspecionar Shift — somente leitura para conferir as telas; o programa não cria O.S. reais nesta versão.')
