# Regressão e agrupamento — 2.4.2

A implementação parte da cópia íntegra da 2.4, comparada arquivo por arquivo com o ZIP 2.4.1 enviado. Na 2.4.1 mudaram somente `scan_import.py`, `tiss.py`, `app.py` e `VERSAO.json`; foram acrescentados instruções e dois testes. Não houve mudança no mecanismo OCR, no PyMuPDF ou em `tiss_geometry.py` nessa revisão.

## Erros reproduzidos

| Caso inteiramente sintético | 2.4 | 2.4.1 | 2.4.2 |
| --- | --- | --- | --- |
| PDF com pedido, guia parcial, continuação sem identificação e anexo | 4 fichas | 4 fichas | 1 ficha provisória no modo individual |
| Páginas acessíveis nas fichas | 4; desconhecida tratada como pedido | 3; desconhecida fora das visualizações | 4; desconhecida/complementar preservada separadamente |
| Primeiro nome separado por grande espaço | Perdia o primeiro nome | Reconhecia o nome | Reconhece o nome |
| Mesmo nome, controle numérico em coluna vizinha sem rótulo reconhecido | Reconhecia o nome | Nome vazio | Reconhece o nome sem incorporar controle |

O relatório reproduzível das entradas/saídas sintéticas está em `COMPARACAO_2_4_2.json`. Na 2.4.1 a página continuava no arquivo e no lote, mas era excluída de ambos os documentos visíveis; isso é diferente de apagar a página do PDF.

As causas foram: `compatible()` exigia nomes idênticos e identificadores comuns em cada par; `read_scan()` criava um grupo para toda continuação/página incerta sem evidência suficiente; `build_cases()` não tinha uma área própria para páginas de apoio; a 2.4.1 passou a descartá-las de ambas as visualizações. Nomes eram truncados por espaços grandes na 2.4; a leitura da linha inteira na 2.4.1 absorvia outra coluna e então rejeitava o nome por conter dígitos. A interpretação conjunta de páginas também podia apagar um nome completo devido a uma variante parcial impressa na continuação.

## Funções modificadas e responsabilidades

| Arquivo/função | Correção |
| --- | --- |
| `identity_evidence.compatible`, `names_compatible`, `identifier`, `full_name` | Evidência de identificação, fragmentos contíguos de nomes realmente impressos, formatos de identificadores e escolha de um nome completo existente. Não monta nomes a partir de fragmentos nem usa aproximação de letras/códigos. |
| `scan_import.read_scan` | Modos `single` e `multiple`. No individual, uma ficha provisória por arquivo; páginas desconhecidas ou sem identificação não fragmentam esse PDF. No múltiplo, exige evidências e ausência de conflitos, sem presumir uma pessoa por PDF. A API mantém o padrão múltiplo por compatibilidade; a interface inicia no modo individual. |
| `scan_import.classify` | Distingue documento complementar e continuação. Sem certeza, mantém a página como incerta e visível. |
| `scan_import.build_cases`, `_merged_fields` | Documentos de pedido/guia conservam suas páginas; anexos/desconhecidos têm documento de apoio próprio. Valores são reconciliados por campo a partir das páginas, sem deixar página vazia/variante parcial apagar valor completo. Cada origem física é preservada. Campos realmente ausentes não são copiados de outro documento por suposição. |
| `scan_import.assess_group`, `confirm_group`, `group_fingerprint` | Ficha provisória não significa associação aprovada. Confirmação explícita exige revisor, motivo, visualização de todas as páginas, identificação suficiente e ausência de conflito. Mudança de páginas/identificação invalida a confirmação anterior. |
| `scan_import.apply_identity_edits`, `save_batch` | Correções por página preservam valor original/histórico, incluindo lotes antigos sem os novos campos opcionais. Reclassificação e reunião das fichas de um PDF usam as leituras existentes e preservam revisões. Reimportação/sobreposição e alteração de páginas originais continuam bloqueadas. |
| `tiss_names.name_words`, `tiss.extract` | Conserva primeiro nome e sobrenomes espaçados dentro da célula, com controle de colunas/tamanho das palavras. Não incorpora controles numéricos vizinhos. Mantém interpretação geométrica e separação dos números TISS. |
| `tiss_comparison.compare_tiss` | Nome parcial compatível pode ser comparado com nome completo quando há identificador comum válido; conflitos continuam bloqueando. Identificadores são comparados em formato normalizado, conservando os textos e zeros originais. Quantidades solicitada, autorizada e executada mantêm significados separados. |
| `engine_v2.FIELDS/ALIASES`, `review_errors` | Identificadores opcionais CPF/CNS mantêm campos próprios; pendências da validação das páginas são exibidas e impedem preparo. Não são obrigatórios quando a identificação é confirmada por outros dados suficientes. |
| `app.import_scans`, `classification_window`, `open_case`, `check_pages`, `case_stage`, `DocumentView.render` e `page_panel.PagePanel` | Seletor dos modos, ficha com miniaturas clicáveis de todas as páginas, correção de tipo/grupo/identificação, confirmação do agrupamento e recuperação de PDFs fragmentados. Comparação continua acessível. Reprocessamento preserva distribuição/correções, mas exige nova aprovação do agrupamento. Dados de outro caso não permanecem na área de páginas ao abrir atendimento legado. Setas e miniaturas mantêm página, tipo, editor e conferência sincronizados. |

Os números de prestador, principal, operadora, carteira e senha permanecem distintos, com zeros iniciais. Exames continuam visíveis mesmo sem catálogo; execução não fornece autorização nem duplica a solicitação. Páginas complementares não alimentam automaticamente exames do pedido. Registros preparados são protegidos. Importação legada, catálogo, perfis, fluxo interno e simulador foram mantidos.

## Validação e limites

A suíte executa o fluxo de importação pelo botão até pré-cadastro local, além de testes unitários. Inclui quatro páginas digitais e escaneadas/giradas, nomes parciais/ausentes, campos TISS, comparação, conflito, movimento sem reimportar, correção na interface, reprocessamento, revisões e duplicidades. `RELATORIO_CAMPOS_2_4_2.json` confere os valores e a origem física, além de quantidade de fichas/páginas e bloqueio do conflito. A matriz de 175 verificações da 2.4 também foi reexecutada; o relatório histórico foi preservado.

Os testes desta rodada usam apenas documentos fictícios. Não validam todos os layouts reais, manuscritos ou carimbos. Campos ilegíveis continuam pendentes. Não foram presumidos códigos internos, autorização ou conversão de conselho/UF numéricos. Regras e catálogo do laboratório exigem homologação. CPF/CNS são opcionais e a finalidade de cada identificador deve ser conferida na página.

Execução nativa do Windows permanece pendente; o programa e os fluxos gráficos foram testados em Linux. Movimentos são entre fichas do mesmo lote, sem transferência entre lotes importados separadamente. O modo individual gera uma ficha por arquivo selecionado, e não une vários PDFs entre si por suposição. Não houve envio de documentos clínicos, acesso ao Shift real ou impressão oficial.
