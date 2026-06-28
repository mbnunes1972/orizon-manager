# Design — Provisões versionadas + aprovação financeira

**Data:** 2026-06-27
**Frente:** Provisões versionadas (continuação da Frente C / item #8 financeiro)
**Status:** ✅ Implementado e mergeado na `main` (2026-06-28, sessão 35; suíte 369 no merge).
**Base:** `docs/modulos/financeiro/PROVISOES_E_VARIAVEIS.md`, spec da config financeira
(`2026-06-24-config-financeira-loja-provisoes-design.md`), §"Provisões financeiras" do ciclo
(`2026-06-15-ciclo-completo-projeto-design.md`).

## Contexto

A Frente C já entregou: config financeira por loja (taxas), o motor que calcula as provisões
(`mod_provisoes.provisoes_orcamento` → `Frete_Fab_Orc`, `Com_Adm_Orc`, `Com_Venda_Orc`,
`Com_Med_Orc`, `Com_Proj_Exec_Orc`, `Frete_Loc_Orc`, `Assist_Orc`, `Ins_Loc_Orc`, `Prov_Imp`,
`Out_Forn`, `Cust_Var`, `Marg_Cont`), e a exibição do **agregado** (`Cust_Var`/`Marg_Cont`) na
negociação sob o cadeado de impostos.

Falta o que o usuário pediu: as provisões são uma **previsão de despesa futura** que precisa ser
**registrada** e **aprovada/revisada** pelo Gerente Adm/Fin, em **versões**.

## Objetivo

Registrar as provisões de forma **versionada** (Venda → Rev 1 → Rev 2) e dar ao Gerente Adm/Fin um
fluxo de **Concorda / Revisa** em cada aprovação financeira. A **separação das rubricas**
(itemização) aparece **a partir da Aprovação Financeira I**; a negociação permanece com o agregado.

## Decisões (fechadas no brainstorm)

- **Rubricas da provisão** (previsão de despesa futura): Frete Fábrica (`Frete_Fab_Orc`), Comissões
  Administrativas (`Com_Adm_Orc`), Comissão de Vendas (`Com_Venda_Orc`), Medidor (`Com_Med_Orc`),
  Projeto Executivo (`Com_Proj_Exec_Orc`), Frete Local (`Frete_Loc_Orc`), Assistências
  (`Assist_Orc`), Insumos (`Ins_Loc_Orc`), Impostos (`Prov_Imp`), Outros Fornecedores (`Out_Forn`).
  O custo de fábrica `CFO` é **custo comprometido** (não provisão futura) — entra no `Cust_Var` e
  aparece como referência, mas não é uma rubrica de provisão.
- **Três registros versionados** (cada um gravado com itens + quem/quando + decisão):
  - **Provisões da Venda** — snapshot na **Etapa 7 (geração do contrato)**, calculada da config da
    loja, **congelada**. Se o contrato for **regerado**, a Venda é **re-snapshotada**.
  - **Provisões Rev 1** — na **Etapa 8 (Aprovação Financeira I)**: o Adm/Fin **Concorda** (Rev 1 =
    cópia da Venda) ou **Revisa** (edita os **valores R$** das rubricas + `Out_Forn`, **com senha**).
  - **Provisões Rev 2** — na **Etapa 11d (Aprovação Financeira II)**: mesma lógica Concorda/Revisa.
- **"Revisa" edita os valores R$ das rubricas + `Out_Forn`** — NÃO edita as taxas % da loja (essas
  são política, ficam na config). `Out_Forn` pode ser lançado na Rev 1 **ou** na Rev 2.
- **Negociação inalterada:** mantém só o agregado (`Cust_Var`/`Marg_Cont`) sob o cadeado. Itemização
  só a partir da Etapa 8.
- **Coerência (staleness):** se a negociação/pagamento mudar **após** a Venda registrada, mostrar
  aviso de "provisões desatualizadas" (mesma ideia do guard de contrato); regerar atualiza a Venda.
- **Acesso:** tudo sob `aprovar_financeiro` (diretor / gerente adm-fin) — mesmo gate da Etapa 8/11d
  e do cadeado de impostos.

## Arquitetura

**Abordagem A — tabela de registros versionados.**

- **Nova tabela `provisao_registro`:**
  - `id` (PK), `orcamento_id` (FK orcamentos), `versao` (`venda` | `rev1` | `rev2`),
    `itens_json` (dict `{rubrica: valor_R$}` das 10 rubricas), `out_forn` (Float),
    `cust_var` (Float), `marg_cont` (Float), `decisao` (`concorda` | `revisa` | null para a Venda),
    `por_id` (FK usuarios, quem registrou), `criado_em` (DateTime).
  - `UNIQUE(orcamento_id, versao)` — um registro por versão por orçamento (re-snapshot da Venda
    sobrescreve a linha `venda`).
- **`mod_provisoes` (puro):**
  - `itens_provisao(siglas) -> dict` — extrai as 10 rubricas do breakdown (`d`) num dict
    `{frete_fab, com_adm, com_venda, com_med, com_proj_exec, frete_loc, assist, ins_loc, prov_imp,
    out_forn}`. (Os valores já existem em `d`; é só mapear.)
- **Backend (`main.py`, cola fina):**
  - **Na geração do contrato (Etapa 7):** após gerar, computar o breakdown e gravar/atualizar o
    registro `venda` (itens + out_forn + cust_var + marg_cont, `decisao=null`, `por_id`=quem gerou).
  - `GET /api/orcamentos/<id>/provisoes` → as versões existentes (venda/rev1/rev2) + a "atual"
    calculada ao vivo (para o aviso de desatualizado). Auth: `aprovar_financeiro`.
  - `POST /api/orcamentos/<id>/provisoes/<rev1|rev2>` → corpo `{decisao, itens?, out_forn?, senha}`:
    valida a senha (`aprovar_financeiro`, reusa o mecanismo de `liberar_impostos`); se `concorda`,
    copia a versão anterior; se `revisa`, grava os itens editados; registra `por_id`/`criado_em`.
    **NÃO avança a etapa** — o registro da provisão é desacoplado do avanço do ciclo. O avanço da
    Etapa 8/11d continua no botão "Aprovar (gerencial)" existente (`concluirAprovacaoFinanceira`),
    mantendo o gate de aprovação financeira como fonte única do estado do ciclo. (Decisão tomada na
    implementação; revisão final endossou o desacoplamento.)
- **Frontend (`static/index.html`):** na etapa de aprovação financeira (8 e 11d), um botão
  **"Provisões"** abre uma tela/modal com as **tabelas lado a lado** (Venda | Rev 1 | Rev 2, conforme
  existirem) e a ação **Concorda / Revisa** (edição dos valores + `Out_Forn` sob senha). Aviso de
  desatualizado quando a negociação mudou após a Venda.

## Fluxo

```
Etapa 7 (contrato gerado) ──> grava "Provisões da Venda" (config, congelada)
Etapa 8 (Aprov. Fin. I)   ──> botão "Provisões": mostra Venda; Adm/Fin Concorda|Revisa(senha) ──> "Rev 1"
Etapa 11d (Aprov. Fin. II)──> botão "Provisões": mostra Venda|Rev 1; Concorda|Revisa(senha) ──> "Rev 2"
```

## Erros / bordas
- Tentar Rev 1 sem a Venda registrada (contrato não gerado) → 409 "Gere o contrato primeiro".
- Senha inválida / sem `aprovar_financeiro` → 403.
- "Revisa" com item negativo → rejeita (clamp/validação, como `out_forn>=0`).
- Negociação mudou após a Venda → resposta marca `desatualizado=true`; UI avisa.

## Fora de escopo
- Editar as taxas % da loja por negócio (fica na config).
- Itemização na negociação (mantém o agregado).
- Provisões Rev 3+ (só Venda/Rev1/Rev2 no escopo).

## Testes
- **Puro:** `mod_provisoes.itens_provisao` (10 rubricas corretas a partir de um breakdown).
- **Backend e2e:** geração de contrato grava `venda`; `POST .../rev1` com `concorda` copia a Venda;
  com `revisa` grava itens editados; senha inválida → 403; Rev 1 sem Venda → 409; re-snapshot da
  Venda na regeração; escopo/IDOR (orçamento de outra loja → 404).
- **Frontend:** verificação manual (sem teste JS) — tabelas lado a lado, Concorda/Revisa, edição sob
  senha, aviso de desatualizado.

## Arquivos afetados
- **Editado:** `database.py` (`ProvisaoRegistro` + migração), `mod_provisoes.py` (`itens_provisao`),
  `main.py` (grava `venda` na geração do contrato + rotas GET/POST de provisões), `static/index.html`
  (botão "Provisões" + tabelas + Concorda/Revisa na etapa de aprovação financeira).
- **Novo:** testes (`tests/test_provisao_registro.py` + e2e).
