# FASE D2 — Provisão completa no fechamento + travar orçamento contratado + etapa Conciliação Final

**Data:** 2026-07-12 · **Frente:** infraestrutura contábil (continuação da FASE D — reconciliação) +
ciclo do projeto. **Status:** design **FECHADO** (sem pontos em aberto) — **implementação ainda não
começou**. Este documento é o briefing para a próxima sessão de dev (Claude Code) executar, com TDD,
por fases, parando antes de mergear cada fase para conferência dos números.

## Contexto

Surgiu de uma simulação ponta a ponta ("Simulação Claude 2", rodada pelo padrão de teste da Vera —
`.claude/agents/vera.md` — via API real, projeto de teste `Simulacao_Claude_2` no `orizon.db` local:
cliente Pedro Paulo Nunes, parceiro Flávia Menezes 12%, orçamento contratado id 36 — VAVO R$208.347,50,
CFO R$65.477,13, contrato id 21). A simulação seguiu até a assinatura do contrato (Aprovação Financeira I)
e revelou 3 pontos que o usuário validou/corrigiu em conversa. Nenhum código foi alterado ainda — só
investigação (leitura de `mod_contabil.py`, `main.py`, `static/index.html`) e esta spec.

## Ajuste 1 — Seletor de orçamento: travar no orçamento CONTRATADO após o fechamento

**Comportamento atual (confirmado no código):** `carregarOrcamentos()` em `static/index.html` (~linha
4056) escolhe qual orçamento fica "ativo" por padrão assim: (1) último orçamento salvo no
`localStorage` (`lastOrc_<nome_safe>`), senão (2) o orçamento com `updated_at` mais recente. Nenhum dos
dois critérios olha para qual orçamento foi de fato **contratado** (`contratos.orcamento_id`). O seletor
(▾, `renderOrcamentosBar()`) continua útil e deve **continuar existindo** — ele permite ver/comparar os
outros orçamentos do projeto a qualquer momento. O problema é só o **padrão** ao reabrir o projeto.

**Comportamento esperado (confirmado pelo usuário — "adorei a proposta, só trava sempre no contratado"):**
quando o projeto tem um contrato (assinado ou não — a decisão relevante já está feita nesse ponto) o
`_orcamentoAtivoId` deve ser **sempre** o `orcamento_id` do contrato vigente do projeto, ignorando
localStorage/updated_at nesse caso. Antes de existir contrato, o comportamento atual (localStorage →
mais recente) continua válido, já que ainda não há "o contratado" para travar.

**Onde mexer:** `carregarOrcamentos()` deve checar primeiro se o projeto tem contrato (o endpoint que já
serve os dados do projeto/contrato tem esse `orcamento_id` — reaproveitar, não duplicar chamada); se
tiver, usar esse id direto, sem consultar localStorage. É mudança só de frontend, baixo risco — mas
ainda assim rodar a verificação manual de sempre (`node --check` + navegador) antes de fechar.

## Ajuste 2 — Provisionar TUDO no ato do contrato; matching pleno de despesa na NF-e; editável via reconciliação

**Desenho FECHADO (validado com o usuário, verificado numericamente com Fable 5 usando dados reais da
Simulação Claude 2 — Balanço fecha em cada etapa, nenhum centavo duplicado na DRE).** Decisões, em ordem:

1. **Provisionar TUDO no contrato** — as 10 rubricas (as 9 de sempre + **Custo de Fábrica 2.1.04.06**,
   que hoje fica de fora até o faturamento) são constituídas em **Passivo** no fechamento, sem tocar a DRE.
2. **Matching pleno na NF-e** — toda despesa (não só o CMV) é reconhecida na DRE **de uma vez, na NF-e**,
   usando os valores **planejados** (os mesmos provisionados no contrato). É a política que o usuário
   escolheu (a alternativa seria reconhecer cada despesa só quando o custo real ocorresse — descartada,
   por gerar lucro contábil temporariamente inflado entre a NF-e e a execução de cada rubrica).
3. **Editável via reconciliação** — "no ato da NF-e quase todas as despesas estão planejadas, mas ainda
   existem valores que mudam" (usuário). Qualquer diferença entre o valor reconhecido na NF-e (planejado)
   e o valor real pago depois vira ajuste **na DRE**, via o mecanismo de sobra/falta que **já existe hoje**
   (`resolver_saldo_provisao`: sobra → `4.4.02` Reversão de Provisões, receita; falta → `5.6.10` Ajuste de
   Provisões, despesa) — agora aplicado às 10 rubricas, não só ao subconjunto de hoje.

### Por que precisa de DUAS famílias de conta (prova, não suposição)

Na NF-e, reconhecer a Receita cheia exige debitar uma conta que **zera** naquele momento. Mas a Provisão
de Custo de Fábrica (2.1.04.06, Passivo) precisa **sobreviver** à NF-e — é justamente o valor que a
reconciliação tem que continuar monitorando (o usuário foi explícito: "um dos valores que precisa
aparecer e ser monitorado é exatamente a provisão de fábrica"). Se a mesma conta 2.1.04.x fosse debitada
pra gerar a Receita, ela zeraria na NF-e e não sobraria nada pra acompanhar depois. Logo: a Receita e o
Custo precisam de contas de **deferimento** (ativo) separadas da Provisão em si (passivo).

- **`2.1.06` Adiantamento de Clientes vira "Receita a Realizar"**: recebe o valor **cheio** do contrato no
  fechamento (não só o adiantamento em caixa, como hoje); os eventos de faturamento que já existem no
  código (`2.1.06 × 4.1.01`/`4.2.01`) já servem para debitá-la na NF-e — não precisa de evento novo aqui.
  `recebimento_venda` muda de `1.1.01 × 2.1.06` para `1.1.01 × 1.1.02` (o Aymoré em 10x abate Contas a
  Receber, não a Receita a Realizar).
- **Grupo novo `1.1.06` "Custos a Apropriar"** (ativo), com subcontas espelho por rubrica (`1.1.06.02`,
  `.03`, `.05`, `.06` Custo de Fábrica, `.07`, `.08`, `.09`, `.10`, `.11`, `.12`, `.14` Outros
  Fornecedores) — é a MESMA receita já usada para Impostos (`1.1.05 × 2.1.04.13`), generalizada pras
  outras 10 rubricas. O débito do contrato vira `1.1.02 Contas a Receber` (não Caixa — o dinheiro só
  entra conforme o Aymoré paga).

### Sequência de lançamentos (valores da Simulação Claude 2, verificados)

| Momento | Evento | Débito | Crédito | Valor (ref.) | Toca DRE? |
|---|---|---|---|---:|---|
| Contrato | Registra a venda | 1.1.02 Contas a Receber | 2.1.06 Receita a Realizar | Val_Cont (236.826,82) | não |
| Contrato | Constitui cada uma das 10 provisões (incl. Custo de Fábrica) | 1.1.06.0X Custos a Apropriar | 2.1.04.0X Provisão | soma 104.682,27 | não |
| Recebimentos | Parcelas do financiamento (Aymoré) | 1.1.01 Caixa | 1.1.02 Contas a Receber | conforme paga | não |
| **NF-e** | Reconhece a Receita (fato gerador) | 2.1.06 Receita a Realizar | 4.1.01/4.2.01 Receita | Val_Cont | **sim** |
| **NF-e** | Reconhece TODAS as despesas planejadas (matching pleno) | 5.6.0X (ou 5.1.01 pro Custo de Fábrica) | 1.1.06.0X | soma 104.682,27 | **sim** |
| Depois da NF-e | Paga cada rubrica (Custo de Fábrica incluso — sobrevive até aqui) | 2.1.04.0X | 1.1.01 Caixa | valor real | não |
| Quando o real diverge do planejado | Sobra (real < planejado) — **já existe hoje** | 2.1.04.0X | 4.4.02 Reversão de Provisões | diferença | **sim** |
| Quando o real diverge do planejado | Falta (real > planejado) — **já existe hoje** | 5.6.10 Ajuste de Provisões | 2.1.04.0X | diferença | **sim** |
| **Conciliação Final** | Resolve à força qualquer saldo remanescente das 10 provisões | (sobra/falta acima) | | saldo residual | conforme o caso |

**Verificado:** resultado final (Receita − custos reais) bate centavo a centavo tanto reconhecendo tudo na
NF-e e ajustando depois (este desenho) quanto reconhecendo cada despesa só na execução real — as duas
políticas convergem pro mesmo lucro final, só mudam o momento em que a DRE mostra o número. R$133.971,03
no cenário de teste (Receita 236.826,82 − custos reais 102.855,79).

### O que muda no código (visão geral, detalhar no plano por fases)

- `mod_contabil.py`: novo grupo `1.1.06` no `PLANO_PADRAO` (subcontas espelho de `1.1.05`/`2.1.04`).
  `_PROV_FECHAMENTO` passa a debitar `1.1.06.0X` (em vez de `5.6.0X` direto) para as 9 rubricas de sempre,
  e ganha a 10ª entrada (Custo de Fábrica → `1.1.06.06` × `2.1.04.06`). Novo evento de NF-e que, para cada
  rubrica com saldo em `1.1.06.0X`, debita a despesa (`5.6.0X` ou `5.1.01` pro Custo de Fábrica) contra a
  baixa do ativo — dispara junto com o faturamento, mesma transação.
- `2.1.06`: os eventos de faturamento existentes já cobrem a baixa; só muda o que entra nela no fechamento
  (valor cheio, não só adiantamento) e o `recebimento_venda` (passa a abater `1.1.02`).
- **Rename do nome "Adiantamento de Clientes" → "Receita a Realizar" (decidido): migração pontual, NÃO
  name-sync geral no `seed_plano`.** `seed_plano` hoje só cria contas que faltam (`if codigo in
  existentes: continue`) — nunca atualiza o `nome` de conta já existente, de propósito. `editar_conta`
  permite renomear **qualquer** conta, inclusive as do `PLANO_PADRAO` (não há flag "travada"/padrão que
  impeça). Um name-sync geral (toda vez que `seed_plano` roda, força o nome de volta ao `PLANO_PADRAO`)
  reverteria silenciosamente qualquer conta que um Gerente Adm/Fin tenha renomeado deliberadamente pelo
  painel — não só a `2.1.06`, todas as ~99. Fazer uma migração pontual e idempotente (registra em
  `schema_migrations`, mesmo padrão já usado no projeto) que renomeia `2.1.06` **só se o nome ainda for o
  default antigo** ("Adiantamento de Clientes") — pula silenciosamente se o owner já customizou.
- `reclassificar_provisao` (2.1.04.06 → 2.1.04.14) precisa espelhar a baixa correspondente em
  `1.1.06.06 → 1.1.06.14`, senão a sobra/falta por rubrica desalinha depois da NF-e.
- `resolver_saldo_provisao`/reconciliação: hoje cobre só o subconjunto usado pela FASE D — passa a se
  aplicar às 10 rubricas.
- **Decidido:** projetos já fechados no fluxo antigo (9 rubricas batendo DRE no fechamento) **ficam como
  estão — sem migração retroativa**. O novo comportamento (10 rubricas, matching pleno) vale só para
  contratos gerados a partir da implementação desta fase em diante. Não criar regra de corte por data nem
  reprocessar lançamentos antigos.

### Reconciliação por etapa do ciclo

**Decidido: nenhuma etapa intermediária ganha efetivação/reclassificação automática nesta frente.**
Solicitação de Medição, Medição, Projeto Executivo, Implantação do Pedido, Produção e Entrega no Depósito
seguem sem gatilho automático de reconciliação. A Aprovação Financeira II (etapa `11d`) continua usando
`reclassificar_provisao` (2.1.04.06→2.1.04.14, Outros Fornecedores) do jeito que já funciona hoje — ação
existente, não nova. Toda resolução forçada de saldo remanescente (sobra/falta das 10 provisões) fica
concentrada na nova etapa **Conciliação Final** (Ajuste 3), no fim do ciclo. Automação por etapa
intermediária fica de fora do escopo desta frente — backlog futuro, se fizer sentido depois de rodar a
Simulação Claude 2 completa (até a NF-e) e ver o comportamento real.

**Sem mudança (confirmado, não é achado):** contas de provisão zeradas (ex.: Outros Fornecedores antes da
Aprovação Financeira II) continuam aparecendo no painel com valor zero — já é o comportamento atual
(painel é data-driven sobre o Plano de Contas), não mexer nisso.

**Aprovação Financeira II:** o usuário avisou que essa etapa "poderá ter algumas alterações em breve" —
ainda sem desenho definido. Não implementar nada novo nela além do que já existe até o usuário detalhar.

## Ajuste 3 — Nova etapa do ciclo: "Conciliação Final" + status "Concluído"

**O que é:** uma etapa nova no ciclo do projeto, depois da atual etapa `20` ("Aprovação final"), que
**fecha os números finais do projeto** (concilia todas as provisões × efetivado × saldo, sem pendência
aberta) e **encerra o projeto**. Ao concluir essa etapa, o projeto passa a ter um **status novo no
painel: "Concluído"**.

**Onde mexer:**
- Backend, fonte de verdade: `mod_ciclo.py` (comentário no topo do arquivo já diz que
  `ETAPAS_CICLO`/`ETAPAS_PRINCIPAIS` do frontend são espelho dele — mexer lá primeiro).
- Frontend: `static/index.html`, `ETAPAS_CICLO` (~linha 10285) — adicionar
  `{ codigo: "21", nome: "Conciliação Final", sub: false }` ao final, e incluir `"21"` em
  `ETAPAS_PRINCIPAIS` (~linha 10313).
- Status do projeto: `projetos_meta.status` hoje tem pelo menos `aberto`/`fechado`/`perdido`. **Decidido:
  `"Concluído"` é um estado POSTERIOR e DISTINTO de `"fechado"`** (`fechado` = contrato assinado, projeto
  ainda em execução; `Concluído` = ciclo 100% executado e conciliado, atribuído só ao terminar a
  Conciliação Final). Não substitui `fechado` — o projeto passa por `fechado` primeiro e chega em
  `Concluído` depois. Confirmado: `"fechado"` hoje só é setado num lugar (`main.py`, na assinatura do
  contrato) e não há gate de backend que dependa dele além disso — baixo risco de quebra ao adicionar um
  status novo depois dele.
- O que a etapa faz de fato (cálculo/validação da reconciliação final) ainda não está especificado —
  precisa de uma rodada de design própria (provavelmente com Fable 5, por ser lógica financeira) antes do
  TDD.

## Processo (padrão do projeto — não pular)

1. Antes de tocar `mod_contabil.py`: auditoria do desenho exato do Ajuste 2 (ponto em aberto acima) com o
   usuário — é área sensível (dinheiro), reverte parte de uma decisão já documentada (Sessão 65).
2. Plano por fases, aprovado pelo usuário, antes de codar.
3. TDD (backend). Parar antes de mergear cada fase para conferência dos números pelo usuário.
4. Fechar frente: suíte verde, nova `## Sessão N` no `DEV_LOG.md`, atualizar este spec com o resultado,
   `git add` só os arquivos da mudança, merge, push, **re-ingerir o grafo MCP**.
5. Rodar a Vera (`.claude/agents/vera.md`) — idealmente repetindo a simulação Claude 2/3 pelo fluxo real —
   antes de fechar, dado que foi ela quem achou os 3 pontos desta spec.

## Resultado (IMPLEMENTADO — 2026-07-12, Sessão 70)

**Status: ✅ CONCLUÍDA e mergeada na `main`.** 6 fases, TDD, parando antes de mergear cada uma p/ conferência
dos números. Suíte 909→**946**. Commits: Fase 1 `af0c334` · Fase 2 `afe4c1c` · Fase 3 `d6bb760` · Fase 4
`ef09947` · Fase 5 `ba827cd` · Fase 6 `25a84df`.

**Auditada pela Vera** (prova de não-duplicação ponta a ponta pelo razão, cenário com valores reais divergentes
do planejado): Balanço fecha em cada etapa; cada custo entra na DRE **uma única vez** (a constituição diferida
não toca a DRE; o custo só vira resultado no matching da NF-e); Σ(4.1.01+4.2.01) = Val_Cont; nenhuma sobra/falta
órfã (a diferença real×planejado aparece inteira em `4.4.02`/`5.6.10`); `resultado_exercicio` do Balanço =
`lucro_liquido` da DRE. **Veredito: APTA PARA MERGE.**

**Decisões que se confirmaram na implementação:** migração do rename `2.1.06` = **pontual** (não name-sync);
status **"Concluído" distinto de "fechado"**; **nenhuma etapa intermediária** ganha efetivação/reclassificação
automática (tudo concentrado na Conciliação Final). Novo grupo `1.1.06` com 11 subcontas espelho; `faturamento_cmv`
**retirado** (CMV via matching `5.1.01 × 1.1.06.06`); `reclassificar_provisao` espelha `1.1.06` só na proporção
não baixada; `conciliar_final` exclui impostos (rota fiscal própria).

**🟡 Pendência aberta (não-bloqueante, herdada da FASE D):** o painel de Reconciliação mostra `saldo` bruto
(provisionado−efetivado) mesmo após a resolução — a resolução vive na coluna `resolvido`. Avaliar com o usuário
se, num projeto já "Concluído", exibir esse `saldo` residual confunde (contabilmente está fechado).
