# Ponto de Venda (PDV avançado) — conceito, contas e painéis (2026-07-22)

## Demanda
Modelar o caso Caraguatatuba: ponto de vendas avançado da Inspirium (São José dos Campos), com
equipe menor mas TODAS as funções comerciais de uma loja — enquanto o processo administrativo,
financeiro e fiscal é integralmente da loja-mãe. Cadastro feito pelo **super_admin no painel
Admin, dentro do cadastro da loja** (o lojista NÃO configura PDVs). Cada PDV tem **painel
próprio**, resultados **individualizados** e indicadores gerenciáveis em separado.

**Decisões (2026-07-22):** emissão fiscal pelo **CNPJ da matriz** (PDV sem emitente próprio);
**razão contábil PRÓPRIO** por PDV com consolidação mãe+PDVs por relatório; equipe financeira da
mãe opera por **visão unificada** no painel da Inspirium (filtro por unidade), sem trocar de
contexto.

## Conceito central: PDV = Loja com mãe
O PDV **é uma `Loja`** no modelo, com dois campos novos: `loja_mae_id` (self-FK, NULL = loja
plena) e `tipo` (`loja` | `ponto_venda`). Isso dá de graça, pela tenancy existente: painel
próprio, equipe/usuários com escopo, projetos, ciclo completo, negociação, escopo por projetista,
config financeira, **razão contábil próprio** (`owner_tipo="loja"`, `owner_id=pdv.id` — zero
mudança no motor contábil) e portanto DRE, margens e indicadores separados **por construção**.
O que muda em relação a uma loja plena são quatro desvios, abaixo.

### Desvio 1 — Fiscal: emite pela mãe
`mod_fiscal.resolver_emitente` ganha um elo na cadeia de fallback:
`loja.emitente_id → loja_mae.emitente_id → rede.emitente_central_id`. O PDV nasce sem `Emitente`
e toda NF-e/NFS-e sai pelo emitente da Inspirium (padrão já existente com o emitente central da
rede — mesma mecânica). `prontidao_emitente` e a segmentação Mercadoria/Serviço seguem intocados.
**Contabilmente a receita é do PDV** (lança no razão dele), ainda que a face fiscal seja o CNPJ
da mãe — o razão do Orizon é gerencial; a contabilidade oficial do CNPJ continua consolidada no
contador da Inspirium, que já recebe tudo da matriz.

### Desvio 2 — Documentos: contrato é da mãe
O contrato/proposta/aditivo do PDV usa os **modelos de documento da loja-mãe**
(`documento_modelos` da mãe; `NOME_EMPRESA`/`CNPJ_EMPRESA`/endereço resolvem para a mãe —
juridicamente o cliente contrata com a Inspirium). O PDV ganha `codigo` próprio (ex.: `CAR`) para
a numeração do contrato rastrear a origem da venda. Testemunhas podem ser as do PDV (cadastro
próprio) — decisão de preenchimento, não de modelo.

### Desvio 3 — Financeiro: operado pela mãe, em visão unificada
- **Módulos do PDV**: comercial/ciclo ativos; o painel financeiro NÃO aparece no PDV
  (`modulos_ativos` do PDV sem `financeiro` na UI dele — os LANÇAMENTOS existem normalmente no
  razão do PDV; o que se esconde é a tela).
- **Escopo estendido na mãe**: conceito novo `lojas_do_escopo(ator)` — para perfis
  financeiro/Diretor da mãe devolve `[mãe] + PDVs dela`; para os demais, `[loja própria]`.
  Aplicado **opt-in, painel a painel** (financeiro, reconciliação, contas, relatórios,
  aprovação financeira), nunca global — evita vazamento de escopo em queries comerciais. Cada
  tela ganha **seletor de unidade** (Inspirium | Caraguá | Consolidado) que define o owner das
  consultas/ações; operações continuam atômicas numa unidade por vez.
- O `escopo_operacional` atual (uma loja) permanece para todo o resto do sistema.

### Desvio 4 — Cadastro: só super_admin
No painel Admin, dentro do cadastro da loja, seção **"Pontos de Venda"**: criar/ativar/desativar
PDV (nome, código, endereço, telefone, testemunhas, equipe, metas). Gated além do
`editar_dados_loja`: exige super_admin (mesmo padrão de gating do console). O lojista vê seus
PDVs, não os edita.

## Integração das contas (o "como" da individualização + consolidação)
1. **Individualização**: automática — cada PDV é um owner do razão. Todos os painéis contábeis
   existentes funcionam por PDV sem mudança (DRE, margens, provisões, reconciliação).
2. **Consolidação**: visão "Consolidado" = soma dos saldos/DRE de `[mãe] + PDVs`, mesma mecânica
   de um relatório multi-loja de rede. Na consolidação, os saldos intercompany se **eliminam**
   (`1.1.09` da credora × `2.1.09` da devedora fecham por construção — não distorcem o
   consolidado; exibir linha "eliminações" quando ≠ 0 por pendência de acerto).
3. **Custos da mãe em nome do PDV** (rateio administrativo, aluguel, folha compartilhada,
   marketing): reusa a **conta corrente intercompany** da frente "Acordos com a Fábrica"
   (`1.1.09` Conta Corrente com Lojas do Grupo — a receber / `2.1.09` — a pagar; `seed_plano` é
   idempotente — qualquer das duas frentes que chegar primeiro cria as contas). Ação "Rateio ao
   PDV" na visão unificada: no razão da **mãe** `DR 1.1.09 × CR 1.1.01` (pagou pelo PDV); no
   razão do **PDV** `DR 5.x (despesa da rubrica escolhida) × CR 2.1.09`. Aqui o lançamento nos
   dois razões numa ação só É legítimo — diferente do caso fábrica (evento comercial de loja
   independente), o ator é a equipe da mãe COM escopo sobre ambos, numa ação administrativa
   consciente; ref espelhada `rateio:<id>` nos dois lados, reversível em par.
4. **Liquidação**: transferência real mãe↔PDV baixa a conta corrente (`liquidacao_conta_corrente`
   da outra frente, mesma semântica), ou o saldo permanece como conta corrente permanente —
   decisão gerencial, igual ao caso Inspirium×Verano.

## Indicadores
Metas e faixas de comissão da equipe do PDV: `config_financeira_json` **próprio**, seeded como
cópia da mãe na criação (Diretor da mãe/super_admin ajusta depois). Dashboards comercial/ciclo já
saem por PDV (tenancy); o comparativo entre unidades entra na visão unificada da mãe
(mesmos widgets, série por unidade).

## Fatias e complexidade (estimativa)
1. **Fatia 1 — Fundação** (~1,5 sessão): `loja_mae_id`/`tipo` + migração leve; cadastro Admin
   "Pontos de Venda"; fallback do emitente; modelos de documento da mãe; código próprio na
   numeração; testes de tenancy (PDV não vê a mãe; mãe não vê PDV fora dos painéis opt-in).
2. **Fatia 2 — Visão unificada** (~1,5–2 sessões): `lojas_do_escopo` + seletor de unidade nos
   painéis financeiros da mãe; ocultação do financeiro na UI do PDV. É a fatia de maior risco
   (escopo) — cobrir com testes de acesso por perfil.
3. **Fatia 3 — Consolidação + rateios** (~1 sessão): visão Consolidado com eliminações; ação de
   rateio com par intercompany; reaproveita contas/eventos da frente dos acordos (se ela ainda
   não tiver entrado, esta fatia cria as contas 1.1.09/2.1.09 — seed idempotente resolve a ordem).
4. **Fatia 4 — Migração Caraguatatuba** (~0,5–1 sessão): criar o PDV real e direcionar as vendas
   novas. **Recomendação: NÃO migrar projetos/lançamentos históricos** — ficam na mãe (razão
   já constituído, refs idempotentes amarradas ao owner); Caraguá começa limpo no PDV e o
   histórico consolidado continua íntegro na visão da mãe. Migrar projeto aberto sem fechamento
   contábil é possível caso a caso (mover `loja_id` do projeto), nunca projeto com lançamentos.

## Riscos e pontos de atenção
- **Escopo é a área sensível**: `lojas_do_escopo` opt-in por painel, jamais mexer no
  `escopo_operacional` global; suíte de tenancy (já existente) ganha os casos PDV.
- **Refs contábeis por owner**: nada muda (cada razão tem as suas), mas relatórios que somam por
  `projeto_nome` entre owners devem agrupar por (owner, projeto).
- **Omie/integracões** e **folha**: conferir se há amarração por loja que precise apontar pro
  PDV ou pra mãe (decidir por integração, na Fatia 1).
- **Rede vs mãe**: PDV pertence à LOJA, não à rede — `rede_id` do PDV espelha o da mãe (herdado,
  não editável) para os relatórios de rede não perderem as vendas do PDV.

## Definições pendentes (Diretor)
1. Código do PDV Caraguatatuba na numeração de contrato (sugestão: `CAR`).
2. Metas/faixas de comissão iniciais do PDV (seed copia da Inspirium; ajustar depois?).
3. Rateios recorrentes mãe→PDV que já se sabe existirem (aluguel? folha?) — lista inicial para a
   ação de rateio nascer com os casos reais.
4. Confirmar que projetos históricos de Caraguá ficam na mãe (recomendado acima).
