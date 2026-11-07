# Correção e evolução 2.3

## Diagnóstico

O fluxo real é importação → leitura PyMuPDF/Tesseract → palavras/linhas → interpretação → SQLite/fila de eventos → variáveis e tabelas Tkinter. A 2.2 já chamava o OCR, mas seu modelo genérico juntava diferentes identificadores em Guia e mantinha uma quantidade única. Isso não representava uma guia SP/SADT. Rótulos numerados, valores em células, números grudados no rótulo pelo OCR e a tabela executada não eram distinguidos com segurança.

A versão 2.3 mantém o fluxo e acrescenta interpretação geométrica separada. O OCR pode ter sucesso e a interpretação falhar; a interface registra essas etapas separadamente. Os testes induzem erro de atualização de UI para verificar que o diagnóstico não o apresenta como falha de OCR.

## Implementação e campos

`tiss.py` usa rótulos numerados e coordenadas, com verificação semântica do rótulo. O perfil de numeração contempla os campos solicitados 2–10, 13, 15–18, 22 e 25–28. Não usa número isolado como prova da finalidade. Rótulos como `18-UF` são tratados. Valores de identificadores permanecem strings, inclusive zeros iniciais. Data/validade da senha, carteira e diferentes guias não são intercambiáveis.

Campos repetidos com valores diferentes ou OCR de baixa confiança preservam candidatos e exigem conferência. Nome e descrição quebrados em linhas preservam os trechos de origem. O nome estruturado do solicitante e seu conselho/número/UF têm origem em campos próprios; não se extrai CRM do código do contratado ou CBO. Marca literal em cabeçalho pode identificar operadora, mas não é uma regra de fonte pagadora.

A tabela solicitada possui código, descrição, quantidade solicitada e autorizada, além de material quando presente. Linhas executadas ficam em outra coleção e não criam uma segunda solicitação nem preenchem autorização faltante. Procedimento executado sem correspondente exige conferência. Código ausente do catálogo, descrição/código incompatíveis, material divergente, quantidade ausente/zero/divergente, status explícito negado, paciente divergente ou conselho ilegível impedem preparação no fluxo TISS.

O catálogo de produção vazio é deliberado: a leitura pode ocorrer sem cadastro de exames, mas não inventa códigos internos. Os antigos exemplos DEMO continuam somente por escolha explícita de exemplos. Os novos códigos 90000001 etc. são fixtures fictícias, não uma tabela real TUSS nem códigos Shift. O teste de preparação usa códigos internos SIM-LAB fornecidos explicitamente pela fixture.

## OCR e origem

`ocr_processing.py` avalia orientações ortogonais com OCR local, ajusta contraste/nitidez/resolução e estima inclinação no intervalo pequeno de ±4 graus. A validação usa 2 graus e quatro orientações. Não se promete correção de toda fotografia, perspectiva ou manuscrito. Tabelas recebem uma segunda leitura local para palavras/números espacialmente ausentes, sem copiar quantidades da coluna solicitada para a autorizada. Quantidades com baixa confiança continuam não identificadas. Nenhum original é alterado.

Caixas da leitura corrigida são transformadas para o sistema de coordenadas original, inclusive para páginas PDF renderizadas. A interpretação utiliza coordenadas de leitura; o botão Origem usa caixas do original. Campos, procedimentos e células mantêm documento/página/região/trecho. Configurações de perfil são identificadas como origem de configuração, sem fabricar documento de autorização.

## Mapeamento e interface

`payer_mapping.py` valida perfil, fonte pagadora, tipo de atendimento e procedimentos abrangidos. A seleção de um perfil não homologa automaticamente regras. Homologação requer responsável, data e escopo. Padrões técnicos exigem aprovação específica; não há zero automático. Operadora não substitui fonte pagadora.

O formulário de configuração permite cadastrar/editar perfis, escolher a origem de cada campo Shift, marcar obrigatoriedade e padrões aprovados sem alterar código. Perfis são dados locais do aplicativo. Modelos fornecidos são não homologados. Atendimento interno sem guia externa só usa perfil explícito com dispensa de autorização e escopo compatível; não dispensa todos os pacientes internos. Esse fluxo é individual.

A interface foi agrupada em Paciente, Guia TISS e Médico/atendimento, com importação destacada e ferramentas técnicas separadas. A fila preserva atendimentos independentes, leitura pendente/concluída, informações incompletas, divergência, conferência e preparação. Processado refere-se somente à simulação; nunca a envio ao Shift real. Os estados de leitura são transitórios, e o histórico de caso mantém revisões e originais.

## Simulação e integração futura

`simulador.py` contém um serviço somente em loopback com dados fictícios e uma interface web local. Nome isolado não permite busca segura; confirmação exige correspondência única por identificadores. Há seleção de médico conhecido, criação simulada de paciente com aprovação explícita, anexos fictícios, códigos e quantidades de teste e O.S. simulada com prevenção de duplicidade. Nenhuma impressão oficial é disparada.

Os testes Playwright percorrem pesquisa, revisão, médico, anexos, preparação, mudança de identidade e duplicidade no navegador. O serviço não recebe dados do atendimento clínico da aplicação: é uma demonstração funcional isolada. Nenhuma sessão ou URL do Shift real é acessada. A futura integração de produção depende de homologação, acesso autorizado e uma tarefa posterior.

## Validação e limites

Resultado: **133 testes aprovados, zero falhas e zero ignorados**, incluindo 25 testes de interface Tkinter e 3 no navegador. **350 comparações por campo/procedimento aprovadas**, com página/região de origem. Veja `RESULTADO_TESTES_2_3.txt` e `RELATORIO_CAMPOS_2_3.json`. O ambiente é Linux Debian 13, Python 3.12.14, PyMuPDF 1.26.6, Pillow 13.0.0, Tesseract 5.5.0, Tkinter/Xorg e Chromium com Playwright 1.62.0. Todos os testes usam dados fictícios. O relatório por campo verifica também valores estruturados e origem; os testes de interface verificam widgets visíveis e a preparação local com conferência, não somente texto OCR.

Não houve validação nativa no Windows nem homologação de documentos reais do laboratório. Permanecem sujeitos a conferência: manuscritos, rasuras, fotografias deformadas, variações TISS não exercitadas, rótulos desconhecidos, layouts sem âncoras reconhecíveis, informações adicionais em carimbos e exames fora de catálogo. Não é garantido reconhecer todos os exames de qualquer documento legível. A simulação não constitui cadastro real.

Para uso operacional, a equipe precisa homologar numeração/rótulos e versões de guias usadas, contratos/fontes, escopos internos/IPASGO/outros, mapeamentos, validade, códigos/sinônimos, materiais e critérios de identidade. Data de execução e indicação clínica não são inferidas da data de solicitação; requerem informação explícita/conferida.

O novo instalador não usa PowerShell/ExecutionPolicy, winget ou alteração de segurança. Não inclui o executável do Tesseract nem baixa instaladores de programas. Isso não demonstra ausência de malware nem resolve uma detecção cujo nome/arquivo nunca foi informado. Mantenha bloqueios do antivírus até identificar o alerta. Hash e testes funcionais comprovam integridade/comportamento testado, não certificação antivírus.
