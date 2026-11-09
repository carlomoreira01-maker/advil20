# Cadastro Assistido Shift 2.5.3: integração verificável com o simulador

O pré-cadastro conferido agora possui uma entrega explícita à RPA simulada, com os valores da revisão aprovada e os arquivos originais. A integração de gravação no Shift real permanece bloqueada e não homologada.

## Causas verificadas e mudanças

1. **A demonstração estava separada do atendimento.** `rpa_training_ui.open_training()` criava `demo_data()`. `SimulatedRPA.__init__()` gerava novos PDFs. Mesmo uma demonstração bem-sucedida não comprovava que o pré-cadastro da interface chegava ao navegador. O treinamento antigo foi preservado; `rpa_handoff.build_handoff()`, `SimulatedRPA.from_handoff()` e `rpa_case_ui.open_case_simulation()` implementam a entrega do atendimento fictício conferido.
2. **Os anexos pressupunham dois arquivos.** O servidor e `fill_order()` exigiam exatamente dois anexos, incompatível com um PDF integral contendo pedido e guia. `Simulation.__init__()` aceita um manifesto explícito associando as funções aos SHA-256 físicos. O mesmo original pode cumprir ambas as funções; o navegador recebe um arquivo íntegro, sem gerar outro PDF. O contrato antigo de dois arquivos continua válido quando não há manifesto.
3. **A aprovação não estava vinculada ao resultado da interface.** A nova entrega exige status PREPARADO, revisão esperada, catálogo vigente, modelos iguais aos aprovados, ausência de pendências, cinco confirmações, revisor e declaração de dados fictícios. Confere os originais na construção e antes de abrir a sessão. Não aceita rascunho como aprovação nem converte dados desconhecidos para a demonstração padrão.
4. **O profissional poderia ser apresentado apenas por CRM/UF.** A nova entrega também confere o nome com o profissional fictício cadastrado. Não seleciona outro nome por possuir o mesmo número impresso.
5. **Callbacks sobreviviam ao fechamento de janelas.** O teste gráfico identificou `invalid command name ...poll` após destruir uma janela. As janelas de integração, treinamento e inspeção agora cancelam o temporizador no evento Destroy; há um teste que verifica sua remoção da fila do Tk.
6. **Cancelar com uma confirmação já presente podia permitir a próxima etapa.** `SimulatedRPA.interactive()` agora consulta o cancelamento antes da pesquisa, preenchimento e submissão, inclusive quando a expressão de espera já é verdadeira. O teste cancela antes da pesquisa e após a confirmação; nenhuma O.S. fictícia é gerada.

## Módulos e funções

- Novos: `rpa_handoff.py` (construir, validar e rastrear a entrega), `rpa_case_ui.py` (conferência e sessão), `treinamento_integrado.py` (mesmo aplicativo com base fictícia separada), `validar_integracao_253.py` (gabarito reproduzível).
- Alterados: `lis_simulado.Simulation.__init__/create`, `lis_simulado.start_lis`, `rpa_simulada.SimulatedRPA.__init__/from_handoff/fill_order/interactive`, `workbench.Workspace.make_preview`, encerramento de `rpa_training_ui.open_training` e `shift_inspection_ui.open_inspection`.
- Preservados os leitores, interpretadores TISS, comparadores, agrupamento, cache, correções manuais, rascunhos, validação de autorização e bloqueio de integração real. As mudanças visuais se limitam ao botão funcional do pré-cadastro e à identificação do treinamento.

## Uso do treinamento

`INICIAR_TREINAMENTO_INTEGRADO.bat` abre o aplicativo existente em `dados_treinamento_integrado`, separado de `dados_v2`. Não cria confirmações humanas. Importa somente exemplos reconhecidos pelo manifesto da base; prepara o catálogo SIM-LAB e o perfil FICTICIO sem alterar as configurações da rotina. Os exemplos são preservados ao reabrir, evitando novos arquivos com hashes diferentes a cada treinamento.

O mapeamento de treino é explícito: fonte IPASGO do exemplo para FONTE-FICTICIA no LIS local; código TUSS fictício para o procedimento fictício, com o código interno SIM-LAB registrado na entrega. Isso não homologa IPASGO, códigos internos ou qualquer regra para produção. O conjunto do simulador continua restrito a cinco exames de quantidade 1. Valores dos campos 23 e 30 permanecem na interface e no pré-cadastro; o formulário de treino atual não os transmite para um campo de produção.

`record_result()` mantém um registro separado da simulação e um evento técnico sem nomes ou dados clínicos. Não altera o resultado aprovado para sugerir envio ou O.S. real. A proteção persistente de duplicidade do simulador continua ativa, inclusive após fechar e reabrir o navegador.

## Validação e evidências

Os resultados e os logs efetivos são entregues em `RESULTADO_TESTES_2_5_3.txt` e `INTEGRACAO_COMPLETA_2_5_3.json`. O gabarito compara valores esperados/encontrados nos widgets, na origem da página/região e no navegador, não apenas caracteres de OCR. Inclui correção manual de CRM, um arquivo nas duas funções, outro paciente, dados alterados, originais alterados, revisão/catálogo antigos, falta de confirmação, duplicidade e cancelamento. O percurso integrado usa cliques reais no Tk e Playwright; somente os diálogos de seleção e a resposta humana de confirmação são simulados pelos testes.

Na execução inicial desta rodada, o Python da `.venv` não possuía Playwright: 299 testes passaram e 13 falharam na importação do componente opcional, antes de abrir o navegador. Os 13 foram reexecutados e passaram com o Python que já continha Playwright 1.62. Essa falha de preparação não foi apresentada como defeito do OCR ou correção do código. A suíte final e a validação do ZIP utilizam o ambiente com os componentes efetivamente instalados.

Os relatórios históricos da 2.5.2, incluindo 539 verificações de campos, foram preservados. Não foram apresentados como uma nova medição de precisão ou velocidade. Esta rodada não modifica OCR, resolução, cache ou paralelismo; não há alegação de novo ganho de desempenho.

## Bloqueio de acesso ao Shift real

O usuário confirmou que o endereço é produção. A observação atual do ambiente tem política restrita aplicada, revisão 1 e lista customizada vazia. O domínio `sh.labsaudeonline.com.br` está no rascunho salvo, mas não na política em execução. A tentativa anterior recebeu 403 do proxy antes do login; sem mudança aplicada, não foram repetidas tentativas nem utilizadas credenciais.

Ambiente: `ccarenv_b64_Y2NhcmVudl9mZjI3NThkZjY5ZWM4MTkxODVjZDdkNjZjNDIyNTc3OQ`. O desktop é anunciado como disponível, mas não foram oferecidas ferramentas `cua_repl.js`, `open_in_codex` ou `cloud_environment.request_changes`. As ferramentas de onboarding salvam propostas e não aplicam/publicam a configuração. A liberação precisa de revisão e salvamento nas configurações; publicação quando oferecida. A skill de ambiente orienta: “Ask the user to review domain additions”. Fonte: `skill://plugin_connector_1p_c5b7d5df5d7081918f2c4be5a633ed5d/cloud-environment-runtime/SKILL.md`.

Não houve login real, consulta de prontuários, criação de pacientes/O.S. ou impressão oficial. `rpa_bloqueado.ShiftRPA.enviar()` continua impedindo gravações. O inspetor local pode levantar somente estrutura sem valores para posterior revisão; não comprova automação de produção.

## Limitações restantes

- Windows nativo, instalação em computadores do laboratório e comportamento do antivírus não foram executados nesta nuvem Linux.
- As telas autenticadas do Shift real, seus seletores e seu comportamento ainda não foram inspecionados. Não há comprovação de operação 100% em produção.
- Códigos internos, fontes pagadoras, regras de atendimento, cadastro de médicos, confirmação da gravação, duplicidade e mecanismo oficial de etiquetas exigem homologação da equipe e testes próprios antes de habilitar o adaptador real.
- Layouts não cobertos, ilegibilidade, nomes incompletos e divergências continuam exigindo conferência. A simulação não dispensa requisitos de um cadastro real.
