# Spec — Contrato em HTML/Markdown → PDF (aposenta o Word)

**Data:** 2026-07-02
**Status:** design aprovado (aguardando revisão do spec + plano de implementação)
**Escopo desta frente:** somente o **contrato**. A proposta (que espelha a 1ª página) é frente seguinte, reaproveitando o mesmo motor (ver §9).

---

## 1. Objetivo e motivação

Substituir a geração de contrato baseada em **template Word (`.docx`) + LibreOffice** por um pipeline
**HTML/Markdown → PDF** com o motor **WeasyPrint**.

**Motivação:** o `.docx` com listas de numeração automática do Word é frágil — os números e o
alinhamento das cláusulas quebram de forma imprevisível (recuos deslocados, alíneas reiniciando
letra). A edição manual do template no Word reintroduz esses defeitos a cada ajuste. Um formato de
marcação versionável (Markdown para o texto + HTML/CSS para layout) elimina a fragilidade: o
alinhamento é controlado por CSS (previsível e reproduzível) e os números são texto literal (o que se
digita é o que aparece).

O contrato passa a ser **sempre PDF**. Os campos variáveis vêm do Cadastro (cliente) e do sistema
(empresa); ajustes de acordo diferente já são cobertos pelo **campo de texto complementar do ciclo**.
Não há edição in-place do documento gerado — a "interface que exige dados + confirmação" já é o fluxo
de revisão que existe antes de gerar. A rota de edição do `.docx` protegido é **aposentada**.

## 2. Decisões de design (fechadas com o usuário)

1. **Formato híbrido:** texto das cláusulas em **Markdown** (fácil de editar); capa, cabeçalho, rodapé
   e alinhamento/numeração controlados por **HTML/CSS** por baixo.
2. **Escopo:** só o contrato, **corte limpo** — remove o caminho `.docx`/LibreOffice e a rota
   `/contrato/editar`. Proposta vem depois.
3. **Sem edição in-place:** fluxo = conferir + confirmar → gerar PDF. O texto complementar do ciclo
   entra no contrato como um campo (`[TEXTO_COMPLEMENTAR]`).
4. **Motor:** **WeasyPrint** (API Python pura, sem navegador). Alternativas descartadas: Chromium
   headless (pesado; cabeçalho/rodapé corridos mais limitados); wkhtmltopdf (QtWebKit antigo,
   praticamente abandonado).
5. **Numeração (Opção A):** números **literais** no Markdown; o CSS cuida do recuo por nível e do
   *hanging* (número na "calha", linhas quebradas alinhadas). Referências cruzadas ("item 2.3") são
   texto literal. Motivo: num documento jurídico, exatidão/previsibilidade > renumeração automática, e
   a migração do texto atual é ~1:1.

## 3. Ambiente e dependências

- Servidor: **Ubuntu 24.04**, instalação via **apt** (PEP 668). Ambos disponíveis:
  - `weasyprint` (apt 67.0) — motor de PDF.
  - `python3-markdown` (apt 3.10) — Markdown → HTML.
- Dev (WSL, Python 3.14): instalar via `pip` (`weasyprint`, `markdown`) + libs de sistema do WeasyPrint
  (pango/cairo/gdk-pixbuf) já presentes ou instaláveis.
- `requirements.txt` ganha `weasyprint` e `markdown`; o cabeçalho do arquivo documenta o `apt install`
  correspondente para o servidor.
- **Remove-se** a dependência de LibreOffice **para o contrato** (verificar se algo mais usa antes de
  desinstalar do servidor — a conversão da proposta ainda usa; ver §9).

## 4. Arquivos e componentes

### 4.1 `mod_contrato.py` (refatorado)

Mantém tudo que é **dado/cálculo puro** e ganha o novo **motor de PDF**:

- **Mantidos:** `construir_contexto`, `_parse_pagamento`, `ambientes_valor_contrato`, `_montar_mapping`,
  `_formatar_valor` / `_formatar_valor_str` / `_formatar_data_br`, `_forma_label`, `gerar_num_contrato`,
  `calcular_hash_assinatura`, `contrato_desatualizado`, `validar_cliente_para_contrato`,
  `validar_loja_para_contrato`.
- **Removidos (caminho docx):** `preencher_contrato`, `_preencher_grade`, `_preencher_ambientes`,
  `_subst_paragrafo`, `_substituir_marcadores`, `_set_cell_text`, `_localizar_tabela`, `_unique_cells`,
  `_proteger_editaveis`, `_libreoffice_cmd`, `_converter_pdf`, `LibreOfficeIndisponivel`,
  `montar_variaveis_contrato`/`_formatar_bloco_pagamento` (legado). `_MODELO` (aponta pro `.docx`) sai.
- **Novo motor:**
  - `gerar_pdf_contrato(contrato_id, ctx, destino=CONTRATOS_DIR) -> str` — orquestra a geração e
    devolve o caminho do PDF (mesma assinatura conceitual da atual, mas sem docx no meio).
  - `_montar_html_contrato(ctx) -> str` — monta o HTML final (shell + capa + corpo) e substitui os
    `[MARCADORES]`.
  - `_html_capa(ctx) -> str` — gera as 5 seções da capa (as linhas dinâmicas de ambientes e parcelas).
  - `_html_corpo() -> str` — carrega `contrato.md`, aplica a convenção de níveis e converte para HTML.
  - `_substituir_marcadores_html(html, mapping) -> str` — substituição de `[MARCADOR]` sobre string
    HTML (regex simples; reaproveita o `_MARK_RE` atual). Marcador sem chave é mantido.

O mecanismo de substituição de marcadores continua o mesmo (`[MARCADOR]`, MAIÚSCULAS, tolera `[[`),
mas agora opera sobre **texto/HTML**, não sobre runs do docx — muito mais simples e sem o problema de
achatamento de formatação que existia no docx.

### 4.2 `contrato_template/` (assets, versionados em git)

- **`contrato.md`** — texto das cláusulas, migrado 1:1 do `.docx` atual (texto jurídico **exato**;
  revisão obrigatória). Convenção de autoria (§6).
- **`contrato.css`** — folha de impressão: `@page` (A4, margem 1cm — herda a decisão da frente
  anterior), **cabeçalho corrido** (logo + número + data em toda página), **rodapé "Página X de Y"**,
  estilos da capa (paleta marrom `#3b2f2a` / dourado `#C4A265` / rótulo cinza `#888888` / valor em
  negrito), e **recuo por nível + hanging** das cláusulas.
- **`contrato.html`** — shell (documento HTML: `<head>` com `<link>`/`<style>`, elementos corridos de
  cabeçalho/rodapé, `<!-- CAPA -->` e `<!-- CORPO -->` como pontos de injeção). Sem Jinja2 —
  substituição por marcadores simples de bloco + o motor de `[MARCADOR]` para os campos.
- **`logo_dalmobile.png`** (ou `.svg`) — asset do cabeçalho, referenciado pelo CSS via `base_url`.

## 5. Fluxo de dados / integração

1. **Rota `POST /api/projetos/<nome>/contrato`** monta o `ctx` como hoje (cliente do Cadastro, empresa
   do sistema, pagamento parseado, ambientes via `ambientes_valor_contrato`, **+ texto complementar do
   ciclo** → `ctx["texto_complementar"]`, exposto no mapping como `TEXTO_COMPLEMENTAR`).
2. `gerar_pdf_contrato(contrato.id, ctx)`:
   a. `mapping = _montar_mapping(ctx)` (inclui `TEXTO_COMPLEMENTAR`).
   b. `capa = _html_capa(ctx)` — linhas dinâmicas de ambientes (2 por linha, traços na sobra, total) e
      de parcelas (só as linhas usadas, traços nos slots vazios da última).
   c. `corpo = _html_corpo()` — `contrato.md` → HTML.
   d. `html = _montar_html_contrato(...)` — injeta capa/corpo no shell e substitui `[MARCADORES]`.
   e. `weasyprint.HTML(string=html, base_url=contrato_template/).write_pdf(pdf_path)`.
   f. retorna `pdf_path`.
3. A rota **serve/armazena** o PDF como hoje (`contrato_<id>.pdf` em `CONTRATOS/`; caminho no registro
   `Contrato`).
4. **Assinatura inalterada** — o hash (`nome|cpf|contrato_id|timestamp`) e o registro em DB não mudam;
   o PDF é o artefato final.
5. **Remove** a rota `POST /api/projetos/<nome>/contrato/editar` e o botão correspondente no frontend.
   A confirmação é a revisão que já existe antes de gerar.

## 6. Capa e cláusulas

### 6.1 Capa (HTML/CSS, página 1)

As 5 seções viram HTML com a mesma aparência atual:

- **Cabeçalho corrido** (toda página): logo à esquerda; número do contrato + data à direita. A linha
  "Consultor / Telefone" fica na capa (página 1).
- **1. Identificação**, **2. Endereço Residencial**, **3. Endereço de Instalação:** rótulos fixos +
  `[MARCADORES]` (rótulo cinza pequeno em cima, valor em negrito embaixo).
- **4. Ambientes do Projeto:** linhas geradas em Python — 2 ambientes por linha, **traços** (`--------`)
  na sobra de linha ímpar, linha **VALOR DO CONTRATO** = total (`[TOTAL_CONTRATO]`).
- **5. Forma de Pagamento:** entrada/modalidade + grade de parcelas gerada em Python — **só as linhas
  com parcela** (linhas vazias eliminadas), traços nos slots vazios da última linha; cartão sem data.
- Após a capa: `break-before: page` no início do corpo → cláusulas começam na página 2.

### 6.2 Cláusulas (Markdown, Opção A)

Convenção leve de autoria em `contrato.md`, com um pré-processador fino em Python que atribui **classe
por nível** antes do `markdown`:

- `# CLÁUSULA PRIMEIRA – DO OBJETO E PREÇO` → título de cláusula (texto literal; "PRIMEIRA/SEGUNDA…" é
  parte do texto jurídico, não gerado).
- Linha iniciando por `N.` / `N.N.` / `N.N.N.` → parágrafo de cláusula, **nível = nº de pontos**.
- Linha iniciando por `a)` / `b)` … → sub-item lettered.
- O **CSS** aplica, por nível: recuo esquerdo (`padding-left` crescente) + *hanging* (`text-indent`
  negativo) para o número ficar na calha e o texto quebrado alinhar. `markdown` cuida de ênfases
  (negrito/itálico) dentro do texto.
- Referências cruzadas ("nos termos do item 2.3") são **texto literal** — responsabilidade do autor,
  como em qualquer documento.

## 7. Tratamento de erros

- **WeasyPrint ausente/falha:** a rota retorna **500** com mensagem clara (ex.: "gerador de PDF
  indisponível — instale `weasyprint`"). Sem fallback para docx (corte limpo). Assets ausentes
  (`.md`/`.css`/logo) → erro explícito na geração.
- Diferente de hoje: **não** há mais o caminho "entrega o `.docx` com aviso quando o LibreOffice falta"
  — some junto com o docx.

## 8. Testes

- **Mantidos:** testes de `ambientes_valor_contrato` (função pura) e de `_parse_pagamento` /
  `_montar_mapping` / formatadores.
- **Novos (asseguram sobre o HTML intermediário — asserções de string, fáceis e rápidas):**
  - marcadores substituídos (sem `[MARCADOR]` remanescente no HTML final);
  - seção de ambientes: 2 por linha, traços na sobra, total = soma;
  - grade de parcelas: só linhas usadas, traços nos slots vazios, cartão sem data;
  - `[TEXTO_COMPLEMENTAR]` presente quando há texto do ciclo, ausente/vazio quando não há;
  - corpo das cláusulas presente e com as classes de nível corretas;
  - convenção de níveis: `2.3.1` → nível 3, `a)` → sub-item.
- **Smoke test do PDF:** `gerar_pdf_contrato` produz um PDF não-vazio (checa tamanho > limiar / header
  `%PDF`). **Pula se `weasyprint` não estiver instalado** (mesmo padrão do skip de LibreOffice hoje),
  para não travar a suíte em ambiente sem a lib.
- **Removidos:** testes específicos do docx (`_preencher_grade`, `_preencher_ambientes` docx,
  `_subst_paragrafo`, `_localizar_tabela`, `test_template_*` do `.docx`, `_proteger_editaveis`).
- **E2E:** o `test_fluxo_completo_e2e` (etapa 7 — contrato) passa a exercitar o novo caminho; ajustar o
  hook de geração se necessário (hoje ele tolera LibreOffice ausente).

## 9. Escopo / próxima frente

- **Só o contrato** nesta frente. A **proposta** (`modelo_proposta.docx`) espelha a 1ª página do
  contrato e será migrada para o mesmo motor numa frente seguinte, reaproveitando `_html_capa` e o CSS.
  Enquanto a proposta não migrar, o LibreOffice permanece como dependência **da proposta** (não
  desinstalar do servidor até lá).
- **Não** faz: edição arbitrária do contrato gerado; numeração automática de cláusulas; migração da
  proposta.

## 10. Migração do texto jurídico

- Extrair as ~150 cláusulas do `.docx` atual para `contrato.md`, preservando o **texto exato** (incl.
  os números literais que já existem) e a hierarquia de níveis.
- Feito programaticamente (lendo os parágrafos + `ilvl` do docx) e depois **revisado** — documento
  jurídico, erro de texto é caro. A revisão do `contrato.md` é um gate antes de considerar a frente
  pronta.
- A capa (rótulos fixos + marcadores) é reescrita em HTML (não extraída).

## 11. Riscos e mitigações

- **Fidelidade visual da capa** (cores/tabelas) vs. o `.docx` atual → conferência visual com PDF
  gerado (render via WeasyPrint), como nas frentes anteriores.
- **Precisão do texto legal** na migração → revisão obrigatória do `contrato.md` (§10).
- **WeasyPrint no dev (Python 3.14)** → se a instalação via pip falhar, o smoke test do PDF é pulado e
  a verificação visual usa o servidor/uma máquina com a lib; o restante dos testes (sobre o HTML) roda
  em qualquer ambiente.
- **Quebra de página / cabeçalho corrido** no WeasyPrint → validar com um contrato real de várias
  páginas (curto e longo) antes de fechar.

## 12. Nota sobre modelo de execução (não faz parte do produto)

A **redação deste spec** não exige Fable 5 — Sonnet 5 bastaria (documentação de decisões já tomadas).
A **implementação** — sobretudo a migração fiel das ~150 cláusulas jurídicas — é onde vale usar um
modelo mais capaz; o padrão é Opus 4.8, com Fable 5 como opção se quiser o teto de capacidade num
texto legal onde erro é caro. Decidir na hora de implementar.
