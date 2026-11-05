> Documento de planejamento herdado da versão 1. Esta entrega não implementa integração RPA. Consulte LEIA-ME.md para usar a versão 2.

# Etapa 2 — planejamento, sem execução

## Arquitetura proposta

A etapa 1 usa Tkinter para a janela, regras determinísticas para interpretação, PyMuPDF/Pillow/Tesseract para leitura, SQLite para persistência e um serviço de domínio separado da interface. A fila importa em segundo plano; operações de revisão e persistência acontecem no fluxo principal. Arquivos ficam no computador. Não há servidor web. O arquivo `rpa_bloqueado.py` contém apenas uma função que interrompe qualquer tentativa de envio.

A etapa 2 deve ser outro projeto/ambiente, não um botão que habilita produção nesta demonstração. O pré-cadastro DEMO não deve ser aceito em produção. O contrato de produção precisará de versão de schema, identificador de ambiente, catálogo homologado, documentos e evidências, caso/revisão, identidade verificada, itens com quantidades e materiais, revisão autenticada e chave de idempotência.

## O que a TI e a área técnica precisam fornecer

| Dependência | Evidência necessária antes de implementar |
|---|---|
| Homologação | URL e versão do Shift de teste, usuários de teste e dados sintéticos |
| Permissão | Aprovação específica do laboratório para automação e condições de suporte/licenciamento do fornecedor |
| Telas | Fluxo documentado de pesquisa de paciente, cadastro, convênio, pedido, exames, confirmação e cancelamento |
| Interface | Capturas sem dados reais, campos obrigatórios, mensagens, seletores estáveis ou acesso acompanhado à homologação |
| Catálogo | Exportação validada de códigos internos Shift, códigos TUSS aplicáveis, sinônimos, materiais, unidades e regras de coleta |
| Autorizações | Status válidos, quantidades, vigência, cobertura, regras de guias parciais e relação código/procedimento |
| Identidade | Identificadores confiáveis, política de homônimos, menores, pacientes sem documentos e duplicados |
| Segurança | Perfis de acesso, proteção de disco/banco, retenção, acesso à auditoria, backup, incidentes e avaliação de privacidade/LGPD |
| Distribuição | Windows alvo, Python/Tk, instalação aprovada, OCR português, assinatura de executável e canal de atualização |
| Operação | Responsável por revisar cada paciente, suporte, parada de emergência e contingência manual |

## Fluxo RPA planejado com Playwright

1. Operador entra manualmente na homologação. Não guardar senha, cookies, estado autenticado ou perfil de navegador no pacote. MFA e CAPTCHA exigem atuação humana; automação deve parar.
2. Confirmar URL/ambiente de homologação numa lista permitida. Conferir perfil e versão da tela; se divergirem, parar.
3. Abrir somente um caso revisado com snapshot imutável e revisão atual. Procurar paciente e possíveis ordens existentes antes de preencher. Identidade incerta requer decisão humana.
4. Preencher rascunho com seletores por label/role ou test-id homologados, sem coordenadas frágeis. Ler de volta os valores da tela. Qualquer campo divergente interrompe o fluxo.
5. Mostrar resumo final ao operador ANTES da ação que grava. Revisão do OCR e autorização para envio são eventos distintos.
6. Executar uma única confirmação autorizada. Capturar o identificador retornado e verificar os itens efetivamente registrados. Timeout após o clique significa resultado INCERTO: não reenviar automaticamente.
7. Em resultado incerto, consultar a existência da ordem com critérios aprovados. Exigir reconciliação manual se a consulta não for conclusiva. Não tentar compensar por exclusão automática.
8. Só considerar impressão em uma fase posterior, com outro aceite e identificação/formatos homologados. Esta entrega não imprime.

Estados futuros: EXTRAIDO → PENDENTE_REVISAO → REVISADO → PREENCHIDO_HOMOLOGACAO → AGUARDANDO_CONFIRMACAO → ENVIANDO → CONFIRMADO ou INCERTO/BLOQUEADO. Toda alteração de documento/catálogo invalida a revisão. Toda mudança de layout interrompe a automação até nova homologação.

## IA e OCR futuros

Amostras sintéticas de layouts precisam ser produzidas primeiro. Medir precisão por campo/exame, falsos positivos de autorização e erros de associação entre pacientes; não apenas taxa global de OCR. Exames desconhecidos ou ambiguidades devem permanecer bloqueados. Se um modelo local for necessário, a TI deve validar licença, hardware, execução sem rede, retenção, limites e comportamento diante de texto malicioso em documentos. Nenhum texto do documento pode virar instrução de sistema ou executar ações.

## Critérios para sair da homologação

Testar pacientes já existentes, homônimos, guia vencida/negada/parcial, exame fora do catálogo, códigos conflitantes, lotes com erros, documentos de pessoas diferentes, duplicidade simultânea, queda de rede, timeout após envio, sessão expirada, mudança de tela e reinício no meio do fluxo. Exigir zero gravação sem revisão explícita, reconciliação dos resultados incertos e evidência da auditoria autenticada. A área técnica valida amostras e materiais. O laboratório e a TI aprovam a versão e um plano de reversão antes de uma implantação restrita.

## Referências técnicas consultadas em 05/11/2026

- PyMuPDF, extração e OCR por página: https://pymupdf.readthedocs.io/en/latest/page.html
- Tesseract, instalação local e idiomas: https://tesseract-ocr.github.io/tessdoc/Installation.html
- Playwright, autenticação e risco dos arquivos de estado: https://playwright.dev/python/docs/auth

As referências são gerais; nenhuma documentação específica das telas do Shift foi fornecida ou inferida nesta fase.
