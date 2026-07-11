# FASE B — Infra contábil: segmentação de receita + eventos de dupla-partida

**Data:** 2026-07-11 · **Frente:** infraestrutura contábil ponta a ponta (contas + eventos + painéis)
**Status:** B1 (segmentação) implementada e mergeada; B2 (eventos) em design; C/D pendentes.

## Contexto e decisões do usuário

Montar TODA a infra contábil para o "Projeto Simulação" popular DRE, Balanço, Provisões e
Reconciliação **pelo fluxo real de fechamento** (não script sintético). Fases:

- **A — caixinhas** (feito): `2.1.06 Adiantamento de Clientes` (passivo), `2.1.04.06 Provisão de Custo de
  Fábrica` + provisões das demais rubricas monitoradas. Backfill idempotente.
- **B1 — segmentação de receita** (feito, esta spec).
- **B2 — eventos** de dupla-partida (design com Fable 5).
- **C — painel de Provisões** por tipo A/B/C/D. **D — painel de Reconciliação** (Provisionado × Efetivado
  × Saldo × Destino).

### Decisão-chave (receita segmentada Mercadoria × Serviço)

NÃO desligar a NFS-e. A receita do projeto é **segmentada**: `Val_Cont = Mercadoria + Serviço`, por um
percentual configurável (default **65/35**, soma obrigatória 100).
- **Mercadoria** = `pct_mercadoria%·Val_Cont` → NF-e de produto → conta **4.1.01** (Receitas com Vendas).
- **Serviço** = `pct_servico%·Val_Cont` → NFS-e → conta **4.2.01** (Receita de Serviços).
- Σ = Val_Cont → **sem receita dobrada**. A montagem (embutida no Val_Cont) é a parcela de Serviço.
- Assistência avulsa (sem projeto) segue no evento próprio (4.1.02), fora dessa regra.
- **Prepara a distribuidora** (sem criar a entidade agora): Mercadoria = receita da distribuidora, Serviço
  = receita da loja. Modelado como **dado do projeto**.
- **Default por loja** (Admin › Dados da Loja): `Loja.pct_mercadoria`/`pct_servico`, semeados 65/35 na
  implantação. **Override por venda**: em `Projeto.parametros_json`, editável **só pelo Diretor**
  (gate `aprovar_financeiro`, mecanismo atual do `perfis.py`; NÃO amarrar à refatoração de perfis).
- **Fiscal (frente à parte, confirmar com contador):** base de cada documento segue a proporção (ICMS na
  mercadoria, ISS no serviço). A segmentação é a fonte; regra tributária definitiva não trava agora.

### CMV Fábrica = `orc.cfo`

CMV (custo do produto no resultado) = **CFO congelado na assinatura** (`orc.cfo`), casando com Marg_Cont da
modal e com a Provisão Custo Fábrica. O custo real (NF da fábrica + outros fornecedores + insumos) entra
como o **Efetivado** da reconciliação (FASE D); a diferença **CFO − real** vai ao resultado (sobra→receita
/ falta→despesa). A NF da fábrica NÃO é o CMV inicial.

## B1 — implementação

**Funções puras** (`mod_orcamento_params.py`):
- `SEGMENTACAO_DEFAULT = {"pct_mercadoria": 65.0, "pct_servico": 35.0}`
- `segmentar(val_cont, pct_mercadoria) → (merc, serv)` — serviço = **resto** (Val_Cont − merc) p/ fechar
  exatamente no Val_Cont (sem centavo perdido).
- `validar_segmentacao(pm, ps)` — soma 100 (tol 0.01) + faixa 0..100 (ValueError).
- `resolver_segmentacao(pm, ps)` — NULL/ausente → default 65/35.
- `segmentacao_efetiva(loja_seg, projeto_params)` — override do projeto vence o default da loja.

**Modelo/migração** (`database.py`): `Loja.pct_mercadoria`/`pct_servico` (Float, default 65/35). Migração
idempotente: `ALTER TABLE lojas ADD COLUMN ...` + `UPDATE ... WHERE ... IS NULL` (seed 65/35 nas existentes).

**Endpoints** (`main.py`):
- `PATCH /api/admin/lojas/<id>`: aceita `pct_*` (gate `editar_dados_loja`, valida soma=100). `_loja_dict`
  expõe `pct_*` (fallback 65/35).
- `POST /api/projetos/<nome>/parametros`: `pct_*` override (gate `aprovar_financeiro`, valida). Como
  `merge_parametros` ignora chaves fora do `PARAMETROS_DEFAULT`, `pct_*` é tratado à parte — e **preservado**
  quando um salvamento normal não os envia (`elif _k in atual`).

**Frontend** (`static/index.html`):
- Admin › Dados da Loja: 2 campos % com checagem soma=100.
- Modal de Parâmetros: segmentação **sob o mesmo cadeado 🔒 da margem real** (`_impostosLiberados`,
  liberação por senha via `modal-liberar-impostos`). Sempre visível; campos revelados só após a senha;
  **auto-salva ao alterar** (debounce, chamada isolada — 403 não quebra o save dos outros parâmetros); os 2
  campos espelham-se p/ somar 100.

**Testes:** `test_segmentacao.py`, `test_loja_segmentacao.py`, `test_endpoints_segmentacao.py` (17 no total),
incl. "override sobrevive a salvamento de outros parâmetros".

## B2 — eventos (a implementar; design com Fable 5)

Eventos NOVOS (nenhum alterado): `recebimento_venda` (1.1.01×2.1.06); no faturamento, **receita segmentada**
→ Mercadoria (4.1.01, NF-e) e Serviço (4.2.01, NFS-e), cada uma com split adiantado/a-receber contra o
Adiantamento; `faturamento_cmv` (5.1.01×2.1.04.06 = CFO); `pagamento_fabrica` (2.1.04.06×1.1.01).
Prova de não-duplicação (5.1.01 = único débito em 5.1 → CFO 1× no resultado; provisão é passivo fora do DRE;
baixa passivo×ativo não toca resultado). Timing marcado `[CONFIRMAR COM CONTADOR]`.
Corrigir junto: `reconciliar(metodologia="proporcional_custo_direto")` → KeyError `custo_servico`
(`mod_contabil.py`) — alinhar `custo_servico` à proporção da segmentação, não a `_peso` avulso.
