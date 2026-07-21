# Descontos e Acréscimos Excepcionais de Fábrica — análise e design (2026-07-21)

## Demanda
A negociação com a fábrica gera condições **excepcionais por loja**, além da condição padrão
(desconto sequencial 36% + 2% + 2%, já embutida no `order_total` do XML Promob):

- **Inspirium**: desconto adicional de **3%** (dívida da fábrica com o grupo de lojas);
- **Verano**: desconto adicional de **5%** (mesma dívida);
- **Loja 3**: **acréscimo de 10% sobre a nota emitida** (amortiza dívida da loja com a fábrica)
  + **desconto de 5% (cashback)** como compensação. Exemplo: pedido R$ 100.000 → 5% off =
  R$ 95.000; NF-e emitida com +10% = **R$ 104.500**.

Pedido: configurador no Painel Financeiro — **Descontos e Acréscimos Excepcionais** — com ajustes
**recorrentes** (todas as vendas da loja) ou **pontuais** (vendas específicas), aplicados **sobre o
valor de fábrica padrão**. Decisões desta análise (2026-07-21): **saldo das dívidas controlado no
razão** (abatido a cada aplicação até zerar) e alcance **só financeiro** (a negociação/markup
continua na condição padrão; `mod_negociacao` NÃO muda).

## Diagnóstico — onde a condição padrão flui hoje
1. **XML Promob** → `PoolAmbiente.order_total` (CFA); a condição 36+2+2 já vem embutida no XML.
2. **Motor** (`mod_negociacao`): `CFO = Σ CFA` → markup/margens. (Intocado nesta frente.)
3. **Contrato** (FASE D2): `constituir_provisoes_fechamento` lança `custo_fabrica` = CFO —
   `1.1.06.06` (ativo diferido) × `2.1.04.06` (provisão), sem tocar a DRE.
4. **Etapa 12** (`conferencia_pedido`, `POST /api/projetos/<nome>/conferencia`): ajusta a provisão
   ao valor conferido/PE (`custo_fabrica_novo`, digitado) + reclassifica p/ Outros Fornecedores.
5. **Etapa 15**: NF-e da fábrica (XML em `CicloDocumento tipo=nfe_fabrica_xml`) e emissão da NF-e
   da loja → `reconhecer_despesas_nfe` (matching pleno pelo **saldo planejado** do 1.1.06.0X — a
   face da NF-e da fábrica não entra no razão).
6. **Divergência real × planejado** → `resolver_saldo_provisao` / `conciliar_final` (etapa 21):
   sobra `4.4.02`, falta `5.6.10`.

**Lacuna:** as condições excepcionais são invisíveis ao sistema. Ou o operador digita um
`custo_fabrica_novo` "já ajustado" na conferência (sem rastro do porquê), ou a diferença estoura na
conciliação como sobra/falta — o que **classifica amortização de dívida como custo/despesa do
projeto** (os R$ 9.500 da Loja 3 virariam `5.6.10`, contaminando a DRE e a margem real da venda) e
não controla saldo algum.

## Semântica contábil proposta
Duas naturezas distintas, escolhidas **por ajuste** no configurador (`tratamento`):

- **`custo`** (ajuste comercial puro): muda o custo econômico da venda. Reusa
  `ajustar_provisao_delta` (ativo diferido × provisão, nunca DRE) — o CMV futuro passa a ser o
  valor ajustado e a margem real melhora/piora. Ex.: o cashback de 5% da Loja 3.
- **`consumir_saldo`** (vinculado a um acordo com saldo no razão): o custo econômico **não muda**;
  a aplicação realiza/amortiza um saldo pré-existente:
  - **Desconto por crédito** (fábrica deve ao grupo): paga-se menos à fábrica, o crédito baixa, o
    ativo diferido (CMV) fica íntegro. Ex.: Inspirium 3%, Verano 5%.
  - **Acréscimo por dívida** (loja deve à fábrica): `DR 2.1.08 × CR 2.1.04.06` — o "a pagar" à
    fábrica sobe até casar com a NF-e/desembolso, a dívida antiga baixa, a DRE fica intocada.
    Ex.: Loja 3 +10%.

### Acordo triangular — crédito de UMA loja consumido por OUTRA (decisão 2026-07-21, revisada)
O crédito da fábrica pertence à **Verano** (credora real), mas o desconto é concedido também nas
compras da **Inspirium**. Quando a Inspirium consome 3%, ela recebe um benefício que não é dela —
nasce uma **dívida da Inspirium com a Verano** (contabilidade de partes relacionadas: mútuo/conta
corrente entre empresas do grupo). O acordo tem uma **loja credora** (`loja_credora_id`).

**Princípio (revisão 2026-07-21): a venda de uma loja NUNCA lança no razão de outra.** O desenho
de lançamento espelhado automático foi **descartado** — acoplaria o razão da Verano a um evento
comercial da Inspirium (transação cross-owner, trilha de auditoria estranha, fere a independência
das lojas). Em vez disso, dois momentos desacoplados:

- **Na venda (só o razão da compradora).** Inspirium consome 3.000: `DR 2.1.04.06 3.000 ×
  CR 2.1.09 3.000` (Conta Corrente com Lojas do Grupo — a pagar) — paga 3.000 a menos à fábrica e
  passa a dever 3.000 à Verano; CMV íntegro. A aplicação fica registrada em
  `ajuste_fabrica_aplicacao` com status **`pendente_acerto`**. Nada é lançado na Verano.
- **No acerto periódico (só o razão da credora).** Ação no painel do acordo (Diretor/aprovador da
  Verano): seleciona as aplicações pendentes até a data-corte e gera **UM lançamento consolidado**
  no razão da Verano — `DR 1.1.09 × CR 1.1.08` pela soma — marcando-as `acertadas`. É um evento
  contábil **da própria Verano**, lastreado no extrato de consumo (mesma natureza de uma
  conciliação bancária). Idempotente por `ref = acerto:<acordo_id>:<data-corte>`.
- **Loja compradora = credora** (Verano consome os 5% dela): caso simples, um razão só, direto na
  venda — `DR 2.1.04.06 × CR 1.1.08` (sem conta corrente, sem acerto).
- **Liquidação financeira** (quando/se as lojas acertarem em dinheiro): Inspirium `DR 2.1.09 ×
  CR 1.1.01`; Verano `DR 1.1.01 × CR 1.1.09` — cada uma lança a sua ponta quando o dinheiro se
  move (evento `liquidacao_conta_corrente`, valor livre, capado ao saldo).

**Cap com desacoplamento:** entre acertos, o `1.1.08` da Verano ainda não reflete o consumo da
Inspirium. O saldo DISPONÍVEL do acordo é calculado como `saldo 1.1.08 da credora − Σ aplicações
pendente_acerto` (a tabela de aplicações é a ponte entre os razões) — é esse valor que capa novas
aplicações das duas lojas. O painel exibe os três números: saldo contábil, pendente de acerto e
disponível. A defasagem do `1.1.08` entre acertos é diferença de timing dentro do período,
corrigida integralmente no acerto — gerencialmente aceitável e visível no painel.

**Contas novas** (`seed_plano` backfilla, idempotente — padrão Custo Fixo): `1.1.08` **Créditos com
a Fábrica** (ativo), `2.1.08` **Acordos com a Fábrica a Amortizar** (passivo), `1.1.09` **Conta
Corrente com Lojas do Grupo (a receber)**, `2.1.09` **Conta Corrente com Lojas do Grupo (a pagar)**
e `3.5` **Ajustes de Exercícios Anteriores** (PL). Nenhuma fica no grupo `2.1.04.x`, então a
reconciliação data-driven (painel, `conciliar_final`, `devolver_venda`) não as varre por engano.

**Implantação dos saldos iniciais (orientação adotada, sem contador):** crédito e dívida são
direitos/obrigações de **eventos passados**, anteriores ao razão gerencial — pela regra contábil
(CPC 23, retificação de períodos anteriores), entram pelo **patrimônio líquido**, nunca pela DRE
corrente: crédito da Verano `DR 1.1.08 × CR 3.5`; dívida da Loja 3 `DR 3.5 × CR 2.1.08`. Lançar
pelo resultado (4.4.x/5.6.x) inflaria receita/despesa de hoje com fatos de ontem — incoerente.

**Eventos novos** em `EVENTOS`: `implantacao_credito_fabrica` (`1.1.08 × 3.5`),
`implantacao_divida_fabrica` (`3.5 × 2.1.08`), `desconto_excepcional_fabrica`
(`2.1.04.06 × 1.1.08`, credora consumindo o próprio crédito), `desconto_excepcional_intercompany`
(`2.1.04.06 × 2.1.09`, SÓ no razão da compradora), `acerto_acordo_intercompany` (`1.1.09 ×
1.1.08`, SÓ no razão da credora, consolidado por período), `acrescimo_excepcional_fabrica`
(`2.1.08 × 2.1.04.06`) e `liquidacao_conta_corrente` (`2.1.09 × 1.1.01` na devedora / `1.1.01 ×
1.1.09` na credora — cada loja lança a sua ponta). Implantação e acerto são lançamentos de owner
(sem `projeto_id`); aplicações levam `projeto_id` + `ref` idempotente.

### Exemplo fechado (Loja 3, pedido de R$ 100.000)
1. Contrato: `DR 1.1.06.06 100.000 × CR 2.1.04.06 100.000` (fluxo atual, intocado).
2. Conferência com ajustes: desconto 5% `tratamento=custo` → `ajustar_provisao_delta` 100.000→95.000
   (`DR 2.1.04.06 5.000 × CR 1.1.06.06 5.000`); acréscimo 10% sobre o valor pós-desconto
   (95.000 × 10% = 9.500) `tratamento=consumir_saldo` → `DR 2.1.08 9.500 × CR 2.1.04.06 9.500`.
3. Estado: a pagar `2.1.04.06` = **104.500** (casa com a NF-e da fábrica); CMV futuro `1.1.06.06` =
   **95.000**; dívida `2.1.08` abatida em **9.500**.
4. NF-e: matching pleno reconhece `DR 5.1.01 95.000 × CR 1.1.06.06 95.000` (mecanismo atual, sem
   mudança). `pagamento_fabrica` baixa os 104.500 contra caixa. Conciliação fecha **sem
   sobra/falta** — hoje esses 9.500 virariam falta `5.6.10`.

Inspirium (3% consumindo crédito da **Verano**): na venda, a Inspirium paga 97.000 à fábrica,
segue com CMV 100.000 e fica devendo 3.000 à Verano na conta corrente (`2.1.09`) — nada é lançado
na Verano. No acerto do período, a Verano lança consolidado `DR 1.1.09 × CR 1.1.08` pelo total
consumido pelas lojas irmãs. O saldo do acordo vive no `1.1.08` da Verano; o cap usa o
**disponível** (contábil − pendente de acerto).

## Configurador — modelo de dados (duas opções)
- **Opção 1 — JSON em `config_financeira_json`** (chave `ajustes_fabrica: [...]`): zero migração,
  validação em `validar_config_financeira`, padrão já existente. **Limites**: não registra
  aplicações por venda, não versiona, pontuais não têm onde morar, sem saldo. Serve só p/ a
  alternativa A1 abaixo.
- **Opção 2 — tabelas próprias** (recomendada p/ o escopo escolhido), em DOIS níveis — o ACORDO é
  entidade de primeira classe (decisão 2026-07-21; ver painel Admin abaixo), o AJUSTE é a regra de
  consumo por loja:
  - `acordo_fabrica`: `id, descricao, tipo (credito|divida), loja_titular_id (credora do crédito /
    devedora da dívida — dona do saldo no razão), conta_saldo (1.1.08|2.1.08), valor_implantado,
    status (ativo|esgotado|encerrado), criado_por_id, criado_em`. Cadastro dispara a implantação
    (`× 3.5`) no owner titular. Cobre os casos futuros do mesmo jeito: crédito negociado
    reembolsado em descontos = `tipo=credito` consumido por ajustes-desconto; linha de crédito
    especial liquidada em NF-es = `tipo=divida` amortizada por ajustes-acréscimo.
  - `ajuste_fabrica`: `id, acordo_id (NULL p/ tratamento=custo puro), loja_id (quem consome),
    descricao, tipo (desconto|acrescimo), natureza (recorrente|pontual), pct, base (pos_descontos
    — default | valor_conferido), tratamento (custo|consumir_saldo), vigencia_de/ate (opcionais),
    ativo, criado_por_id, criado_em`. `loja_id ≠ loja_titular_id` do acordo ⇒ fluxo intercompany
    (conta corrente + acerto). Pontual nasce vinculado a projeto(s). O crédito da Verano vira UM
    acordo com DOIS ajustes — 3% loja=Inspirium e 5% loja=Verano — capados pelo mesmo saldo.
  - `ajuste_fabrica_aplicacao`: `id, ajuste_id, projeto_nome, base_calculo, pct_snapshot, valor,
    status (pendente_acerto|acertada|n/a), lancamento_ref, acerto_ref, criado_em` — trilha de
    auditoria + fonte dos relatórios e do saldo DISPONÍVEL (o razão é a fonte do saldo CONTÁBIL).

## Painel Admin — "Acordos com a Fábrica" (decisão 2026-07-21)
Painel próprio no **Admin** (gating dos endpoints `/api/admin/...`: super_admin/Diretor, console
com `X-Loja-Ativa`), separado da config financeira por loja — acordos são negociação de Diretoria
e cruzam lojas. Conteúdo: lista de acordos com os três saldos (contábil, pendente de acerto,
disponível) e status; detalhe com extrato (implantação, aplicações por loja/projeto, acertos,
liquidações — tudo via refs do razão + tabela de aplicações); ações **implantar** (cadastro c/
valor), **acertar** (data-corte, consolidado na titular), **liquidar conta corrente** (R$ livre,
capado) e **encerrar** (exige saldo zero; resíduo final se resolve por lançamento de baixa contra
3.5, espelho da implantação). Os AJUSTES (% por loja) são geridos no mesmo painel, aninhados no
acordo; ajustes `tratamento=custo` (sem acordo, ex.: cashback Loja 3) ganham uma lista à parte no
mesmo lugar. Na etapa 12 (conferência) nada muda: só o preview/aplicação.

## Ponto único de aplicação: a Conferência do Pedido (etapa 12)
Melhor gancho do ciclo: o valor real do pedido já é conhecido (PE), a rota **já exige aprovador
financeiro** e já é o lugar do ajuste de Custo de Fábrica. `conferencia_pedido` passa a receber a
lista de aplicações (pré-calculada no GET de preview, editável na tela):

1. Ajusta a provisão ao valor conferido (`custo_fabrica_novo` — mecanismo atual).
2. Aplica **descontos** excepcionais sobre o valor conferido (recorrentes vêm pré-marcados se
   vigentes; pontuais, se vinculados ao projeto).
3. Aplica **acréscimos** sobre o valor **pós-descontos** (é o que reproduz 95.000 → 104.500).

Regras: aplicação `consumir_saldo` é **capada ao saldo em aberto** da conta do acordo (padrão do
cap de `ajustar_provisao_delta`) — consome parcial e alerta; **saldo zerado → ajuste
auto-desativa** (status `esgotado`). Idempotência por `ref = ajx:<projeto>:<ajuste_id>`.
Ajuste criado depois da conferência: aplicação avulsa pelo painel do projeto (mesmos eventos, ref
própria) — não reabre a conferência.

## Alternativas e complexidade
- **A0 — só processo, zero código.** Operador digita na conferência o custo real (95.000) e deixa o
  resto p/ a conciliação. **Custo:** amortização vira falta `5.6.10` (DRE errada), descontos viram
  sobra `4.4.02` genérica, nenhum saldo/auditoria. É o estado atual com disciplina manual.
- **A1 — configurador leve (Opção 1), sem saldo no razão.** Percentuais recorrentes por loja em
  `config_financeira_json`; a conferência sugere o `custo_fabrica_novo` já ajustado via
  `ajustar_provisao_delta`. **Esforço ~1 sessão.** Limites: tudo é tratado como custo (margem),
  amortização de dívida continua contaminando CMV/conciliação, sem trilha nem saldo. Não atende a
  decisão "saldo no razão" — registrada como degrau intermediário, não como fim.
- **A2 — recomendada (Opção 2 + contas/eventos + aplicação na conferência + painel Admin).**
  Atende o escopo decidido. **Esforço estimado: 4 sessões** — (i) backend contábil+modelo:
  3 tabelas, 5 contas, 7 eventos, `mod_ajustes_fabrica.py` puro (cálculo, ordem, caps, acerto) +
  CRUD/endpoints admin (~1,5–2 sessões); (ii) frontend: painel "Acordos com a Fábrica" no Admin
  (lista, extrato, ações) + bloco de preview na tela da etapa 12 (~1–1,5 sessão em
  `static/index.html`); (iii) testes+e2e (~1 sessão).
- **A3 — extensões futuras (fora desta frente):** refletir o custo ajustado nas margens da
  negociação (mexe no motor — área sensível; decisão de hoje: não); consolidação do grupo — o razão
  é por owner (loja), a visão "dívida da fábrica com o GRUPO" nasce como **relatório multi-loja**
  (super_admin soma 1.1.08 das lojas; implantar o saldo já ratear por loja); validação automática
  da face da NF-e da fábrica (XML da etapa 15 já é parseável por `fiscal/mod_nfe`) contra o
  esperado `conferido − descontos + acréscimos` — alerta de divergência antes do matching.

## Riscos e casos de borda (A2)
- **Reconciliação/invariantes:** o `CR` extra em `2.1.04.06` (amortização) quebra a leitura
  "constituído = Σ fechamento+AF" — os painéis que comparam constituído × efetivado devem tratar a
  origem nova (`origem='ajuste_excepcional'`) como componente do provisionado. Testar
  `conciliar_final` e o painel de reconciliação com aplicação no meio do ciclo.
- **Devolução de venda** (`devolver_venda`): reverter aplicações proporcionais à fração devolvida
  (devolve saldo ao acordo). Sem isso, devolução "consome" dívida/crédito indevidamente.
- **Ordem/base de cálculo:** descontos sobre o valor conferido; acréscimos sobre o pós-descontos.
  Fixar em `mod_ajustes_fabrica` puro + testes com o exemplo 100k→95k→104,5k fechado ao centavo
  (arredondar por aplicação, `round(…, 2)`).
- **Vigência × projetos em andamento:** ajuste novo vale para conferências futuras; nunca
  retroage sozinho (aplicação retroativa só manual, pelo painel do projeto).
- **Tenancy/permissão:** CRUD gated como o `config-financeira` (PUT por loja, `editar_dados_loja`/
  aprovador financeiro na aplicação); `owner` via `resolver_owner` (hoje loja). Ajuste com
  `loja_credora_id` de outra loja só pode ser criado por perfil com visão das duas (Diretor de
  rede/super_admin).
- **Desacoplamento intercompany:** nenhuma escrita cross-owner — a venda lança só na compradora,
  o acerto só na credora. Invariantes testáveis: `Σ 2.1.09 (devedora) == Σ aplicações (pendentes +
  acertadas)` e, pós-acerto, `Σ 1.1.09 (credora) == Σ aplicações acertadas`. Reversão de aplicação
  **já acertada** (devolução tardia) não estorna o razão da credora: gera aplicação NEGATIVA
  `pendente_acerto`, absorvida no acerto seguinte — preserva o princípio de que só a credora lança
  na credora.
- **Pagamento:** `pagamento_fabrica` baixa `2.1.04.06` pelo total (104.500) — conferir telas de
  contas a pagar que assumem "a pagar = CFO".

## Revisão "Acordos Financeiros" (2026-07-21, feedback de TESTE do usuário — SUPERA o acerto)
O mecanismo de acerto consolidado por data-corte reprovou no teste de usabilidade ("bem confuso") e
foi **eliminado**. Modelo novo, mais simples e mais geral:

- **Contraparte generalizada** no acordo: `fabrica` | `empresa` (nome livre; do grupo ou não) |
  `banco`. Aba renomeada **"Acordos Financeiros"** (internamente as rotas/tabelas mantêm os nomes
  `acordos-fabrica`/`acordo_fabrica` — mesmo precedente do "parcela→Fase").
- **Cada loja registra só o SEU lado** (nenhuma escrita cross-owner, nenhum acerto automático):
  a Verano cadastra a Inspirium como DEVEDORA (acordo crédito-empresa, `1.1.09`, nasce zerado e
  recebe por **transferência manual** do crédito-fábrica); a Inspirium cadastra a Verano como
  CREDORA (acordo dívida-empresa, `2.1.09`, nasce zerado e **ACUMULA sem cap** a cada desconto
  consumido na conferência). Liquidação: cada lado registra o seu movimento (pagar/receber).
- **Bancos/empréstimos**: acordo dívida-banco (`2.1.10` nova). Criação com `captacao=true` lança
  `1.1.01 × 2.1.10` (o dinheiro entra agora); saldo pré-existente → PL (`3.5 × 2.1.10`).
  **Atualização de juros** (`5.5.02 × dívida` — despesa corrente LEGÍTIMA, única exceção
  deliberada ao "sem DRE") e **pagamento** (`dívida × 1.1.01`) pelo painel.
- **Movimentos manuais por acordo** (`acordo_movimento`, endpoint `/movimento`): pagar | receber |
  atualizar | transferir (crédito→crédito da MESMA loja, capado à origem). Substituem os antigos
  `/acertar` e `/liquidar`.
- **Saldo por acordo** = implantado + aplicações COM SINAL (dívida-empresa+desconto acumula; os
  demais consomem) + movimentos. `pendente_acerto` deixou de existir.
- **Desconto por período** sem crédito/dívida: ajuste `tratamento=custo` com `vigencia_de/ate`
  (o motor já respeitava vigência; agora o painel expõe os campos nos ajustes avulsos).

## 2ª revisão (2026-07-22, feedback de teste): Credores/Devedores, juros e desacoplamento total
- **Cadastro de Credores/Devedores** (`contraparte_financeira`): o acordo é lançado contra uma
  contraparte CADASTRADA (seletor). O papel vem do tipo do acordo: crédito nosso ⇒ contraparte
  devedora; dívida nossa ⇒ contraparte credora.
- **Pagamento com NOMINAL + JUROS separados**: nominal baixa o passivo (`dívida × 1.1.01`); juros
  vão direto a despesa (`5.5.02 × 1.1.01`, evento `pagamento_juros_acordo`) — bancos sempre têm.
  "Atualizar encargos" (incorpora ao saldo) continua disponível.
- **Desacoplamento TOTAL**: descontos/acréscimos são SEMPRE de custo (% que ajusta a provisão de
  Custo de Fábrica na conferência — mudam a condição comercial); `consumir_saldo` foi
  DESCONTINUADO (400 na criação). Se um desconto/acréscimo se referir a um crédito/dívida, o
  lado financeiro é lançado MANUALMENTE no acordo (acrescer/abater sem caixa, × 3.5) — reflete
  no balanço sem acoplar os painéis. Consequência assumida: o CMV passa a ser o custo REAL da
  nota (ex.: Loja 3 → CMV 104.500), não mais o custo "econômico" — validar com contador.
- **Vigência pela DATA DA VENDA**: o desconto por período aplica se o pedido foi VENDIDO dentro
  da janela (data do contrato), mesmo que a conferência ocorra depois.
- **PL × credores (pergunta do Diretor, respondida)**: o passivo JÁ vive em contas de credores
  (2.1.08/2.1.09/2.1.10); o `3.5` (PL) é apenas a contrapartida da implantação de saldos
  PRÉ-EXISTENTES (CPC 23 — fatos passados não passam pela DRE corrente). Empréstimo NOVO entra
  pelo caixa (captação), sem tocar o PL.

## Limitações conhecidas (registradas no QA de 2026-07-21)
- **Conta corrente por contraparte** *(RESOLVIDA pela revisão Acordos Financeiros)*: o saldo por
  acordo agora é 100% derivado da trilha própria (implantado + aplicações + movimentos), não do
  saldo agregado da conta do razão — múltiplos acordos na mesma conta não se contaminam. As
  contas `1.1.09`/`2.1.09` seguem agregadas no razão (balanço), o que é aceitável.
- **Dados legados do acerto**: verificado em 2026-07-21 (local + VPS A/B) que NENHUMA aplicação
  `pendente_acerto` existia antes da revisão — a mudança de leitura do saldo não órfã nada.
- **Reconferência com PE diferente** rebaseia os ajustes por DELTA (razão acompanha o PE novo;
  refs `ajx:<proj>:<ajuste>[:rN]`); o cap do recálculo devolve ao disponível o consumo do próprio
  projeto antes de capar.

## Testes
`test_ajustes_fabrica.py` (motor puro: ordem, caps, esgotamento, vigência, pontual×recorrente);
`test_contabil_ajustes_excepcionais.py` (4 eventos, cap ao saldo, idempotência por ref,
auto-desativação, ciclo completo contrato → conferência c/ ajustes → matching → pagamento →
conciliação **sem sobra/falta** no exemplo da Loja 3 e no da Inspirium); reconciliação com origem
nova; `devolver_venda` com aplicação; e2e no `test_fluxo_completo_e2e.py`. Rodar também contra
Postgres real (`TEST_DATABASE_URL`).

## Decisões já tomadas (2026-07-21)
- Saldo das dívidas **no razão**; alcance **só financeiro** (motor de negociação intocado).
- Crédito da fábrica pertence à **Verano** (credora única); o saldo implanta inteiro no `1.1.08`
  da Verano, sem rateio. Inspirium consome via **conta corrente intercompany DESACOPLADA**: a
  venda lança só na Inspirium (passivo `2.1.09`), a Verano reconhece por **acerto periódico
  consolidado** — venda de uma loja nunca lança no razão de outra (revisão 2026-07-21, a pedido
  do Diretor; o espelhamento automático foi descartado).
- Implantação de saldos pelo **PL (3.5 Ajustes de Exercícios Anteriores)**, nunca pela DRE
  corrente (CPC 23) — orientação adotada sem contador, por decisão do Diretor.
- Inspirium 3% e Verano 5%: `tratamento=consumir_saldo` (realizam o crédito; não infla margem).
  Loja 3: 5% cashback = `tratamento=custo` (melhora a margem da venda) + 10% acréscimo =
  `consumir_saldo` da dívida.
- **Saldos iniciais**: informados na **implantação do acordo** pelo painel Admin "Acordos com a
  Fábrica" (o cadastro pede o valor em R$ e dispara o evento de implantação `× 3.5` no owner
  titular — credora p/ crédito, devedora p/ dívida). Sem carga por script/seed.
- **Painel próprio em Admin** para acordos/linhas de crédito com a fábrica (entidade
  `acordo_fabrica` separada dos ajustes) — comporta os casos futuros: créditos negociados
  reembolsados em descontos e linhas de crédito liquidadas com acréscimos em NF-e.
- **Acerto e liquidação**: **manuais, sob demanda** (decisão gerencial, sem periodicidade fixa) —
  botões no painel do acordo; nenhuma rotina agendada. A data-corte do acerto é escolhida no ato
  (ref idempotente por acordo+data-corte).
- **Sem teto** além do próprio saldo (o % aplica cheio até esgotar, com cap ao disponível), **sem
  prazo/vigência** (acordo vale até o saldo zerar → status `esgotado`; os campos `vigencia_de/ate`
  ficam no modelo como opcionais, não usados nos acordos atuais) e **sem juros/atualização
  monetária** — todos os saldos (crédito, dívida, conta corrente) são nominais.

Não restam definições pendentes — a spec está pronta para virar frente de desenvolvimento
(esforço A2: 3–4 sessões; ver seção Alternativas).
