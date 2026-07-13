# Spec — Desmembramento parcial na Revisão de PE (comparação, aprovação e liquidação por parcela)

> Design spec derivado do briefing `docs/superpowers/plans/2026-07-13-desmembramento-pe-parcial.md`
> (mecânica validada com Fable 5 em 2026-07-13). Este documento **fecha as 8 decisões da seção 4 do
> briefing** e define o fatiamento de implementação. Fundamentado em leitura real do código
> (`database.py`, `main.py`, `mod_ciclo.py`, `mod_contabil.py`, `mod_negociacao.py`).

## 1. Objetivo

Permitir que, na subfase **Revisão de PE (11c)**, o projeto siga **completo** ou **desmembrado** em
**parcelas** (grupos de ambientes) que percorrem Aprovação Financeira → Implantação → Produção →
Entrega → NF-e/NFS-e de forma **independente e em liquidações sucessivas**. Antes disso, entregar a
dor visível: **comparar** o valor de venda com o valor atualizado do Projeto Executivo (PE) por
ambiente, com o XML de PE armazenado **fora do pool** do orçamento.

## 2. Princípios herdados (não renegociar)

- **Fonte única = razão contábil**; painéis são views derivadas.
- **Rigor contábil**: começar pela opção contabilmente correta e mais barata; abrir evento novo só
  quando o negócio exigir (ver decisão #3).
- **Trava `_contrato_assinado` do pool é correta** (`main.py:3944-3949`) e **não será relaxada**.
- **Legado intacto**: desmembrar é opt-in; projeto sem parcela roda o fluxo atual sem migração.

## 3. Decisões arquiteturais fechadas (seção 4 do briefing)

### #1 — Unidade da aprovação parcial = **parcela** (grupo de ambientes)
Tabela nova `parcela_projeto` + membership `parcela_ambiente` (N:N com `pool_ambientes`). A parcela
congela, na criação, a **fração do `Val_Cont`** e o **valor congelado** (ver #5). Status próprio
(`aguardando` | `em_aprovacao` | `liquidada`). **Não** é aprovação ambiente-a-ambiente pura.

### #2 — XML de PE vive **FORA do pool** *(decisão enfatizada)*
Tabela nova `arquivo_pe`, **sem FK para `orcamentos`/`orcamento_ambientes`** e sem criar linha em
`pool_ambientes`. O XML de PE é **documento de comparação/liquidação**: é parseado só para extrair o
`valor_atualizado`; **não alimenta o motor** (`mod_negociacao`), **não entra no orçamento assinado**,
**não gera versão de pool**. Por não tocar `pool_ambientes`, a feature **não esbarra** na trava
`_contrato_assinado` (`main.py:3944`), que continua bloqueando upload no pool pós-contrato — como deve.
O Promob-PE nativo é guardado como arquivo (não parseado). Layout em disco: subpasta por ambiente com
os 4 arquivos (Promob venda, XML venda, Promob PE, XML PE); os de venda já existem (pool), os de PE são
os novos.

### #3 — Semântica contábil da atualização = **opção (a)** *(começar pela barata, decisão do usuário)*
*(refinado pela decisão #11 — vale ler as duas juntas: #3 continua valendo pra Fatia 1/#9, que é
snapshot puro; a partir da confirmação formal de uma Aprovação Financeira, #11 introduz um evento de
ajuste que a versão original desta decisão ainda não previa.)*

O `valor_atualizado` do PE é **snapshot/comparação**. Não gera evento contábil de ajuste de provisão
por liquidação. A divergência real×planejado continua **absorvida pelo mecanismo existente**
(`resolver_saldo_provisao` + `conciliar_final`, etapa 21 — FASE D2). A opção (b) (delta-constituição/
reversão por liquidação, no padrão de `reclassificar_provisao`) fica **documentada como evolução
futura**, a ser adotada só se o negócio precisar de margem fechada por parcela antes da conciliação
final. **Implicação para a Fatia 3:** a liquidação parcial usa a mecânica FASE D2 já existente,
apenas **proporcionada e escopada por parcela** (fração de #5 + refs de #6) — sem eventos contábeis
novos.

### #4 — Valor da comparação = **CUSTO DE FÁBRICA (CFO) por ambiente, não valor de venda**
*(correção 2026-07-13 — a versão original desta decisão comparava a grandeza errada)*

O XML do Promob — tanto o de venda quanto o de PE — carrega **custo de fábrica** (campo de
orçamento/budget); o valor de venda é derivado **depois**, pelo motor (`mod_negociacao`), aplicando
markup/negociação em cima do custo. Logo o `valor_atualizado` extraído de um XML de PE recarregado é
um **novo CFO**, não um novo valor de venda — e é o CFO que alimenta a rubrica que um PE recarregado
afeta diretamente, a Provisão de Custo de Fábrica (`1.1.06.06 × 2.1.04.06`).

A coluna "original" da comparação usa portanto o **CFO por ambiente já existente no pool**
(`PoolAmbiente.order_total`/campo de custo equivalente do XML de venda), **não**
`_ambientes_valor_para_contrato` (que é valor de venda rateado com financeiro — grandeza do lado
errado, não comparável a um custo). Ambientes sem XML de PE carregado aparecem com "CFO atualizado"
= 0 e diferença = −CFO original (sinalizado como "PE não carregado", não como redução real).

Uma coluna de valor de venda pode existir como informação complementar pro cliente (reaproveitando
`_ambientes_valor_para_contrato` só para exibição), mas **não é ela que move provisão/margem** — só o
CFO é.

### #5 — Fração da parcela e arredondamento
Na criação, cada parcela congela `fracao_val_cont = Σ(valor_contrato dos seus ambientes) / Val_Cont` e
`val_cont_congelado = round(fracao_val_cont × Val_Cont, 2)`. **A última parcela leva o resto:**
`val_cont_congelado(última) = Val_Cont − Σ(val_cont_congelado das anteriores)`. Isso evita sobra de
centavos e é a base do faturamento e do matching de NF-e parciais (Fatia 3). Invariante testável:
`Σ val_cont_congelado == Val_Cont` (exato, ao centavo).

### #6 — Refs idempotentes ganham dimensão "parcela"
Hoje `reconhecer_despesas_nfe` é chamado com `ref_base="match:"+projeto_nome` (`main.py:528`, fixo por
projeto → 2ª NF-e faria no-op). Passa a `ref_base="match:"+projeto_nome+":"+str(parcela_id)`. O mesmo
padrão vale para os demais eventos por parcela na Fatia 3: `faturar_segmento`,
`constituir_provisoes_*`, `efetivar_impostos_segmento`, `conciliar_final` — todos com o sufixo
`:<parcela_id>` no `ref_base`. Sem isso, liquidações sucessivas da mesma rubrica se anulam
silenciosamente. Projeto **não desmembrado** mantém o `ref_base` atual (sem sufixo) — compatibilidade.

### #7 — Status agregado das etapas 12-16 = **uma linha de `CicloLogistico` por parcela**
`CicloLogistico` **não tem UniqueConstraint em `projeto_nome`** (confirmado em `database.py:620-648`) →
já aceita N linhas por projeto. Adiciona-se `parcela_id` (FK nullable) a `CicloLogistico`; cada parcela
vira uma linha com seu `status_atual`. A tela do ciclo (etapas 12-16) lista as parcelas com progresso
individual. `CicloEtapa` (que tem `UniqueConstraint(projeto_nome, etapa_codigo)`) permanece **agregado
por projeto** e só fecha `concluida` quando **todas as parcelas** concluíram aquela etapa. Lock
pós-Implantação: ambiente cuja parcela entrou em "Implantação do Pedido" fica bloqueado para
edição/comparação (flag derivada do status da parcela).

### #8 — Legado / não desmembrado = fluxo atual, opt-in
Desmembrar é escolha explícita na 11c. `projeto sem linha em parcela_projeto` ⇒ caminhos atuais
intactos (`CicloEtapa`/`CicloLogistico` projeto-wide; contábil whole; `ref_base` sem sufixo). Nenhuma
migração automática. Todo código novo ramifica em "o projeto tem parcelas?".

### #9 — Saldo evolutivo = RECONCILIAÇÃO ESTIMADA referenciada ao Val_Cont (não contábil)
*(realinhado 2026-07-13 após feedback do usuário — a versão "número solto de CFO" gerava confusão)*

O saldo **não** é um número isolado de custo de fábrica. É a **reconciliação estimada de TODAS as
rubricas**, ancorada no **valor de contrato (Val_Cont)**, dando a visão evolutiva do processo *antes*
da liquidação formal (Fatia 3). Resolve o "faltando as outras rubricas": mostra a estrutura completa.

Estende a reconciliação existente (`mod_contabil.reconciliacao`) com uma coluna **Estimado**: por
rubrica → `Provisionado` (constituído no contrato) × `Estimado` × `Δ`. Na **Fatia 1**, só a rubrica
**Custo de Fábrica** muda no Estimado (Σ dos `CFO_pe` dos ambientes com PE carregado — #4); as demais
rubricas seguem o valor do contrato (são % fixo do Val_Cont, só se movem na liquidação — Fatia 3).
Ancorado ao Val_Cont: **margem estimada = Val_Cont − Σ(estimado)**, ao lado da margem contratada.
Mostra TODAS as rubricas (mesmo provisionado=0) para dar a estrutura.

**Read-only, não lança nada** (#3); derivado (recalculável de `pool_ambientes` + `arquivo_pe` + razão).
`parcela_projeto.saldo_margem_estimado` é só cache opcional. Exibido na Revisão de PE e na Aprovação
Financeira, **rotulado "estimativa gerencial"** e visualmente separado do saldo contábil real (o da
reconciliação, que só muda na liquidação, #3) — a UI não pode deixar os dois se confundirem
(rótulo/cor diferente, "estimativa" sempre visível).

### #10 — Gate da Aprovação Financeira (Rev1/Rev2/Rev3) — **FATIA 2** (sensível)
*(adicionado 2026-07-13, a pedido do usuário)*

O modal de Provisões tem colunas por versão (`ProvisaoRegistro.versao`: venda/rev1/rev2). A Aprovação
Financeira é um **gate de escrita por etapa** (≠ da visão read-only da #9):
- **AF1** edita a coluna **Rev1**; **após aprovar, trava** Rev1. Aumento de custo acima do
  **Limite de Aprovação Financeira 1** (default **1%**) exige **aprovação do Diretor** (mecanismo de
  step-up já existente no projeto).
- **AF2** edita a coluna **Rev2**; **após aprovar, trava** Rev2. Aumento acima do **Limite de
  Aprovação Financeira 2** (default **2%**) exige Diretor.
- **Rev3**: **nova coluna** — só a estrutura/placeholder agora; a etapa que a usa entra numa fase
  futura de desenvolvimento.
- **Limites configuráveis** no painel **Config de Provisões**: "Limite de Aprovação Financeira 1" e
  "Limite de Aprovação Financeira 2".
- Quando o projeto está **desmembrado** (#1), o gate roda **por parcela**.

Toca aprovação/ciclo + provisões → **área sensível: Vera antes de mergear + TDD**. Não faz parte da
Fatia 1 (read-only). Fica na **Fatia 2** (junto do desmembramento operacional/aprovação por parcela).

### #11 — Confirmar AF1/AF2 lança **ajuste (delta)**, só ativo×provisão, NUNCA DRE
*(adicionado 2026-07-13, a pedido do usuário — refina #3/#10 com a mecânica contábil que faltava)*

A confirmação de uma Aprovação Financeira (travar Rev1 na AF1, travar Rev2 na AF2 — #10) — quando a
estimativa mudou desde a versão anterior — lança um evento de **ajuste pontual (delta)**: débito/
crédito **só entre `1.1.06.0X` (ativo diferido) e `2.1.04.0X` (provisão)**, do tamanho exato da
diferença entre o valor da versão anterior e o novo. Mesmo padrão de `reclassificar_provisao`
(append-only, idempotente por ref, capado ao saldo em aberto). **Nunca toca DRE** — isso é
efetivação, reservada pra decisão #12. O próprio gate de aprovação (#10, incl. step-up pro Diretor
acima do limite) já protege a ação; não é preciso mecanismo de senha novo.

Efeito prático: cada Aprovação Financeira vai corrigindo o ativo/provisão pro valor mais atual
conhecido, em passos pequenos e auditáveis — quando a NF-e sair (#12), o saldo que ela vai baixar
**já está certo**, sem reconciliação a posteriori contra um valor antecipado.

### #12 — Matching (DRE) fica reservado pra emissão real da NF-e — sem antecipação
*(adicionado 2026-07-13 — fecha a dúvida "o que é matching" levantada na revisão do usuário)*

Nenhuma Aprovação Financeira (I, II, ou a conferência da #13) reconhece despesa na DRE
antecipadamente. O único evento que move `5.6.0X`/`5.1.01` (DRE) × baixa `1.1.06.0X` (ativo) continua
sendo `reconhecer_despesas_nfe`, disparado pela emissão real da NF-e — **proporcional por parcela**
(fração congelada #5; `val` capado pela fração da parcela em vez do saldo aberto inteiro do projeto;
ref ganha sufixo `:parcela_id`, #6). Não há risco de divergência entre "efetivado cedo" × NF-e real,
porque não existe reconhecimento cedo — só os ajustes de ativo/provisão da #11, que já deixam o saldo
correto esperando a NF-e.

### #13 — Etapa "Conferência e Implantação do Pedido" (mesclada) + split PE × Outros Fornecedores
*(adicionado 2026-07-13, a pedido do usuário)*

A etapa 12 (Implantação do Pedido) é **renomeada** para **"Conferência e Implantação do Pedido"** —
**sem** virar etapa nova no ciclo (mesmo ator, o financeiro, confere e em seguida libera a fábrica/
aprova as compras, sem handoff pra outro papel entre as duas ações; etapa separada só aumentaria
gating/cronograma/UI sem ganho real). Granularidade da **tela/etapa = 1**, granularidade do **razão
continua = 2**: ao confirmar a conferência, o sistema lança **dois ajustes delta separados e
auditáveis** (mesmo mecanismo da #11, mesmas contas, refs distintas) — um pela diferença de valor do
Projeto Executivo, outro pela parte migrada pra Outros Fornecedores (`2.1.04.06→2.1.04.14` / espelho
`1.1.06.06→1.1.06.14`, reaproveitando `reclassificar_provisao`). Preserva a rastreabilidade fina
(quanto foi PE, quanto foi migração) com uma única tela/ação pro usuário. Uma eventual "Aprovação
Financeira 3"/Conciliação Final revisada fica registrada como pendência de modelo a fechar depois —
não bloqueia esta fatia.

## 4. Modelo de dados (novas tabelas)

```
parcela_projeto
  id                PK
  projeto_nome      FK projetos_meta.nome_safe   (indexado)
  ordem            Int      (1..N; a de maior ordem é a "última" p/ o resto de #5)
  status           Str      aguardando|em_aprovacao|liquidada   default 'aguardando'
  fracao_val_cont  Float    congelada na criação (#5)
  val_cont_congelado Float  congelado na criação (#5)
  orcamento_id     FK orcamentos.id   (o orçamento assinado de origem, p/ o valor de venda)
  saldo_margem_estimado  Float  NÃO É COLUNA OBRIGATÓRIA — campo calculado (#9); persistir só se
                                virar cache de performance, nunca fonte de verdade
  criado_em/por_id

parcela_ambiente               (membership N:N)
  parcela_id       FK parcela_projeto.id
  pool_ambiente_id FK pool_ambientes.id
  PK (parcela_id, pool_ambiente_id)

arquivo_pe                     (XML/Promob de PE — FORA do pool, #2)
  id                PK
  projeto_nome      FK projetos_meta.nome_safe  (indexado)
  pool_ambiente_id  FK pool_ambientes.id        (a QUAL ambiente o PE se refere)
  formato           Str   'xml_pe' | 'promob_pe'
  arquivo_path      Str
  valor_atualizado  Float nullable  (CFO/custo de fábrica extraído do XML — NÃO valor de venda, #4;
                                     só p/ 'xml_pe' parseado; null = não carregado)
  carregado_em/por_id
  UniqueConstraint(projeto_nome, pool_ambiente_id, formato)
```

`CicloLogistico`: **+`parcela_id`** (Integer FK parcela_projeto.id, nullable — NULL = linha projeto-wide
legada).

Migração idempotente (padrão do projeto): `ALTER TABLE ciclo_logistico ADD COLUMN parcela_id` guardado
por checagem de coluna; criação das 3 tabelas via `Base.metadata.create_all`.

## 5. Fatiamento (cada fatia entregável e testável sozinha)

### Fatia 1 — Comparação de CFO + reconciliação ESTIMADA (read-only) *(NÃO toca contabilidade nem ciclo)* ← entregar primeiro
Escopo: tabela `arquivo_pe`; extrator de **CFO** do XML-PE (Σ order_total, #4); endpoints de upload
(fora do pool) e de comparação; UI na 11c ("Carregar XMLs atualizados", "Comparar valores dos
ambientes" + tabela ambiente | CFO venda | CFO PE | Δ); a **reconciliação estimada** referenciada ao
Val_Cont (#9 — todas as rubricas, Provisionado × Estimado × Δ, "estimativa gerencial"), exibida na 11c
e espelhada na Aprovação Financeira (11d) como referência **só leitura**.
**Não cria parcela, não altera etapas, não lança contábil** (lê o razão só para exibir). Resolve a dor
visível e dá o quadro completo para validar.

### Fatia 2 — Desmembramento operacional das etapas 12-16 *(toca CICLO → Vera antes de mergear)*
Seletor "Projeto completo × Desmembrar" na 11c; modal de seleção de ambientes → cria `parcela_projeto`
+ `parcela_ambiente` com fração congelada (#5); `parcela_id` em `CicloLogistico`; sub-estado por parcela
nas etapas 12-16; gating (etapa fecha só com todas as parcelas); lock pós-Implantação; UI do ciclo por
parcela. Aprovação Financeira (11d) passa a ser por parcela (deixa claro qual parcela e o status das
demais), com o gate Rev1/Rev2/Rev3 + limites da #10 e os ajustes delta ativo×provisão da #11. Etapa 12
renomeada "Conferência e Implantação do Pedido", com o split PE×Outros Fornecedores da #13.

### Fatia 3 — Liquidação financeira parcial *(toca CONTABILIDADE → Vera antes de mergear)*
Faturamento/matching/impostos por **fração de parcela** (#5) com **refs dimensionadas por parcela**
(#6), sob a **semântica (a)** (#3) + o reforço da #12 (matching/DRE só na NF-e real, nunca antecipado):
reusa a mecânica FASE D2 existente proporcionada por parcela; nenhum evento de DRE novo — só o que já
existe (`reconhecer_despesas_nfe`), parametrizado por fração. Os ajustes de ativo/provisão que
antecedem a NF-e (#11/#13) já rodaram na Fatia 2; aqui só falta o matching em si.

## 6. Fatia 1 — detalhamento (TDD; é o que se implementa agora)

### Arquivos
- `database.py` — nova classe `ArquivoPE` (+ `ParcelaProjeto`/`ParcelaAmbiente` já criadas p/ não
  re-migrar depois; usadas só a partir da Fatia 2).
- `mod_pe_comparacao.py` (novo) — lógica pura: extrair valor do XML-PE e montar a tabela de comparação.
- `tests/test_pe_comparacao.py` (novo) — TDD da lógica pura.
- `main.py` — endpoints `POST /api/projeto/<nome>/pe/upload` (armazena fora do pool) e
  `GET /api/projeto/<nome>/pe/comparacao`.
- `static/index.html` — botões e tabela na subfase 11c (+ botão espelho em 11d).

### Contrato da função pura (alvo do 1º teste)
`montar_comparacao_pe(itens_cfo_original, valores_pe) -> list[dict]` onde:
- `itens_cfo_original`: `[(nome_exibicao, cfo_original_float), ...]` (saída do CFO por ambiente já no
  pool — `PoolAmbiente.order_total`/campo de custo equivalente do XML de venda; **não**
  `_ambientes_valor_para_contrato`, que é valor de venda — ver correção #4).
- `valores_pe`: `{pool_ambiente_id_ou_nome: cfo_atualizado_float}` (CFO extraído do XML de PE).
- retorna `[{ambiente, cfo_original, cfo_pe, diferenca, pe_carregado(bool)}, ...]`, `diferenca =
  round(cfo_pe − cfo_original, 2)`, `pe_carregado=False` quando o ambiente não tem XML-PE (cfo_pe=0).
- (opcional, só exibição) uma coluna adicional de valor de venda pode ser calculada à parte via
  `_ambientes_valor_para_contrato`, mas fica fora do contrato desta função pura — não participa do
  cálculo de diferença/margem.

Invariantes testáveis da Fatia 1:
1. Ambiente sem PE → `cfo_pe==0`, `pe_carregado==False`, `diferenca==−cfo_original`.
2. Ambiente com PE → `diferenca == round(cfo_pe−cfo_original,2)`.
3. Upload de XML-PE **não cria** linha em `pool_ambientes` e **não dispara** `_contrato_assinado`
   (armazena só em `arquivo_pe`).
4. Ordem/rótulos da tabela seguem os do pool/orçamento (mesma fonte de CFO original, #4).
5. `saldo_margem_estimado` (#9) da parcela == soma de `diferenca` (só ambientes com `pe_carregado`)
   dos seus ambientes membros.

## 7. Riscos e compatibilidade
- **Parser de XML-PE:** reusar o extrator de total do pool; se o layout do PE divergir, isolar em
  `mod_pe_comparacao` e cobrir com teste de um XML real de exemplo.
- **Legado:** toda leitura nova deve tratar "projeto sem parcela/arquivo_pe" como o estado atual.
- **Vera:** obrigatória antes de mergear Fatia 2 (ciclo) e Fatia 3 (contabilidade).
- **Opção (b)** (evento contábil por liquidação) fica registrada como evolução, não implementada.
