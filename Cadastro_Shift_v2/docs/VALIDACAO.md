# Validação — Cadastro Assistido Shift v2

Dados exclusivamente sintéticos. Nenhum acesso ao Shift ou a banco de dados real.

A suíte reúne os 18 testes originais da v1 e os testes novos de extração, layouts, conferência, persistência e interface. Resultado da execução final em `RESULTADO_TESTES_V2.txt`.

Cobertura:

- Extração direta de PDF digital, com teste garantindo que o OCR não seja chamado.
- OCR real em português em JPG, PNG, PDF escaneado, PDF misto e página híbrida.
- Documento borrado/ilegível, imagem vazia, falha de OCR e baixa confiança.
- Tabelas com colunas em diferentes ordens, duas tabelas paralelas, descrição quebrada em linhas, listas e rótulo acima do valor.
- Origem por página e região, navegação e zoom na interface.
- Quantidade ausente não recebe valor presumido.
- Pacientes divergentes, nascimento ausente, códigos conflitantes, exames ausentes, quantidades diferentes e materiais divergentes.
- Catálogo configurável, TUSS e equivalências somente com aprovação identificada.
- Bloqueios para revisão incompleta, alertas sem justificativa, revisão desatualizada, catálogo alterado e duplicidade.
- Manifestos de lote com associação explícita, rejeição de caminho externo, reutilização de arquivo e par com o mesmo documento.
- Persistência ao reabrir, auditoria de correções e pré-cadastro local sem ordem real.
- Interface Tkinter em servidor gráfico virtual: importação assíncrona, conferência estruturada, preparação e exportação JSON.
- Funcionalidades e 18 testes originais preservados.

Ambiente: Linux, Python 3.12.14, PyMuPDF 1.26.6, Pillow 13.0.0 e Tesseract 5 com modelo português tessdata_fast. As dependências binárias para Windows 64 bits/Python 3.12 tiveram a disponibilidade verificada por download.

O instalador Windows é assistido por BAT/PowerShell, não um executável compilado. Sua execução nativa em Windows não foi testada neste ambiente. O funcionamento em documentos reais depende do layout e da qualidade; a conferência visual completa é sempre obrigatória. A leitura heurística não garante reconhecer todas as linhas de todo modelo de guia.

Para repetir no Windows: TESTAR_WINDOWS.bat. Os testes novos geram seus próprios documentos sintéticos temporários. Os testes de OCR requerem o Tesseract, instalado por INSTALAR_WINDOWS.bat.
