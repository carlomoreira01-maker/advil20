# Etapas futuras — proposta, sem conexão de produção

A versão 2.2 mantém a correção de instalação/OCR e o fluxo local atual. O material de contexto propõe etapas adicionais; elas não foram executadas no Shift real.

1. Fluxo de cadastro: separar identificação mínima, associação de documentos e comparação do cadastro completo. Exigir confirmação da identidade antes de reutilizar ou criar paciente. Projetar estados explícitos e bloquear campos sem origem/certeza. Ampliar layouts TISS com exemplos sintéticos aprovados, separando número de guia/autorização e CRM/UF.
2. Lotes: ampliar a fila existente com identificador por atendimento, estados de extração, revisão e pré-cadastro; manter arquivos/modelos isolados por caso. Usar transações e chaves de duplicidade. Extração concorrente deve ser limitada; gravação externa futura deve ser sequencial e revisada.
3. Simulação RPA: criar site local fictício e um adaptador Playwright desligado por padrão. Cobrir busca de paciente, confirmação/criação, fonte pagadora, guia, médico, exames, anexos, prevenção de duplicidade e confirmação da O.S. Somente testar etiquetas fictícias no simulador.
4. Antes de qualquer produção: revisar escopo, permissões e sessão autorizada com TI e responsáveis; validar dados mínimos, recuperação de falhas e auditoria sem conteúdo clínico nos logs. Qualquer integração real exigirá instrução explícita posterior. Não alterar banco, fonte, autenticação ou configurações internas do Shift.
