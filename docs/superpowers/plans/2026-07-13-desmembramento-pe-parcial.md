# Briefing — Desmembramento parcial na Revisão de PE

> Texto pra passar pro Claude Code escrever o spec (`docs/superpowers/specs/`) e tentar a
> implementação. Consolida duas rodadas de avaliação de complexidade feitas pelo Fable 5 em
> 2026-07-13 (a primeira, sobre uma versão recursiva de fases, foi descartada; esta é a versão
> refinada que ficou). **Não implementar direto** — escrever o spec primeiro, resolvendo as
> decisões em aberto na seção 4 antes de codar.

## 1. Problema de negócio

Na execução da obra, o cliente às vezes quer prosseguir só com parte dos ambientes (ex.: 2 de 4) e
deixar os outros pra depois. A partir desse ponto, a Aprovação Financeira precisa acontecer em
etapas manuais — por grupo de ambientes ("parcela"), não mais tudo-ou-nada por projeto. As etapas
seguintes do ciclo (Implantação, Produção, Entrega, NF-e/NFS-e) também passam a rodar por parcela,
em liquidações sucessivas.

## 2. Mecânica proposta

1. Na subfase **Revisão de PE** (etapa 11c), uma escolha binária: **projeto completo** ou
   **desmembrado**. Se desmembrado, abre um modal pra selecionar quais ambientes formam a primeira
   parcela (os que seguem agora) — os demais ficam retidos, aguardando uma parcela futura.
2. Cada parcela desmembrada passa pelas etapas seguintes do ciclo (Aprovação Financeira,
   Implantação, Produção, Entrega, NF-e/NFS-e) **de forma independente** das outras parcelas do
   mesmo projeto.
3. **Liquidações sucessivas**: cada parcela é aprovada/liquidada financeiramente na sua vez, não
   simultaneamente. As provisões são atualizadas conforme cada parcela é liquidada (via nova carga
   de XML de PE daquela parcela — ver seção 4 sobre onde isso entra na contabilidade).
4. **Lock pós-Implantação**: assim que um ambiente entra em "Implantação do Pedido", fica bloqueado
   — sem mais alterações nem comparações. Ou seja, não existe "redesmembrar" um ambiente já
   implantado.
5. **Arquivos por ambiente**: cada projeto ganha uma subpasta por ambiente, com 4 arquivos: Promob
   de venda, XML de venda, Promob do PE, XML do PE (2 gerações × 2 formatos). O XML de PE fica
   **fora do pool de XMLs do orçamento** — é documento de comparação/liquidação, não alimenta o
   motor de cálculo nem o orçamento assinado (ver decisão #2 na seção 4).

## 3. Telas e botões necessários

### Subfase Revisão de PE (11c)
- **Seletor "Projeto completo" × "Desmembrar projeto"** — decisão tomada uma vez nesta subfase.
- Se desmembrar: **modal de seleção de ambientes** — quais formam a parcela atual (seguem) vs. quais
  ficam retidos (aguardam parcela futura).
- **Botão "Carregar XMLs atualizados"** — upload do XML de PE por ambiente (fora do pool, ver
  seção 4). Aceita também o arquivo Promob nativo correspondente (guardado como documento, não
  parseado).
- **Botão "Comparar valores dos ambientes"** — abre a tabela de comparação: ambiente | valor de
  venda | valor atualizado (PE) | diferença. Ambientes sem XML de PE carregado ainda aparecem com
  "valor atualizado" = zero.

### Tela/modal de Aprovação Financeira (11d — Provisões Rev1/Rev2)
- **O mesmo botão "Comparar valores dos ambientes"** aparece aqui também, abrindo a mesma tabela
  (referência lado a lado com a decisão de Rev1/Rev2 da parcela em aprovação).
- Quando o projeto está desmembrado, a aprovação passa a ser **por parcela**: a tela precisa deixar
  claro qual parcela está sendo aprovada e o status das demais (aguardando / já liquidada).

### Etapas 12–16 (Implantação, Produção, Entrega, NF-e/NFS-e)
- Cada card de etapa precisa de **sub-estado por parcela** (não é mais um status único por projeto):
  lista de parcelas com seu progresso individual dentro daquela etapa.
- Indicador visual de **lock** nos ambientes que já entraram em Implantação (bloqueados pra edição/
  comparação).
- Etapa só fecha como "concluída" quando **todas as parcelas** concluíram.

## 4. Decisões arquiteturais que o spec precisa fechar antes de codar

Baseado na leitura real do código (`mod_ciclo.py`, `mod_provisoes.py`, `mod_contabil.py`,
`mod_negociacao.py`, `database.py`) feita pelo Fable nas duas rodadas de avaliação:

1. **Unidade da aprovação parcial = "parcela"** (grupo de ambientes), não ambiente-a-ambiente puro.
   Recomendado: tabela nova pra parcela (membership de ambientes, status, fração do Val_Cont
   congelada na criação da parcela).
2. **Onde vive o XML de PE**: fora do pool (`PoolAmbiente`/`OrcamentoAmbiente`), em tabela/local
   próprio, sem vínculo com o orçamento. Isso é o que permite a feature **não esbarrar** na trava
   `_contrato_assinado` que hoje bloqueia novo upload no pool pós-contrato (trava correta, não deve
   ser relaxada — `main.py:3944-3949`).
3. **Semântica contábil da atualização por parcela** — decisão de negócio, não só de código:
   - **(a) barata**: valor atualizado do PE é só *snapshot*/comparação; a divergência real×planejado
     é absorvida pelo mecanismo que já existe (`resolver_saldo_provisao` + Conciliação Final, etapa
     21) no fechamento do projeto.
   - **(b) mais fiel ao passivo**: cada liquidação parcial gera um evento contábil novo de ajuste de
     provisão (delta-constituição ou reversão parcial), no padrão append-only/idempotente que o
     módulo contábil já usa (`reclassificar_provisao` como referência).
   - Recomendação do Fable: começar por (a), que é mais barato e já tem rede de segurança pronta;
     migrar pra (b) só se o negócio realmente precisar de margem fechada por parcela antes da
     conciliação final do projeto.
4. **Qual valor de venda a tabela de comparação usa** — VBVA bruto, VAVA com desconto, ou o valor já
   rateado com financeiro (o mesmo que vai pro contrato, via `_ambientes_valor_para_contrato`). Sem
   fixar isso, a tabela "não bate" com o que o cliente vê no contrato.
5. **Fração da parcela e regra de arredondamento**: cada parcela nasce com uma fração do `Val_Cont`
   congelada; a **última parcela leva o resto** (evita sobra de centavos). Isso é a base do
   faturamento e do matching de NF-e parciais.
6. **Refs idempotentes ganham dimensão "parcela"**: hoje `reconhecer_despesas_nfe` usa
   `ref_base="match:"+projeto_nome` (fixo por projeto — uma 2ª NF-e faria no-op). Precisa virar
   `match:<projeto>:<parcela>` (e equivalente nas outras refs de evento), senão liquidações
   sucessivas da mesma rubrica se anulam silenciosamente.
7. **Status agregado das etapas 12-16**: como cada uma agrega N parcelas em progresso, decidir se
   cada parcela vira um card próprio em `CicloLogistico` (a tabela já aceita N linhas por projeto,
   segundo a leitura do Fable) e como isso aparece na tela do ciclo.
8. **Projetos legados / não desmembrados continuam no fluxo atual** — desmembrar é opt-in na 11c,
   não migra nada por padrão.

## 5. Fatiamento recomendado (cada fatia é entregável e testável sozinha)

1. **Comparação + storage de PE** — telas, botões, tabela de comparação, upload fora do pool. Não
   toca contabilidade nem ciclo. Resolve a dor visível do usuário primeiro.
2. **Desmembramento operacional das etapas 12-16** — sub-estado por parcela, gating, UI, lock
   pós-Implantação.
3. **Liquidação financeira parcial** — faturamento/matching/impostos por fração de parcela + a
   decisão contábil da seção 4.3.

**Chamar a Vera (agente de QA) antes de mergear as fatias 2 e 3** — são as que tocam ciclo e
contabilidade, áreas sensíveis do projeto (ver CLAUDE.md).

## 6. Nota sobre as estimativas de esforço

As rodadas de avaliação do Fable deram números em "dias-pessoa" (~15-24 dias pra essa versão
refinada, contra ~25-40 da versão recursiva original) — mas são uma estimativa **qualitativa de
tamanho relativo/risco**, não calibrada à velocidade real deste projeto (que roda em sessões de
Claude Code com TDD, não em dias de um dev humano solo). O que vale confiar é a **ordem relativa**
entre as frentes (comparação é bem mais simples que liquidação parcial) e o **porquê** de cada uma
ser cara ou barata — isso está fundamentado em código real que o Fable leu, não em achismo.
