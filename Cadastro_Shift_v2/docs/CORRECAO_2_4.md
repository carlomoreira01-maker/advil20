# Correção da leitura e conferência 2.4

## Causas confirmadas no código

1. A importação tratava um arquivo inteiro como pedido ou guia e exigia dois arquivos diferentes. Não havia classificação nem proveniência por página para um único PDF misto.
2. O escore de orientação multiplicava confiança pelo tamanho ilimitado de cada token. Uma sequência sem sentido de milhares de caracteres vencia uma orientação com rótulos legíveis. Isso ocorreu em duas páginas dos exemplos locais.
3. O interpretador dependia das linhas globais do OCR para construir os cabeçalhos. Em guias densas, linhas misturavam rótulos pequenos com valores logo abaixo; o valor entrava no cabeçalho e era descartado da região de leitura. Limites de células ignoravam campos adjacentes como 14 e 19. Valores sem dois-pontos na própria linha também eram perdidos.
4. Cabeçalhos 25–28 separados em linhas não formavam tabela. A substituição da interpretação genérica pelo resultado TISS vazio deixava a tabela sem procedimentos.
5. A comparação descartava exames não mapeados no catálogo. Assim, podia haver exames extraídos e tabela de comparação vazia.
6. Campos ausentes exigiam marcação individual de revisão, alertas exigiam resolução e o botão de preparo não explicava previamente todos os bloqueios. A edição de campos não atualizava imediatamente a comparação. Isso dificultava a conferência sem resolver as pendências essenciais.

## Implementação

`tiss_geometry.py` associa palavras a rótulos sem depender das linhas globais, preserva células vizinhas e distingue cabeçalhos de valores. Usa aproximação somente para palavras de rótulos; não corrige nomes, números ou códigos por aproximação. As tabelas são ancoradas nos códigos de cada linha e nos cabeçalhos de solicitação/autorização/execução. O solicitante estruturado é limitado à seção anterior aos procedimentos; executante/assinatura não o substitui.

`tiss.py` conserva zeros iniciais, referências e diagnósticos por campo. Confiança insuficiente/conflito deixa o valor não identificado. Códigos numéricos de conselho/UF ficam como candidatos com região, sem conversão inventada. Não há validação oficial de versões/layouts TISS nem regras universais por marca.

`scan_import.py` preserva o original completo e classifica cada página. Associação automática exige nome e identificador comum, sem conflitos. Continuação sem referência suficiente fica separada. O usuário pode editar classificação e grupos, com motivo/confirmação. Conflitos de identificadores continuam bloqueando. Duplicação de escaneamento e sobreposição de páginas são bloqueadas. Reclassificação/reprocessamento preservam o histórico e protegem casos preparados.

`app.py` mantém importação legada no menu. O novo fluxo importa automaticamente, exibe originais por página física, campos editáveis, exames sem catálogo e pendências. A conferência é acessível com falhas; preparar depende de revisão salva, validações e confirmação humana. A correção manual revoga confirmação anterior e tem origem identificada como manual. Caminhos de originais são recuperados na pasta atual após copiar dados_v2 para outra instalação.

## Testes e limites

Consulte `RESULTADO_TESTES_2_4.txt` e `RELATORIO_CAMPOS_2_4.json`. Os testes de interface exercitam importação pelo botão, atualização dos campos/tabelas, edição, salvamento, bloqueios e liberação do pré-cadastro local. Os testes não se resumem ao retorno do Tesseract.

Os exemplos reais foram processados exclusivamente no ambiente local, fora do repositório. Foram localizadas cinco linhas de procedimentos em cada uma das sete páginas após os ajustes. Isso não comprova a exatidão de todos os caracteres/valores. Há campos ainda incertos e autorizações não confirmadas: a interface exige conferência. A identificação automática por papel funcional também requer revisão quando uma SP/SADT é usada como solicitação e não contém título explícito de pedido médico. Não é seguro decidir autorização apenas pelo título de guia.

A validação humana independente de todos os valores dos exemplos e o teste nativo Windows permanecem pendentes. Catálogo real, códigos numéricos de conselho/UF, perfis e mapeamentos devem ser homologados pelo laboratório. Campo ausente/zero/ilegível não autoriza procedimento. Não houve acesso ao Shift real, criação de O.S. ou impressão oficial. O alerta antivírus anterior permanece sem identificação da ameaça/arquivo e não foi classificado como falso positivo.
