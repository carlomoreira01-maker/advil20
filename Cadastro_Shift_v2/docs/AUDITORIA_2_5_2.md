# Auditoria adicional 2.5.2

## Escopo verificado

O ZIP 2.5.1 foi preservado e conferido (316 arquivos, SHA-256 `4249d08876a8be3350dc1dab560feb4b9df077efdcd3b27c254a4fe793708805`). Os 296 testes da base passaram novamente. A primeira tentativa de testes foi interrompida porque o display não estava ativo; o Xorg foi restabelecido e a execução completa foi repetida com sucesso.

Todos os documentos e cadastros utilizados nos testes desta rodada são sintéticos. Os testes de navegador operam no simulador em loopback. A tentativa de acessar a página pública de produção foi separada dos testes e não enviou credenciais.

## Falhas reproduzidas antes das correções

`REPRODUCAO_2_5_2.json` registra cinco verificações que falharam na versão anterior:

1. Seleção divergente não revogava a identidade confirmada anteriormente.
2. Essa confirmação antiga ainda permitia criar uma O.S. fictícia após seleção inválida.
3. O conjunto fixo de PDFs fictícios tinha quantidade 1, mas o contrato aceitava outra quantidade nos dados aprovados.
4. Um rascunho com modelos antigos podia ser salvo usando a revisão atual lida do banco, ocultando que a interface estava desatualizada.
5. A reimportação reutilizava uma cópia local já existente sem conferir se seu conteúdo ainda correspondia ao hash original.

## Correções implementadas

- `lis_simulado`: pesquisa e seleção revogam confirmações anteriores; nova confirmação gera token exclusivo. A criação exige esse token atual, dados aprovados iguais inclusive nos tipos JSON e confirmação humana final. Dados malformados retornam bloqueio e não criam O.S. Os exames/quantidades precisam corresponder aos cinco procedimentos de quantidade 1 dos PDFs de treinamento. Isso limita deliberadamente esse simulador ao conjunto sintético que ele gera.
- `simulador_web/lis.html` e `rpa_simulada`: alterar identificadores limpa token, confirmações e autorização final. O preenchimento verifica a confirmação atual no navegador e no servidor. Uma nova pesquisa não utiliza resultados antigos da tela.
- `draft_workflow`: revisão esperada é obrigatória e conferida sob transação; motivo e modelos são gravados atomicamente. `workbench` transmite a revisão vista pelo atendente e preserva a nota ao salvar rascunhos em lote. Uma revisão desatualizada é recusada com orientação para reabrir a ficha.
- `scan_import`: verifica o conteúdo da cópia local mesmo quando a leitura vem do cache. Não sobrescreve silenciosamente um original alterado.
- `document_integrity` e `CaseStore.prepare`: reconferem as cópias locais conhecidas antes de preparar o pré-cadastro. Documento indisponível ou alterado impede a preparação; nenhum resultado é gravado nesse caso. Fluxos legados sem referência física não recebem uma comprovação de integridade inventada.
- `rpa_bloqueado`: mensagem distingue inspeção disponível de gravação em produção ainda não homologada.

A bateria adicional inclui ainda revisão concorrente pela interface, alteração e reversão de identidade no navegador, token obsoleto, quantidade booleana no lugar de número, JSON malformado, pesquisa repetida e proteção do relatório estrutural. Os contratos internos de rascunho e confirmação do simulador foram atualizados nos respectivos chamadores e testes, mantendo as expectativas de bloqueio e revisão humana.

## Site de produção e bloqueio real

Domínio informado: `sh.labsaudeonline.com.br`. A consulta pública pelo proxy recebeu `403` na abertura do túnel HTTPS, antes do login. A política de rede estava aplicada e não incluía esse domínio. Foi salva uma proposta contendo somente esse domínio adicional; a ferramenta retornou `saved` e `requires_publish: true`. Isso não aplica a regra ao ambiente em execução.

Nenhuma credencial foi usada ou incluída em arquivos, configuração, relatórios ou GitHub. Não houve acesso autenticado, mapeamento validado das telas reais, criação de O.S. real ou impressão oficial. A integração real não foi declarada concluída.

O ambiente verificado foi `ccarenv_b64_Y2NhcmVudl9mZjI3NThkZjY5ZWM4MTkxODVjZDdkNjZjNDIyNTc3OQ`, com observações atuais e política de rede `enforced`. O desktop compartilhado estava habilitado com estado `unknown`; a ferramenta JavaScript de controle do desktop não estava disponível. A conectividade pública pôde ser verificada por HTTP via proxy; os testes locais usaram Xorg e Playwright.

Para avançar na inspeção pela nuvem, é necessário revisar, salvar e publicar a liberação do domínio nas configurações do ambiente e confirmar sua aplicação com uma conexão nova. Não foi tentada rota alternativa para contornar o bloqueio.

## Inspeção local opcional

`shift_inspection.py`, `shift_inspection_ui.py` e `INSPECIONAR_SHIFT.bat` permitem abrir o endereço informado no Windows, com login digitado manualmente no navegador temporário. O programa apenas lê a estrutura de controles da tela do domínio autorizado; não preenche campos nem envia formulários.

O exportador não lê valores dos controles, não exporta HTML, screenshots, cookies, tokens de sessão ou URLs internas. Somente aliases técnicos conhecidos e IDs específicos de framework podem gerar seletores candidatos; outros atributos são omitidos. Campos e seletores permanecem não homologados e não habilitam gravação. Uma tela com senha visível não exporta seus controles. O recurso foi testado contra telas sintéticas; sua execução autenticada no Shift real permanece pendente.

## Limitações que permanecem

- Automação de gravação no Shift real, seletores internos, regras por fonte pagadora, códigos internos e fluxo de confirmação precisam ser verificados e homologados; o endereço e as credenciais não bastam para comprová-los.
- Não houve teste nativo no Windows nem medição de desempenho nova no equipamento da recepção.
- OCR de layouts desconhecidos, escrita manual ou documentos ilegíveis pode exigir conferência. Os testes cobrem cenários conhecidos e não provam ausência de qualquer erro possível.
- A inspeção estrutural é uma ferramenta preparatória e não um adaptador de cadastro em produção. Não substitui testes em homologação e conferência humana dos dados reais.

Contagens finais, resultados por campo, matrizes históricas reexecutadas e verificações gráficas estão nos relatórios desta versão.
