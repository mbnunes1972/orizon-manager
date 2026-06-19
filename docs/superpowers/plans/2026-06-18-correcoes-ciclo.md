# Correções do Ciclo (Sub-projeto 1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir o gating das sub-etapas (desbloqueiam junto com a etapa-mãe) e renomear o botão pós-aprovação para "Assinar Contrato" com o estilo do "Rever Orçamento".

**Architecture:** Backend `mod_ciclo.py` é a fonte da verdade do gating; o frontend (`static/index.html`) espelha a regra em `_etapaBloqueada`. A correção é genérica: qualquer sub-etapa `Nx` herda o gating da mãe `N`. O botão é ajustado em `atualizarBotoesAprovacao()`.

**Tech Stack:** Python (pytest) para o backend; HTML/JS vanilla + verificação Playwright para o frontend.

---

## File Structure

- **Modificar** `mod_ciclo.py` — novo `etapa_pai()`; `pode_avancar()` passa a aplicar o gating da mãe às sub-etapas.
- **Modificar** `tests/test_ciclo.py` — atualizar o teste que assume "sub-etapa sempre livre"; adicionar testes de `etapa_pai` e do novo gating.
- **Modificar** `static/index.html` — `_etapaBloqueada()` (sub-etapa herda a mãe) e `atualizarBotoesAprovacao()` (botão "Assinar Contrato").

> Frontend não tem harness JS: tarefas de frontend são *implementar → verificar com Playwright → commit*. Backend é TDD com pytest. Rodar `python -m pytest -q` ao fim de cada tarefa de backend e na verificação final.

---

## Task 1: Backend — `etapa_pai` + gating de sub-etapas

**Files:**
- Modify: `mod_ciclo.py` (`pode_avancar`; novo `etapa_pai`)
- Test: `tests/test_ciclo.py`

- [ ] **Step 1: Atualizar/escrever os testes**

Em `tests/test_ciclo.py`, **substituir** o teste existente `test_pode_avancar_subetapa_sempre_livre` (que codifica o comportamento antigo) por:

```python
def test_etapa_pai():
    assert mc.etapa_pai("11a") == "11"
    assert mc.etapa_pai("11e") == "11"
    assert mc.etapa_pai("17a") == "17"
    assert mc.etapa_pai("11") is None      # principal não tem "pai"
    assert mc.etapa_pai("1") is None


def test_pode_avancar_subetapa_herda_gating_da_mae():
    # Sub-etapa do PE (11x) segue o gating da etapa-mãe 11 (que exige a 10 concluída).
    assert mc.pode_avancar("11a", {"10": "pendente"}) is False
    assert mc.pode_avancar("11a", {}) is False
    assert mc.pode_avancar("11a", {"10": "concluido"}) is True
    # Mesma resposta que a etapa-mãe:
    for st in ({}, {"10": "pendente"}, {"10": "concluido"}, {"10": "entregue"}):
        assert mc.pode_avancar("11a", st) == mc.pode_avancar("11", st)
    # Sub-etapa da Montagem (17a) segue a 17 (que exige a 16 concluída).
    assert mc.pode_avancar("17a", {"16": "pendente"}) is False
    assert mc.pode_avancar("17a", {"16": "entregue"}) is True
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_ciclo.py::test_etapa_pai tests/test_ciclo.py::test_pode_avancar_subetapa_herda_gating_da_mae -v`
Expected: FAIL — `AttributeError: module 'mod_ciclo' has no attribute 'etapa_pai'` e/ou o gating antigo retorna `True`.

- [ ] **Step 3: Implementar `etapa_pai`**

Em `mod_ciclo.py`, adicionar após a função `is_principal` (ou junto dos helpers de código):

```python
def etapa_pai(codigo):
    """Etapa principal de uma sub-etapa ('11a' -> '11', '17a' -> '17').
    Retorna None se o código já for principal ou não tiver pai principal."""
    num, suf = _parse_codigo(codigo)
    if not suf:                      # já é principal (sem sufixo)
        return None
    pai = str(num)
    return pai if pai in ETAPAS_PRINCIPAIS else None
```

- [ ] **Step 4: Aplicar o gating da mãe em `pode_avancar`**

Em `mod_ciclo.py`, substituir o início de `pode_avancar`:

```python
def pode_avancar(codigo, status_por_codigo):
    """
    True se a etapa pode sair de 'pendente' (iniciar/concluir).
    Sub-etapas herdam o gating da etapa-mãe (desbloqueiam junto com ela).
    Principais exigem a anterior concluída.
    """
    if codigo not in ETAPAS_PRINCIPAIS:
        pai = etapa_pai(codigo)
        if pai is None:
            return True
        return pode_avancar(pai, status_por_codigo)
    ant = etapa_anterior(codigo)
    if ant is None:
        return True
    return status_por_codigo.get(ant) in STATUS_CONCLUSIVOS
```

- [ ] **Step 5: Rodar os testes da Task 1**

Run: `python -m pytest tests/test_ciclo.py -q`
Expected: PASS (incluindo os dois novos; o antigo "sempre livre" não existe mais).

- [ ] **Step 6: Rodar a suíte completa**

Run: `python -m pytest -q`
Expected: PASS, sem regressões.

- [ ] **Step 7: Commit**

```bash
git add mod_ciclo.py tests/test_ciclo.py
git commit -m "fix(ciclo): sub-etapas herdam o gating da etapa-mae (etapa_pai + pode_avancar)"
```

---

## Task 2: Frontend — `_etapaBloqueada` herda a etapa-mãe

**Files:**
- Modify: `static/index.html` (`_etapaBloqueada`)

- [ ] **Step 1: Substituir `_etapaBloqueada`**

Localizar (Grep `function _etapaBloqueada`) e substituir a função inteira por:

```javascript
function _etapaBloqueada(codigo) {
  const i = ETAPAS_PRINCIPAIS.indexOf(codigo);
  if (i < 0) {
    // sub-etapa: herda o bloqueio da etapa-mãe (desbloqueia junto com ela)
    const pai = String(parseInt(codigo, 10));
    if (pai === codigo || ETAPAS_PRINCIPAIS.indexOf(pai) < 0) return false;
    return _etapaBloqueada(pai);
  }
  if (i === 0) return false;                 // primeira etapa nunca bloqueada
  const ant = ETAPAS_PRINCIPAIS[i - 1];
  return !STATUS_CONCLUSIVOS.has(_cicloData[ant]?.status);
}
```

- [ ] **Step 2: Sanity check do arquivo**

Run: `python -c "h=open('static/index.html',encoding='utf-8').read(); print('defs _etapaBloqueada:', h.count('function _etapaBloqueada'))"`
Expected: `1`.

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "fix(ciclo-front): sub-etapas herdam o bloqueio da etapa-mae em _etapaBloqueada"
```

---

## Task 3: Frontend — botão "Assinar Contrato"

**Files:**
- Modify: `static/index.html` (`atualizarBotoesAprovacao`, criação de `#btn-assinar-contrato`)

- [ ] **Step 1: Ajustar o botão**

Localizar (Grep `btn-assinar-contrato`) o bloco de criação. Substituir as três linhas do `#btn-assinar-contrato`:

```javascript
      btn.id = 'btn-assinar-contrato';
      btn.style.cssText = 'color:#1a1200;background:#b8960c;border:none;font-size:.85rem;font-weight:600;padding:8px 16px;border-radius:4px;cursor:pointer';
      btn.innerHTML = '&#x1F512; Or&ccedil;amento aprovado &ndash; assinar contrato';
```

por:

```javascript
      btn.id = 'btn-assinar-contrato';
      btn.className = 'btn btn-ghost';
      btn.style.cssText = 'border-color:var(--warn,#c8a84b);color:var(--warn,#c8a84b);font-size:.85rem;font-weight:600;padding:8px 16px;border-radius:4px;cursor:pointer';
      btn.innerHTML = '&#x270D; Assinar Contrato';
```

(o `onclick` e o `appendChild` logo abaixo permanecem inalterados.)

- [ ] **Step 2: Sanity check**

Run: `python -c "h=open('static/index.html',encoding='utf-8').read(); print('Assinar Contrato:', 'Assinar Contrato' in h); print('texto antigo removido:', 'Or&ccedil;amento aprovado &ndash; assinar' not in h)"`
Expected: `True` e `True`.

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat(negociacao): botao 'Assinar Contrato' com estilo do 'Rever Orcamento'"
```

---

## Task 4: Verificação integrada (dados reais)

**Files:** nenhuma alteração (apenas verificação); corrigir inline se algo falhar.

- [ ] **Step 1: Suíte completa**

Run: `python -m pytest -q`
Expected: PASS (todos verdes).

- [ ] **Step 2: Verificação Playwright (servidor real)**

Reiniciar o servidor (matar listeners da 8765, `python main.py`), logar (`pdm2026`/`teste123`), abrir um projeto e na aba Ciclo confirmar:
1. Antes de a etapa 10 estar concluída, as sub-etapas **11a–11e** aparecem com cadeado 🔒 (bloqueadas) — não mais abertas.
2. Ao concluir a etapa 10, a etapa **11** e as sub-etapas **11a–11e** desbloqueiam **juntas**.
3. O mesmo para **17a** em relação à etapa 17.
4. Após aprovar um orçamento, o botão na tela de negociação mostra **"✍ Assinar Contrato"** com o **mesmo visual** do "Rever Orçamento" (contorno âmbar), e clicá-lo abre o card 7 (assinatura).

> Para inspecionar o bloqueio sem clicar manualmente, pode-se avaliar no navegador `_etapaBloqueada('11a')` com `_cicloData` simulando a etapa 10 pendente/concluída.

- [ ] **Step 3: Atualizar DEV_LOG.md**

Adicionar entrada da sessão descrevendo: gating de sub-etapas herdado da mãe; botão "Assinar Contrato".

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md
git commit -m "docs: atualiza DEV_LOG (correcoes do ciclo — gating sub-etapas + botao Assinar Contrato)"
```

---

## Self-Review (cobertura do spec)

- **Item 1 (gating sub-etapas, genérico, desbloqueia com a mãe)** → Task 1 (backend) + Task 2 (frontend). ✓
- **Item 2 (botão "Assinar Contrato", estilo idêntico ao "Rever Orçamento")** → Task 3. ✓
- **Verificação pytest + Playwright** → Task 4. ✓
- **Consistência de nomes:** `etapa_pai`, `pode_avancar`, `_etapaBloqueada`, `#btn-assinar-contrato`, `btn btn-ghost` + `var(--warn,#c8a84b)` — usados de forma idêntica entre as tarefas.
- **Sem placeholders.** Teste antigo `test_pode_avancar_subetapa_sempre_livre` é explicitamente substituído (não fica órfão).
