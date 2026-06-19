# Spec — Sub-projeto 1: Correções do ciclo

> Omie_V3 | Dalmóbile | Data: 2026-06-18
> Parte 1 de 4 da decomposição (itens 1 e 2). Status: aprovado para plano.

## Contexto

Dois ajustes independentes e de baixo risco no ciclo de vida do projeto:

1. **Gating de sub-etapas:** as sub-etapas do Projeto Executivo (`11a`–`11e`) e da
   Montagem (`17a`) aparecem **desbloqueadas antes** de o fluxo chegar à etapa-mãe.
   Causa raiz:
   - Frontend `_etapaBloqueada(codigo)`: para sub-etapa, `ETAPAS_PRINCIPAIS.indexOf("11a")`
     é `-1` → cai no `i <= 0` → retorna `false` (nunca bloqueada).
   - Backend `mod_ciclo.pode_avancar`: sub-etapa (não-principal) retorna sempre `True`
     ("sub-etapas são livres").

2. **Botão pós-aprovação:** após aprovar o orçamento, o botão na tela de negociação
   é `🔒 Orçamento aprovado – assinar contrato`, com estilo dourado próprio,
   diferente do botão `✎ Rever Orçamento` (ao lado).

## Decisões (confirmadas com o usuário)

- Sub-etapas desbloqueiam **junto com a etapa-mãe** (no momento em que a mãe fica
  disponível — i.e., quando a etapa anterior à mãe é concluída).
- A correção é **genérica**: qualquer sub-etapa `Nx` herda o gating da etapa-mãe `N`
  (cobre PE 11, Montagem 17 e futuras), sem casos especiais.
- O botão passa a se chamar **"Assinar Contrato"**, com estilo **idêntico** ao
  "Rever Orçamento" (contorno âmbar, `btn btn-ghost`).

## Detalhamento

### Item 1 — Gating de sub-etapas

**Regra:** uma sub-etapa `Nx` está bloqueada **se, e somente se**, a etapa-mãe `N`
está bloqueada. Assim, mãe e sub-etapas desbloqueiam no mesmo instante. A conclusão
das sub-etapas dentro da mãe e a reabertura em cascata permanecem inalteradas.

**Backend — `mod_ciclo.py`:**
- Novo helper `etapa_pai(codigo)`: retorna a etapa principal de uma sub-etapa
  (`"11a" → "11"`, `"17a" → "17"`), ou `None` se já for principal/sem pai.
  Implementação via `_parse_codigo` (parte numérica → `str(num)`), retornando esse
  código se ele estiver em `ETAPAS_PRINCIPAIS`.
- `pode_avancar(codigo, status_por_codigo)`: para sub-etapa, em vez de `return True`,
  passa a retornar `pode_avancar(etapa_pai(codigo), status_por_codigo)` (herda o
  gating da mãe). Se não houver pai identificável, mantém `True`.

**Frontend — `_etapaBloqueada(codigo)` (`static/index.html`):**
- Para sub-etapa (não está em `ETAPAS_PRINCIPAIS`), em vez de `return false`, calcular
  a etapa-mãe (parte numérica do código) e retornar `_etapaBloqueada(pai)`.
- A mãe continua bloqueada quando a etapa anterior a ela não está concluída
  (lógica atual preservada para etapas principais).

### Item 2 — Botão "Assinar Contrato"

Em `atualizarBotoesAprovacao()` (`static/index.html`), o botão `#btn-assinar-contrato`:
- **Texto:** `✍ Assinar Contrato` (remove "Orçamento aprovado –").
- **Estilo:** idêntico ao `#btn-rever-orcamento` — `className = 'btn btn-ghost'` e o
  mesmo `cssText` (contorno/cor `var(--warn,#c8a84b)`, `font-size:.85rem`,
  `font-weight:600`, `padding:8px 16px`, `border-radius:4px`, `cursor:pointer`).
- **Comportamento inalterado:** abre a aba Ciclo no card 7 (assinatura do contrato).

## Fora de escopo (YAGNI)

- Mudar a regra de conclusão das sub-etapas (continuam livres dentro da mãe).
- Qualquer alteração nos perfis, aprovação financeira ou medição (sub-projetos 2–4).

## Verificação

- **Backend (pytest, `tests/test_ciclo.py`):**
  - `etapa_pai("11a") == "11"`, `etapa_pai("17a") == "17"`, `etapa_pai("11") is None`.
  - `pode_avancar("11a", ...)` é `False` quando a etapa 10 não está concluída e
    `True` quando 10 está concluída (mesma resposta que `pode_avancar("11", ...)`).
- **Frontend (Playwright, dados reais):** abrir um projeto; antes de concluir a
  etapa 10, as sub-etapas 11a–11e aparecem 🔒 (bloqueadas); ao concluir a etapa 10,
  a etapa 11 e as sub-etapas desbloqueiam juntas. Botão pós-aprovação exibe
  "✍ Assinar Contrato" com o mesmo visual do "Rever Orçamento".
- Suíte completa permanece verde.

## Processo

Pipeline superpowers: spec → plano (writing-plans) → implementação com revisão a
nível de controlador → verificação (pytest + Playwright) → merge local.
