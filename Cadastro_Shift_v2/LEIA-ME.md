# Cadastro Assistido Shift — versão 2.1

## Instalar no Windows 10/11 (64 bits)

1. Extraia **todo o ZIP** em uma pasta, por exemplo `Documentos\Cadastro_Shift_v2`. Não execute dentro do ZIP.
2. Abra **INSTALAR_WINDOWS.bat**. Aguarde a instalação. Se o Windows solicitar permissão para instalar Python ou Tesseract, confirme se deseja instalá-los.
3. Quando aparecer “Instalacao concluida”, abra **INICIAR_WINDOWS.bat** ou o atalho “Cadastro Assistido Shift v2”.

O instalador procura seu Python existente, cria um ambiente próprio e instala as bibliotecas e o Tesseract quando necessário. Os idiomas português e inglês já acompanham este pacote. A primeira instalação precisa de internet; a leitura de documentos e o uso diário funcionam sem internet. O aplicativo não tem chamadas a serviços externos.

Se não existir `winget`, instale Python 3.12 em https://www.python.org/downloads/windows/ (marque **Add Python to PATH**) e Tesseract em https://github.com/UB-Mannheim/tesseract/wiki . Execute novamente INSTALAR_WINDOWS.bat. Se o Tesseract estiver fora da pasta padrão, configure a variável de ambiente `SHIFT_TESSERACT` com o caminho completo de `tesseract.exe`.

**Mantenha o programa anterior em sua própria pasta.** Não há migração automática do histórico antigo. O botão **DEMO v1** abre a interface anterior; para manter seu histórico v1, copie a pasta `dados_demo` da instalação antiga para a pasta desta versão, com os dois programas fechados. A v2 usa um histórico separado.

## O que foi corrigido

A leitura já era chamada ao importar, mas rótulos sem dois pontos e alguns campos em colunas não eram reconhecidos. Falhas de OCR podiam resultar em documentos visíveis com campos vazios, sem diagnóstico destacado. A versão 2.1 amplia os rótulos, trata caminhos configurados no Windows e idiomas explicitamente, mostra as falhas por página e abre o formulário preenchido. Ausências e conflitos aparecem como **Não identificado**, sempre para conferência.

O botão **Origem** mostra documento, página, trecho e região da informação. Uma classificação sem título claro fica não identificada; a escolha de tipo deve ser conferida. Se ambos os títulos indicarem pedido e guia invertidos, o aplicativo troca as posições. Não há inferência de códigos desconhecidos nem aprovação de divergências.

Veja [o relatório da correção](docs/CORRECAO_2_1.md) para evidências e limites da validação.

## Primeiro teste

1. Informe seu nome em **Revisor**.
2. Clique em **3 exemplos**. Os três pacientes fictícios continuam disponíveis.
3. Para testar documentos digitalizados, clique em **Importar e ler par** e escolha `exemplos_v2/01_pedido_digital.pdf` e `exemplos_v2/01_guia_escaneada.pdf`.
4. Aguarde a leitura: os campos aparecem automaticamente em **Comparar e conferir**. A aba **Diagnóstico de leitura** mostra método, caracteres e falhas por página.

Todos os exemplos fornecidos são sintéticos. O catálogo inicial também é de demonstração. Antes de preparar pré-cadastros com documentos do laboratório, ajuste os nomes, códigos, sinônimos e materiais no botão **Catálogo**, conforme os dados aprovados pelo laboratório.

## Usar: Importar → Ler → Comparar → Conferir → Preparar

1. **Importar e ler par:** selecione primeiro o pedido, depois a guia do mesmo paciente. Aceita PDF, JPG, JPEG, PNG e TXT. A leitura é automática. PDFs com texto utilizável são lidos diretamente; páginas sem texto utilizável e áreas raster sem texto utilizável passam por OCR local.
2. **Originais lado a lado:** confira os dois documentos. Use </> para mudar de página e -/+ para zoom. As barras de rolagem permitem examinar detalhes.
3. **Comparar e conferir:** o quadro superior mostra exames, quantidades, códigos internos e páginas. Abaixo ficam as pendências. Em telas pequenas, use as barras de rolagem da aba para chegar aos botões inferiores. As abas **Pedido** e **Guia** contêm os campos estruturados.
4. Corrija cada campo e marque **Conferido**, inclusive quando o original não trouxer a informação. **Origem** abre a página e destaca a região de leitura, quando disponível. A barra inferior informa página e confiança da leitura. Confiança 100 em texto digital não garante que o conteúdo esteja correto.
5. Em cada exame, dê duplo clique ou use **Editar / conferir**. Corrija descrição, código lido, quantidade, material e página. Marque que conferiu o exame e aplique. Quantidade ausente fica vazia; o programa não presume “1”. Use **Adicionar exame** para linhas não reconhecidas e **Excluir linha** para rodapés interpretados como exames, registrando o motivo.
6. Dê duplo clique em cada alerta e registre o que verificou/corrigiu. Abra todas as páginas e marque a conferência visual completa em cada documento.
7. Clique em **Salvar conferência e comparar** e registre uma observação. Resolva as pendências. Alterar um campo desmarca sua conferência; mudar o catálogo exige reconferir os exames.
8. Marque a confirmação final e clique em **Preparar pré-cadastro**. A preparação fica bloqueada enquanto houver divergências ou conferências incompletas.
9. Na última aba, use **Salvar pré-cadastro JSON**. Este arquivo não é enviado nem importado automaticamente pelo Shift. Não cria ordem real e não imprime etiquetas oficiais.

Se um documento não trouxer o nascimento, preencha apenas após verificá-lo em fonte confiável disponível no laboratório, registrando o motivo da correção. Sem nome e nascimento compatíveis nos dois registros, a associação fica bloqueada. Nunca invente dados ausentes.

Não é necessário editar a transcrição bruta. Os originais e a leitura inicial ficam preservados; as correções entram no histórico local do caso. Os novos registros técnicos de auditoria não recebem nomes, motivos livres nem conteúdo clínico.

## Catálogo e equivalências

- **Catálogo → Adicionar / Editar:** nome, código interno, TUSS opcional com 8 dígitos, sinônimos separados por `;` e material.
- **Importar JSON:** carrega catálogo compatível, com o mesmo formato de `catalogo_demo.json`. A escolha fica salva para as próximas aberturas.
- **Aprovar código equivalente:** selecione o exame, informe o código equivalente e a justificativa. O catálogo local registra responsável e data. Só códigos explicitamente aprovados participam da equivalência. Não há equivalência aproximada de nomes, painéis ou quantidades.
- Descrição/código incompatíveis, sinônimos ambíguos, exames duplicados e materiais divergentes bloqueiam a preparação. O catálogo sugere o material; o material só conta como “lido” quando aparece no documento.

## Vários pacientes

Use **Importar lote CSV**. O arquivo precisa ter cabeçalho `pedido;guia`, com um par explícito por linha e os documentos na mesma pasta ou subpastas. Exemplo pronto: `exemplos_v2/lote.csv`.

```csv
pedido;guia
01_pedido_digital.pdf;01_guia_escaneada.pdf
02_pedido_tabela.pdf;02_guia_divergente.pdf
```

O programa não associa pacientes por ordem alfabética ou por suposição. Reutilizar o mesmo arquivo em dois pares é bloqueado no lote. A identidade é conferida novamente antes da preparação. Erros em um par não impedem a leitura dos demais; confira as mensagens e a fila.

## Qualidade de leitura

Funciona melhor com documentos digitados/impressos nítidos, rótulos como “Paciente:”, “Nascimento:”, “Guia:” e tabelas com cabeçalho Código / Descrição / Qtd / Material. Reconhece listas e tabelas com coordenadas para manter as colunas associadas. Layouts diferentes, descrições quebradas, carimbos, manuscritos, fotos tortas e texto muito pequeno podem exigir preenchimento manual. Nenhum documento é aprovado automaticamente. O operador precisa conferir **todas** as páginas, inclusive conteúdo que não tenha sido reconhecido.

Limites: 30 MB por arquivo, 30 páginas por PDF, 25 megapixels por imagem e 100 pares por lote. PDFs protegidos devem ser desbloqueados fora do programa antes de importar.

## Testar e solucionar problemas

- **TESTAR_WINDOWS.bat:** executa os testes automatizados com documentos sintéticos. Os testes de OCR precisam do Tesseract instalado.
- Erro de OCR: execute INSTALAR_WINDOWS.bat novamente. A leitura incompleta gera alerta e permite preenchimento estruturado manual.
- Códigos desconhecidos: configure o catálogo ou corrija a leitura conforme o original. Não crie equivalências apenas para eliminar uma pendência.
- Pré-cadastro duplicado: consulte a fila; o mesmo paciente/nascimento/guia já pode estar preparado. Casos preparados não são editados para preservar a conferência.
- Os documentos importados, o catálogo e as conferências ficam na pasta `dados_v2`. Para fazer backup, feche o programa e copie a pasta inteira. Esses arquivos não são criptografados pelo aplicativo; mantenha-os em computador e pasta com acesso restrito conforme a rotina do laboratório.

## Escopo desta entrega

Aplicativo desktop Python/Tkinter, leitura local com PyMuPDF e Tesseract português e inglês, pré-cadastro JSON e histórico. Sem conexão ao Shift, sem banco de dados real e sem impressão oficial. A interface v1 e suas etiquetas fictícias continuam disponíveis pelo botão DEMO v1.

Validação executada em Linux com Python 3.12.14, PyMuPDF 1.26.6, Pillow 13.0.0 e Tesseract 5. Os scripts de instalação para Windows foram preparados para instalação assistida; sua execução nativa no Windows não foi validada neste ambiente.

Referências técnicas: https://pymupdf.readthedocs.io/en/latest/recipes-text.html e https://tesseract-ocr.github.io/tessdoc/Installation.html . Modelo português: https://github.com/tesseract-ocr/tessdata_fast (licença Apache 2.0 incluída em `tessdata/LICENSE.txt`).
