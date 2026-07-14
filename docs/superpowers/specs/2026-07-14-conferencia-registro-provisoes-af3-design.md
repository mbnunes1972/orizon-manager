# Conferência, Registro Único de Provisões e AF3 — Design

**Data:** 2026-07-14 · **Branch:** `feat/desmembramento-fatia2-ciclo` · **Status:** desenho FECHADO (validação da
contabilização da substituição pendente — candidata a Fable 5 na F2).

Extensão de `2026-07-13-resultado-venda-aprovacoes-financeiras-design.md` (Resultado da Venda + AF) e da FASE D2
(`2026-07-12-fase-d2-*`). Surgiu do teste manual da AF1 (Sessão de 2026-07-14): as provisões novas não apareciam
para ajuste, as duas telas divergiam em ordem/cobertura, e a semântica de reconciliação estava sendo aplicada no
estágio errado.

---

## 0. Invariante mestre (reafirmada)

**Nada toca a DRE antes da NF-e real.** Todo ajuste de AF, Conferência, troca de ramo e devolução é
**ativo diferido × provisão** (ou ativo × ativo / passivo × passivo). A **Receita de Conferência** (economia por
substituição) **não** é exceção: fica diferida num ativo até a NF-e, quando é reconhecida — igual à receita da
venda (padrão FASE D2 `2.1.06`/`1.1.02`).

---

## 1. Registro único ordenado de rubricas — fonte única das duas telas

Hoje há três listas divergentes: `_PROV_RUBRICAS` (modal, à mão), `order_by(Conta.codigo)` (reconciliação),
`_AF_ITEM_RUBRICA` (backend). **Substituir por UM registro ordenado** que o modal de Provisões E a reconciliação
percorrem **na mesma ordem** — ordem explícita do registro, NÃO pelo número da conta (o código não segue a ordem
semântica). Não renumerar contas.

Cada entrada: `(ordem, grupo, código, chave_painel, rótulo, editável_na_AF, gatilho_de_ajuste)`.

| # | Grupo | Cód | Rubrica | Chave | AF |
|---|---|---|---|---|---|
| 1 | **Custo de Fábrica** | 2.1.04.06 | Custo de Fábrica | — (CFO) | 🔒 Conferência (#13) |
| 2 | **Provisões da venda** | 2.1.04.12 | Ret. Comissão Vendas | `com_venda` | ✏️ |
| 3 | | 2.1.04.10 | Comissão Medidor | `com_med` | ✏️ |
| 4 | | 2.1.04.11 | Comissão Proj/Exec | `com_proj_exec` | ✏️ |
| 5 | | 2.1.04.20 | **Comissão Administrativa** | `com_adm` | ✏️ *(novo — §2)* |
| 6 | | 2.1.04.15 | Comissão Arquiteto | `com_arq` | ✏️ *(bug ①)* |
| 7 | | 2.1.04.16 | Programa Fidelidade | `pro_fid` | ✏️ *(bug ①)* |
| 8 | | 2.1.04.17 | Custo de Viagem | `cust_via` | ✏️ *(bug ①)* |
| 9 | | 2.1.04.18 | Brinde | `brinde` | ✏️ *(bug ①)* |
| 10 | **Operacionais** | 2.1.04.07 | Frete Fábrica | `frete_fab` | ⚙️ auto (recalc do CFO) + override por senha |
| 11 | | 2.1.04.08 | Frete Local | `frete_loc` | ✏️ |
| 12 | | 2.1.04.09 | Insumos Locais | `ins_loc` | ✏️ |
| 13 | | 2.1.04.02 | Montagem | `prov_mont` | ✏️ |
| 14 | | 2.1.04.03 | Garantia | `prov_gar` | ✏️ |
| 15 | | 2.1.04.05 | Assistência Técnica | `assist` | ✏️ |
| 16 | | 2.1.04.14 | Outros Fornecedores | `out_forn` | 🔒 Conferência (substituição) |
| 17 | **Impostos e custo fin.** | 2.1.04.13 | Impostos | `prov_imp` | ✏️ |
| 18 | | 2.1.04.19 | Custo Financeiro | `custo_financeiro` | 🔒 box do ramo + override por senha (§5) |

Fora do registro: `2.1.04.01` (Comissão genérica) e `2.1.04.04` (Devolução) — não-constituídas/saldo sempre 0.
Os cadeados (🔒/⚙️) são **provisórios**, reavaliados no teste.

**Implicação:** a reconciliação passa a exibir **as mesmas 18 linhas, na mesma ordem**, e os grupos (1–4)
substituem o agrupamento A/B/C/D atual de `_PROV_PAINEL_TIPO`.

---

## 2. Contas novas (todas `[CONFIRMAR CONTADOR]`)

| Conta | Nome | Papel |
|---|---|---|
| `2.1.04.20` | Provisão de Comissão Administrativa | passivo — `com_adm` vira provisão (paridade total) |
| `1.1.06.20` | Custos a Apropriar — Comissão Administrativa | ativo diferido espelho de `2.1.04.20` |
| `1.1.08` | **Créditos de Conferência** | ativo — economia por substituição, diferida até a NF-e |
| `2.1.08` | **Receita de Conferência a Realizar** | passivo — espelho diferido de `1.1.08` (padrão `2.1.06`) |
| `4.4.04` | **Receita de Conferência** | DRE — receita reconhecida SÓ na NF-e |

`com_adm` ganha evento `fechamento_venda_com_adm` (`1.1.06.20 × 2.1.04.20`), entra em `_PROV_FECHAMENTO`,
`_AF_ITEM_RUBRICA`, matching pleno na NF-e e reconciliação — igual às demais.

---

## 3. Modelo de revisão: AF1/AF2/AF3 ↔ Rev1/Rev2/Rev3

Três momentos de aprovação/revisão, cada um dono de UMA coluna de revisão, **reeditável até a aprovação daquele
estágio** (o backend já deleta+regrava a versão travada com step-up do Diretor; falta o frontend deixar reabrir a
coluna do estágio corrente em vez de auto-avançar):

| Estágio | Código da etapa | Coluna |
|---|---|---|
| **AF1** | 8 (Aprovação Financeira I) | Rev1 |
| **AF2** | 11d (Aprovação Financeira II, subfase do PE) | Rev2 |
| **AF3** | 12 (Conferência e Implantação do Pedido) | **Rev3** *(nova)* |

O **saldo a monitorar** (diferença da comparação PE) aparece na **evolução das colunas** Venda → Rev1 → Rev2 →
Rev3 → Atual. O frontend para de auto-avançar `pendingRev`; a coluna editável é a do **estágio do ciclo corrente**.

**Referência — ciclo numerado (os códigos têm buracos: etapas 5/6 eliminadas; NÃO renumerar — são identificadores
estáveis no banco/endpoints/gating):**

| Ordem | Cód | Etapa | AF |
|---|---|---|---|
| 1–5 | 1,2,3,4,7 | Cadastro · Projeto · Briefing · Orçamento · Contrato | |
| 6 | **8** | Aprovação Financeira I | **AF1 · Rev1** |
| 7–8 | 9,10 | Solicitação de medição · Medição | |
| 9 | 11 | Projeto Executivo (11a–11e; **11d** = Aprov. Fin. II) | **AF2 · Rev2** (11d) |
| 10 | **12** | Conferência e Implantação do Pedido | **AF3 · Rev3** |
| 11–12 | 13,14 | Produção · Entrega no depósito | |
| 13 | **15** | Emissão da NF-e do cliente | *(reconhece a DRE)* |
| 14–18 | 16,17,18,19,20 | Entrega · Montagem · Assistência · Vistoria · Aprovação final | |
| 19 | **21** | Conciliação Final | *(reabre painel · encerra)* |

> **Posição × código interno:** a UI não mostra número — só o nome da etapa. A coluna "Cód" é o **identificador
> interno** (estável no banco/endpoints/gating), com buraco em 5/6 (removidas), então de Contrato em diante o
> código fica +2 vs a posição — ex.: Conferência é a **10ª** etapa, código interno **12**. Ao comunicar, usar
> posição+nome; o código aparece só onde a implementação o exige.

---

## 4. Conferência (etapa 12 = AF3)

A própria loja faz o **Projeto Executivo (PE)**; quase sempre há diferença de custo de fábrica.

**4.1 Comparação PE — tela ENXUTA (na subetapa 11c "Revisão de PE").** `montar_comparacao_pe`: CFO da venda ×
CFO do PE por ambiente (`extrair_cfo_pe` = Σ `order_total`). A tela mostra **só**: **valor do projeto** (Val_Cont),
**Δ de custo de fábrica por ambiente com diferença %**, e a **média final** (variação global = Δ total / CFO venda
total). **NÃO** mostra as provisões (o bloco de reconciliação estimada foi removido daqui — confuso nesta etapa; a
evolução de provisões/margem vive no painel de Provisões / colunas Rev). XMLs de teste `_PE` (CFO alterado por
ambiente) em `XML/*_PE.xml`. ✅ implementado (`peComparacaoRender`, 2026-07-14).

**4.1.1 Upload de PE — multi-arquivo + ciclo de trava.** "Carregar PE" abre seletor **`multiple accept=".xml"`**;
cada XML é **casado ao ambiente pelo nome** e alimenta `arquivo_pe` (store da comparação/Conferência). Os PEs ficam
**acessíveis para ver/substituir/remover** enquanto a **11e (Aprovação do PE pelo cliente = assinatura)** não é
concluída; **após a 11e travam**, e alterar exige **step-up de Diretor** (`perfis.pode(nivel,"autorizar")`). _(A
seleção múltipla+casamento pode ir antes; a trava da 11e fica na F2.)_

**4.1.2 Gate do PE (pré-req, já corrigido 2026-07-14).** `_podePE` no frontend comparava o nível contra nomes de
função obsoletos (`diretor`/`gerente_vendas`/…) → botões de PE ocultos para todos. Corrigido p/ os níveis-base
(`executar_pe`: master/gerencial/operador; `revisar_pe`: master/gerencial), espelhando `perfis.py`. Bug latente na
`main`. **Follow-up robusto:** backend enviar as capacidades resolvidas na sessão e o front só ler (mata a classe de
desync); auditar outros gates com hardcode de função.

**4.1.3 Desmembramento = "Fase" (terminologia).** O projeto se desmembra em **Fases** (não "parcela" — colidiria com
as etapas do ciclo e com parcela de pagamento). Só os **rótulos visíveis** mudam; endpoints/tabelas/identificadores
(`/parcelas`, `ParcelaProjeto`, `.desm-parc`) seguem internos, comentados no código. ✅ rótulos aplicados (2026-07-14).

**4.2 Frete Fábrica — auto-recalcula + override.** Ao conferir o novo CFO, o frete fábrica (`% × CFO`,
`mod_provisoes.py:169`) **recalcula automaticamente** (o caso da grande maioria). Um **override manual por senha**
cobre negociação específica (volumes maiores de entrega) — mesmo gate do custo financeiro (§5).

**4.3 Substituição de custo → Créditos de Conferência (a economia).** A redução da fábrica **não** é reclassificação
1:1. Ex.: saem R$10.000 da fábrica, entram **R$8.000** em Outros Fornecedores, e os **R$2.000** de economia ficam
apartados como **ativo diferido** até a NF-e:

- **Na Conferência** (proposta a validar com Fable 5 — mantém a invariante, DRE intacta):
  - passivo: `DR 2.1.04.06 10.000  ×  CR 2.1.04.14 8.000  +  CR 2.1.08 (Rec. Conf. a Realizar) 2.000`
  - ativo:   `DR 1.1.06.14 8.000  +  DR 1.1.08 (Créditos de Conferência) 2.000  ×  CR 1.1.06.06 10.000`
  - Resultado: obrigação real vira 8k (Outros Forn); a economia de 2k fica diferida (ativo `1.1.08` ↔ passivo
    `2.1.08`), espelhando o padrão da receita da venda (`1.1.02` ↔ `2.1.06`).
- **Na NF-e (entrega):** `DR 2.1.08 × CR 4.4.04 Receita de Conferência` (reconhece na DRE) e baixa do ativo
  `1.1.08` no recebimento — igual ao `recebimento_venda` que abate `1.1.02`.

> **Ponto aberto p/ Fable 5 (F2):** fechar o par exato da baixa de `1.1.08` na NF-e/recebimento e conferir o
> Balanço centavo a centavo em cada etapa. O requisito é fixo (economia diferida → receita só na NF-e); o
> lançamento exato é o que se valida.

**4.4 Outros custos que surgem.** Custos novos identificados na Conferência (não previstos na venda) são lançados
como provisão na rubrica cabível do registro (§1) via ajuste da Rev3 — ativo diferido × provisão, reconhecidos na
NF-e como os demais.

---

## 5. Custo Financeiro — ramo + override manual (duplo gate)

Padrão: valor vem do motor, ajusta-se pelo **box do ramo** (loja/antecipação/financeira), que recalcula os juros
(`trocar_ramo_custo_financeiro`). **Override manual** do valor é permitido porque tabelas financeiras mudam e os
juros flutuam — **liberado por senha de Direção + Admin/Fin (duplo step-up)**. O mesmo gate libera o override do
frete fábrica (§4.2). Uso normal é não mexer; o override é exceção auditável (origem própria no razão).

---

## 6. Conciliação Final (etapa 21) reabre o painel de provisões

Antes de encerrar, a Conciliação Final **reabre o painel de provisões** para uma última rodada de ajustes finos
(Viagem, Insumos Locais, Assistências, etc.) — ajuste ativo×provisão, e então `conciliar_final` resolve o saldo
remanescente das rubricas (sobra→`4.4.02`/falta→`5.6.10`) e leva o projeto a **Concluído**.

---

## 7. Bug ② — "efetivado" não pode contar ajuste de AF

Na `reconciliacao` (`mod_contabil.py:938`), débitos de origem `ajuste_provisao_af` (redução de AF) são contados
como **efetivado** (custo real). Corrigir: **excluir `ajuste_provisao_af` de `efetivado`** e **descontá-lo de
`provisionado`** — revisão de AF só move o `provisionado`, nunca o `efetivado`/`saldo`. `efetivar`/`resolver`
ficam indisponíveis antes do estágio pós-NF-e; renomear a coluna "Efetivado" → "Custo Real (NF-e)".

---

## 8. Plano por fases (TDD; parar p/ conferência dos números; Vera antes de fechar)

- **F0 — Registro único.** Criar o registro ordenado; apontar modal + reconciliação para ele. Resolve ordem +
  cobertura + **bug ①** (inclui `com_arq`/`pro_fid`/`cust_via`/`brinde`/`custo_financeiro` nas telas).
- **F1 — `com_adm` provisão + bug ②.** Conta `2.1.04.20`/`1.1.06.20` + evento + reconhecimento; corrigir
  `efetivado` na reconciliação.
- **F2 — AF3/Rev3 + Conferência.** Rev3 amarrada à etapa 12; frete auto-recalcula; **substituição → Créditos de
  Conferência → Receita de Conferência na NF-e** (contas `1.1.08`/`2.1.08`/`4.4.04`; contabilização validada com
  Fable 5). Frontend: coluna editável = estágio corrente.
- **F3 — Override manual** (custo financeiro + frete fábrica) atrás do duplo gate Direção + Admin/Fin.
- **F4 — Conciliação Final reabre o painel** de provisões p/ ajuste fino antes de encerrar.

## 9. Pontos p/ contador / Fable 5

- `[CONFIRMAR CONTADOR]`: códigos/nomes de `2.1.04.20`, `1.1.06.20`, `1.1.08`, `2.1.08`, `4.4.04`; natureza da
  Receita de Conferência (operacional × outras receitas).
- `[FABLE 5]`: contabilização completa da substituição (§4.3), incluindo a baixa de `1.1.08` na NF-e e a prova de
  Balanço em cada etapa.
