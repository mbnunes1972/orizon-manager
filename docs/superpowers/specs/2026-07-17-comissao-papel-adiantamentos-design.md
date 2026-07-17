# Comissão por Papel + Adiantamentos + Comissão Fixa — Design

**Data:** 2026-07-17
**Contexto:** Extensão da Folha (após Fase 3, que fez o motor calcular pela Função). Cobre três frentes definidas com o usuário, sequenciadas **A → B → C**.

## Problema

A Fase 3 deixou o motor calculando pela Função (fixa + benefícios + comissão do Consultor + base de comissão editável). Faltam:
- **A.** A comissão dos **papéis operacionais** (PE / Medição / Montagem / Assistência) ser **preparada automaticamente** quando cada etapa do ciclo é concluída, indo para a folha do mês de conclusão.
- **B.** **Adiantamentos e empréstimos** ao funcionário (incl. a regra oficial de 40% do salário fixo), com **saldo de débito** e abatimento **editável** no líquido.
- **C.** Uma **comissão fixa** por função, parcela mensal sobre a qual **não incidem encargos** (férias/13º/INSS) — instrumento de planejamento.

## Decisões (do brainstorming)

1. **Base da comissão de papel** = Σ `order_total` dos **ambientes atribuídos** àquele executor naquele papel (Mapa de Atribuições). `pool_ambiente_id` NULL = projeto inteiro.
2. **Gatilho e competência:** comissão preparada na **conclusão de cada etapa**, na folha do **mês de `concluido_em`** — mesmo que o ciclo do projeto não tenha terminado. Ex.: mediu em 05/jul → comissão em julho (recebida início de agosto).
3. **Ajuste manual:** todo valor de comissão é **editável** na folha (a base já é editável desde a Fase 3).
4. **Contábil:** modelo **simples** (débito despesa 5.3.x × crédito Caixa/Banco na paga). O **provisionamento** do balanço já é feito pelo painel de **Provisões** (médias previstas do modelo de negócio); a **reconciliação** ajusta a diferença entre previsto e realizado. Contas exatas / encargos → **com o contador**.
5. **Sequência:** **A primeiro** (comissão por papel), depois **B** (adiantamentos), depois **C** (comissão fixa). C pode ser antecipada se conveniente (é pequena e independente).

---

## Frente A — Comissão por Papel (detalhada)

### Fontes de dados (já existem)
- **`CicloEtapa`**: `status`, `concluido_em` (→ competência), `funcao_responsavel_id` (a **Função** que executa a fase, do Cronograma Padrão v12 — traz o % de comissão), `responsavel_funcionario_id` (**quem** executou).
- **`atribuicoes_ambiente`** (Mapa): `papel` → executor → `pool_ambiente_id`. Base por ambiente.
- **`PoolAmbiente.order_total`**: valor de venda do ambiente. **`budget_total`**: custo (não usado aqui).
- **`mod_escopo`**: `PAPEIS`, `resolver_responsavel`, mapeamento etapa→papel.
- Ponto de gatilho central: **`_set_etapa_status(db, nome_safe, codigo, "concluido", ...)`** em `main.py` (todos os caminhos de conclusão passam por status="concluido" + `concluido_em`).

### Novo modelo: `comissao_folha` (itens de comissão)
Um funcionário pode ter **várias** comissões no mês (várias etapas/projetos). A folha atual só tem uma `base_comissao`/`parte_variavel` — insuficiente. Introduz-se uma tabela de itens:

```
comissao_folha
  id                PK
  loja_id           FK lojas
  funcionario_id    FK funcionarios
  competencia       'AAAA-MM'            # = mês de concluido_em da etapa
  origem            'papel' | 'venda'    # venda = comissão do Consultor (unifica)
  papel             projeto_executivo|medicao|montagem|assistencia|venda
  projeto_nome      nome_safe            # rastreabilidade
  etapa_codigo      Text, nullable       # etapa que disparou (papel) ; NULL p/ venda
  base              Float                # Σ order_total dos ambientes atribuídos (ou vendas líq. p/ venda)
  base_ajustada     Float, nullable      # override manual da base (edita na folha)
  pct               Float                # % da Função (faixa/flat) aplicado
  valor             Float                # base_efetiva × pct/100 (parte_variavel do item)
  status            'previsto'|'confirmado'|'cancelado'  # previsto ao concluir etapa; confirmado ao gerar/pagar folha
  ref_etapa         Text                 # idempotência: '<projeto>:<etapa_codigo>:<funcionario>'
  criado_em         DateTime
```

- **Migração dupla** (SQLite `_add_cols`/create + Postgres). Nova tabela → `Base.metadata.create_all` cobre; garantir que roda em ambos.
- **`parte_variavel`** da folha passa a ser **Σ `valor`** dos itens `comissao_folha` (status ≠ cancelado) daquele funcionário/competência. A coluna `base_comissao` da Fase 3 permanece para o caso **Consultor sem itens** (retrocompat), mas o caminho novo soma itens.

### Fluxo
1. **Conclusão de etapa** (`_set_etapa_status → "concluido"`): `mod_comissao.preparar_comissao_etapa(db, projeto, etapa)`:
   - Resolve **papel** (etapa→papel via `mod_escopo`), **executor** (`responsavel_funcionario_id`) e **Função** (`funcao_responsavel_id`).
   - Se a Função não tem comissão configurada, ou não há executor funcionário (terceiro é tratado à parte, fora de escopo agora), **não** cria item.
   - **Base** = Σ `order_total` dos ambientes atribuídos ao executor nesse papel (Mapa); se atribuição = projeto inteiro (NULL), usa o `order_total` do projeto.
   - **pct** = `_resolver_pct_funcao`/faixas da Função (reusa Fase 3).
   - Cria/atualiza `comissao_folha` **idempotente por `ref_etapa`**, `competencia` = mês de `concluido_em`, `status='previsto'`.
2. **Gerar folha do mês** (`gerar_folha`): passa a somar os itens `comissao_folha` da competência em `parte_variavel` (além da comissão de venda do Consultor, que também será um item `origem='venda'`). Marca itens como `confirmado` ao pagar.
3. **Editar** um item (base_ajustada) na folha → recalcula `valor` e a `parte_variavel`/total da folha. Endpoint `PATCH /api/comissao/<id>` (ou estende o PATCH de folha).
4. **Pagar** folha: `parte_variavel` (Σ itens) → 5.3.01 como hoje; sem mudança contábil estrutural (simples).

### Reversão
Se uma etapa concluída é **reaberta** (`concluido_em = None`, visto em `main.py:5766`), o item `comissao_folha` correspondente (mesmo `ref_etapa`) vira `status='cancelado'` se a folha ainda não foi paga.

### Testes A (TDD)
- `preparar_comissao_etapa` cria item com base = Σ order_total dos ambientes atribuídos, pct da Função, competência = mês de conclusão; idempotente por ref_etapa.
- Executor sem Função com comissão → nenhum item.
- Atribuição "projeto inteiro" → base = order_total do projeto.
- `gerar_folha` soma itens na parte_variavel; consultor vira item origem='venda'.
- Reabertura de etapa cancela item (folha não paga); folha paga não é afetada.
- Editar base_ajustada recalcula valor/total.

---

## Frente B — Adiantamentos / Empréstimos + Saldo de Débito (esboço)

### Modelo
```
adiantamento_funcionario
  id, loja_id, funcionario_id
  tipo            'adiantamento' | 'emprestimo' | 'oficial'
  competencia     'AAAA-MM'         # mês em que foi concedido
  valor           Float
  abater          Bool (editável)   # se abate no líquido do mês seguinte
  competencia_abate 'AAAA-MM', nullable
  quitado         Bool
  observacao      Text
```
- **Saldo de débito** do funcionário = Σ concedido − Σ quitado/abatido.
- **Adiantamento Oficial:** config da loja `folha.adiantamento_oficial_ativo` + `folha.adiantamento_oficial_pct` (default **40%**). Aplica-se ao **salário fixo de funcionários em carteira** (`Funcao.regime_contratacao='registrado'`). Ao gerar a folha, cria automaticamente um adiantamento `tipo='oficial'` e o **abate no próprio mês** (contracheque). Loja pode ligar/desligar como padrão.
- **Abatimento editável:** cada adiantamento/empréstimo pode ou não abater o líquido do mês seguinte (`abater` togglável na folha).
- **Líquido a pagar** = total (fixa + variável + benefícios + comissão fixa) − Σ adiantamentos a abater na competência.

### UI
- Config → Folha: box **"Adiantamento Oficial"** (ativo + %).
- Folha do mês: coluna/expandir **Adiantamentos** por funcionário (adicionar, marcar abater, ver saldo de débito). Líquido a pagar exibido.

### Contábil
- Adiantamento/empréstimo concedido = ativo (direito a receber do funcionário) × Caixa; abatimento reduz o líquido pago. Contas exatas → **com o contador** (esboço: `1.1.x Adiantamentos a Funcionários`).

---

## Frente C — Comissão Fixa por Função (esboço)

- Novo campo `Funcao.comissao_fixa` (Float) — parcela **mensal fixa** paga como comissão, **isenta de encargos** (férias/13º/INSS) para fins de planejamento.
- Entra no **total** da folha (soma com fixa/variável/benefícios), mas **marcada** como base isenta de encargos (relevante quando o cálculo de encargos for implementado — fora de escopo agora).
- Configurada no modal **Config → Remunerações** (ao lado de salário fixo/benefícios).
- Contábil: despesa de comissão (5.3.x) como as demais; sem encargos associados.

### Testes C
- `funcao_aplicar/serialize` gravam/retornam `comissao_fixa`; migração dupla; `calcular_folha` soma `comissao_fixa` no total.

---

## Faseamento (planos separados)
- **Fase 4 (A):** `mod_comissao.py` + tabela `comissao_folha` + gatilho em `_set_etapa_status` + soma na `gerar_folha` + edição + reversão. Backend TDD (sensível — motor + ciclo). Frontend: itens de comissão na folha.
- **Fase 5 (B):** adiantamentos/empréstimos + Adiantamento Oficial + saldo de débito + líquido a pagar. Backend TDD + UI.
- **Fase 6 (C):** comissão fixa por função (config + motor + UI). Pequena.

## Fora de escopo / pendências
- **[Contador]** contas exatas de adiantamentos, encargos trabalhistas (o que incide sobre quê), tratamento no contracheque.
- **[Terceiros]** comissão de executor **terceiro** (não-funcionário) — o Mapa admite terceiro_id; tratamento (repasse a terceiro, não folha) fica para depois.
- **[Reconciliação]** o ajuste previsto×realizado entre Provisões e a comissão efetiva já tem lar (reconciliação); o encaixe fino é fase futura.
- **[Modelo contábil completo]** matching à la FASE D2 (constituir passivo "comissões a pagar" na conclusão, baixar na paga) — adiado; hoje usa o modelo simples + Provisões.

## Arquivos afetados (previstos)
- **A:** `database.py` (tabela `comissao_folha` + migração), `mod_comissao.py` (novo), `mod_folha.py` (soma itens em `gerar_folha`/`serialize`), `main.py` (gatilho em `_set_etapa_status`; `PATCH /api/comissao/<id>`), `static/index.html` (itens de comissão na folha), `tests/test_comissao.py`.
- **B:** `database.py` (tabela `adiantamento_funcionario` + config da loja), `mod_folha.py` (líquido a pagar), `main.py` (endpoints), `static/index.html` (box Adiantamento Oficial + coluna Adiantamentos), `tests/`.
- **C:** `database.py` (`Funcao.comissao_fixa` + migração), `mod_cadastro.py` (funcao_aplicar/serialize), `mod_folha.py` (soma no total), `static/index.html` (modal Remunerações), `tests/`.
