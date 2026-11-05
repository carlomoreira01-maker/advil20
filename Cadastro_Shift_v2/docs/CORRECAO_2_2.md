# Cadastro Assistido Shift 2.2 — configuração do OCR

## Atualização simples

Siga `ATUALIZAR_PARA_2_2.txt` na pasta principal. Extraia em uma pasta nova, instale e abra o programa. Em **Configurações OCR**, selecione o `tesseract.exe` da sua instalação e clique em **Testar e salvar**. A busca automática inclui `Downloads\TESSERACT`, sem fixar nome de usuário no código. O caminho fica salvo para as próximas aberturas.

Para preservar o histórico, feche as duas versões, faça backup e copie `dados_v2` da 2.1 para a pasta nova antes de começar a usar a 2.2. Não sobrescreva dados novos. Não copie a `.venv`. Atendimentos cuja leitura havia falhado podem ser selecionados e lidos novamente com **Reanalisar documentos**, sem duplicação e com histórico preservado. A reanálise substitui a leitura atual com confirmação explícita e exige nova conferência. Casos preparados são protegidos.

## Causa e correções

A versão 2.1 procurava no PATH, Program Files e alguns diretórios em LocalAppData, mas não em `Downloads\TESSERACT`. Um caminho de variável que não existia também podia ocultar uma instalação válida. A busca agora considera configuração salva, variável, PATH, chaves conhecidas do Registro do Windows, Program Files (64/32 bits), LocalAppData, Downloads e pastas portáteis ao lado do aplicativo. Um caminho ausente permite procurar outra instalação; o diagnóstico executa o mecanismo encontrado antes de indicar sucesso.

O instalador chamava Python com código embutido em `-c`, incluindo aspas internas. A passagem de aspas por PowerShell/linha de comando do Windows podia alterar esse texto. As verificações agora ficam em `instalacao_aux.py`, chamado como arquivo, sem código Python embutido. O Python auxiliar foi compilado e executado nos testes. O `.bat` mantém o código de saída do instalador, e o PowerShell usa saída UTF-8 no próprio processo.

A tela mostra um indicador de OCR. Verde exige resposta do Tesseract, presença de português e inglês e leitura REAL de uma imagem fictícia em `por`, `eng` e `por+eng`. Ausência do executável, idioma faltante, arquivo não executável ou falha na leitura deixam um aviso visível. A escolha manual só é gravada depois de um teste aprovado; falha ou cancelamento preservam a configuração anterior.

No Windows a configuração fica em `%APPDATA%\CadastroAssistidoShift\ocr.json`, separada do código e do Shift. Sem APPDATA, o padrão é `dados_v2/configuracao_ocr.json`. `SHIFT_OCR_CONFIG` permite um local alternativo para testes/instalações controladas. O arquivo contém somente o caminho do executável. Não contém documentos, credenciais nem texto OCR. Não deve ser publicado no GitHub.

Os modelos `por.traineddata` e `eng.traineddata` continuam incluídos em `tessdata`, com hashes e licença. O diretório do pacote é passado explicitamente ao Tesseract quando contém os idiomas, evitando depender de TESSDATA_PREFIX de outra instalação. `SHIFT_TESSDATA`, quando explicitamente definida, é respeitada; o diagnóstico aponta idiomas faltantes se essa pasta estiver incompleta. Nenhum modelo nem documento é baixado durante a leitura.

## Verificação executada

Resultado: **89 testes aprovados, zero falhas e zero ignorados**, incluindo **16 testes na interface Tkinter real**.

Comando: `DISPLAY=:88 SHIFT_GUI_TESTS=1 .venv/bin/python -m unittest discover -s tests -v`.

Ambiente: Linux Debian 13, Python 3.12.14, PyMuPDF 1.26.6, Pillow 13.0.0, Tesseract 5.5.0, Xorg com driver dummy. Veja `RESULTADO_TESTES_2_2.txt`.

Os testes novos cobrem busca em Downloads sem PATH, caminhos comuns e Registro simulado, seleção de executável em caminho com espaços/acentos, persistência em outro processo e após reiniciar a interface, idioma inglês ausente, executável inválido, configuração corrompida e recuperação, falha sem sobrescrever preferências, argumentos de subprocesso do Windows simulados, auxiliar do instalador, status visível e leitura ponta a ponta. Imagem e PDF escaneado fictícios são reconhecidos com o executável escolhido; paciente, guia e dois exames são conferidos nas tabelas/campos da interface. A reanálise recupera um atendimento originalmente sem OCR, mantém o mesmo ID e preserva a leitura inicial e revisões. Os testes anteriores de extração, tabelas, comparação, revisão humana e exportação local continuam passando.

Há testes que bloqueiam `socket.socket` para impedir chamadas de rede Python. O Tesseract é executado localmente. Nenhum documento clínico real foi utilizado ou enviado.

## Limites da validação

Não houve execução nativa no Windows, acesso ao computador do usuário ou execução do binário instalado nele. A detecção do caminho informado é exercitada com uma estrutura equivalente `Downloads/TESSERACT/tesseract.exe`; o caminho real deve ser selecionado/testado no computador de destino.

PowerShell 5.1, winget, atalho, permissões, antivírus e execução nativa do Tesseract continuam pendentes de validação no Windows com `TESTAR_WINDOWS.bat`. Eliminar o código Python embutido remove a dependência das aspas que causava o SyntaxError; isso não equivale a certificar todo o instalador nativo.

Esta atualização concentra-se nos sete itens solicitados: localização, seleção, persistência, idiomas, instalador, estado visível e leitura fictícia. Mantém a extração e a conferência existentes. Rotação arbitrária, manuscritos e todos os layouts TISS não são garantidos. Não foi acrescentada automação de produção, consulta ao Shift real ou impressão oficial. O plano futuro está em `PLANO_PROXIMAS_ETAPAS.md`.
