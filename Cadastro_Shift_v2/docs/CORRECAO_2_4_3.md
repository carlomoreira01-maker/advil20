# Correção 2.4.3 — interpretação e conferência de guias reais

Esta atualização modifica o projeto Python/Tkinter existente sobre a 2.4.2, que preserva a base estável 2.4. A pedido do usuário, os dois PDFs reais fornecidos foram processados localmente com Tesseract. Os originais, imagens, nomes, códigos, identificadores e textos clínicos não integram a entrega nem os relatórios publicados. Os documentos são chamados apenas A e B neste relatório.

## Erros encontrados e correções

| Problema | Causa e mudança |
| --- | --- |
| Nomes parciais ou acrescidos de texto estranho | A geometria podia anexar uma letra isolada de outra coluna ou a legenda da seção seguinte. `tiss_names.name_words()` passou a verificar distância e tamanho da fonte. Nomes completos só são recuperados quando efetivamente lidos, sem montagem de sobrenomes. |
| Carteirinha/guia/CRM perdidos ou conflitantes | Segmentação de página inteira omitia caracteres pequenos nas células. `ocr_regions.collect_regions()` faz releituras locais de cabeçalho, beneficiário, solicitante e procedimentos, com posições preservadas. `tiss_refinement.reconcile_fields()` exige leituras concordantes para recuperar campos ausentes e mantém divergências para revisão. |
| Rótulo/data interpretados como senha | O cabeçalho “6-Data Validade da senha” não delimitava corretamente a célula 5. `tiss_geometry.header_token()` e `anchors()` reconhecem essa variação; `cell_words()` limita valores distantes. `tiss.valid()` recusa datas em campos de identificadores. Uma data de validade não pode preencher senha. |
| Conselho contaminado pelo número do CRM | A borda esquerda da palavra cruzava ligeiramente a coluna vizinha. `cell_words()` usa o centro da palavra para associar a célula. Conselho/UF numéricos continuam exigindo correspondência homologada. |
| Quantidades legíveis ausentes | Cabeçalhos fundidos/abreviados e alinhamento à direita dificultavam a associação às colunas. Os rótulos conhecidos são normalizados sem alterar valores. `tiss_refinement.reconcile_exams()` recupera células somente com código impresso correspondente e concordância de leituras locais. Não usa a seção de execução como autorização. |
| Nascimento inválido e conflito de identificação falso | Um sobrenome contendo “Nascimento” podia disparar a regra; o texto após uma data podia ser incluído no valor. `engine_v2.parse_document()` exige e valida uma data após o rótulo, com origem limitada à data. |
| Documento e destaque visual girados | `DocumentView.render()` e `page_panel.PagePanel.load()` apresentam a orientação reconhecida. `document_geometry.rotated_box()` transforma o destaque somente para a tela, mantendo as coordenadas de origem e o PDF intactos. O botão Girar permite ajuste da visualização. |
| Campo incerto sem acesso prático às leituras | `App.candidate_window()` mostra alternativas locais, página e confiança, com acesso à origem e escolha humana. A escolha revoga a confirmação/revisão anterior; não libera pré-cadastro por si só. Códigos numéricos de conselho/UF sem mapeamento não podem ser usados como valor normalizado. |

`ocr_processing.recognize_page()` integra as releituras à transformação de orientação/inclinação. `engine_v2.read_document()` armazena as regiões separadas do texto principal para não duplicar conteúdo e normaliza coordenadas para a página original. O diagnóstico de página exclusivamente escaneada agora informa OCR local, sem rotulá-la como híbrida. O cache de normalização de rótulos é somente em memória. Não foi adicionada dependência de serviço externo.

O fluxo de agrupamento de `scan_import.py` da 2.4.2 foi preservado: modo individual provisório, modo de vários pacientes, conflitos bloqueados, movimentação/classificação sem reimportar e rastreabilidade. A aba Comparar e conferir permanece acessível com pendências. As correções desta rodada atingem a leitura, interpretação e apresentação que alimentam esse fluxo.

## Verificação nos dois PDFs reais

Foram importados pelo aplicativo Tkinter em um diretório privado de teste, com catálogo de produção vazio. Nenhum código fictício foi aplicado aos documentos reais. A execução usou OCR novo das sete páginas; não apenas resultados antigos. Não houve aprovação, pré-cadastro, acesso ao Shift real, criação de O.S. ou impressão.

| Verificação | Documento A | Documento B |
| --- | --- | --- |
| Páginas preservadas | 3 de 3 | 4 de 4 |
| Fichas provisórias no modo individual | 1 | 1 |
| Paciente e carteira apresentados na ficha | Sim | Sim |
| Páginas com guia no prestador: antes → depois | 2 → 3 | 4 → 4 |
| Páginas com número de conselho/CRM lido: antes → depois | 1 → 3 | 2 → 4 |
| Células de quantidade solicitada identificadas: antes → depois | 11 → 11 | 5 → 10 |
| Células de quantidade autorizada identificadas: antes → depois | 0 → 0 | 7 → 16 |
| Linhas exibidas na interface | 15 | 20 |
| Verificações de interface aprovadas | 59 de 59 | 59 de 59 |
| Originais preservados byte a byte | Sim | Sim |
| Pré-cadastro real preparado | Não | Não |

As 35 linhas são registros por página/documento: não significam 35 exames únicos nem 35 autorizações. Há informações repetidas entre páginas/documentos e números de guia diferentes; não foram somadas ou descartadas arbitrariamente. Quantidade solicitada e autorizada continuam independentes.

As verificações cobrem importação, ficha e páginas corretas, atualização dos campos visíveis, quantidade de linhas nas tabelas, acesso à conferência, miniaturas, navegação à origem, ausência de saída preparada e integridade dos originais. O relatório público `TESTES_REAIS_2_4_3.json` contém somente estados e contagens.

Esses testes confirmam a passagem dos valores interpretados até a interface e o comportamento dos bloqueios. Não constituem gabarito clínico independente de cada valor real. Confiança de OCR e concordância entre segmentações não substituem conferência humana.

## Pendências reais, sem preenchimento por suposição

- Algumas quantidades e campos de autorização continuam ausentes ou sem leitura confiável. Ausência ou zero não autoriza procedimento.
- No documento B há números de conselho/CRM divergentes entre páginas; a ficha consolidada deixa o campo pendente, embora as páginas tenham leituras individuais. A origem deve ser conferida.
- Algumas páginas têm carteira incerta. Quando outra página fornece uma leitura compatível e confiável, a ficha usa essa informação com sua origem; não completa a página incerta por suposição.
- Conselho/UF em códigos numéricos dependem de tabela homologada pelo laboratório. Não foi inventada conversão.
- As sete páginas receberam classificação de guia SP/SADT. A finalidade de cada página, pedido versus autorização, não foi certificada somente pelo título; permanece sujeita à conferência/classificação manual.
- Catálogo, códigos internos, correspondências, perfis e regras de fontes pagadoras continuam sob homologação do laboratório.
- Instalação e execução nativas no Windows não puderam ser testadas neste ambiente Linux. A entrega é código Python com inicializadores Windows já existentes; não é um executável Windows certificado.

## Regressão e entrega

A suíte final passou com 200 testes, zero falhas e zero ignorados, incluindo 46 testes de interface Tkinter e 3 de navegador simulado local. Os documentos automatizados permanecem inteiramente fictícios. As duas matrizes sintéticas somam 270 verificações aprovadas de valores, origens e invariantes. Os 13 novos testes unitários e 3 gráficos cobrem os erros de geometria, releitura, quantidade zero, seção executada, data/senha, origem girada e escolha humana.

O fluxo sintético de quatro páginas foi exercitado até o preparo local após todas as conferências, além de reprocessamento, separação de pacientes e bloqueio de conflitos/duplicidades. O ZIP extraído recebe ainda uma verificação gráfica antes da publicação; o registro dessa entrega fica em `entrega/VERIFICACAO_PACOTE_2_4_3.txt` no GitHub. Instruções simples: `ATUALIZAR_PARA_2_4_3.txt`.

Para aplicar a nova leitura às fichas antigas, use Reprocessar leitura e refaça a conferência. As confirmações anteriores não são reaproveitadas automaticamente. Guias densas podem exigir alguns minutos de leitura detalhada. Os dados reais utilizados ficam fora do repositório e do ZIP; o conteúdo clínico de uso normal permanece somente na instalação local do usuário.
