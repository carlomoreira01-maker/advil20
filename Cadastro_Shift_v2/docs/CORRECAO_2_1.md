# Correção 2.1 — campos após importação

## Abrir no Windows

1. Extraia TODO o ZIP corrigido em uma pasta nova. Mantenha a versão anterior como backup.
2. Dê dois cliques em `INSTALAR_WINDOWS.bat` e aguarde “Instalacao concluida”. Internet é usada apenas para instalar as ferramentas.
3. Abra `INICIAR_WINDOWS.bat`. O título deve mostrar **2.1**.
4. Informe um revisor e clique em **Importar e ler par**. Para o primeiro teste escolha `exemplos_correcao/01_pedido_digital.pdf` e `exemplos_correcao/02_guia_escaneada.png` (também há JPG e PDF).
5. Os campos aparecem automaticamente em **Comparar e conferir**. **Diagnóstico de leitura** mostra documento por posição, página, execução, método, idiomas, caracteres e motivo técnico de falha. **Origem** mostra o trecho e destaca a página localmente.
6. Execute `TESTAR_WINDOWS.bat` para diagnóstico e testes completos, incluindo a interface. Não mova arquivos durante os testes.

Em uma instalação não padrão, `SHIFT_TESSERACT` deve apontar para `tesseract.exe`. Aspas externas são aceitas. `SHIFT_TESSDATA`, se usada, deve apontar para a pasta que contém os dois modelos; normalmente NÃO é necessário configurar nenhuma variável. Os modelos português e inglês já estão incluídos. Não copie a antiga pasta `.venv`.

Para reutilizar histórico v2, feche ambos os aplicativos, faça backup e copie **somente** `dados_v2` para a nova pasta. As tabelas antigas continuam legíveis; nenhuma reanálise de casos preparados é feita automaticamente. Os novos diagnósticos de casos antigos refletem a leitura original armazenada. Os novos logs não recebem informações identificáveis; registros antigos não são reescritos. Dados e revisões do caso continuam locais e sensíveis, separados dos registros técnicos.

## Diagnóstico e causa

Fluxo rastreado: diálogo de importação → `App.import_pairs` → worker local → `read_document` → texto PyMuPDF ou Tesseract TSV → linhas com coordenadas → `parse_document` → fila de eventos → SQLite → `open_case` → variáveis dos campos e tabelas visíveis.

A extração já era executada após importar; exibir o documento não demonstrava que a extração tinha funcionado. Reproduzimos no código ORIGINAL do ZIP que `Paciente  Pessoa Sintetica Alfa`, `Fonte pagadora  Convenio Ficticio` e `Guia  TESTE-001` deixavam os três campos vazios: o parser exigia rótulos com dois pontos. Outros formulários com rótulos acima de valores em colunas também não eram associados corretamente.

No caminho OCR, erros podiam virar apenas alertas dentro da conferência enquanto o original continuava aparecendo. O pacote tinha apenas o modelo português; a variável global TESSDATA_PREFIX e a seleção de diretório por nome de idioma não eram adequadas para idiomas combinados. Não é possível atribuir a instalação específica do Windows a uma única dessas causas sem executá-la. O PyMuPDF leu os PDFs digitais nos testes desta entrega.

## Alterações efetivas

- Reconhecimento de rótulos com/sem dois pontos, campos numerados, aliases usuais e rótulos acima de valores em colunas. Valores não são reinterpretados como novos rótulos sem delimitador.
- Texto digital utilizável é lido diretamente, inclusive documentos curtos. OCR somente para páginas sem texto utilizável ou áreas raster substanciais sem texto utilizável. Páginas híbridas preservam texto digital não duplicado e normalizam as coordenadas.
- Resolução explícita do executável, diretórios Windows usuais, caminhos com espaços/acentos e diretório dos modelos. Português e inglês incluídos; diagnóstico real dos três modos por, eng e por+eng, verificação de TSV e timeout.
- Classificação por títulos explícitos de pedido/guia. Quando os dois títulos comprovam inversão, posições são corrigidas. Tipo ausente, contraditório ou incerto exige conferência, sem inferência clínica.
- Campos preenchidos imediatamente no formulário após análise, “Não identificado” para ausências, baixa confiança ou valores conflitantes; o marcador não é tratado como dado válido no modelo.
- Origem por documento, página, caixa e trecho; candidatos conflitantes são preservados. Exames, códigos, quantidades e materiais continuam como lidos, sem inventar quantidades ou códigos ausentes.
- Painel técnico por documento/página, inclusive falhas; recuperação do worker e estado de leitura; diagnóstico restaurado ao reabrir casos. Exceções de callbacks não despejam tracebacks no console.
- Comparação por catálogo e correspondências aprovadas, mantendo bloqueios de códigos desconhecidos/inconsistentes, quantidades, materiais, identidade e exames ausentes. Status de guia ausente também bloqueia.
- Novos registros técnicos de auditoria não guardam nomes, conteúdo clínico, caminhos, texto OCR, motivos livres ou stderr. Revisões completas ficam na tabela local de dados do caso, não em logs.
- Interface v1, lotes, catálogo, revisão, persistência e exportação continuam disponíveis. O OCR v1 reutiliza a configuração dos idiomas; seus novos registros técnicos também excluem nomes e texto clínico, preservando revisões nos dados locais do caso. Nenhum envio ao Shift ou impressão oficial foi adicionado.

## Evidência de validação

Ambiente: Linux Debian 13, Python 3.12.14, PyMuPDF 1.26.6, Pillow 13.0.0, Tesseract 5.5.0; interface Tkinter real em Xorg com driver dummy. Dados exclusivamente fictícios, criados durante os testes. As chamadas de rede Python são bloqueadas explicitamente em testes de leitura/importação.

Comando completo: `DISPLAY=:88 SHIFT_GUI_TESTS=1 .venv/bin/python -m unittest discover -s tests -v`.

Resultado final: **67 testes aprovados, zero falhas e zero ignorados**, incluindo oito fluxos de interface. O relatório `RESULTADO_TESTES_2_1.txt` registra a execução final. Inclui os testes anteriores e regressões de extração, Unicode/espaços, idiomas, erros, privacidade e estado da interface. Os testes de interface incluem importação via diálogos, PDF digital + PNG OCR, preenchimento dos campos e tabelas VISÍVEIS, troca por títulos, falha e recuperação, reabertura, paginação/zoom/origem, bloqueio de divergências e conferência até exportação JSON local. Não se usou apenas uma suíte de funções isoladas.

`diagnostico.py` também executa OCR real em português, inglês e ambos, verifica hashes dos modelos e lê um PDF digital sintético.

## Limites e validação Windows

Não houve execução nativa de Windows neste ambiente. Falta validar instalação pelo winget, criação de atalho, flags de subprocesso sem console, fontes/DPI, permissões/antivírus e o OCR em um caminho Windows com acentos. Os caminhos e argumentos foram testados em Linux com espaços/acentos e com configuração simulada de executável Windows. Não são equivalentes a testar no Windows.

Execute `TESTAR_WINDOWS.bat` no computador de destino e repita a importação do exemplo acima. Este é o passo pendente de validação da plataforma, não uma afirmação de sucesso no computador do usuário.

Extração heurística não cobre todos os layouts, manuscritos, rasuras ou imagens ruins. Nesses casos o programa exige conferência; não garante transcrição de todo documento legível. O catálogo continua sendo de demonstração e precisa de validação do laboratório para uso operacional. Nenhum documento deve ser enviado para este chat para o teste.
