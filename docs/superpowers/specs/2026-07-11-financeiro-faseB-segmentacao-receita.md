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

## B2 — eventos (IMPLEMENTADO, Sessão 65; design com Fable 5)

**Eventos (mod_contabil.py):** `recebimento_venda` (1.1.01×2.1.06); faturamento **segmentado** →
Mercadoria (4.1.01, NF-e) e Serviço (4.2.01, NFS-e), cada uma com split adiantado/a-receber via
`faturar_segmento()` (saca `min(pool, segmento)` do Adiantamento → 2.1.06 ≥ 0, Σ receitas = Val_Cont);
`faturamento_cmv` (5.1.01×2.1.04.06 = **CFO**, 1×/projeto, ref `cmv:<proj>`); `pagamento_fabrica`
(2.1.04.06×1.1.01). Congelamento da segmentação na assinatura (`_congelar_segmentacao_no_projeto`, A6).

**Constituição COMPLETA no fechamento** (`constituir_provisoes_fechamento`, valores do motor
`_negociacao_breakdown`): montagem/garantia/assist + frete fáb/local/insumos/com med/proj/retenção →
Despesa `5.6.01-09` × Provisão `2.1.04.02-12`. Custo Fábrica NÃO entra aqui (é CMV=CFO). **Custo
financeiro** (Cust_Fin = Val_Cont − VAVO) = despesa DIRETA no contrato (`5.5.03 × 2.1.05`).

**Impostos = PROVISÃO diferida** (Tipo D): contas novas `1.1.05 Impostos a Apropriar` (ativo diferido) +
`2.1.04.13 Provisão de Impostos`. CONTRATO: `1.1.05 × 2.1.04.13` (passivo nasce, DRE intocada). EMISSÃO
(proporcional Merc/Serv — NF-e e NFS-e são emissões separadas, mesma data): `4.3.01 × 1.1.05` (dedução
entra na DRE, baixa o ativo) + `2.1.04.13 × 2.1.03` (obrigação fiscal real). `efetivar_impostos_segmento`.

**Face fiscal (B2.3):** `mod_nfe.rescalar_itens_para_total` reescala os itens da NF-e p/ Σ = parcela
Mercadoria (fecha ao centavo); NFS-e = parcela Serviço. Markup vira output/fallback. ICMS/alíquotas → frente
Fiscal (contador). `_valores_segmentados_do_projeto` = fonte única (face fiscal + wiring contábil).

**Prova de não-duplicação (validada na simulação):** 5.1.01 = único débito em 5.1 → CFO 1× no resultado;
provisões são passivo fora do DRE; baixas passivo×ativo não tocam resultado; Σ receitas = Val_Cont. O razão
reconcilia com o motor: **lucro líquido = Val_Liq − Cust_Var** (margens diferem só pela base Val_Cont ×
Val_Liq = Cust_Fin).

**Bug corrigido (B2.2):** `margem_projeto` expõe `custo_servico` (5.2 + provisões 5.6.x) → destrava
`reconciliar(proporcional_custo_direto)` (era KeyError).

`[CONFIRMAR CONTADOR]`: receita no doc fiscal · adiantamento passivo (Simples) · timing dos impostos-provisão
· custo financeiro direto · estorno de cancelamento fiscal (backlog FASE D).

## C — painel de Provisões por tipo A/B/C/D (IMPLEMENTADO, Sessão 66)

**Backend** (`mod_contabil.py`): `_PROV_PAINEL_TIPO` (`2.1.04.x → A/B/C/D`, data-driven; conta nova sem tipo
→ "O" Outros). `contas_provisao_do_plano` devolve `tipo`; `dashboard_financeiro` ganha
`provisoes_por_tipo` (grupos A→B→C→D→O com `rotulo`/`itens`/`subtotal`; mantém `provisoes` + total p/
compat). Σ subtotais = `total_provisoes_abertas`.
Mapeamento: **A** comissões/pessoas (.10/.11/.12) · **B** custos futuros (.02/.03/.05) · **C** aquisição/
fábrica (.06/.07/.08/.09) · **D** fiscal (.13).

**Frontend** (`static/index.html`, `finDashboardCarregar`): um card por grupo (cabeçalho `tipo · rótulo` +
subtotal; linhas por dentro), tokens/`.surface-2`, 2 temas. Fallback à lista plana se o backend não
devolve `provisoes_por_tipo` (evita painel vazio antes do restart — C1 é Python).

## D — reconciliação (PENDENTE)

Por provisão/projeto: **Provisionado × Efetivado × Saldo × Destino**. O custo real (NF fábrica + outros
fornecedores + insumos) entra como **Efetivado** (manual); a diferença provisionado−real (ex.: CFO−real)
vai ao resultado (sobra→receita / falta→despesa). + eventos de **estorno** de cancelamento fiscal (backlog
da B2).
