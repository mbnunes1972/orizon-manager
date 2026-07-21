# Custo Especial — custo adicional NÃO rateado nos ambientes (2026-07-20)

## Demanda
Incluir um custo adicional **fixo por projeto** que **não se distribui nos ambientes**. Exemplo:
venda de 3 ambientes — cozinha R$ 80.000 + sala R$ 50.000 + banheiro R$ 20.000 — com custo especial de
R$ 1.000 → total do projeto R$ 151.000. Retirando cozinha e banheiro, novo total R$ 51.000: **sai
ambiente, o custo especial fica integral**. Configurável no modal de parâmetros de forma análoga a
comissão de arquiteto / fidelidade / custo de viagem / brinde (toggle + valor), com **provisão
própria** no fechamento contábil.

## Semântica no motor (`mod_negociacao.calcular_orcamento`)
Chaves novas em `parametros_json`: `custo_especial` (R$) + `custo_especial_ativo` (toggle). Sigla nova no
retorno: **`Cust_Esp`**.

- **Linha do ORÇAMENTO, fora do loop de ambientes** — é isso que o torna não-rateado. Viagem
  distribui proporcional ao VBVA e brinde igual por ambiente (pelo pool do projeto,
  `n_total_proj`/`vbvo_proj`); o Custo Especial ignora esse contexto e entra **integral** em qualquer
  subconjunto de ambientes.
- **Repassado** (`incluir_custos` ON): `VBNO += cf` e `VAVO += cf` **fora do fator de desconto**
  (blindado — o cliente paga o valor cheio; `Val_Liq` e `Desc_Tot` ficam idênticos ao cenário sem o
  custo). `Val_Cont = VAVO + Cust_Fin` já o carrega → contrato/marcadores/NF-e herdam sem mudança.
- **Absorvido** (OFF): preço ao cliente inalterado; `cust_ad += cf` abate o `Val_Liq`.
- **Comissões arq/fid não incidem** sobre ele (são calculadas por ambiente; o custo especial vive fora).
- Consequência assumida: com o custo especial ativo, **Σ `Val_Liq` dos ambientes ≠ `Val_Liq` do orçamento** —
  a diferença é exatamente a linha `Cust_Esp` (mesma lógica no waterfall da UI).

## Provisão própria (família Cust_Ad, 5º membro)
- `mod_provisoes._RUBRICAS_CUST_AD += {"cust_esp": "Cust_Esp"}` → vira linha em `itens_provisao`
  (painel AF) e **não** soma no `Cust_Var` (padrão F0: já deduzido do `Val_Liq`; somar dobraria).
- `mod_contabil`: contas novas **`1.1.06.20` Custo Especial a Apropriar × `2.1.04.20` Provisão de Custo
  Especial** + despesa **`5.3.17` Custo Especial de Projeto**. Eventos `fechamento_venda_cust_esp` (contrato,
  ativo diferido × provisão, sem tocar a DRE — padrão FASE D2) e `reconhecimento_despesa_cust_esp`
  (NF-e: 5.3.17 × baixa do 1.1.06.20; a provisão sobrevive). Mapeado em `_PROV_FECHAMENTO` e
  `_MATCHING_NFE`; conciliação final (etapa 21), `ajustar_provisao_delta` (AF), `devolver_venda` e o
  painel de reconciliação são **data-driven** sobre o grupo 2.1.04.x → pegam a rubrica sem mudança.
  `seed_plano` backfilla as contas novas em owners existentes (idempotente).
- `main.py`: `"cust_esp": d.get("Cust_Esp")` no dict de `constituir_provisoes_fechamento`
  (`_fin_provisoes_venda_seguro`) + chave no bloco `custos_adicionais` do GET `/api/orcamentos/<id>/provisoes`.

## Frontend (`static/index.html`)
Bloco "Custo Especial" no modal de parâmetros após o Brinde (`mp-cfixo-ativo`/`mp-cfixo`,
`mpToggleCustoEspecial`); linha "− Custo Especial" (`mp-a-cesp`) no Apoio à negociação (preview do motor
via `s.Cust_Esp`; eco do input no caminho EP07; dedução manual no caminho legado); chaves nos DOIS
payloads de save (`salvarParametrosAuto` e `fecharModalParams`), no snapshot/restore do Voltar e em
`lerMargensNegociacao`; rubrica `{key:'cust_esp', label:'Custo Especial'}` em `_PROV_RUBRICAS` (AF).
**De propósito, NÃO entra** nos gross-ups por ambiente (`renderTabelaNeg`/`calcularValorBrutoCliente`)
— os preços por ambiente não mudam; o custo especial aparece só nos totais (motor) e como linha própria.

## Decisões
- **Nome "Custo Especial"** (decisão do usuário, 2026-07-20): a 1ª proposta era "Custo Fixo", mas o
  termo tem sentido consagrado em contabilidade (custo de estrutura, invariante ao volume — o oposto
  deste, que é custo direto incorrido só na venda) e confundiria a leitura da DRE/reconciliação.
- **Sem default de loja**: valor é por projeto (como viagem/brinde); nasce 0/OFF.
- **Numeração**: 1.1.06.19/2.1.04.19 já eram do Custo Financeiro → o custo especial usa **.20**. Despesa em
  5.3 (Despesas de Venda), como as irmãs (5.3.12/14/15) — `5.3.17` era o próximo livre.
- **Proposta/contrato**: nenhum marcador novo — o custo especial já compõe `Val_Cont`/`VAVO` do motor.

## Testes
`test_negociacao.py` (7 novos: exemplo da demanda, remoção de ambiente com contexto de pool,
blindagem do desconto, absorvido, toggle off, comissões não incidem), `test_orcamento_params.py`
(set de 12 chaves + coerção), `test_provisoes.py` (rubrica na AF sem dobrar Cust_Var),
`test_custos_adicionais_provisao.py` (par contábil no `_PARES` + ciclo completo constituição →
matching → conciliação), `test_fluxo_completo_e2e.py` (set de 18 chaves do snapshot da AF).
Suíte: 1322 passed (SQLite) / 1320+2 skipped (Postgres real via `TEST_DATABASE_URL`).
