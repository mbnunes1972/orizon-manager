# Pagamento correto + grade + template por marcadores (Sub-projeto F1) — Design

**Data:** 2026-06-17
**Status:** aprovado (com pivô de template — ver §0)

## Problema (causa-raiz confirmada)

O contrato gerado saiu errado: número do contrato não gerado, data do cabeçalho
vazia, parcelas não listadas, valor bruto "à vista" caindo na 13ª parcela e datas
fora do lugar.

Investigação (dados reais do `Contrato` id 6 em `omie.db`) revelou **duas causas**:

1. **Captura de pagamento com colunas trocadas (bug real).**
   A tabela "Plano de Pagamento" tem colunas `# | Tipo | Vencimento | Valor`
   (Aymoré em `static/index.html:848`, linhas em `:3302-3312`). `_capturarPagamento`
   (`static/index.html:6954`) lê por índice: `data = tds[1]` (rótulo) e
   `valor = tds[2]` (a **data**), descartando a coluna real de dinheiro (`tds[3]`).
   Ainda inclui "Assinatura", "Entrada" e "Total pago pelo cliente" como parcelas — a
   linha "Total" (13ª) é onde o valor bruto aparece. O painel Total Flex tem 9 colunas
   (`:1038-1047`), logo corrigir por índice de coluna é frágil.

2. **Servidor obsoleto (parcial).** O `Contrato` id 6 foi gerado por servidor iniciado
   antes do merge anterior (`num_contrato = None`). Verificação desta vez: servidor
   fresco **e dados reais** (sem JSON fabricado — erro que mascarou o bug antes).

## §0. Pivô: template único por marcadores

Descoberta durante o planejamento: a geração lê `modelo_contrato_final.docx`
(`mod_contrato._MODELO`), mas o usuário vinha editando `modelo_contrato_mapeado.docx`
— um contrato **completo** (142 parágrafos, 4 tabelas, cláusulas) com **todos os campos
como marcadores** `[MARCADOR]`. Decisão do usuário: **promover o mapeado a template
oficial**.

Consequência: o `preencher_contrato` atual localiza parágrafos por **conteúdo
hardcoded** (`"Ferreira Machado"`, `t == "NOME:"`, etc.) — isso **não casa** com um
template de marcadores. Portanto a geração passa a ser por **substituição de
marcadores**, abordagem mais robusta e que reflete o template que o usuário construiu.

### Template oficial
- `mod_contrato._MODELO` passa a apontar para `modelo_contrato_mapeado.docx`.
- O arquivo passa a ser **versionado no git** (é a fonte de verdade do contrato).
- `modelo_contrato_final.docx` é **aposentado** (removido) para evitar confusão.
- O usuário continua editando **esse mesmo arquivo** quando quiser mudar o contrato.

### Marcadores do template (inventário atual)
- **Cabeçalho (caixa de texto):** `[Num_Contrato]`, `[[Data_contrato]` (tolerar `[[` e
  caixa alta/baixa).
- **Cliente (T0):** `[NOME_CLIENTE]`, `[CPF]`, `[EMAIL]`, `[TELEFONE]`.
- **Endereço residencial (T1):** `[RES_LOGRADOURO]`, `[RES_NUMERO]`,
  `[RES_COMPLEMENTO]`, `[RES_BAIRRO]`, `[RES_CIDADE]`, `[RES_CEP]`, `[RES_UF]`.
- **Endereço instalação (T2):** `[INST_LOGRADOURO]` … `[INST_UF]` (idem).
- **Pagamento (T3):** `[VALOR_ENTRADA]`, `[FORMA_ENTRADA]`, `[DATA_ENTRADA]`,
  `[MODALIDADE]`, `[NUM_PARCELAS]`, `[TOTAL_CONTRATO]` (= "Valor do Contrato", T3 r2 c2).
- **Grade (T3 r3–r10):** `[VALOR_PARCELA]` (×24, NÃO único) e `[DATA_PARCELA_1]` …
  `[DATA_PARCELA_24]` (únicos). **Sem ordinais.**
- **Corpo:** `[CONSULTOR_NOME]`, `[CONSULTOR_TELEFONE]`, `[DATA_CONTRATO]`,
  `[NOME_CLIENTE] CPF/CNPJ: [CPF]` (cliente = 2º signatário, numa linha),
  `[TESTEMUNHA_1_NOME]`, `[TESTEMUNHA_1_DOC]`, `[TESTEMUNHA_2_NOME]`,
  `[TESTEMUNHA_2_DOC]`.

> A diagramação (nome do cliente numa linha; testemunhas nome + CPF semelhantes) é agora
> **propriedade do template** — o layout dos marcadores já entrega isso. O código só
> substitui os valores, preservando a formatação dos runs.

## Objetivo

Gerar o contrato a partir do template de marcadores: cada parcela com **valor e data**
(sem ordinal), traços nos campos sem parcela, valor total, número do contrato e data no
cabeçalho, cartão no primeiro campo, demais campos do cliente/endereço/consultor/
testemunhas preenchidos por marcador.

## Arquitetura da solução

### 1. Frontend — fonte de dados estruturada (`static/index.html`)

Cada render de plano (`atualizarAymore` ~`:3245`, cartão ~`:3391`, VP ~`:3559`,
TF ~`:3979`) já constrói `d` com `d.parcelas` (campos `tipo`, `num`, `data`, valor via
`d.valor_parcela`/`p.valor`) e `d.total_cliente`. Introduzir um global único
`window._planoPagamento`, preenchido por cada render:

```js
window._planoPagamento = {
  tipo: 'aymore'|'vp'|'tf'|'cartao'|'avista',
  nome_forma: '...',
  entrada_valor: <number>, entrada_data: '<iso>', entrada_forma: '<str>',
  total_cliente: <number>,            // "Total pago pelo cliente"
  texto_cartao: '12x R$ 10.000,00',   // só cartão; senão ''
  parcelas: [ { num: 1, data: '18/07/2026', valor: 4820.00 }, ... ], // SÓ parcelas reais
};
```

Regras:
- **Só** linhas com `tipo` em (`primeira`, `parcela`) viram `parcelas`. Assinatura
  (`contrato`), Entrada (`entrada`) e Total **não** entram.
- `valor` = `d.valor_parcela` (Aymoré/VP) ou `p.valor_digitado`/efetivo (TF); `data` = a
  data de vencimento exibida (`p.data`); `total_cliente = d.total_cliente`.
- Cartão: `parcelas: []`, `texto_cartao` = string já montada (`atualizarCartao`).

`_capturarPagamento` passa a **retornar `window._planoPagamento`** (com fallback seguro
`{tipo:'avista', parcelas:[], total_cliente:0, texto_cartao:''}` se o global estiver
vazio). A raspagem de DOM é removida.

### 2. Backend — `_parse_pagamento` (`mod_contrato.py`)

```python
parcelas = pag.get("parcelas") or []          # já só parcelas reais
num_parcelas = len(parcelas)
datas   = [ _formatar_data_br(p.get("data") or "") for p in parcelas ]
valores = [ _formatar_valor_str(p.get("valor")) for p in parcelas ]   # dinheiro
datas   = (datas   + [""] * 24)[:24]
valores = (valores + [""] * 24)[:24]
```

Retorno acrescenta/ajusta: `valores`, `num_parcelas_int`, `valor_contrato`
(= `_formatar_valor(total_cliente)`), `texto_cartao`. (`datas` já existia.)
`_formatar_valor_str`: aceita número **ou** string já formatada → `"R$ x.xxx,xx"`.

### 3. Backend — motor de marcadores (`mod_contrato.py`)

Substituir a lógica posicional/conteúdo de `preencher_contrato` por:

```python
def _substituir_marcadores(doc, mapping):
    # mapping: {'NOME_CLIENTE': 'Ana', ...} (chaves SEM colchetes, casadas case-insensitive)
    # Regex tolera '[[' e espaços: \[+\s*([A-Za-z0-9_ ]+?)\s*\]
    # Aplica em: doc.paragraphs, todas as células de todas as tabelas, e os w:t dos headers.
    # Por parágrafo: junta runs, substitui no texto, regrava (1º run = resultado, demais vazios)
    #   para tolerar marcadores quebrados em runs. Marcador sem chave no mapping → mantido.
```

- A chave casada é normalizada para MAIÚSCULAS antes do lookup (cobre `[Num_Contrato]`).
- Marcadores desconhecidos ficam intactos (revela divergências no template, não some).

### 4. Backend — grade (posicional, antes do passe genérico)

A grade tem `[VALOR_PARCELA]` repetido (não único) → preencher **por posição**, não por
substituição genérica. Tabela `tables[3]`, linhas 3–10, pares `[(0,1),(2,3),(4,5)]` =
(valor, data):

```python
t3 = doc.tables[3]
for gi, row_idx in enumerate(range(3, 11)):
    cells = t3.rows[row_idx].cells
    for j, (vcol, dcol) in enumerate([(0,1),(2,3),(4,5)]):
        if dcol >= len(cells): break
        p = gi * 3 + j + 1
        if tipo == "cartao":
            _set_cell_text(cells[vcol], texto_cartao if p == 1 else _TRACO)
            _set_cell_text(cells[dcol], "" if p == 1 else _TRACO)
        elif p <= num and valores[p-1]:
            _set_cell_text(cells[vcol], valores[p-1])
            _set_cell_text(cells[dcol], datas[p-1] or _TRACO)
        else:
            _set_cell_text(cells[vcol], _TRACO)
            _set_cell_text(cells[dcol], _TRACO)
```

- **Sem ordinal.** Slots vazios = traços no valor **e** na data. **Linhas preservadas.**
- `_set_cell_text(cell, txt)`: escreve no 1º parágrafo da célula preservando o estilo;
  sobrescreve o marcador `[VALOR_PARCELA]`/`[DATA_PARCELA_n]`.
- Roda **antes** de `_substituir_marcadores` (os marcadores da grade já somem).

### 5. Backend — montagem do mapping e ordem em `preencher_contrato`

```python
def preencher_contrato(contrato_id, ctx):
    doc = Document(_MODELO)
    pag = ctx.get("_pag", {})
    _preencher_grade(doc, pag)                 # §4 (posicional)
    mapping = _montar_mapping(ctx, pag)        # §0 inventário → valores
    _substituir_marcadores(doc, mapping)       # §3 (corpo + tabelas + header)
    doc.save(...); return path
```

`_montar_mapping` cobre todos os marcadores do inventário (§0), inclusive:
`NUM_CONTRATO`, `DATA_CONTRATO`, `NOME_CLIENTE`, `CPF`, `EMAIL`, `TELEFONE`,
`RES_*`, `INST_*`, `VALOR_ENTRADA`, `FORMA_ENTRADA`, `DATA_ENTRADA`, `MODALIDADE`,
`NUM_PARCELAS`, `TOTAL_CONTRATO`, `CONSULTOR_NOME`, `CONSULTOR_TELEFONE`,
`TESTEMUNHA_1_NOME`/`_DOC`, `TESTEMUNHA_2_NOME`/`_DOC`.

- Testemunhas vêm de `_TESTEMUNHAS` (constante; futuro: painel de loja).
- `NOME_CLIENTE`/`CPF` respeitam o `signatario_override` (Sub-projeto E): se o signatário
  não for o cliente cadastrado, usam os dados do override.
- Código antigo posicional (`_unique_cells`, `_set_cell` com rótulo, `_relabel_cpf_cnpj`,
  matching por conteúdo, remoção de linhas vazias) é **removido** — o template de
  marcadores torna tudo isso desnecessário (labels e "CPF/CNPJ" já estão no template).

### 6. num_contrato + cabeçalho

`gerar_num_contrato`, geração no handler e a coluna `num_contrato` (merge anterior)
**permanecem**. `_preencher_cabecalho` é absorvido por `_substituir_marcadores` (que já
varre os headers). Re-verificar com servidor fresco + dados reais.

## Fluxo de dados

```
UI (render) → window._planoPagamento (estruturado, só parcelas reais)
  → _capturarPagamento() retorna o global
  → POST /contrato (pagamento_json)
  → _parse_pagamento(): datas[], valores[](dinheiro), valor_contrato, texto_cartao
  → construir_contexto(): _pag + escalares no ctx
  → preencher_contrato(): grade (posicional) + _substituir_marcadores (todo o resto)
```

## Testes (`tests/test_contrato.py`) — estrutura REAL

- `_parse_pagamento` com parcelas reais → `valores` = dinheiro, `datas` = datas,
  `num_parcelas_int` = nº de parcelas reais, `valor_contrato` preenchido; cartão →
  `texto_cartao` setado, `parcelas` vazias.
- `_substituir_marcadores`: substitui `[NOME_CLIENTE]`, tolera `[[Data_contrato]` e
  caixa; mantém marcador desconhecido.
- Geração do doc (template novo) com N parcelas → grade com valor+data nas N primeiras
  (sem ordinal), traços no resto, **linhas preservadas**; `[TOTAL_CONTRATO]`,
  `[NUM_PARCELAS]`, cabeçalho (num/data), cliente e testemunhas substituídos; nenhum
  marcador `[...]` remanescente (exceto desconhecidos, que não devem existir).
- Cartão → 1ª célula da grade = `texto_cartao`, resto traços.
- **Substituir** as fixtures antigas (JSON fabricado) pela estrutura real.

## Verificação (runtime, dados reais)

1. Reiniciar o servidor (matar listeners; UM fresco).
2. Pela UI (Playwright), montar plano Aymoré (entrada + N parcelas), aprovar e gerar.
3. Abrir o `.docx`: cabeçalho `INS-AAAA-MM-DD-NNN` + data; grade valor+data, traços nos
   vazios, sem linhas removidas; `[TOTAL_CONTRATO]` com o total; cartão 1º campo
   `Nx R$ ...`; cliente/testemunhas em linha; **zero** marcadores `[...]` sobrando.
4. `Contrato.num_contrato` gravado e estável ao regerar.

## Fora de escopo (Sub-projeto F2)

Botão "Editar" + escolha Word/LibreOffice + watcher que regera o PDF ao salvar.

## Arquivos afetados

- `static/index.html` — `_planoPagamento` nos renders; `_capturarPagamento` lê o global.
- `mod_contrato.py` — `_parse_pagamento`; `_substituir_marcadores`; `_preencher_grade`;
  `_montar_mapping`; `_MODELO` → mapeado; remoção do código posicional antigo.
- `tests/test_contrato.py` — fixtures reais + asserts do motor de marcadores.
- `modelo_contrato_mapeado.docx` — promovido a template oficial (versionado).
- `modelo_contrato_final.docx` — removido (aposentado).
- `.gitignore` — garantir que o template novo seja versionado.
