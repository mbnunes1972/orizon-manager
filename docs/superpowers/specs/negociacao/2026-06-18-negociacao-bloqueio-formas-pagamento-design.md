# Spec — Negociação: bloqueio pós-aprovação, Rever Orçamento, À Vista e Formas de Pagamento

> Sessão 10 | Orizon Manager | Dalmóbile
> Data: 2026-06-18
> Status: aprovado para plano

## Contexto

Hoje, ao aprovar o orçamento (etapa 6 do ciclo concluída), apenas os botões
**Salvar/Aprovar** são ocultados — os demais campos da negociação (page-02)
**continuam editáveis**. Existe um fluxo "↩ Voltar ao Orçamento" escondido dentro
da aba Ciclo (card 7), protegido por senha de gerente, que chama
`POST /ciclo/desfazer_aprovacao` (reseta etapas 6/7).

A modalidade **À Vista** (`a_vista`) não exibe nenhum painel. As **formas de
pagamento** (PIX/TED/Boleto/Cheque/Dinheiro/Cartão) da entrada e das parcelas
ainda não existem na interface. Os campos de data são `type="date"` nativos
(calendário só pelo iconezinho).

O template `modelo_contrato_mapeado.docx` já tem `[FORMA_ENTRADA]` (preenchido
hoje) e `[NUM_PARCELAS]`, mas **não tem** marcador para a forma das parcelas
(verificado no XML bruto do arquivo salvo). O backend `_parse_pagamento`
**já lê** `entrada_forma` e `parcelas[].forma`.

## Objetivos

1. Após aprovar o orçamento, **bloquear toda a negociação** (somente-leitura).
2. Criar o botão **"Rever Orçamento"** na tela de negociação (senha gerencial)
   que retorna à negociação e libera a edição da forma de pagamento.
3. Modalidade **À Vista** com **entrada (valor + data)** e **liquidação do saldo
   (data)**, sem condição de parcelas.
4. **Calendário** clicável em todos os campos de data.
5. Capturar a **forma de pagamento** da entrada e das parcelas, por modalidade,
   e levá-la ao contrato.

## Decisões (confirmadas com o usuário)

- "Rever Orçamento" **substitui** o "Voltar ao Orçamento": mesmo backend
  (`desfazer_aprovacao`, reseta etapas 6/7), reposicionado na tela de negociação.
- Calendário: **nativo aprimorado** (`showPicker()` + CSS), sem dependência nova.
- À Vista: liquidação com **valor automático** (`total − entrada`, somente-leitura).
- Forma das parcelas em VP/TF: **escolha única para todas** as parcelas.
- Formas À Vista (entrada e liquidação): **PIX / TED / Boleto / Cheque / Dinheiro**.
- Template: **inserir `[TIPO]` via script idempotente** junto de `[NUM_PARCELAS]`.

## Detalhamento

### 1. Bloqueio total da negociação após aprovação

Nova função `aplicarBloqueioNegociacao()`:
- Quando `_orcamentoAprovado()` é `true`, deixa **toda a page-02 em
  somente-leitura**: desconto global, desconto individual por ambiente (coluna
  Desc.%), `neg-pagamento` (modalidade), `neg-parcelas`, extras do Total Flex,
  todos os campos dos painéis (datas, entrada, valores), `neg-total-final`
  editável e os novos seletores de forma de pagamento.
- Implementação: desabilitar inputs/selects e bloquear handlers de clique de
  edição (ex.: `negTotalIniciarEdicao`), além de aplicar estilo "travado".
- Chamada em `atualizarBotoesAprovacao()` e ao recarregar um orçamento já
  aprovado. Desbloqueio somente via "Rever Orçamento".

### 2. "Rever Orçamento" (substitui "Voltar ao Orçamento")

- Remover o botão "↩ Voltar ao Orçamento" do card 7 da aba Ciclo.
- Em `atualizarBotoesAprovacao()`, quando aprovado, a action-row da page-02
  passa a ter **dois botões lado a lado**:
  `🔒 Orçamento aprovado – assinar contrato` e **`✎ Rever Orçamento`**.
- "Rever Orçamento" abre o modal de senha gerencial existente
  (`abrirModalVoltarOrcamento` → renomear para `abrirModalReverOrcamento`) →
  `POST /ciclo/desfazer_aprovacao` (reusa backend) → em sucesso: remove o
  bloqueio, reexibe Salvar/Aprovar e remove os dois botões pós-aprovação.

### 3. Modalidade À Vista com entrada + liquidação

Novo painel `painel-avista` (exibido quando `a_vista`; hoje nada aparece):
- **Entrada:** valor (máscara R$), data, forma (PIX/TED/Boleto/Cheque/Dinheiro).
- **Liquidação do saldo:** valor = `total − entrada` (auto, somente-leitura),
  data, forma (mesmo conjunto).
- Alimenta `window._planoPagamento` como **entrada + 1 "parcela"** (a liquidação),
  para o contrato sair uniforme (entrada + grade com 1 linha).
- `onPagamentoChange()` passa a chamar `avistaMostrarPainel(codigo === 'a_vista')`.

### 4. Calendário em todos os campos de data

Abordagem **nativa aprimorada** (sem dependência):
- Handler global delegado em `input[type="date"]` que chama `showPicker()` ao
  clicar em qualquer parte do campo (com guarda try/catch p/ navegadores sem
  suporte).
- CSS deixando o ícone do calendário visível/clicável e o campo com cursor
  pointer. Cobre campos fixos (ay/cc/vp/tf/avista) e dinâmicos das tabelas VP/TF
  (delegação cobre os criados depois).

### 5. Formas de pagamento (entrada e parcelas)

Dois seletores novos na barra lateral (abaixo de Modalidade/Parcelas), com
opções dependentes da modalidade ativa:

| Modalidade        | Forma da entrada              | Forma das parcelas              |
|-------------------|-------------------------------|---------------------------------|
| Cartão de Crédito | PIX / TED / Boleto            | fixo "Cartão de Crédito" (oculto)|
| Aymoré            | PIX / TED / Boleto            | fixo "Boleto" (oculto)          |
| Venda Programada  | PIX / TED / Boleto            | Boleto / Cheque (única p/ todas)|
| Total Flex        | PIX / TED / Boleto            | Boleto / Cheque (única p/ todas)|
| À Vista           | PIX/TED/Boleto/Cheque/Dinheiro| (liquidação — seção 3)          |

- Estado JS: `_formaEntrada`, `_formaParcela`; atualizados em
  `onPagamentoChange()` (reset/repopula conforme modalidade).
- Entram em `window._planoPagamento` (`entrada_forma`, `forma_parcela`; cada
  parcela recebe `forma`) e persistem no `forma_pagamento` JSON do orçamento
  (`PATCH /orcamentos/<id>/valor`), restaurando ao reabrir e ao recarregar
  orçamento aprovado.

### 6. Contrato (template + backend)

- `_parse_pagamento` já lê `entrada_forma` e `parcelas[].forma`. Derivar um
  único `forma_parcela` (forma da 1ª parcela, ou campo top-level).
- Entrada: `[FORMA_ENTRADA]` já existe e já é preenchido. ✓
- Parcelas: **script idempotente** insere o marcador `[TIPO]` no mesmo campo de
  `[NUM_PARCELAS]` (vira `[NUM_PARCELAS] / [TIPO]`, ex.: "12 / Boleto"); mapear
  `"TIPO": forma_parcela` em `_montar_mapping`.
- Verificar a geração **com dados reais** (Playwright + `/calcular_aymore`),
  conforme a regra de não fabricar `pagamento_json`.

## Fora de escopo (YAGNI)

- Forma de pagamento **por parcela** individual (decidido: única para todas).
- Biblioteca de datepicker de terceiros (mantém nativo).
- Alterações no cálculo financeiro das modalidades (apenas captura/persistência
  de forma e o painel À Vista).

## Verificação

- Suíte de testes mantida verde.
- Teste end-to-end com **dados reais** via navegador (Playwright) + endpoints de
  cálculo, validando: bloqueio pós-aprovação; Rever Orçamento desbloqueia;
  painel À Vista; calendário; formas por modalidade no contrato gerado.

## Processo

Pipeline superpowers: este spec → plano (writing-plans) → implementação com
revisão em duas etapas → verificação com dados reais → merge local.
