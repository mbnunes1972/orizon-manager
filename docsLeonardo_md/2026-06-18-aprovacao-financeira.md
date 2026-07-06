# Aprovação Financeira Gerencial (Sub-projeto 3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Concluir as etapas de aprovação financeira (8 "Aprovação financeira I" e 11d "Aprovação financeira II") passa a exigir login+senha de um perfil com `aprovar_financeiro` (Diretor ou Gerente Adm/Financeiro), com auditoria.

**Architecture:** Nova capacidade `aprovar_financeiro` em `perfis.py`; o conjunto de etapas financeiras vive em `mod_ciclo.py`; o gate é aplicado no handler `PATCH /api/projetos/<nome>/ciclo/<codigo>` de `main.py`; o frontend pede credenciais via o popup `pedirCredenciaisGerente` existente.

**Tech Stack:** Python (pytest p/ funções puras), HTML/JS vanilla; endpoint verificado via API real (curl), no estilo do projeto.

---

## File Structure

- **Modificar** `perfis.py` — flag `aprovar_financeiro` em cada perfil + `_DEFAULT`.
- **Modificar** `mod_ciclo.py` — `ETAPAS_APROVACAO_FINANCEIRA` + `exige_aprovacao_financeira()`.
- **Modificar** `main.py` — helper `_aprovador_financeiro` + gate no PATCH `/ciclo/<codigo>` + auditoria.
- **Modificar** `static/index.html` — `_renderCardAprovacaoFinanceira(codigo,...)`, dispatch da 11d, `concluirAprovacaoFinanceira(codigo)` com popup de credenciais.

> Backend puro = TDD (pytest). Endpoint e frontend = implementar → verificar via API real (curl)/inspeção, no estilo do projeto. Rodar `python -m pytest -q` ao fim de cada tarefa de backend.

---

## Task 1: `perfis.py` — capacidade `aprovar_financeiro`

**Files:**
- Modify: `perfis.py`
- Test: `tests/test_perfis.py`

- [ ] **Step 1: Escrever o teste (TDD)**

Acrescentar a `tests/test_perfis.py`:

```python
def test_capacidade_aprovar_financeiro():
    assert perfis.pode("diretor", "aprovar_financeiro") is True
    assert perfis.pode("gerente_adm_fin", "aprovar_financeiro") is True
    assert perfis.pode("gerente_vendas", "aprovar_financeiro") is False
    assert perfis.pode("consultor", "aprovar_financeiro") is False
    assert perfis.pode("medidor", "aprovar_financeiro") is False
    assert perfis.pode("inexistente", "aprovar_financeiro") is False
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_perfis.py::test_capacidade_aprovar_financeiro -v`
Expected: FAIL (a flag ainda não existe → `pode(...)` retorna False para diretor/adm_fin, quebrando os dois primeiros asserts).

- [ ] **Step 3: Adicionar a flag `aprovar_financeiro`**

Em `perfis.py`, adicionar a chave `"aprovar_financeiro"` a CADA perfil em `PERFIS` e ao `_DEFAULT`:
- `diretor` e `gerente_adm_fin` → `True`.
- Todos os demais (gerente_vendas, consultor, assistente_logistico, conferente, supervisor_montagem, assistente_administrativo, projetista_executivo, medidor) e `_DEFAULT` → `False`.

Exemplo (diretor e um operacional):
```python
    "diretor":          {"rotulo": "Diretor", "desconto_max": 50.0, "ver_parametros": True,  "autorizar": True,  "gerir_usuarios": True,  "aprovar_financeiro": True},
    "gerente_adm_fin":  {"rotulo": "Gerente Administrativo/Financeiro", "desconto_max": 0.0, "ver_parametros": True, "autorizar": False, "gerir_usuarios": True, "aprovar_financeiro": True},
    "gerente_vendas":   {"rotulo": "Gerente de Vendas", "desconto_max": 20.0, "ver_parametros": True, "autorizar": True, "gerir_usuarios": False, "aprovar_financeiro": False},
    "medidor":          {"rotulo": "Medidor", "desconto_max": 0.0, "ver_parametros": False, "autorizar": False, "gerir_usuarios": False, "aprovar_financeiro": False},
```
E `_DEFAULT`:
```python
_DEFAULT = {"rotulo": "—", "desconto_max": 0.0, "ver_parametros": False,
            "autorizar": False, "gerir_usuarios": False, "aprovar_financeiro": False}
```
(Adicionar `"aprovar_financeiro": False` aos demais perfis também.)

- [ ] **Step 4: Rodar testes**

Run: `python -m pytest tests/test_perfis.py -q` → PASS.
Run: `python -m pytest -q` → PASS (sem regressões).

- [ ] **Step 5: Commit**

```bash
git add perfis.py tests/test_perfis.py
git commit -m "feat(perfis): capacidade aprovar_financeiro (diretor + gerente_adm_fin)"
```

---

## Task 2: `mod_ciclo.py` — etapas de aprovação financeira

**Files:**
- Modify: `mod_ciclo.py`
- Test: `tests/test_ciclo.py`

- [ ] **Step 1: Escrever o teste (TDD)**

Acrescentar a `tests/test_ciclo.py`:

```python
def test_exige_aprovacao_financeira():
    assert mc.exige_aprovacao_financeira("8") is True
    assert mc.exige_aprovacao_financeira("11d") is True
    assert mc.exige_aprovacao_financeira("7") is False
    assert mc.exige_aprovacao_financeira("11") is False
    assert mc.exige_aprovacao_financeira("9") is False
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_ciclo.py::test_exige_aprovacao_financeira -v`
Expected: FAIL (`AttributeError: module 'mod_ciclo' has no attribute 'exige_aprovacao_financeira'`).

- [ ] **Step 3: Implementar**

Em `mod_ciclo.py`, adicionar (após `STATUS_CONCLUSIVOS`):

```python
# Etapas que exigem autorização financeira (login+senha de quem pode aprovar).
ETAPAS_APROVACAO_FINANCEIRA = frozenset({"8", "11d"})


def exige_aprovacao_financeira(codigo):
    return codigo in ETAPAS_APROVACAO_FINANCEIRA
```

- [ ] **Step 4: Rodar testes**

Run: `python -m pytest tests/test_ciclo.py -q` → PASS.
Run: `python -m pytest -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_ciclo.py tests/test_ciclo.py
git commit -m "feat(ciclo): conjunto de etapas de aprovacao financeira (8, 11d)"
```

---

## Task 3: `main.py` — gate de aprovação financeira no PATCH `/ciclo/<codigo>`

**Files:**
- Modify: `main.py` (helper `_aprovador_financeiro` + handler PATCH `^/api/projetos/([^/]+)/ciclo/([^/]+)$`)

> Verificação via API real (curl) na Task 5. `perfis`, `mod_ciclo`, `Usuario`, `LogAcaoGerencial` já estão importados em `main.py`.

- [ ] **Step 1: Adicionar o helper `_aprovador_financeiro`**

Em `main.py`, adicionar um helper de módulo (perto de outros helpers, ex.: antes da classe `Handler`):

```python
def _aprovador_financeiro(db, login, senha):
    """Retorna o Usuario apto a aprovar financeiro (ativo, senha correta e perfil com
    'aprovar_financeiro') ou None."""
    u = db.query(Usuario).filter_by(login=(login or "").strip()).first()
    if not u or not u.ativo or not u.check_senha(senha or ""):
        return None
    if not perfis.pode(u.nivel, "aprovar_financeiro"):
        return None
    return u
```

- [ ] **Step 2: Aplicar o gate no handler PATCH `/ciclo/<codigo>`**

Localizar (Grep `ciclo/([^/]+)$`) o handler. Após o bloco de gating sequencial (o `if not mod_ciclo.pode_avancar(...)` que retorna 400) e ANTES do `if novo_status:`, inserir:

```python
                    # Aprovação financeira (8/11d): exige login+senha de quem pode aprovar.
                    aprovador = None
                    if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and mod_ciclo.exige_aprovacao_financeira(etapa_cod):
                        aprovador = _aprovador_financeiro(db, req.get("login", ""), req.get("senha", ""))
                        if not aprovador:
                            self.send_json({
                                "ok": False,
                                "erro": "Apenas Gerente Administrativo/Financeiro ou Diretor podem "
                                        "aprovar a etapa financeira (login/senha inválidos ou sem permissão).",
                            }, code=403)
                            return
```

Em seguida, no bloco `if novo_status:`, trocar a linha que define `responsavel_id` para usar o aprovador quando houver:

```python
                        if novo_status in mod_ciclo.STATUS_CONCLUSIVOS:
                            etapa.concluido_em  = datetime.utcnow()
                            etapa.responsavel_id = aprovador.id if aprovador else usuario["id"]
```

E ANTES do `db.commit()`, registrar a auditoria quando houver aprovador:

```python
                    if aprovador is not None:
                        db.add(LogAcaoGerencial(
                            solicitante_id=usuario["id"],
                            autorizador_id=aprovador.id,
                            acao="aprovar_financeiro",
                            projeto_nome=nome_safe,
                            etapa_alvo=etapa_cod,
                        ))
```

- [ ] **Step 3: Sanity de import**

Run: `python -c "import main; print('main OK')"` → `main OK`.
Run: `python -m pytest -q` → PASS (não tocou em código testado por unidade).

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(ciclo): aprovacao financeira (8/11d) exige login+senha autorizado + auditoria"
```

---

## Task 4: Frontend — popup de credenciais nas etapas financeiras

**Files:**
- Modify: `static/index.html` (dispatch do card ~6558-6562; `_renderCardAprovacaoFinanceira`; `concluirAprovacaoFinanceira`)

- [ ] **Step 1: Rotear a 11d para o card financeiro**

Localizar (Grep `_renderCardAprovacaoFinanceira(dados, bloqueada)`) o dispatch:
```javascript
          : etapa.codigo === '8'
            ? _renderCardAprovacaoFinanceira(dados, bloqueada)
            : _renderCardGenerico(etapa, dados, bloqueada)}
```
Substituir por (passando o código):
```javascript
          : (etapa.codigo === '8' || etapa.codigo === '11d')
            ? _renderCardAprovacaoFinanceira(etapa.codigo, dados, bloqueada)
            : _renderCardGenerico(etapa, dados, bloqueada)}
```

- [ ] **Step 2: Parametrizar `_renderCardAprovacaoFinanceira` por código**

Localizar `function _renderCardAprovacaoFinanceira(dados, bloqueada)` e substituir a assinatura e os usos de código fixo:
```javascript
function _renderCardAprovacaoFinanceira(codigo, dados, bloqueada) {
  const concluido = dados.status === 'concluido';
  if (concluido) {
    const dt = dados.concluido_em
      ? new Date(dados.concluido_em).toLocaleDateString('pt-BR')
      : '';
    const reabrir = codigo === '8'
      ? `<button onclick="abrirModalReabrir('8')"
           style="border:1px solid var(--muted);color:var(--muted);background:none;
           border-radius:5px;padding:6px 14px;font-size:.8rem;cursor:pointer">
           🔓 Reabrir (gerente)</button>`
      : '';
    return `
      <p style="color:var(--ok);margin:0 0 10px">
        &#x2713; Aprovação financeira concluída${dt ? ' em ' + dt : ''}.
      </p>${reabrir}`;
  }
  if (bloqueada) {
    return `
      <p style="color:var(--muted);font-size:.85rem;margin:0">
        🔒 Conclua a etapa anterior para liberar esta etapa.
      </p>`;
  }
  return `
    <p style="color:var(--muted);font-size:.85rem;margin:0 0 14px">
      Confirme a aprovação financeira. Exige login e senha do Gerente Administrativo/Financeiro ou Diretor.
    </p>
    <button onclick="concluirAprovacaoFinanceira('${codigo}')"
      style="background:#b8960c;color:#000;border:none;border-radius:6px;
      padding:8px 18px;font-size:.9rem;font-weight:700;cursor:pointer">
      &#x2713; Aprovar (gerencial)
    </button>`;
}
```

- [ ] **Step 3: Generalizar `concluirAprovacaoFinanceira(codigo)` com credenciais**

Substituir a função `concluirAprovacaoFinanceira()` por:
```javascript
async function concluirAprovacaoFinanceira(codigo) {
  if (!projetoAtivo) return;
  const cred = await pedirCredenciaisGerente({
    titulo: 'Aprovação Financeira',
    mensagem: 'Login e senha do Gerente Administrativo/Financeiro ou Diretor.' });
  if (!cred) return;
  try {
    const r = await fetch(
      `/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/${encodeURIComponent(codigo)}`,
      { method: 'PATCH', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'concluido', login: cred.login, senha: cred.senha }) });
    const d = await r.json();
    if (!d.ok) { await avisoPopup(d.erro || 'Falha na aprovação', {titulo:'Aprovação Financeira'}); return; }
    showToast('Aprovação financeira concluída!', false);
    await carregarCiclo();
  } catch(e) { await avisoPopup('Erro de rede: ' + e.message, {titulo:'Aprovação Financeira'}); }
}
```

- [ ] **Step 4: Sanity**

Run: `python -c "h=open('static/index.html',encoding='utf-8').read(); print('card codigo param:', '_renderCardAprovacaoFinanceira(codigo' in h); print('dispatch 11d:', \"etapa.codigo === '11d'\" in h); print('concluir codigo:', 'concluirAprovacaoFinanceira(codigo)' in h or \"concluirAprovacaoFinanceira('\" in h)"`
Expected: `True`, `True`, `True`. Ler ~6 linhas em torno de cada edição para confirmar JS válido.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(ciclo-front): aprovacao financeira (8/11d) pede login+senha (popup credenciais)"
```

---

## Task 5: Verificação integrada (API real) + DEV_LOG

**Files:** nenhuma alteração de código; corrigir inline se algo falhar.

- [ ] **Step 1: Suíte completa**

Run: `python -m pytest -q` → PASS.

- [ ] **Step 2: Subir o servidor + cenário via curl**

Reiniciar o servidor (matar listeners 8765, `python main.py`). Usar um projeto existente com a etapa 7 concluída (para a 8 estar liberada). Para cada cenário, logar como Diretor para manipular o ciclo e usar o endpoint de aprovação com credenciais variadas:

1. **Gerente de vendas recusado:** `PATCH /ciclo/8 {status:'concluido', login:'lds2026', senha:'teste234'}` → HTTP 403, erro de permissão.
2. **Senha errada recusada:** `... login:'gaf2026', senha:'errada'` → 403.
3. **Gerente Adm/Fin aprova:** `... login:'gaf2026', senha:'teste456'` → ok; etapa 8 concluída; `responsavel_id` = id do gaf2026.
4. **Diretor aprova a 11d** (com a etapa 11 liberada): `PATCH /ciclo/11d {status:'concluido', login:'pdm2026', senha:'teste123'}` → ok.
5. **Auditoria:** conferir no banco que há linhas em `log_acoes_gerenciais` com `acao='aprovar_financeiro'` para as aprovações.

> Restaurar o estado do projeto de teste ao final (reabrir/limpar etapas criadas), conforme a memória de verificação.

- [ ] **Step 3: Atualizar DEV_LOG.md**

Adicionar entrada do sub-projeto 3 (aprovação financeira gerencial: capacidade `aprovar_financeiro`, gate nas etapas 8/11d, auditoria).

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md
git commit -m "docs: atualiza DEV_LOG (sub-projeto 3 — aprovacao financeira gerencial)"
```

---

## Self-Review (cobertura do spec)

- **Capacidade `aprovar_financeiro` (diretor + gerente_adm_fin; vendas não)** → Task 1. ✓
- **Etapas 8 e 11d como financeiras** → Task 2. ✓
- **Gate backend (login+senha+capacidade → 403; responsável; auditoria)** → Task 3. ✓
- **Frontend popup de credenciais nas duas etapas; 11d roteada ao card financeiro** → Task 4. ✓
- **Verificação pytest + API real (vendas 403; adm_fin/diretor ok; senha errada; auditoria)** → Task 5. ✓
- **Consistência de nomes:** `aprovar_financeiro`, `exige_aprovacao_financeira`, `ETAPAS_APROVACAO_FINANCEIRA`, `_aprovador_financeiro`, `concluirAprovacaoFinanceira(codigo)`, `_renderCardAprovacaoFinanceira(codigo,...)` — idênticos entre tarefas.
- **Sem placeholders.**
