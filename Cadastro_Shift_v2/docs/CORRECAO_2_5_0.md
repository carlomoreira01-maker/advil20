# Correção funcional e interface 2.5.0

## Base e fluxo auditado

A atualização modifica o projeto existente sobre a entrega 2.4.5, com seu ZIP íntegro preservado fora da árvore de trabalho. Antes das alterações foram executados os 242 testes existentes: todos passaram, sem ignorados. Os documentos desta rodada são inteiramente sintéticos.

Fluxo preservado: `App.import_scans` → worker local → `scan_import.read_scan` → `engine_v2.read_document` → classificação por página → `parse_document`/`tiss.extract` → agrupamento por identidade → `scan_import.build_cases`/`save_batch` → `CaseStore` → variáveis editáveis → `compare_models`/`review_errors` → revisão humana → preparação local protegida.

O iniciador Windows continua executando `app.py`. Esse ponto de entrada abre a interface `workbench.create_workbench`, que estende o mesmo controlador `App`. Banco, catálogo, extração, armazenamento dos originais, validação, histórico e simulação são os existentes. A conferência detalhada anterior continua acessível pelo menu.

## Causas verificadas e correções

| Problema | Causa no código | Correção |
|---|---|---|
| Contratado executante não identificado | Campo 30 ausente de `tiss.SCHEMA`; o descarte de campos depois da tabela também o excluía. | Campo 30 possui esquema, reconhecimento de rótulos/célula, origem e entrada própria; pode ser extraído abaixo da tabela. |
| Campo 23 incompleto | Valores textuais eram reduzidos à primeira linha. | Indicação clínica reúne as linhas da célula, preservando conteúdo e separação; títulos de seção são excluídos. |
| Indicação clínica aparecendo como exame | Na ausência de procedimentos estruturados, a procura genérica por nomes de exames podia reutilizar o texto do campo 23. | Candidatos dentro da região clínica são excluídos dessa busca; uma indicação mencionando hemograma não cria solicitação. |
| Nome da empresa rejeitado ou confundido com médico | A validação de nomes de pessoas não representa uma razão social. | Extração própria para empresa, permitindo números e nomes empresariais, separada do campo 15. |
| Não era possível distinguir vazio de não localizado | Os dois casos terminavam como um valor vazio. | `extraction_state` e `located` preservam quatro estados; campo vazio localizado mantém página e região. |
| Acesso ao pré-cadastro bloqueado | A preparação validada era a única saída; exigia campos/revisão/perfil/catálogo mesmo para visualizar uma minuta. | `draft_workflow` separa o rascunho da preparação validada. Navegação e rascunho são acessíveis com pendências; o preparo final mantém os validadores existentes. |
| Revisor/motivo difíceis de encontrar | Metadados obrigatórios e ações ficavam distribuídos pela interface detalhada. | Revisor no cabeçalho e motivo na conferência, com foco e mensagem que indicam onde preencher. |
| Excesso de informações na tela | Documentos, campos, alertas, transcrição e opções técnicas concorriam pelo espaço. | Cinco telas, dados complementares recolhidos, opções técnicas secundárias e origem sob demanda. |
| Risco de perder correções ao mudar de ficha | Edições ainda não salvas pertenciam somente ao estado corrente da tela. | Rascunho local por ficha/revisão, restauração ao voltar e invalidação se a revisão base mudar. |
| Progresso antigo após terminar | A notificação moderna só acompanhava mudanças enquanto `busy` estava ativo. | A conclusão do worker também atualiza a mensagem visível com o próximo passo. |

## Campos e identidade

São priorizados os campos 2, 3, 7, 5, 10, 8, 15, 17, 18, 23 e 30, além do conselho 16. Números continuam strings. Campo 17 usa sua célula e é confrontado com outras evidências profissionais; não herda CBO ou UF presumida. As correções anteriores para carimbo e títulos SP/SADT permanecem e são cobertas pela regressão.

As abas **Cadastro de um paciente** e **Cadastro de vários pacientes** aceitam o mesmo importador seguro por evidências. A aba individual não força documentos de pessoas diferentes em uma ficha. Um arquivo com pedido A, guia B, guia A e pedido B produz duas fichas. Nome parcial/ausente não constitui prova suficiente para reunir páginas no modo automático: continuações sem evidências podem exigir associação manual. O modo provisório anterior de reunir um PDF inteiro continua disponível na interface detalhada, sempre sujeito ao bloqueio de conflitos.

Classificação, movimentação de páginas e identificação podem ser corrigidas sem novo OCR. O original integral, página física e região permanecem rastreáveis. Uma guia isolada não cria um pedido nem exames na função pedido.

## Rascunho e preparação

`build_draft` não chama `prepare`. `save_draft` usa a tabela local `rascunhos_locais` e não altera a revisão clínica, o status de preparação nem o resultado validado. Seu JSON declara `RASCUNHO_LOCAL_NAO_ENVIAR`, `os_real: null`, `pronto_para_envio: false` e enumera pendências. O lote salva rascunhos individualmente; não aprova atendimentos em massa. Dados preparados permanecem protegidos.

Salvar correções e salvar conferência exigem identificação do revisor e motivo. A conferência exige ver as páginas e confirmação humana dos dados, ausências, exames e alertas. A preparação validada continua passando por comparação, identidade, quantidades, autorização, perfil homologado e correspondências do catálogo, além da confirmação final. A revisão não remove divergências materiais. Campos não aplicáveis só podem ser aplicados pelas regras homologadas anteriores.

O sistema permanece assistido e local. O objetivo futuro de automatizar o Shift ainda depende de um adaptador autorizado e homologação com o laboratório. Nesta versão há rascunho e simulação, sem acesso ao Shift real, O.S. ou etiquetas oficiais.

Uma instalação nova também foi verificada sem catálogo: cinco exames são lidos em cada documento e o rascunho pode ser salvo. Enquanto não houver correspondência validada no catálogo, a comparação apresenta os candidatos do pedido e da guia separadamente, com código interno pendente; não os aprova nem os considera dois pedidos. A preparação validada depende da configuração do laboratório.

## Arquivos principais alterados/adicionados

- `app.py`: entrada da interface principal, ponte de navegação com rascunho e identificação da versão; controladores anteriores preservados.
- `workbench.py`: telas reais, duas abas, campos editáveis, páginas, exames, ações de conferência, pendências e navegação.
- `priority_fields.py`: campos prioritários, estados e escolha da origem efetivamente presente.
- `draft_workflow.py`: minuta local separada da preparação validada.
- `tiss.py`, `tiss_geometry.py`, `tiss_names.py`: campos 23/30, localização, nomes de empresa e estados.
- `engine_v2.py`: exclusão de indicação clínica da busca de exames e propagação dos estados de leitura.
- `gerar_exemplos_250.py`, `tests/test_modern_core_250.py`, `tests/test_workbench_gui_250.py`, `validar_interface_250.py`: documentos, regressões e relatório por valor/origem/widget.
- `ATUALIZAR_PARA_2_5_0.txt`, `LEIA-ME.md`, `VERSAO.json` e relatórios: instruções e evidências.

## Limites

Resultados e contagens finais estão em `RESULTADO_TESTES_2_5_0.txt` e nos relatórios JSON desta versão. A interface real e o OCR são executados em Linux. Instalador, permissões, binários OCR, DPI e desempenho nativos do Windows precisam de validação local. O pacote mantém os scripts de instalação/inicialização existentes, sem instalador executável novo.

As amostras não certificam todos os layouts. Escrita manual, carimbos degradados, campos com conflito e páginas sem identificação podem continuar exigindo correção humana. Catálogo, códigos internos, regras por fonte pagadora e dispensa de autorização dependem de homologação do laboratório. Documentos reais não foram usados nem incluídos nesta rodada.
