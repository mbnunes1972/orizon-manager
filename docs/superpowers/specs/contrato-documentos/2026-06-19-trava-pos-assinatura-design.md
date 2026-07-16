# Design — Trava total pós-assinatura + status "Fechado"

> Data: 2026-06-19 · Sub-projeto 2 de 3 (1) snapshot da negociação ✅ · 2) trava total
> pós-assinatura · 3) versionamento de documentos)

## Problema

Após o contrato ser assinado, o projeto ainda oferece edição da negociação: os botões da
sidebar (Parâmetros, Ambientes, Novo Orçamento) seguem clicáveis, e o "Rever Orçamento" desfaz
a aprovação. O bloqueio atual (`aplicarBloqueioNegociacao`) é só pós-**aprovação** (etapa 6) e
**reversível**. É preciso uma trava **total e permanente** a partir da **1ª assinatura**, na UI
e reforçada no backend. Além disso, falta um status terminal: quando ambas as partes assinam, o
projeto deve aparecer como **"Fechado"**.

## Decisões (acordadas)

- **Gatilho:** trava a partir da **1ª assinatura** (qualquer assinatura presente).
- **Reforço no backend:** além de esconder na UI, o servidor **recusa (403)** as mutações.
- **"Assinar Contrato" permanece** visível após a 1ª assinatura (a 2ª parte ainda assina).
- **Novo status "Fechado":** automático quando o contrato fica **totalmente assinado**
  (`contrato.status = "assinado"`, loja + cliente). Terminal, não editável manualmente
  (como "convertido").

## Detecção de "assinado"

- **Backend** `_contrato_assinado(nome_safe, db) -> bool`: pega o último `Contrato` do projeto;
  retorna `True` se `status` ∈ {assinado_loja, assinado_cliente, assinado, vigente} **ou**
  `len(assinaturas) > 0`. `False` se não há contrato ou está em rascunho/para_assinatura.
- **Exposição:** o handler `GET /api/projetos/<nome>/ciclo` passa a incluir
  `contrato_assinado: bool` no topo da resposta (já é carregado em `_fetchCiclo` ao abrir o
  projeto). O front guarda `_contratoAssinado` em `_fetchCiclo`.

## Frontend (`static/index.html`)

Quando `_contratoAssinado` é `true`:
- **Escondidos:** "Salvar Orçamento" (`.btn-ok` da action-row), **Parâmetros**, **Ambientes**
  (pool), **Novo Orçamento** (botões da sidebar — receberão ids estáveis), e **não** renderiza
  "Rever Orçamento".
- **Mantido:** "✍ Assinar Contrato" (navega ao card 7 do Ciclo).
- Inputs continuam read-only (a etapa 6 segue concluída → `aplicarBloqueioNegociacao` ativo).
- **Status do projeto** (cabeçalho da page-02): dropdown desabilitado/oculto.
- A lógica vive em `atualizarBotoesAprovacao()` (já é o ponto central de UI pós-aprovação),
  estendida para consultar `_contratoAssinado`.

## Backend — recusar mutações quando assinado (HTTP 403)

Guard `_contrato_assinado(nome_safe, db)` nos handlers (retorna 403 com mensagem clara):
- `POST /projetos/<nome>/orcamentos` (novo orçamento)
- `POST /projetos/<nome>/pool` e `.../pool/sobrescrever|nova_versao|criar_forcado` (inserir XML/ambientes)
- `POST /orcamentos/<id>/ambientes/<pid>` e `.../remover` (add/remove ambiente)
- `PUT /projetos/<nome>/orcamentos/<oid>` (renomear orçamento)
- `PATCH /orcamentos/<id>/valor`, `POST /api/orcamentos/<id>/margens`, `PUT /api/orcamentos/<id>/descontos`
- `PATCH /api/projetos/<nome>/status` (alterar status do projeto)

(Valor/margens/descontos já caem no gate `bloqueado`; o check de assinatura é explícito e
permanente.)

## Status "Fechado"

- **Backend:** no handler de assinatura, no ponto em que `contrato.status = "assinado"` (loja +
  cliente assinaram), chamar `upsert_projeto_status(nome_safe, "fechado")`. Não entra em
  `VALIDOS` do `PATCH /status` (continua não-setável manualmente, como "convertido").
- **Frontend:**
  - `_PROJ_STATUS_LABEL`: adicionar `fechado: { label: '🔒 Fechado', cls: 'fechado' }`.
  - CSS: `.proj-status-badge.fechado` (cor distinta de convertido — terminal/assinado).
  - Badge render: tratar `fechado` (rótulo "🔒 Fechado").
  - Dropdown de status: ocultar/não permitir troca quando `fechado` (como `convertido` — linhas
    que checam `=== 'convertido'` passam a checar também `=== 'fechado'`).
  - Filtro de status (lista de projetos): adicionar item "🔒 Fechado".

## Testes

**Backend (pytest):**
- `_contrato_assinado`: sem contrato → False; rascunho/para_assinatura → False; com 1 assinatura
  ou status assinado_loja/assinado/vigente → True.
- Transição de status: ao assinar as duas partes, `upsert_projeto_status(..., "fechado")` é
  chamado (testar a função de transição/o efeito no `projetos_meta`).

**API real (verificação):** com contrato assinado, POST novo orçamento / pool / ambiente,
PATCH valor/status → **403**; sem assinatura → segue normal.

**Playwright (dados reais — ver [[gui-verification-playwright]]):** com contrato assinado,
confirmar que Salvar/Parâmetros/Ambientes/Novo Orçamento/Rever **não aparecem**, "Assinar
Contrato" permanece, status do projeto travado; após a 2ª assinatura, o badge do projeto mostra
**"Fechado"**.

## Fora de escopo (sub-projeto 3)

- Versionamento de documentos (novos documentos criam versões; não sobrescrevem/apagam).
