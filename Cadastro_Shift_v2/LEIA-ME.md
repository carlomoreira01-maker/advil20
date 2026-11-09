# Cadastro Assistido Shift — versão 2.5.1

Comece por [ATUALIZAR_PARA_2_5_1.txt](ATUALIZAR_PARA_2_5_1.txt).

- **Padrão: um PDF = um atendimento provisório**, tanto na aba individual quanto na aba de vários pacientes. PDFs diferentes permanecem separados. Conflitos bloqueiam confirmação; páginas podem ser separadas ou reunidas manualmente.
- **Cache local, OCR controlado e cancelamento**. Texto digital é lido diretamente; até duas páginas podem fazer OCR. As medições distinguem primeira leitura e cache: [DESEMPENHO_2_5_1.json](docs/DESEMPENHO_2_5_1.json).
- **Interface 2.5 preservada**, com rascunho acessível, correções por campo, origem e pré-cadastro validado protegido.
- **Treinamento RPA no navegador local**: pesquisa paciente, preenche fonte/guia/médico/exames, anexa PDFs sintéticos e, após confirmações humanas, gera O.S. e etiquetas fictícias. Instalação opcional: `INSTALAR_SIMULACAO_RPA.bat`; acesso em Mais opções. Não consome documentos da rotina e não tem conexão com o Shift real.

Causas e limites: [CORRECAO_2_5_1.md](docs/CORRECAO_2_5_1.md). Resultados: [RESULTADO_TESTES_2_5_1.txt](docs/RESULTADO_TESTES_2_5_1.txt). Windows nativo e homologação do laboratório permanecem pendentes.

## Histórico preservado da versão 2.5.0

# Cadastro Assistido Shift — versão 2.5.0

Comece por [ATUALIZAR_PARA_2_5_0.txt](ATUALIZAR_PARA_2_5_0.txt). A atualização modifica o aplicativo existente, mantém os arquivos anteriores e abre um painel simples em cinco telas.

- **Cadastro de um paciente** e **Cadastro de vários pacientes**: use **Importar documentos** para PDF multipágina, JPG/PNG ou vários arquivos. O agrupamento verifica identificadores nas duas abas.
- **Documentos → Dados identificados → Exames → Pré-cadastro**: navegue sem perder dados, veja a origem de cada informação e corrija os campos diretamente.
- **11 campos essenciais + conselho 16**: campo 30 separado do médico, indicação clínica completa e quatro estados de leitura. Indicação clínica não vira solicitação de exame.
- **Rascunho de pré-cadastro**: abra, salve e exporte mesmo com pendências. A preparação validada continua exigindo conferência humana e regras homologadas. Nada é enviado ao Shift real.
- **Mais opções** reúne configurações e a conferência detalhada anterior. Nas fichas antigas, use **Reprocessar leitura** para aplicar a nova interpretação.

Teste `exemplos_250/01_um_paciente.pdf`, `02_dois_pacientes_quatro_paginas.pdf` e `03_campos_vazios.pdf` em uma instalação separada. O segundo arquivo deve gerar duas fichas de duas páginas. Exemplos e gabarito são totalmente fictícios.

Causas, alterações e limites: [CORRECAO_2_5_0.md](docs/CORRECAO_2_5_0.md). Resultados: [RESULTADO_TESTES_2_5_0.txt](docs/RESULTADO_TESTES_2_5_0.txt) e [RELATORIO_INTERFACE_2_5_0.json](docs/RELATORIO_INTERFACE_2_5_0.json). A execução nativa no Windows e a homologação do laboratório permanecem pendentes. Esta entrega inclui os scripts de instalação e inicialização, sem novo executável instalador.

## Histórico preservado da versão 2.4.5 e anteriores


Comece por [ATUALIZAR_PARA_2_4_5.txt](ATUALIZAR_PARA_2_4_5.txt). Esta versão modifica o aplicativo Python/Tkinter existente e preserva dados, importação antiga, perfis, catálogo e simulação local. Não acessa o Shift real.

## Pedido carimbado e conferência guiada 2.4.5

Um pedido com lista de exames, paciente e carimbo profissional legível pode ser reconhecido mesmo sem o título Pedido médico. Guia com carimbo continua guia quando apresenta evidências de guia. O nome impresso junto ao CRM tem origem própria; carimbo isolado não determina o tipo. Listas são preservadas mesmo sem catálogo, sem inventar códigos ou quantidades.

**Revisor e Motivo da conferência agora ficam visíveis.** Revisor é o nome de quem confere. Motivo tem uma sugestão editável. Se faltar um deles, o programa destaca e foca o campo; para o motivo, abre a aba correta. Clicar no pré-cadastro bloqueado também explica a pendência.

Use **CONFERIR ATENDIMENTO** na lateral. A janela reúne Dados, Exames e Alertas. Depois de ver as páginas, confirmar a identidade e marcar as conferências realizadas, clique em **SALVAR CONFERÊNCIA E VER RESULTADO**. A tela distingue revisão salva de cadastro ainda bloqueado. O preparo local continua exigindo todos os requisitos e confirmação final.

Em **Páginas do atendimento**, há correção rápida do tipo e confirmação das páginas. Reprocessar passa a atualizar classificações automáticas antigas; correções humanas explícitas são preservadas. As páginas já vistas não são esquecidas durante a confirmação.

Para praticar o fluxo completo sem configuração do Shift, use uma instalação separada/vazia, clique em **Exemplos fictícios** e selecione a **primeira ficha**. Para testar carimbo, use `exemplos_carimbo/01_pedido_carimbo_e_guia.pdf`.

Veja [CORRECAO_2_4_5.md](docs/CORRECAO_2_4_5.md), [RESULTADO_TESTES_2_4_5.txt](docs/RESULTADO_TESTES_2_4_5.txt), [RELATORIO_CARIMBO_2_4_5.json](docs/RELATORIO_CARIMBO_2_4_5.json) e [RELATORIO_INTERFACE_2_4_5.json](docs/RELATORIO_INTERFACE_2_4_5.json). A execução nativa no Windows permanece pendente. O histórico anterior está preservado abaixo.

## Auditoria e correção do fluxo 2.4.4

O projeto existente foi auditado a partir da 2.4.3, com backup íntegro e 200 testes originais executados antes das alterações. As correções se concentram na classificação de pedido/guia, campo 17, preservação dos valores extraídos e conclusão da conferência. A versão anterior e seus relatórios permanecem como histórico.

- A classificação combina títulos, células TISS e sinais de solicitação; o título extenso SP/SADT é reconhecido. Um pedido com células numeradas continua pedido, e página incerta continua disponível para revisão.
- Campo 17 aceita rótulo quebrado e dígitos separados, com zeros à esquerda. Conselho, número, UF e CBO têm campos próprios. Identificação livre/carimbo tem origem separada e divergências exigem conferência; GO não é presumido.
- Leitura estruturada vazia não apaga valor válido obtido por outro rótulo. Listas de exames são preservadas. Nome/código de entradas diferentes do catálogo são bloqueados mesmo se ambos ainda não tiverem código interno.
- **O que falta para concluir → Resolver pendência selecionada** abre a ação correspondente. A conferência permanece acessível. Ajustes e perfil são preservados ao reclassificar o mesmo conjunto de páginas, com nova revisão obrigatória.
- **Aplicar não aplicáveis do perfil** exige regra homologada para campo opcional, sem apagar valor existente ou dispensar autorização exigida.

Use `exemplos_auditoria/01_quatro_paginas.pdf` em uma instalação de teste para ver uma ficha com pedido, guia, continuação e complementar. O exemplo `08_conflito.pdf` deve bloquear a confirmação. Instruções completas: [ATUALIZAR_PARA_2_4_4.txt](ATUALIZAR_PARA_2_4_4.txt).

Veja [AUDITORIA_2_4_4.md](docs/AUDITORIA_2_4_4.md), [RESULTADO_TESTES_2_4_4.txt](docs/RESULTADO_TESTES_2_4_4.txt), [RELATORIO_AUDITORIA_2_4_4.json](docs/RELATORIO_AUDITORIA_2_4_4.json) e [RELATORIO_INTERFACE_2_4_4.json](docs/RELATORIO_INTERFACE_2_4_4.json) para valores esperados/encontrados, origens e execução gráfica até pré-cadastro fictício. Esta rodada usa somente documentos sintéticos; nenhum documento real foi reprocessado.

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

No Windows, use `TESTAR_WINDOWS.bat`. Playwright/Chromium são opcionais para a simulação e não são instalados na recepção por padrão. As instruções e relatórios 2.1 a 2.4 permanecem como histórico; siga o guia 2.4.5 para atualizar.
