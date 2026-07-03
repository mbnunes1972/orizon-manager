# Padronização da tela de Negociação (todas as modalidades) — Design

**Data:** 2026-07-03
**Status:** Implementado (main). Frontend-only (`static/index.html`), verificação manual.

## Objetivo

Uniformizar graficamente as modalidades de pagamento (Aymoré, Cartão de Crédito, Venda
Programada, Total Flex, À Vista) e enxugar a tela, mantendo o motor de cálculo intacto
(os valores continuam vindo do motor via `negPreview`/`_aplicarPreviewNaTela`).

## Decisões

### 1. Faixa superior de valores
Sequência única no topo: **Valor Bruto → Desconto → Valor à Vista → Valor Total do Contrato**.
- Célula `neg-parcelado-cell` (id `neg-parcelado`) à direita do Valor à Vista.
- Populada por `negMostrarParcelado(valor)`; escondida por `negOcultarParcelado()` na troca de
  modalidade (`onPagamentoChange`).
- Modalidades com financiamento setam com o total que o cliente paga (parcelado); **À Vista**
  seta com o próprio Valor à Vista (`_ayGetValorVenda()`, que lê `neg-avista`), garantindo
  igualdade. Rótulo: **"Valor Total do Contrato"** (antes "Contrato Parcelado").

### 2. Formulário (forma de pagamento) — uma linha, mesma diagramação
Ordem uniforme: **Data do Contrato, Entrada, Data da Entrada**, seguida do campo específico
da modalidade na MESMA linha:
- Aymoré: `+ Carência`
- Cartão de Crédito: `+ Bandeira`
- Total Flex: `+ Prazo (meses)`
- Venda Programada: só os 3
- Campos calculados/informativos ficam **ocultos** (input hidden), preservando o cálculo:
  `ay-data-primeira` (1ª parcela = Data do Contrato + Carência), `vp-data-limite`, `tf-data-limite`.

### 3. Faixa central removida
O bloco `contrato-grid` ("Contrato a Vista — Loja Recebe" + "Contrato Parcelado — Cliente Paga")
foi **removido de todas as modalidades** (duplicava valores). Ids preservados como spans ocultos
para o JS não quebrar.

### 4. Cards de resumo (`cards-3x2`) removidos
Bloco de cards (Loja Recebe, Cliente Paga, Valor/Parcela, Custo Financeiro, Taxa de Retenção,
Liquidação e afins) removido de todas as modalidades. Ids preservados ocultos. Os **avisos de
prazo** (VP/TF) permanecem (são separados).

### 5. Provisão de Impostos — linha fina com cadeado liberável por senha
Painel de impostos vira uma **linha fina uniforme**: `🔒 Impostos … Base de cálculo 🔒`. Usa os
mesmos ids `{p}-r-base-trib` / `{p}-r-impostos` e o mecanismo existente `_renderImpostosLock`
(clique no 🔒 → `abrirModalLiberarImpostos` → senha de diretor/gerente adm-fin revela os valores).
Prefixos: `ay`, `cc`, `vp`, `tf`.

## Correção de bug (mesma frente)

**Desconto por ambiente acima do limite** revertia o campo para o valor anterior mas mantinha o
desconto aplicado na tela. Causa: `_onDescIndBlur` rodava `negPreview()` **antes** de checar o
limite; ao exceder, zerava `_descIndividual` mas não re-rodava o preview — como as células (EP07)
vêm do motor, o desconto persistia. Correção: no ramo de excesso, após reverter, re-roda
`negPreview()` e re-persiste (`_persistirDescontosOrc`) com guard de troca de orçamento.

## Escopo / pendências
- À Vista não tem parcelamento/impostos de financiamento — mantido como estava (agora exibe o
  Valor Total do Contrato = Valor à Vista).
- Provisões: opção B (custos adicionais editáveis recalculando margem) permanece como possível
  frente futura; hoje são informativos (já descontados do Val. Líquido).
