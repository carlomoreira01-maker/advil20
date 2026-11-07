# Cadastro Assistido Shift — versão 2.3

Comece por **[ATUALIZAR_PARA_2_3.txt](ATUALIZAR_PARA_2_3.txt)**. O projeto continua sendo o mesmo aplicativo desktop local Python/Tkinter, com histórico SQLite e originais preservados. Não se conecta ao Shift real.

## O que mudou

- Campos SP/SADT separados por rótulo, número e coordenadas: guia do prestador, guia principal, data/senha/validade da autorização, guia da operadora, carteira/validade, beneficiário, código do solicitante, médico, conselho/número/UF e data da solicitação.
- Texto e zeros iniciais preservados. Números de controle/etiquetas são classificados separadamente; não viram senha ou autorização.
- PDFs digitais continuam com extração direta. OCR local trata orientação 0/90/180/270, contraste, nitidez e inclinação pequena. Coordenadas recuperadas no documento original, sem modificar os arquivos importados.
- Procedimentos solicitados e executados ficam separados. Quantidades solicitada e autorizada não se confundem; quantidade autorizada vazia, zero ou ilegível bloqueia autorização. Status explícito negado também bloqueia.
- Catálogo de produção inicia vazio, sem códigos DEMO automáticos. Código interno do Shift só existe quando fornecido pelo laboratório. Correspondências por código/nome/sinônimo são explícitas, sem aproximação que invente procedimentos.
- Perfis de fonte pagadora configuráveis por formulário, com escopo, responsável, data, campos obrigatórios, mapeamento e valores técnicos aprovados. Marca da operadora não substitui fonte pagadora. Modelos de IPASGO, interno e outros são não homologados.
- Fluxo interno individual sem guia externa, somente sob perfil explícito homologado. Não há dispensa global de autorização para todos os pacientes internos.
- Fila por atendimento, lote CSV com pares explícitos, conferência de identidade e bloqueios de divergência. Telas agrupadas em Paciente, Guia TISS e Médico/atendimento. Diagnóstico distingue OCR, interpretação e interface.
- Simulação funcional local em navegador com pesquisa, confirmação de identidade, solicitante, anexos fictícios, O.S. simulada e prevenção de duplicidade; testes Playwright. Nenhuma autenticação real é solicitada.
- Instalador principal simplificado em Python: sem PowerShell, winget ou mudança de políticas de segurança. Bibliotecas são instaladas via pip com TLS, a partir do arquivo de versões fixadas.

## Instalação

Extraia todo o pacote em pasta nova. Tenha Python 3.12 a 3.14 e Tesseract de origem confiável já instalados. Abra `INSTALAR_WINDOWS.bat`, depois `INICIAR_WINDOWS.bat`. Em **Configurações e ferramentas → Diagnóstico e configuração OCR**, selecione `tesseract.exe` e teste/salve. Os idiomas `por` e `eng` estão em `tessdata` com licença e hashes.

O programa funciona sem internet após as dependências estarem instaladas. A internet é usada somente para instalação das bibliotecas. A simulação em navegador usa exclusivamente loopback do próprio computador.

## Documentos fictícios e testes

A pasta `exemplos_tiss` contém guias completas, sem autorização, autorizada zero, duas tabelas, múltiplas páginas, outro paciente, CRM ilegível, exemplo Unimed, exame desconhecido, material e pedidos girados/inclinados. Todos os dados e códigos são fictícios. `08_atendimento_interno_ficticio.json` documenta o exemplo sem guia externa; o perfil aprovado é somente uma fixture, sem homologação real.

O relatório [RELATORIO_CAMPOS_2_3.json](docs/RELATORIO_CAMPOS_2_3.json) compara valores esperados e obtidos e preserva página, região e trecho. Não é apenas um teste de retorno de texto OCR.

A suíte inclui interface Tkinter real, comparação, revisão até pré-cadastro local, migração compatível de campos e identidade de duplicidade legada, mais navegador Playwright. Veja [CORRECAO_2_3.md](docs/CORRECAO_2_3.md) e `docs/RESULTADO_TESTES_2_3.txt`.

No Windows, `TESTAR_WINDOWS.bat` testa o diagnóstico e a suíte principal com interface. Testes automatizados de navegador são opcionais: dependem de Playwright e Chromium, não são instalados no computador da recepção por padrão. Em ambiente de desenvolvimento validado:

```bash
DISPLAY=:89 SHIFT_GUI_TESTS=1 SHIFT_BROWSER_TESTS=1 python -m unittest discover -s tests -v
```

## Rastreabilidade e segurança

Originais, texto extraído e revisões são dados locais do atendimento em `dados_v2`; não são enviados a APIs. Os logs técnicos guardam estado e contagens, sem conteúdo clínico, nomes de paciente ou stderr dos documentos. Os dados locais não são criptografados pelo aplicativo: controle o acesso e faça backup com o programa fechado.

A senha TISS é um campo do documento de autorização, preservado no atendimento. Senhas de login do Shift não são solicitadas nem armazenadas. Revisão humana continua obrigatória. Nenhuma O.S. real é criada, nenhum arquivo é enviado ao Shift e nenhuma etiqueta oficial é impressa.

Se o antivírus bloquear um arquivo, mantenha a proteção e obtenha nome da ameaça/arquivo. Os testes funcionais e hashes não são certificação antivírus. Não classifique o alerta anterior como falso positivo sem investigação.

## Limites

Os layouts foram validados com documentos sintéticos que exercitam a numeração/rótulos solicitados. Isso não certifica todas as versões TISS nem todos os formulários reais de Unimed/IPASGO. Campos não legíveis ou rótulos não reconhecidos devem ficar não identificados e exigir conferência. Os perfis financeiros, catálogo, materiais e códigos dependem do laboratório. Execução nativa Windows e análise do alerta antivírus permanecem pendentes.

A reanálise existente atende pares pedido/guia. O fluxo interno inicial é individual e sua reanálise específica sem guia não foi ampliada. O simulador é isolado, com dados fictícios; não é um adaptador de produção.

As versões e documentos anteriores permanecem no histórico e nos relatórios 2.1/2.2. As instruções atuais são as da versão 2.3.
