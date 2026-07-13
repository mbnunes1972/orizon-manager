# Texto de fechamento — Fatia 2 (desmembramento operacional) — PARA APROVAÇÃO

> Branch `feat/desmembramento-fatia2-ciclo` (a partir da `main` com Fatia 1 mergeada).
> Spec: `docs/superpowers/specs/2026-07-13-desmembramento-pe-parcial-design.md` (decisões #1/#5/#7/#10/#11/#13).
> **Estado: FUNDAÇÃO implementada (lógica pura, TDD). A integração sensível (ciclo/AF/contábil) e o
> frontend NÃO estão feitos** — ver "O que falta". Não rodei a Vera ainda (a fatia não está completa o
> suficiente pra um teste ponta a ponta honesto). **Não mergear.**

## Por que parei aqui (leitura honesta)
A Fatia 2 é grande e toca ciclo **e** contabilidade. Entreguei os passos 1 e 2 da ordem completos e
mergeados na `main` (design v1.7 + Fatia 1), e comecei a Fatia 2 pela fundação testável. O restante
(#1 criação de parcela, #7 ciclo por parcela, #10 gate na tela de AF, **#11 evento delta contábil**,
#13 conferência + split) é integração que altera fluxos financeiros existentes e precisa de iteração
com a Vera — não é responsável fiar `mod_contabil`/gate de AF sem validação cuidadosa. Preferi um
checkpoint correto e verificado a deixar contábil meio-pronto.

## O que foi implementado de fato (contra o spec)
- **#5 (fração da parcela) — COMPLETO, TDD.** `mod_parcelas.congelar_parcelas`: congela
  `fracao_val_cont` e `val_cont_congelado` por parcela; a última parcela absorve o resto do
  arredondamento. **Invariante `Σ val_cont_congelado == round(Val_Cont, 2)` exato ao centavo** coberto
  por teste (base do faturamento e do matching de NF-e parcial da Fatia 3).
- **#10 (gate de Aprovação Financeira) — regra pura, TDD.** `mod_parcelas.exige_aprovacao_diretor`:
  aumento de custo entre versões de provisão acima do limite (AF1 1% / AF2 2%, `LIMITE_AF*_DEFAULT`)
  exige step-up do Diretor. Regra pura pronta; **falta plugar** na tela/endpoint de AF (ver abaixo).
- **Modelo de dados — já existia (Fatia 1, dormente):** `ParcelaProjeto`, `ParcelaAmbiente`,
  `CicloLogistico.parcela_id` (`database.py`), migração idempotente. Nada a criar aqui.
- `mod_parcelas.py` registrado em `modulos.py` (domínio comercial). 12 testes em
  `tests/test_parcelas.py`. **Suíte inteira: 970 passed.**

## Divergências spec × código encontradas (não forcei nada)
1. **#10 — a base já existe parcialmente.** Há um endpoint `POST /api/orcamentos/<id>/provisoes/(rev1|rev2)`
   ("Concorda/Revisa") em `main.py:3857-3894`, com `ProvisaoRegistro.versao` ('venda'|'rev1'|'rev2') e
   `UniqueConstraint(orcamento_id, versao)`. O gate #10 (trava pós-aprovação + limite → Diretor +
   por-parcela) deve ser construído **em cima desse fluxo existente**, não do zero. Precisa da sua leitura:
   o comportamento atual de "Concorda/Revisa" já trava a versão ou permite reedição? Isso muda como o
   "após aprovar, trava" da #10 encaixa.
2. **#10 — "Limite de Aprovação Financeira 1/2" NÃO existe** no Config de Provisões (só há
   `_limiteAutorizado`, que é de desconto). É campo novo a adicionar na config (com defaults 1%/2%).
3. **#11 — cap do delta:** deixei o cálculo do delta fora do módulo puro de propósito. O cap ("capado ao
   saldo em aberto", padrão `reclassificar_provisao`) depende da semântica exata de
   `mod_contabil.reclassificar_provisao` (linha 620) e `resolver_saldo_provisao` (677) — quero espelhar
   o código real desses, não inventar um cap que divirja. É a primeira coisa da fase de fiação.

## O que falta (breakdown, em ordem sugerida)
1. **#1 — criação de parcela:** endpoint `POST .../parcelas` + `mod_parcelas` (usa `congelar_parcelas`);
   grava `parcela_projeto` + `parcela_ambiente`; valida que os ambientes particionam o pool (sem
   sobreposição/sobra). Frontend: seletor "Projeto completo × Desmembrar" na 11c + modal de seleção de
   ambientes.
2. **#7 — ciclo por parcela:** uma linha de `CicloLogistico` por parcela; `CicloEtapa` (agregado) só
   fecha `concluida` quando TODAS as parcelas concluíram; tela das etapas 12-16 lista parcelas com
   progresso individual; lock pós-Implantação por parcela.
3. **#10 — gate na tela de AF:** plugar `exige_aprovacao_diretor` no fluxo rev1/rev2; trava pós-aprovação;
   limites configuráveis no Config de Provisões; rodar por parcela quando desmembrado.
4. **#11 — evento delta ativo×provisão:** ao confirmar AF1/AF2 com mudança, lançar delta só entre
   `1.1.06.0X` e `2.1.04.0X` (nunca DRE), no padrão `reclassificar_provisao` (append-only, idempotente
   por ref, capado). **Área mais sensível — TDD contra o razão real.**
5. **#13 — "Conferência e Implantação do Pedido":** renomear etapa 12 (sem virar etapa nova); ao
   confirmar, lançar DOIS deltas auditáveis (diferença de PE + migração p/ Outros Fornecedores
   `2.1.04.06→2.1.04.14` espelhando `1.1.06.06→1.1.06.14`, via `reclassificar_provisao`).
6. **Vera** ponta a ponta na Fatia 2 (obrigatória antes de mergear — área sensível).

## Resultado da suíte
`python -m pytest -q` → **970 passed** (958 da base + 12 novos de `test_parcelas.py`). Warnings são legados
de SQLAlchemy 2.0, pré-existentes.

## Relatório da Vera
**Não rodou nesta fatia** — a fundação está verde por TDD, mas um teste ponta a ponta só faz sentido com
o fluxo operacional (#1/#7) e o contábil (#11) implementados. Rodar a Vera agora reportaria "incompleto",
não um veredito útil. Ela entra quando os itens 1-5 acima estiverem fiados.

## Conferência manual antes de aprovar (quando a fatia estiver completa)
- [ ] Desmembrar um projeto em 2+ parcelas na 11c e conferir `Σ val_cont_congelado == Val_Cont` no banco.
- [ ] AF de uma parcela com aumento < limite (sem step-up) e > limite (pede Diretor).
- [ ] Confirmar que a confirmação de AF lança delta SÓ em `1.1.06`/`2.1.04` (a DRE não se move).
- [ ] Etapas 12-16 progridem por parcela; `CicloEtapa` só fecha com todas concluídas.
- [ ] Projeto NÃO desmembrado continua idêntico (opt-in, #8) — nada de regressão no fluxo atual.
