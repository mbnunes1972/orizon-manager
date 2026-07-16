# Design — Persistência completa da negociação por orçamento (snapshot)

> Data: 2026-06-19 · Sub-projeto 1 de 3 (decomposição: 1) snapshot da negociação · 2) trava
> total pós-assinatura · 3) versionamento de documentos)

## Problema

Ao salvar e aprovar um orçamento, a última negociação de **forma de pagamento / parcelamento**
se perde. Hoje `salvarValorNegociado()` grava o plano calculado em `orcamentos.forma_pagamento`,
mas ao **reabrir** um orçamento salvo nada restaura a modalidade, as formas, o nº de parcelas, a
entrada e, no Total Flex, as **datas preenchidas manualmente** — o cálculo regenera um plano
padrão. (Limitação já anotada no DEV_LOG da sessão 10.) Além disso, o salvamento ao **aprovar** é
"fire-and-forget" (`if(!valor) return`, `catch` vazio): pode aprovar sem persistir.

## Decisões (acordadas)

- **Onde:** no banco, em **uma coluna JSON** `orcamentos.negociacao_json` (consistente com
  `margens`/`forma_pagamento`; o dado é sempre lido/gravado inteiro, nunca consultado por campo).
- **Modelo:** salvar as **entradas** da negociação; ao reabrir, **restaurar as entradas e
  recalcular** o plano (as datas manuais do TF/VP entram como entrada preservada).
- **Aprovar:** o salvamento passa a ser **confiável**; a aprovação só prossegue se o salvamento
  confirmou — senão **bloqueia** com aviso (não aprova perdendo dados).
- Descontos (global + por ambiente) **já** são persistidos/restaurados (sub-projeto anterior);
  não são reimplementados aqui.

## Modelo de dados

Nova coluna **`orcamentos.negociacao_json`** (TEXT, nullable; default NULL). JSON com as entradas:

```json
{
  "codigo": "total_flex",          // a_vista | cartao_credito | aymore | venda_programada | total_flex
  "forma_entrada": "pix",
  "forma_parcela": "boleto",
  "n_parcelas": 10,
  "entrada_valor": 15000.0,
  "entrada_data": "2026-07-01",
  "taxa_tf": 1.99,                  // só TF
  "tf_data_contrato": "2026-06-19",// só TF
  "tf_datas": ["2026-07-18", ...], // só TF — datas manuais por parcela
  "vp_datas": ["2026-07-18", ...]  // só venda programada
}
```

Campos ausentes/irrelevantes para a modalidade ficam omitidos. `forma_pagamento` (plano calculado)
permanece como está — é o que o backend do contrato consome.

## Backend (`main.py`, `database.py`)

- `_migrar_colunas`: adiciona `negociacao_json` em `orcamentos` se ausente
  (`ALTER TABLE orcamentos ADD COLUMN negociacao_json TEXT`).
- `PATCH /orcamentos/<id>/valor`: passa a aceitar e gravar `negociacao_json` (string JSON), junto
  de `valor_total`/`valor_liquido`/`forma_pagamento`. Mantém compatibilidade (campo opcional).
- `GET /orcamentos/<id>/ambientes`: passa a devolver `negociacao_json` (objeto já parseado, ou
  `null`) — é o ponto onde o front já recebe `margens`.

## Frontend (`static/index.html`)

**Captura (`_capturarNegociacao()`):** lê o estado atual da sidebar de pagamento — `_codigoPagAtivo`,
`_formaEntrada`, `_formaParcela`, nº de parcelas, entrada (valor+data), e, conforme a modalidade,
`taxa_tf` + `tf_data_contrato` + `_tfDatas`, ou `_vpDatas`. Retorna o objeto do snapshot.
`salvarValorNegociado()` passa a enviar `negociacao_json: JSON.stringify(_capturarNegociacao())`.

**Reprodução:** após `carregarModalidades()` (dentro de `carregarMargensSalvas()`), se o orçamento
tiver `negociacao_json`, uma função `_restaurarNegociacao(snap)`:
1. seta `neg-pagamento` para `snap.codigo` e chama `onPagamentoChange()` (renderiza o painel certo);
2. preenche nº de parcelas, entrada (valor+data), `_formaEntrada`/`_formaParcela` nos selects;
3. para TF: preenche taxa, `tf-data-contrato` e as datas manuais (`_tfDatas`) e re-renderiza;
   para VP: restaura `_vpDatas`;
4. dispara o recálculo — o plano é reproduzido usando as datas salvas.
O `negociacao_json` chega via a resposta do GET de ambientes (guardado, p.ex., em
`projetoAtivo._negociacao` ou variável análoga) e é consumido na reprodução.

**Garantia ao aprovar:** `salvarValorNegociado()` passa a **retornar** sucesso/erro (resolve com
`{ok:true}` só quando o PATCH respondeu ok). O fluxo de aprovação (`salvarOrcamento` quando leva à
aprovação e a função de aprovar — ambas chamam `salvarValorNegociado()`) passa a **aguardar** o
resultado e **abortar a aprovação** com `avisoPopup`/`showToast` se o salvamento falhar. Remove-se
o early-out silencioso que impedia salvar quando o total ainda não estava calculado no caminho de
aprovação (a aprovação exige um total válido de qualquer forma).

## Testes

**Backend (pytest):**
- coluna `negociacao_json` existe e persiste (round-trip via modelo).
- `PATCH /orcamentos/<id>/valor` grava `negociacao_json`; `GET .../ambientes` devolve o objeto.
  (Handlers HTTP seguem a convenção do repo: verificados via API real na fase de verificação;
  o teste pytest cobre o modelo/serialização.)

**Playwright (dados reais — ver [[gui-verification-playwright]]):**
- **Total Flex:** configurar modalidade TF com nº de parcelas e **datas manuais**; Salvar; trocar de
  orçamento e voltar (ou recarregar a página) → confirmar que modalidade, parcelas, entrada e
  **datas manuais** foram reproduzidas e o plano recalculado bate.
- **Cartão / Aymoré / À vista:** salvar e reabrir → modalidade, formas, parcelas e entrada
  reproduzidas.
- **Aprovar:** aprovar um orçamento → reabrir → negociação preservada; e simular falha de
  salvamento → a aprovação é **bloqueada** com aviso (não aprova).

## Fora de escopo (próximos sub-projetos)

- **Trava total pós-assinatura** (esconder botões de salvar/criar orçamento, inserir ambientes,
  alterar parâmetros após contrato assinado) → sub-projeto 2.
- **Versionamento de documentos** (novos documentos criam versões; não sobrescrevem/apagam) →
  sub-projeto 3.
