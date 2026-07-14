# Texto de fechamento — Fatia 2 (desmembramento operacional) — PARA APROVAÇÃO

> Branch `feat/desmembramento-fatia2-ciclo` (a partir da `main` com Fatia 1 mergeada).
> Spec: `docs/superpowers/specs/2026-07-13-desmembramento-pe-parcial-design.md` (decisões #1/#5/#7/#10/#11/#13).
> **Estado: camada de LÓGICA PURA + NÚCLEO CONTÁBIL prontos e testados (TDD). A fiação (endpoints,
> migração, ciclo por parcela, gate na tela de AF, #13) e o FRONTEND ainda faltam.** Vera ainda não
> rodou (a fatia não está usável ponta a ponta). **Não mergear.**

## Decisões revisadas com o usuário (confirmadas antes da fiação)
- **A)** "Travada" (#10) vira coluna em `ProvisaoRegistro` (`travada_em`/`aprovada_por_id`); após
  aprovar, reedição exige Diretor (step-up). *(a fiar)*
- **B)** O limite do gate (#10) mede o **custo variável total** (`cust_var`) da nova versão vs a anterior. *(a fiar)*
- **C)** #11 = `ajustar_provisao_delta` (ativo×provisão, nunca DRE; aumento constitui, redução reverte
  capada ao ativo em aberto). **✅ implementado e testado.**

## O que foi implementado de fato (contra o spec) — TUDO com TDD
- **#5 (fração da parcela) — `mod_parcelas.congelar_parcelas`.** Congela `fracao_val_cont` +
  `val_cont_congelado`; última parcela absorve o resto → invariante `Σ == round(Val_Cont,2)` exato.
- **#1 (partição) — `mod_parcelas.validar_particao_parcelas`.** Pool particionado: cada ambiente em
  exatamente uma parcela (sem sobreposição/sobra/vazia/estranho). Pré-requisito do #5.
- **#10 (gate) — `mod_parcelas.exige_aprovacao_diretor`.** Aumento de custo entre versões acima do
  limite (AF1 1% / AF2 2%) exige Diretor. *(regra pura pronta; falta plugar no endpoint/tela)*
- **#11 (delta contábil) — `mod_contabil.ajustar_provisao_delta`.** Ativo diferido (1.1.06.0X / 1.1.05
  impostos) × provisão (2.1.04.0X); nunca DRE; aumento constitui, redução reverte capada ao ativo em
  aberto; idempotente por ref (sufixo `:parcela_id`, #6); origem própria p/ auditoria. Reaproveita
  `EVENTOS`/`_PROV_FECHAMENTO`. **6 testes** (aumento, redução cheia, redução capada pós-NF-e, zero,
  idempotência, impostos em 1.1.05).
- **Modelo:** `ParcelaProjeto`/`ParcelaAmbiente`/`CicloLogistico.parcela_id` já existiam (Fatia 1,
  dormentes). `mod_parcelas.py` em `modulos.py`.
- **Suíte: 982 passed** (958 base + 24 novos). Commits: fração/gate → partição → #11 delta.

## O que falta (fiação + frontend, em ordem sugerida)
1. **#1 criação (endpoint + frontend):** `POST .../parcelas` que valida (`validar_particao_parcelas`),
   congela (`congelar_parcelas`) e grava `parcela_projeto` + `parcela_ambiente`. Frontend: seletor
   "Projeto completo × Desmembrar" na 11c + modal de seleção de ambientes.
2. **#10 gate na tela de AF:** coluna de trava em `ProvisaoRegistro` + migração idempotente; o endpoint
   `provisoes/(rev1|rev2)` (main.py:3857) passa a **recusar reedição de versão travada** e a exigir
   Diretor quando `exige_aprovacao_diretor(cust_var_anterior, cust_var_novo, limite)` → True; roda por
   parcela quando desmembrado. Limites configuráveis no Config de Provisões (defaults 1%/2%).
3. **#11 disparo:** ao confirmar AF1/AF2, chamar `ajustar_provisao_delta` por rubrica que mudou
   (ref `af:<projeto>:<parcela_id>:<rubrica>:<versao>`). O núcleo já está pronto — falta só o gatilho.
4. **#7 ciclo por parcela:** uma linha de `CicloLogistico` por parcela; `CicloEtapa` (agregado) só fecha
   quando TODAS concluíram; tela das etapas 12-16 por parcela; lock pós-Implantação por parcela.
5. **#13 "Conferência e Implantação do Pedido":** renomear etapa 12; ao confirmar, dois lançamentos —
   `ajustar_provisao_delta` (diferença de PE) + `reclassificar_provisao` (migração p/ Outros
   Fornecedores 2.1.04.06→2.1.04.14, espelho do ativo).
6. **Vera** ponta a ponta (obrigatória antes de mergear).

## Resultado da suíte
`python -m pytest -q` → **982 passed** (warnings são legado de SQLAlchemy 2.0, pré-existentes).

## Relatório da Vera
**Ainda não rodou** — o núcleo está verde por TDD, mas um teste ponta a ponta só faz sentido com a
criação de parcela (#1) e o gate (#10) fiados na tela. Entra quando os itens 1-5 estiverem prontos.

## Conferência manual antes de aprovar (quando a fatia estiver completa)
- [ ] Desmembrar um projeto em 2+ parcelas na 11c e conferir `Σ val_cont_congelado == Val_Cont` no banco.
- [ ] AF de uma parcela com aumento < limite (sem step-up) e > limite (pede Diretor); versão trava após aprovar.
- [ ] Confirmar AF: delta cai SÓ em `1.1.06`/`2.1.04` (DRE não se move); conferir origem `ajuste_provisao_af` no razão.
- [ ] Etapas 12-16 progridem por parcela; `CicloEtapa` só fecha com todas concluídas.
- [ ] Conferência (#13): dois lançamentos auditáveis (PE + Outros Fornecedores).
- [ ] Projeto NÃO desmembrado continua idêntico (opt-in, #8) — sem regressão no fluxo atual.
