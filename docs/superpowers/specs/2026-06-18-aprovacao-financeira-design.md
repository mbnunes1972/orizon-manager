# Spec — Sub-projeto 3: Aprovação financeira gerencial

> Orizon Manager | Dalmóbile | Data: 2026-06-18
> Parte 3 de 4 da decomposição (item 3). Depende do Sub-projeto 2 (perfis). Status: aprovado para plano.

## Contexto

As etapas de aprovação financeira do ciclo — **8 "Aprovação financeira I"** (principal)
e **11d "Aprovação financeira II"** (sub-etapa do Projeto Executivo) — hoje são
concluídas sem nenhuma autorização: a etapa 8 tem `concluirAprovacaoFinanceira()` que
faz `PATCH /ciclo/8 {status:'concluido'}` direto, e a 11d usa o toggle genérico
(`toggleSalvarEtapa`). O requisito: concluir uma aprovação financeira deve **exigir
login + senha de um usuário com permissão de aprovar financeiro** — **Gerente
Administrativo/Financeiro ou Diretor**. **Gerente de vendas não pode aprovar.**

A fundação de perfis (Sub-projeto 2) já fornece o perfil `gerente_adm_fin` e o módulo
`perfis.py`; já existem o popup `pedirCredenciaisGerente(login+senha)` e a tabela de
auditoria `log_acoes_gerenciais`.

## Decisões (confirmadas com o usuário)

- O gate vale para **ambas** as etapas: 8 e 11d.
- O aprovador autentica com **seu login + senha**; o backend valida que o usuário existe,
  a senha confere e que o perfil tem `aprovar_financeiro`. Registra quem aprovou
  (responsável na etapa + auditoria em `log_acoes_gerenciais`).
- Nova capacidade `aprovar_financeiro` = Diretor + Gerente Adm/Financeiro
  (distinta de `autorizar`, que é desconto = Diretor + Gerente de Vendas).

## Detalhamento

### 1. Capacidade `aprovar_financeiro` (`perfis.py`)

Adicionar a flag `aprovar_financeiro` a cada perfil em `PERFIS` e ao `_DEFAULT`:
- `diretor`: True; `gerente_adm_fin`: True.
- Todos os demais (incl. `gerente_vendas`, `consultor`): False.

### 2. Etapas-alvo (`mod_ciclo.py` — fonte da verdade)

```python
ETAPAS_APROVACAO_FINANCEIRA = frozenset({"8", "11d"})

def exige_aprovacao_financeira(codigo):
    return codigo in ETAPAS_APROVACAO_FINANCEIRA
```

### 3. Backend — gate no `PATCH /api/projetos/<nome>/ciclo/<codigo>`

No handler que conclui a etapa, quando `mod_ciclo.exige_aprovacao_financeira(codigo)`
e o novo `status == "concluido"`:
- Ler `login` e `senha` do corpo. Validar: usuário existe e ativo, `check_senha` ok, e
  `perfis.pode(usuario.nivel, "aprovar_financeiro")`. Caso contrário, responder
  **403** com erro claro (ex.: "Apenas Gerente Administrativo/Financeiro ou Diretor
  podem aprovar a etapa financeira.").
- Em sucesso: marca `concluido`, define o **aprovador** como responsável da etapa
  (`responsavel_id` / `concluido_por`), e grava auditoria em `log_acoes_gerenciais`
  (ação `aprovar_financeiro`, projeto, etapa, aprovador, timestamp).
- Demais etapas (não-financeiras): comportamento atual inalterado (toggle sem senha).

Helper de validação de credencial reutilizável (em `auth.py` ou `mod_usuarios.py`),
ex.: `validar_credencial(login, senha)` → retorna o `Usuario` (ativo, senha ok) ou
`None`; o gate combina com `perfis.pode(nivel, "aprovar_financeiro")`.

### 4. Frontend

- Generalizar `concluirAprovacaoFinanceira(codigo)` (8 e 11d): abre
  `pedirCredenciaisGerente({titulo:'Aprovação Financeira', mensagem:'Login e senha do
  Gerente Administrativo/Financeiro ou Diretor'})`; se confirmado, envia
  `PATCH /ciclo/<codigo>` com `{status:'concluido', login, senha}`. Em erro, exibe a
  mensagem do backend (ex.: via `avisoPopup`).
- A sub-etapa **11d** passa a renderizar um card dedicado com o botão de aprovação
  financeira (mesmo fluxo da 8), em vez do toggle genérico — pois o backend passará a
  rejeitar a conclusão da 11d sem credencial.

### 5. Auditoria

Registrar em `log_acoes_gerenciais` cada aprovação financeira concluída
(quem aprovou, projeto, etapa, quando), como já é feito para reabertura de etapas.

## Fora de escopo (YAGNI)

- Mudança no fluxo de reabertura (cascata) das etapas financeiras — segue o gate de
  gerente atual.
- Workflow de medição (Sub-projeto 4).
- Aprovação financeira condicionada a valores/limites — apenas o gate por perfil.

## Verificação

- **pytest:** `perfis.pode(slug, "aprovar_financeiro")` (diretor/gerente_adm_fin True;
  gerente_vendas/consultor/medidor False); `mod_ciclo.exige_aprovacao_financeira("8")`
  e `("11d")` True, demais False; `validar_credencial` (se extraída como função
  testável — senão coberto via API).
- **API real (curl), etapas 8 e 11d:** `gerente_vendas` (lds2026) → 403; `gerente_adm_fin`
  (gaf2026) e `diretor` (pdm2026) → aprovam; senha incorreta → recusada; conclusão sem
  credencial → recusada; auditoria registrada. Suíte completa verde.

## Processo

Pipeline superpowers: spec → plano (writing-plans) → implementação com revisão a nível
de controlador → verificação (pytest + API real) → merge local.
