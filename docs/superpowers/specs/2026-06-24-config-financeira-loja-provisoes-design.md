# Design — Config financeira da loja, provisões e margem real

**Data:** 2026-06-24
**Frente:** C (do dia) — painel financeiro com todas as provisões
**Status:** proposto (decisões fechadas no brainstorm; aguarda revisão)
**Referência canônica:** `docs/modulos/financeiro/PROVISOES_E_VARIAVEIS.md` (tabela do motor — fonte
de verdade das siglas e fórmulas).

## Contexto

O motor `mod_negociacao.calcular_orcamento` já é a fonte única dos números da negociação e produz
as provisões **do ato da venda** (`Com_Arq`, `Pro_Fid`, `Cust_Via`, `Bri`, `Cust_Fin`, `Prov_Imp`,
`CFO`, `Val_Liq`). Faltam:

- As **provisões pós-fechamento** (frete fábrica, comissões adm/vendas/medidor/projeto executivo,
  frete local, assistências, insumos locais) — não existem hoje.
- A **margem real** do negócio (`Cust_Var`, `Marg_Cont`) — não é calculada.
- Um lugar para **configurar as taxas por loja** — hoje os defaults da negociação são constantes
  globais em `mod_orcamento_params.py` (`PARAMETROS_DEFAULT`), modalidades de pagamento são arquivos
  estáticos em `tabelas_financeiras/*.json`, e `lojas` não tem coluna de config.

## Objetivo e escopo (v1)

**v1 = configurar as taxas financeiras por loja + o motor calcular a margem real.** Concretamente:

1. **Config financeira por loja** (painel editável, escopo restrito): defaults de negociação
   (`%Com_Arq`, `%Pro_Fid`, `%Car_Trib`) + taxas de provisão pós-fechamento (`%Frete_Fab`,
   `%Com_Adm`, `%Com_Med`, `%Com_Proj_Exec`, `%Frete_Loc`, `%Assist`, `%Ins_Loc`) + os
   **configuradores da comissão de vendas** (faixas + limitador de desconto).
2. **Motor calcula** `Cust_Var` e `Marg_Cont` por orçamento e expõe no breakdown (visibilidade
   restrita, como os impostos hoje).
3. **`Out_Forn`** (outros fornecedores) — campo editável por orçamento (Gerente Adm/Fin), entra em
   `Cust_Var`.

O **cálculo dinâmico** da comissão de vendas (acumulador mensal + fechamento de ciclo) é **fase 2**:
na v1 os configuradores ficam **gravados** e há uma função pura que resolve `%Com_Venda` a partir de
um valor de venda dado, mas a acumulação mensal e o ciclo provisório→definitivo não entram ainda.

## Decisões fechadas (do brainstorm)

- **Recorte:** config financeira da loja primeiro (fundação das taxas).
- **Imposto:** uma sigla só — `Prov_Imp = %Car_Trib × (VAVO + Cust_Fin)` (= `%Car_Trib × Val_Cont`).
  `Imp_Orc` **eliminado** (era duplicidade). `Prov_Imp` **mantém o nome sem `_Orc`** (exceção
  justificada: sigla consagrada/implementada, sem colisão, sem versão por ambiente).
- **`%Car_Trib` sai do modal de parâmetros** e vira config da loja; fica **0** até a 1ª versão
  (config manual; depois extraída do módulo fiscal).
- **Margem real:** `Cust_Var = CFO + Out_Forn + Frete_Fab_Orc + Com_Adm_Orc + Com_Venda_Orc +
  Com_Med_Orc + Com_Proj_Exec_Orc + Frete_Loc_Orc + Assist_Orc + Ins_Loc_Orc + Prov_Imp`;
  `Marg_Cont = (Val_Liq − Cust_Var) / Val_Liq` (**sobre o valor líquido**; pode ser negativa).
- **Bases das provisões** (cada uma a sua): `%Frete_Fab × CFO`; `%Com_Adm/%Com_Venda/%Com_Med/
  %Com_Proj_Exec × Val_Liq`; `%Frete_Loc/%Assist/%Ins_Loc × VAVO`; `Prov_Imp` sobre `Val_Cont`.
- **Comissão de vendas:** por consultor; `%` é resultado de uma rotina (2 configuradores num modal,
  **regra no backend**). Base de venda = `Val_Liq` acumulado no mês; meta mensal fixa por consultor.
  Limitador de desconto avaliado por **`%Desc_Orc`**, com **toggle** (lojas que não usam), e
  **reduz o `%`** daquela venda específica. `Com_Adm` agregada na v1 (dividida por função adm depois).

## Arquitetura

**Abordagem A (storage):**
- **`lojas.config_financeira_json`** (coluna TEXT/JSON, nullable) guarda **áreas 1+2** (defaults de
  negociação + taxas de provisão + configuradores de comissão). Simples de ler/versionar; conjunto
  fixo e pequeno.
- **Condições de pagamento por loja** (tabela `condicoes_financeiras` com `loja_id`) ficam **fora da
  v1** (fase futura — ver `FUTURO_CALCULO_FINANCEIRO.md`).

**Módulo puro novo `mod_provisoes.py`** (recebe dados, devolve dados — testável sem HTTP):
- `provisoes_orcamento(siglas, cfg)` → dict com `Frete_Fab_Orc`, `Com_Adm_Orc`, `Com_Med_Orc`,
  `Com_Proj_Exec_Orc`, `Frete_Loc_Orc`, `Assist_Orc`, `Ins_Loc_Orc`, `Cust_Var`, `Marg_Cont`.
  `siglas` = saída do motor (`CFO`, `Val_Liq`, `VAVO`, `Prov_Imp`, `Out_Forn`, e o `%Com_Venda` já
  resolvido); `cfg` = a config financeira da loja.
- `resolver_comissao_venda(cfg, val_liq_mes, desc_orc_pct)` → `%Com_Venda` (faixa por
  `val_liq_mes`, redutor por `desc_orc_pct` se o limitador estiver ativo).
- `config_financeira_default()` / `validar_config_financeira(dados)` → defaults + validação (puras).

**Integração no motor:** `mod_negociacao` (ou o ponto que monta o breakdown) chama
`mod_provisoes.provisoes_orcamento` após produzir as siglas-base, e acrescenta `Cust_Var`/`Marg_Cont`
ao breakdown. Os defaults de negociação por loja substituem `PARAMETROS_DEFAULT` global ao **criar**
o `parametros_json` de um projeto novo (a loja do projeto fornece os defaults; o projeto ainda pode
editar `%Com_Arq`/`%Pro_Fid` no modal).

**Rotas finas em `main.py`:**
- `GET /api/admin/lojas/<id>/config-financeira` → devolve a config (ou os defaults).
- `PUT /api/admin/lojas/<id>/config-financeira` → valida e grava (autorização: ver Segurança).

## Modelo de dados — `config_financeira_json`

```json
{
  "defaults_negociacao": {
    "comissao_arq_pct": 0.0,
    "fidelidade_pct": 0.0,
    "carga_trib_pct": 0.0
  },
  "provisoes": {
    "frete_fab_pct": 0.0,
    "com_adm_pct": 0.0,
    "com_med_pct": 0.0,
    "com_proj_exec_pct": 0.0,
    "frete_loc_pct": 0.0,
    "assist_pct": 0.0,
    "ins_loc_pct": 0.0
  },
  "comissao_vendas": {
    "meta_mensal": 0.0,
    "faixas_comissao": [
      {"venda_ate": null, "pct": 0.0}
    ],
    "limitador_desconto": {
      "ativo": false,
      "base_desconto": "Desc_Orc",
      "limites": [
        {"desconto_acima_de": 0.0, "redutor_pct": 0.0}
      ]
    }
  }
}
```

Todos os campos iniciam em 0 / inativo (loja recém-criada não altera o comportamento atual: provisões
= 0 → `Cust_Var = CFO + Out_Forn` e `Marg_Cont` continua coerente).

## Cálculo da margem real (motor)

Por orçamento, após as siglas-base:
```
Frete_Fab_Orc     = %Frete_Fab     × CFO
Com_Adm_Orc       = %Com_Adm       × Val_Liq
Com_Venda_Orc     = %Com_Venda     × Val_Liq      (%Com_Venda via resolver_comissao_venda)
Com_Med_Orc       = %Com_Med       × Val_Liq
Com_Proj_Exec_Orc = %Com_Proj_Exec × Val_Liq
Frete_Loc_Orc     = %Frete_Loc     × VAVO
Assist_Orc        = %Assist        × VAVO
Ins_Loc_Orc       = %Ins_Loc       × VAVO
Cust_Var  = CFO + Out_Forn + Frete_Fab_Orc + Com_Adm_Orc + Com_Venda_Orc + Com_Med_Orc
            + Com_Proj_Exec_Orc + Frete_Loc_Orc + Assist_Orc + Ins_Loc_Orc + Prov_Imp
Marg_Cont = (Val_Liq − Cust_Var) / Val_Liq
```

## Comissão de vendas — configurador (v1) + cálculo (fase 2)

**v1 (config + resolver puro):** os dois configuradores são gravados em
`comissao_vendas` e há `resolver_comissao_venda(cfg, val_liq_mes, desc_orc_pct)`:
1. `%_base` = faixa em `faixas_comissao` por `val_liq_mes`.
2. se `limitador_desconto.ativo` e `desc_orc_pct` ultrapassa limites → pega o `redutor_pct` do
   **maior** limite ultrapassado → `%_efetivo = %_base × (1 − redutor_pct)`; senão `%_efetivo = %_base`.
Na v1, `val_liq_mes` pode ser o `Val_Liq` do **próprio orçamento** (sem acumulação) para fechar o
fluxo de cálculo; a acumulação real entra na fase 2.

**Fase 2 (acumulador mensal):** estado persistente de `Val_Liq` por **(consultor, loja, mês)**;
comissão **provisória** no mês e **definitiva no fechamento do ciclo** (faixa final do mês aplicada
a todos os negócios do ciclo, com o redutor por negócio). Requer saber o consultor dono do orçamento
(via `consultor_id` do briefing/projeto) e isolar por loja.

## Painel / UI

Aba **"Financeiro"** no nível Loja do Painel Admin (ao lado de Dados / Usuários / Projetos). Seções:
- **Defaults de negociação** (`%Com_Arq`, `%Pro_Fid`, `%Car_Trib`).
- **Taxas de provisão** (frete fábrica, com. adm, medidor, projeto executivo, frete local,
  assistências, insumos) — campos `%`.
- **Comissão de vendas** — botão que abre o **modal único** com as duas tabelas (faixas + limitador
  com toggle).
- A **margem real** (`Marg_Cont`/`Cust_Var`) aparece na **tela de negociação**, sob a mesma proteção
  dos impostos (revelada por senha de quem pode ver — ver Segurança).

## Segurança / visibilidade

- **Editar a config financeira:** `gerir_lojas`/`editar_dados_loja` **+** capacidade financeira
  (diretor, gerente adm/fin; admin_rede/super_admin). Reutiliza o gate de `editar_dados_loja` da
  aba Dados, restrito ao escopo de tenancy (admin_rede só lojas da rede).
- **Ver a margem real:** sensível — fica atrás do mesmo cadeado dos impostos (`aprovar_financeiro` /
  `POST /api/auth/liberar_impostos`). O frontend só exibe; o backend é autoritativo.
- **Comissão:** regra 100% no backend (o consultor não força a própria comissão).

## Faseamento

- **v1:** config financeira da loja (`%` simples + configuradores de comissão) + motor calcula
  `Cust_Var`/`Marg_Cont` + `Out_Forn` editável + exibição restrita da margem real.
- **Fase 2:** subsistema de comissão de vendas (acumulador mensal por consultor + fechamento de ciclo,
  provisório→definitivo).
- **Fase 3:** custo financeiro **absorvido** pela loja entra em `Cust_Var`.
- **Futuro:** condições de pagamento por loja (`condicoes_financeiras` com `loja_id`); divisão de
  `Com_Adm` por função adm (diretor / gerente comercial / gerente adm).

## Fora deste spec (v1)
- Condições de pagamento por loja; divisão de `Com_Adm`; acumulador/ciclo da comissão; custo
  financeiro absorvido.

## Micro-pontos a confirmar antes da fase 2 (comissão)
- **Limiares das faixas:** absolutos em R$ ou relativos à `meta_mensal`? (default adotado: R$
  absolutos.)
- **`redutor_pct`:** multiplicativo `%_base × (1 − s)` (default adotado) ou em pontos `%_base − s`.
- **Fronteiras** `<`/`≤` nos limiares e nos limites de desconto (definir inclusivas; default:
  `venda_ate` exclusivo no topo da faixa, `desconto_acima_de` estritamente maior).

## Testes
- **Puros (`mod_provisoes`):** `provisoes_orcamento` (cada provisão na base certa; `Cust_Var`
  soma tudo incl. `CFO`/`Out_Forn`/`Prov_Imp`; `Marg_Cont` correto, inclusive negativo);
  `resolver_comissao_venda` (faixa por venda; redutor por desconto; toggle off → sem redutor;
  fronteiras); `validar_config_financeira`.
- **Integração motor:** breakdown ganha `Cust_Var`/`Marg_Cont` sem alterar as siglas existentes;
  config zerada não muda o comportamento atual (regressão).
- **E2E rotas:** `GET/PUT /api/admin/lojas/<id>/config-financeira` (200 no escopo; 403 fora;
  validação rejeita valores inválidos); margem real só revelada com a senha financeira.
- **Frontend:** verificação manual (sem teste JS) — aba Financeiro grava/relê; modal de comissão.

## Arquivos afetados
- **Novo:** `mod_provisoes.py`; testes (`tests/test_provisoes.py` + e2e da config).
- **Editado:** `database.py` (coluna `config_financeira_json` + migração idempotente);
  `mod_negociacao.py` / ponto do breakdown (integra `Cust_Var`/`Marg_Cont`); `mod_orcamento_params.py`
  (defaults da loja na criação do `parametros_json`); `main.py` (rotas GET/PUT config + `Out_Forn`);
  `static/index.html` (aba "Financeiro" no nível Loja + modal de comissão + exibição restrita da
  margem real na negociação).
