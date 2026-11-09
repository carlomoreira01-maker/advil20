# Correção funcional e preparação RPA 2.5.1

## Base preservada e causas

Base: versão 2.5.0, backup do ZIP conferido por CRC e SHA-256, com 294 arquivos. Os 268 testes anteriores passaram antes das alterações.

O painel 2.5.0 chamava `import_scans(mode='multiple')` nas duas abas. Assim, nomes parciais ou páginas sem identificação provocavam separações, e arquivos diferentes podiam ser associados por identificadores comuns. O núcleo já possuía o modo `single`, que atribui um grupo a cada arquivo. O painel agora usa esse modo nas duas abas; a associação automática por identidade fica em uma opção avançada explícita. O default da API legada `read_scan` foi mantido por compatibilidade; o aplicativo define o modo explicitamente.

`tiss_names.name_words` podia incluir SIM/NÃO de uma célula vizinha quando seu rótulo não era reconhecido. Essas respostas são excluídas da seleção do nome, sem juntar fragmentos de pessoas distintas. Valor e região são testados. Nomes divergentes não são corrigidos por suposição: a ficha permanece provisória e exige revisão.

## Leitura e tempos

- `reading_cache.py`: cache local gzip/JSON, escrita atômica, chave por conteúdo, configuração, idiomas, binário/modelos e código do leitor. Limites de 128 entradas/256 MB. Falha de cache não impede leitura; falha de OCR não é reutilizada como sucesso. O cache contém texto local e requer o mesmo controle de acesso da pasta de atendimentos; não é criptografado.
- `engine_v2.read_document`: extração digital preservada; renderização PyMuPDF permanece serial. Apenas o OCR das imagens é paralelizado em até dois workers, com fila limitada. Nenhum objeto PyMuPDF é compartilhado entre threads. Coordenadas e ordem das páginas são preservadas.
- `reading_control.page_workers`: limita a concorrência por CPU/memória. Máquinas com menos de 4 GB usam uma página. A variável técnica `SHIFT_OCR_WORKERS=1` permite limitar ainda mais. Não há aumento sem limite de processos.
- `ocr_regions.collect_regions`: mantém releituras de regiões com campos/quantidades incertos; evita repetir bandas já identificadas com confiança suficiente. Resolução, correção de orientação e inclinação permanecem.
- `reading_control` e `ocr_runtime.run_local`: cancelamento cooperativo; processos Tesseract em andamento podem ser encerrados. Importação é entregue à fila somente quando o lote termina; cancelar antes da gravação não cria fichas parciais.
- `scan_import`: tempos de leitura por arquivo, OCR por página, interpretação por página e consolidação. Consulta em área técnica separada. Reclassificar, mover páginas e editar campos não fazem OCR.

Os números medidos estão em `DESEMPENHO_2_5_1.json`: mesmo hardware, mesmos arquivos sintéticos, execução sequencial das versões, separando cache frio/quente. A paridade de valores com a base é medida separadamente do gabarito de campos. Ganho no escaneamento testado não estabelece ganho universal; PDF digital pequeno pode ter custo adicional de verificação do cache.

## Classificação e fluxo

A classificação combina títulos de pedido/guia, células TISS, ANS, beneficiário/solicitante e alinhamento das colunas. Novos títulos de pedido são reconhecidos. Pedido sem título pode usar lista, paciente e identificação profissional como conjunto de evidências; carimbo isolado não define tipo. Estrutura parcial TISS continua reconhecida quando não há evidência consistente de pedido. Essa condição foi ajustada após a regressão detectar uma guia parcial de três campos.

Pedido isolado não cria guia; guia isolada não cria pedido. Desconhecido permanece incerto. As correções de tipo continuam disponíveis sem reimportar.

`Reunir páginas deste PDF` recupera divisões de um lote antigo, preservando o original e sem OCR. Não confirma a identidade; conflitos impedem confirmação e preparação. `Mover página` permite separar pessoas ou criar um novo grupo. PDFs distintos continuam distintos no modo padrão. O modo avançado conserva a associação conservadora anterior, sujeita a revisão.

As cinco telas, campos editáveis, estados de leitura, catálogo configurável, pré-cadastro rascunho, regras homologadas e preparação validada foram preservados. Acessar rascunho não aprova autorização ou identidade. Os testes anteriores que esperavam separação automática no painel passaram a selecionar explicitamente a opção avançada; o teste da aba individual agora exige uma ficha provisória com conflito bloqueado. As expectativas de segurança e preservação das páginas permanecem.

## Primeiro módulo RPA

`rpa_simulada.SimulatedRPA` recebe dados estruturados e aprovação vinculada ao hash do conteúdo, com revisor e cinco conferências. Opera somente um servidor próprio em `127.0.0.1`; não recebe URL de produção. Rotas do navegador para outros destinos são bloqueadas.

`lis_simulado` e `simulador_web/lis.html` implementam pesquisa e reutilização do paciente existente, fonte pagadora, guia/senha, médico cadastrado, procedimentos, anexos, O.S. fictícia e prévia de etiquetas. A identidade precisa ser confirmada no navegador antes do preenchimento. A criação exige confirmação humana final, dados iguais aos aprovados e hashes dos dois anexos sintéticos. Duplicidade por atendimento e por paciente/fonte/guia é bloqueada em banco local de treinamento, inclusive após reiniciar a sessão.

O treinamento gera seus próprios PDFs e só aceita pacientes/códigos fictícios conhecidos. A tela não envia a ficha clínica selecionada. O resultado é `OS-SIM-*`, com `os_real: null`; etiquetas trazem DEMONSTRAÇÃO SEM VALIDADE e não chamam impressão. O simulador antigo foi preservado.

Essa implementação valida o contrato e o fluxo de automação; não é um adaptador de produção nem uma importação automática de qualquer pré-cadastro no Shift. Seletores, autenticação autorizada, regras e mapeamento da instância real dependerão de homologação futura. Não há contorno de CAPTCHA, permissões ou login.

## Validação e limites

Veja `RESULTADO_TESTES_2_5_1.txt` para contagens finais e log, `RELATORIO_CAMPOS_INTERFACE_2_5_1.json` para valores/estado/origem/widgets e `RPA_INTERFACE_2_5_1.json` para o fluxo de navegador.

Os testes usam exclusivamente documentos sintéticos, OCR e interface reais em Linux. Windows nativo, instaladores/browsers do Windows, DPI e desempenho no equipamento da recepção não foram executados neste ambiente. Guias ilegíveis, manuscritos e layouts não cobertos podem exigir revisão. Dados obrigatórios, catálogo interno e regras de fonte pagadora continuam dependendo do laboratório.
