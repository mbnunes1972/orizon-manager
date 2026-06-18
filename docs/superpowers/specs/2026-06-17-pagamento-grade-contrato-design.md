# Pagamento correto + grade do contrato (Sub-projeto F1) — Design

**Data:** 2026-06-17
**Status:** proposto

## Problema (causa-raiz confirmada)

O contrato gerado saiu errado: número do contrato não gerado, data do cabeçalho
vazia, parcelas não listadas, valor bruto "à vista" caindo na 13ª parcela e datas
fora do lugar.

Investigação (dados reais do `Contrato` id 6 em `omie.db`) revelou **duas causas**:

1. **Captura de pagamento com colunas trocadas (bug real).**
   A tabela "Plano de Pagamento" tem colunas `# | Tipo | Vencimento | Valor`
   (ex.: Aymoré em `static/index.html:848`, linhas renderizadas em `:3302-3312`).
   `_capturarPagamento` (`static/index.html:6954`) lê por índice de coluna:
   - `desc = tds[0]` (o nº/marcador),
   - `data = tds[1]` (o **rótulo** "Assinatura/Entrada/1a Parcela/Parcela"),
   - `valor = tds[2] || tds[1]` (o **Vencimento/data**, ex. "18/07/2026").

   Ou seja: o campo `data` recebe o rótulo e o campo `valor` recebe a **data**; a
   coluna real de dinheiro (`tds[3]`) é **descartada**. Além disso, as linhas
   "Assinatura", "Entrada" e "Total pago pelo cliente" entram em `parcelas` como se
   fossem parcelas — a linha "Total" (13ª) é onde o valor bruto aparece.

   O backend `_parse_pagamento` confia nesses campos: por isso `datas` ficou com
   rótulos e `valores` com datas, e `num_parcelas_int = 13`.

   O painel **Total Flex** tem uma tabela de 9 colunas (`:1038-1047`), então corrigir
   `_capturarPagamento` por índice de coluna é frágil — cada painel tem layout
   diferente.

2. **Servidor obsoleto (parcial).** O `Contrato` id 6 foi gerado por um processo do
   servidor iniciado **antes** do merge anterior, logo o código novo de `num_contrato`
   e cabeçalho não estava em memória (`num_contrato = None`). Reiniciar resolve; a
   verificação desta vez será com servidor fresco **e dados reais** (sem JSON fabricado).

> Lição aplicada: a verificação anterior usou um `pagamento_json` inventado
> (`{"data": ISO, "valor": "R$ ..."}`) que não corresponde à estrutura real. Esta spec
> exige verificação contra os dados reais capturados pela UI.

## Objetivo

Gerar o contrato com o parcelamento correto: cada parcela com **valor e data**
(sem ordinal), traços nos campos sem parcela, valor total do contrato, número do
contrato e data no cabeçalho, e diagramação de cliente/testemunhas em linha.

## Decisões (já acordadas)

- **Grade sem ordinal.** Cada parcela = `valor` + `data`. (O usuário removeu o pedido
  de ordinais "1ª, 2ª".)
- **Slots vazios = traços** (`--------`) no valor **e** na data. **Não** apagar linhas
  (abordagem anterior de remover linhas vazias é revertida).
- **Cartão de crédito**: preencher **apenas o primeiro campo** de parcela com o texto
  do parcelamento (ex.: `12x R$ 10.000,00`); demais campos = traços.
- **Novo marcador `[valor_contrato]`** = "Total pago pelo cliente", preenchido por
  substituição de texto no corpo.
- **Captura via dados estruturados**, não por raspagem de coluna do DOM (robusto a
  todos os painéis).
- Template final: o usuário salva/fecha `modelo_contrato_final.docx` com os marcadores
  definitivos; a grade é escrita **por posição de célula** (robusta), marcadores
  escalares por substituição de texto.

## Arquitetura da solução

### 1. Frontend — fonte de dados estruturada (`static/index.html`)

Cada função de render de plano (`atualizarAymore` ~`:3245`, cartão ~`:3391`,
VP ~`:3559`, TF ~`:3979`) já constrói o objeto `d` com `d.parcelas` (campos `tipo`,
`num`, `data`, valor por `d.valor_parcela`/`p.valor`) e `d.total_cliente`.

Introduzir um global único `window._planoPagamento` preenchido por cada render:

```js
window._planoPagamento = {
  tipo: 'aymore'|'vp'|'tf'|'cartao'|'avista',
  nome_forma: '...',
  entrada_valor: <number>,
  entrada_data: '<iso>',
  entrada_forma: '<str>',
  total_cliente: <number>,         // "Total pago pelo cliente"
  texto_cartao: '12x R$ 10.000,00', // só cartão; senão ''
  parcelas: [                       // SÓ parcelas reais (tipo primeira/parcela)
    { num: 1, data: '18/07/2026', valor: 4820.00 },
    ...
  ],
};
```

Regras de construção:
- **Apenas** linhas com `tipo` em (`primeira`, `parcela`) viram `parcelas`. Assinatura
  (`contrato`), Entrada (`entrada`) e Total **não** entram.
- `valor` da parcela = `d.valor_parcela` (Aymoré/VP) ou `p.valor_digitado`/efetivo (TF).
- `data` = a data de vencimento já formatada exibida na linha (`p.data`).
- `total_cliente = d.total_cliente`.
- Cartão: `parcelas: []`, `texto_cartao` = string já montada (`atualizarCartao` já
  monta algo como `12x R$ ...`); `tipo: 'cartao'`.

`_capturarPagamento` passa a **retornar `window._planoPagamento`** (com um fallback
seguro se o global estiver vazio — devolve `{tipo:'avista', parcelas:[], ...}`),
em vez de raspar o DOM. A raspagem de DOM é removida.

> Mantém a forma do JSON que o backend recebe, mas agora com semântica correta:
> `parcelas[i].valor` = dinheiro, `parcelas[i].data` = data, `total_cliente`, `texto_cartao`.

### 2. Backend — `_parse_pagamento` (`mod_contrato.py`)

Reescrever para a nova estrutura:

```python
parcelas = pag.get("parcelas") or []        # já só parcelas reais
num_parcelas = len(parcelas)
datas   = [ _formatar_data_br(p.get("data") or "") for p in parcelas ]
valores = [ _formatar_valor_str(p.get("valor")) for p in parcelas ]   # dinheiro
datas   = (datas   + [""] * 24)[:24]
valores = (valores + [""] * 24)[:24]
total_cliente = _formatar_valor(pag.get("total_cliente") or 0)
texto_cartao  = pag.get("texto_cartao") or ""
```

Retorno acrescenta: `valores`, `num_parcelas_int`, `valor_contrato` (= total_cliente
formatado), `texto_cartao`. (`datas` já existia.)

`_formatar_valor_str`: aceita número ou string já formatada; devolve `"R$ x.xxx,xx"`.

### 3. Backend — grade do contrato (`preencher_contrato`)

Tabela `tables[3]`, linhas 3–10, pares de células `[(0,1),(2,3),(4,5)]` =
(valor, data). Para `p` = índice 1-based da parcela:

```python
for gi, row_idx in enumerate(range(3, 11)):
    cells = t3.rows[row_idx].cells
    for j, (val_col, data_col) in enumerate([(0,1),(2,3),(4,5)]):
        p = gi * 3 + j + 1            # nº da parcela (1-based)
        if data_col >= len(cells): break
        if tipo == "cartao":
            # 1º campo = texto do parcelamento; resto = traços
            _set_cell(cells[val_col], texto_cartao if p == 1 else _TRACO)
            _set_cell(cells[data_col], _TRACO if p != 1 else "")
        elif p <= num and valores[p-1]:
            _set_cell(cells[val_col],  valores[p-1])
            _set_cell(cells[data_col], datas[p-1] or _TRACO)
        else:
            _set_cell(cells[val_col],  _TRACO)
            _set_cell(cells[data_col], _TRACO)
```

- **Sem ordinal** (só o valor).
- Slots sem parcela = traços no valor e na data. **Linhas não são removidas.**
- Remover a lógica anterior de remoção de linhas (`_rows_remover`).

### 4. Backend — `[valor_contrato]` no corpo

Adicionar passe de substituição de texto no corpo (análogo a `_preencher_cabecalho`,
mas em `doc.paragraphs` + células de tabela): substitui `[valor_contrato]`
(case-insensitive, tolera `[[`) por `ctx['valor_contrato']`. Reaproveita a infra de
regex já usada para CPF/cabeçalho.

### 5. Backend — diagramação cliente/testemunhas

Hoje o cliente e as testemunhas são escritos com `\n` interno (rótulo + valor em
linhas separadas pelo `_set_para`). Ajustar para o **nome do cliente numa mesma
linha** sempre que possível, e formatar **nome + CPF das testemunhas de forma
semelhante** ao cliente (mesmo padrão de uma linha: `NOME: <nome>` e
`CPF/CNPJ: <doc>` consistentes). Detalhe de implementação no plano, preservando os
rótulos pequenos de nomenclatura (Pt 7) já existentes onde aplicável.

### 6. num_contrato + cabeçalho

Já implementado no merge anterior (`gerar_num_contrato`, `_preencher_cabecalho`,
coluna `num_contrato`, geração no handler). **Sem mudança de código** — apenas
re-verificar com servidor fresco e dados reais, confirmando que número e data
aparecem no cabeçalho.

## Fluxo de dados

```
UI (render do plano) → window._planoPagamento (estruturado, só parcelas reais)
  → _capturarPagamento() retorna o global
  → POST /contrato (pagamento_json)
  → _parse_pagamento(): datas[], valores[](dinheiro), valor_contrato, texto_cartao
  → construir_contexto(): _pag + valor_contrato no ctx
  → preencher_contrato(): grade (valor+data, traços), [valor_contrato], cabeçalho
```

## Testes

**Unitários (`tests/test_contrato.py`)** — usar JSON com a **estrutura real**:
- `_parse_pagamento` com parcelas reais → `valores` = dinheiro, `datas` = datas,
  `num_parcelas_int` = nº de parcelas reais, `valor_contrato` preenchido.
- Cartão → `texto_cartao` preenchido, `parcelas` vazias.
- Geração do doc com N parcelas → grade mostra valor+data nas N primeiras (sem
  ordinal), traços no resto, **linhas preservadas** (count de linhas da grade
  inalterado), `[valor_contrato]` substituído, cabeçalho com num/data.
- Cartão → 1ª célula = texto do parcelamento, resto traços.
- Cliente e testemunhas: nome em linha; documento formatado.

**Regressão:** a fixture de teste anterior (JSON fabricado) deve ser substituída pela
estrutura real para não mascarar o bug novamente.

## Verificação (runtime, dados reais)

1. Reiniciar o servidor (matar listeners antigos; iniciar UM fresco).
2. Pela UI (Playwright), montar um plano Aymoré com entrada + N parcelas, aprovar e
   gerar o contrato.
3. Abrir o `.docx` gerado e conferir:
   - cabeçalho: `INS-AAAA-MM-DD-NNN` + data;
   - grade: cada parcela com **valor + data**, traços nos vazios, sem linhas removidas;
   - `[valor_contrato]` com o total;
   - cartão: 1º campo com `Nx R$ ...`;
   - cliente/testemunhas em linha.
4. Confirmar `Contrato.num_contrato` gravado e estável ao regerar.

## Fora de escopo (vai para F2)

- Botão "Editar" + escolha Word/LibreOffice + watcher que regera o PDF ao salvar.

## Arquivos afetados

- `static/index.html` — `_planoPagamento` nos renders; `_capturarPagamento` lê o global.
- `mod_contrato.py` — `_parse_pagamento`, grade, `[valor_contrato]`, formatação
  cliente/testemunhas.
- `tests/test_contrato.py` — fixtures com estrutura real + novos asserts.
- `modelo_contrato_final.docx` — finalizado pelo usuário (marcadores definitivos).
