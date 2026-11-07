# Cadastro Assistido Shift — versão 2.4.3

Comece por [ATUALIZAR_PARA_2_4_3.txt](ATUALIZAR_PARA_2_4_3.txt). Esta versão modifica o aplicativo Python/Tkinter existente e preserva dados, importação antiga, perfis, catálogo e simulação local. Não acessa o Shift real.

## Leitura e conferência 2.4.3

Os dois PDFs reais enviados foram testados localmente, da importação até os campos e tabelas na interface. Foram corrigidos nomes truncados, rótulos/data confundidos com senha, associação de células de conselho/CRM e recuperação de quantidades em formulários densos. A nova releitura regional exige concordância para recuperar informações ausentes e mantém incertezas para revisão.

As sete páginas e seus originais foram preservados, com 118 verificações gráficas aprovadas. Paciente e carteira aparecem nas duas fichas. Algumas quantidades e o CRM consolidado de uma ficha permanecem pendentes; nenhum atendimento real foi aprovado ou preparado. Os documentos reais e seu conteúdo não acompanham o pacote. A validação não certifica cada valor clínico.

Use **Reprocessar leitura** nas fichas antigas e refaça a conferência. Quando um campo possuir alternativas, **Origem** abre as leituras com suas referências para escolha humana. A visualização acompanha a orientação do OCR; **Girar** altera somente a tela. Guias densas podem levar alguns minutos para a leitura detalhada.

A suíte final passou com **200 testes** (46 de interface e 3 de navegador simulado) e **270 verificações sintéticas**. Veja [CORRECAO_2_4_3.md](docs/CORRECAO_2_4_3.md), [TESTES_REAIS_2_4_3.json](docs/TESTES_REAIS_2_4_3.json), [REGRESSAO_CAMPOS_2_4_3.json](docs/REGRESSAO_CAMPOS_2_4_3.json) e [RESULTADO_TESTES_2_4_3.txt](docs/RESULTADO_TESTES_2_4_3.txt). O agrupamento e as funcionalidades anteriores continuam preservados.

## Correção do agrupamento 2.4.2

Escolha **Um atendimento — várias páginas** para manter todas as páginas de um PDF em uma ficha provisória. Nome parcial, identificação ausente e página complementar não dividem esse arquivo. **Vários pacientes — verificar identificação** mantém a associação conservadora por evidências.

A ficha possui miniaturas de todas as páginas. Em **Corrigir página / agrupamento**, edite tipo, mova páginas entre fichas do lote e corrija identificação com motivo e origem. **Confirmar agrupamento** exige visualização e conferência, sem permitir conflitos. PDFs que versões antigas separaram podem ser reunidos sem novo OCR. O preparo continua dependendo das demais verificações.

Veja [CORRECAO_2_4_2.md](docs/CORRECAO_2_4_2.md), [COMPARACAO_2_4_2.json](docs/COMPARACAO_2_4_2.json), [RELATORIO_CAMPOS_2_4_2.json](docs/RELATORIO_CAMPOS_2_4_2.json) e [RESULTADO_TESTES_2_4_2.txt](docs/RESULTADO_TESTES_2_4_2.txt). Use `exemplos_2_4_2/01_um_atendimento_quatro_paginas.pdf` para o teste principal e `02_identificadores_incompativeis.pdf` para verificar o bloqueio.

## Funcionalidades preservadas

- **IMPORTAR ESCANEAMENTO** aceita PDF multipágina, JPG, PNG e lotes. Lê cada página sem pressupor ordem; associa por nome e identificador comum, bloqueando conflitos. No modo de vários pacientes, páginas incertas/continuações sem identificação podem ficar separadas para revisão; no modo individual ficam na ficha provisória.
- **Identificar documentos** permite editar tipo/atendimento por página, com motivo e confirmação. Os arquivos originais integrais ficam preservados; cada campo/procedimento aponta para arquivo, página física e região.
- OCR local corrige orientação e pequena inclinação. A escolha da orientação deixou de premiar tokens gigantes sem sentido.
- Interpretação SP/SADT passou a usar palavras, rótulos e limites das células, incluindo campos adjacentes. Reconhece valores na mesma linha, cabeçalhos quebrados, tabelas densas e quantidade solicitada/autorizada separadas. Execução não duplica a solicitação nem fornece autorização.
- Exames sem catálogo aparecem na comparação, com pendência explícita. Nenhum código interno é inventado.
- **Comparar e conferir** permanece acessível com dados incompletos. **Reprocessar leitura**, **Corrigir manualmente**, **Conferir campos vistos** e **Salvar correções e comparar** mantêm revisão e histórico. Pré-cadastro exige pendências resolvidas, revisão salva e confirmação humana.

## Validação e limites

Os testes automatizados incluem documentos sintéticos densos, PDF com pedido/guia em ambas as ordens, dois pacientes misturados, guia escaneada girada, imagens, quantidade zero/ausente, exame não autorizado, reclassificação e correção manual na interface até pré-cadastro local. O relatório por campo compara valores e origem: [RELATORIO_CAMPOS_2_4.json](docs/RELATORIO_CAMPOS_2_4.json). Veja [CORRECAO_2_4.md](docs/CORRECAO_2_4.md) e [RESULTADO_TESTES_2_4.txt](docs/RESULTADO_TESTES_2_4.txt).

Os testes automatizados e fixtures usam somente documentos fictícios. Nesta rodada, os dois PDFs reais fornecidos também foram processados localmente em uma instalação privada de teste, sem envio externo. Eles não integram fixtures, pacote ou GitHub. Contagens não substituem conferência dos valores. Quantidades incertas, divergência de CRM, classificação/finalidade das guias e códigos numéricos de conselho/UF exigem revisão. A versão é testável e assistida, sem garantia de leitura integral de qualquer guia.

Execução nativa do instalador, binários OCR e interface no Windows permanece pendente. O laboratório deve homologar catálogo, fontes pagadoras, mapeamentos e regras de atendimento. Continuações sem identificadores exigem conferência; no modo múltiplo podem exigir associação manual. O fluxo interno sem guia permanece individual. Não há adaptador de produção para o Shift.

## Instalação e segurança

Extraia tudo em pasta nova; faça backup e copie `dados_v2` com os programas fechados. Abra `INSTALAR_WINDOWS.bat`, depois `INICIAR_WINDOWS.bat`. Python 3.12–3.14 e Tesseract devem estar instalados. Em Configurações e ferramentas, teste e salve o executável OCR e os idiomas `por`/`eng`.

Após instalar as bibliotecas, o processamento funciona localmente. Documentos clínicos não são enviados a APIs. Originais e revisões em `dados_v2` não são criptografados: controle o acesso e faça backup. Logs técnicos contêm estados/contagens; o conteúdo clínico permanece nos registros locais do caso. Não são solicitadas senhas de login do Shift.

A simulação Playwright usa somente loopback e dados fictícios. Nenhuma ordem real é criada e nenhuma etiqueta oficial é impressa. Mantenha bloqueios de antivírus; esta entrega não certifica o alerta anterior como falso positivo.

## Testes de desenvolvimento

```bash
DISPLAY=:90 SHIFT_GUI_TESTS=1 SHIFT_BROWSER_TESTS=1 python -m unittest discover -s tests -v
python validar_campos_2_4_2.py
```

No Windows, use `TESTAR_WINDOWS.bat`. Playwright/Chromium são opcionais para a simulação e não são instalados na recepção por padrão. As instruções e relatórios 2.1 a 2.4 permanecem como histórico; siga o guia 2.4.3 para atualizar.
