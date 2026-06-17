# Semântica de Aprovação + Botão de Assinatura — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer "Aprovar Orçamento" concluir as etapas 5 (Revisão) e 6 (Aprovação) juntas, remover o toggle manual da etapa 5, e transformar o rótulo pós-aprovação num botão clicável "Orçamento aprovado – assinar contrato" que leva ao card de assinatura.

**Architecture:** O endpoint de contrato (que já marca etapa 6 + 7) passa a marcar a etapa 5 também; `desfazer_aprovacao` reseta 5/6/7. No frontend, a etapa 5 perde `toggleavel` (sem botão de concluir) e ganha uma nota; e o rótulo `#label-aprovado` vira um botão `#btn-assinar-contrato` que chama `abrirCiclo()` + `toggleCicloCard('7')`.

**Tech Stack:** Python 3 `http.server` + SQLAlchemy; frontend HTML/CSS/JS vanilla (`static/index.html`, sem harness JS). Verificação de runtime via API/Playwright na fase final.

**Spec:** `docs/superpowers/specs/2026-06-17-aprovacao-semantica-botao-design.md`
**Branch:** `feat/aprovacao-semantica-botao` (já criada).

**Nota sobre testes:** as mudanças de backend são marcações de etapa *inline* num handler HTTP — o projeto não tem harness HTTP e esses handlers não são cobertos por unit tests (convenção do repo; os *helpers* puros é que são testados). Portanto Task 1 garante suíte verde + sintaxe, e o comportamento end-to-end (5+6 concluídas; desfazer reseta 5) é confirmado na **fase de verificação final** via drive de API/Playwright (como no Sub-projeto B). Tasks 2/3 (frontend) seguem o mesmo padrão: integridade de sintaxe + verificação manual/Playwright.

---

## File Structure

| Arquivo | Mudança |
|---|---|
| `main.py` | endpoint `POST .../contrato` marca etapa 5 (além de 6/7); `desfazer_aprovacao` deleta a etapa 5 também |
| `static/index.html` | remove `toggleavel` da etapa 5 + nota no card; `atualizarBotoesAprovacao` cria botão clicável `#btn-assinar-contrato` |

---

## Task 1: Backend — aprovação conclui etapa 5; desfazer reseta etapa 5

**Files:**
- Modify: `main.py` (endpoint de contrato ~`2105-2116`; `desfazer_aprovacao` ~`1864-1868`)

- [ ] **Step 1: Marcar etapa 5 ao gerar o contrato**

Em `main.py`, no handler `POST /api/projetos/<nome>/contrato`, encontre (atualmente ~linha 2105-2106):

```python
                    contrato.status = "para_assinatura"
                    # Marcar etapa 6 (Aprovação do orçamento) como concluída
                    etapa6 = db.query(CicloEtapa).filter_by(
```

Insira um bloco de marcação da etapa 5 ENTRE a linha `contrato.status = "para_assinatura"` e o comentário `# Marcar etapa 6`:

```python
                    contrato.status = "para_assinatura"
                    # Marcar etapa 5 (Revisão de projeto) como concluída — a aprovação
                    # conclui Revisão e Aprovação juntas.
                    etapa5 = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo="5"
                    ).first()
                    if not etapa5:
                        etapa5 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="5")
                        db.add(etapa5)
                    etapa5.status         = "concluido"
                    etapa5.concluido_em   = datetime.utcnow()
                    etapa5.responsavel_id = usuario["id"]
                    # Marcar etapa 6 (Aprovação do orçamento) como concluída
                    etapa6 = db.query(CicloEtapa).filter_by(
```

(O `db.commit()` existente logo após o bloco da etapa 6 — atualmente ~linha 2116 — persiste as etapas 5 e 6 juntas.)

- [ ] **Step 2: `desfazer_aprovacao` reseta a etapa 5 também**

Em `main.py`, no handler `desfazer_aprovacao`, encontre (atualmente ~linha 1864-1868):

```python
                    # Resetar etapa 6 (e 7 se existir sem assinatura)
                    e6 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="6").first()
                    if e6: db.delete(e6)
                    e7 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="7").first()
                    if e7: db.delete(e7)
```

Substitua por (adiciona o reset da etapa 5; deletar a linha = volta a "pendente", consistente com o padrão existente):

```python
                    # Resetar etapas 5, 6 e 7 (a aprovação concluiu 5+6 e iniciou a 7)
                    e5 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="5").first()
                    if e5: db.delete(e5)
                    e6 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="6").first()
                    if e6: db.delete(e6)
                    e7 = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="7").first()
                    if e7: db.delete(e7)
```

- [ ] **Step 3: Verify**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('syntax ok')"` → `syntax ok`
Run: `python -c "import main; print('import ok')"` → `import ok`
Run: `python -X utf8 -m pytest tests/ -q` → all pass (68; backend handlers aren't unit-tested, so the count is unchanged — this confirms no regression).

Self-check: confirm the etapa-5 block mirrors the etapa-6 block exactly (same query/create/status/concluido_em/responsavel_id) and sits before the etapa-6 block so the existing `db.commit()` covers both; confirm `desfazer_aprovacao` now deletes e5, e6, e7.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(aprovacao): gerar contrato conclui etapa 5 (Revisao) junto da 6; desfazer reseta 5/6/7"
```

---

## Task 2: Frontend — etapa 5 sem toggle manual + nota no card

**Files:**
- Modify: `static/index.html` — `ETAPAS_CICLO` (~`6122`); `_renderCardGenerico` (~`6284`)

- [ ] **Step 1: Remover `toggleavel` da etapa 5**

Em `static/index.html`, na constante `ETAPAS_CICLO`, encontre a linha da etapa 5 (atualmente ~6122):

```javascript
  { codigo: "5",   nome: "Revisão de projeto",                 sub: false, toggleavel: true },
```

Substitua por (remove `, toggleavel: true` — sem ele, o card não renderiza o botão "Marcar como Concluída"):

```javascript
  { codigo: "5",   nome: "Revisão de projeto",                 sub: false },
```

- [ ] **Step 2: Nota explicativa no card da etapa 5**

Em `static/index.html`, na função `function _renderCardGenerico(etapa, dados, bloqueada) {` (atualmente ~6284), que tem casos especiais para `etapa.codigo === '1'` e `'3'` antes do `return` genérico, adicione um novo caso especial para a etapa 5 **imediatamente antes do `return` genérico final** (o que renderiza a textarea de observações). Use exatamente:

```javascript
  // Card especial etapa 5 — Revisão: concluída apenas pela aprovação do orçamento
  if (etapa.codigo === '5' && !concluido) {
    return `
      <div style="font-size:.85rem;color:var(--muted);line-height:1.7">
        Em revis&atilde;o. Esta etapa &eacute; conclu&iacute;da automaticamente ao clicar
        <strong style="color:var(--text)">Aprovar Or&ccedil;amento</strong> na aba Negocia&ccedil;&atilde;o.
      </div>`;
  }
```

(`concluido` já é declarado no topo da função como `dados.status === 'concluido'`. Quando a etapa 5 estiver concluída, cai no render genérico normal com o ✓.)

- [ ] **Step 3: Verify**

- Grep: `toggleavel` na etapa 5 não deve mais existir — confirme que a linha do `codigo: "5"` não contém `toggleavel`.
- Confirme exatamente um par `<script>`/`</script>` e paridade de crases (backticks) par no arquivo.
- Run: `python -X utf8 -m pytest tests/ -q` → all pass (68; frontend não afeta Python).

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(aprovacao): etapa 5 sem toggle manual; nota 'em revisao' no card"
```

---

## Task 3: Frontend — botão pós-aprovação clicável "assinar contrato"

**Files:**
- Modify: `static/index.html` — `atualizarBotoesAprovacao` (~`6205-6228`)

- [ ] **Step 1: Trocar o rótulo por um botão clicável**

Em `static/index.html`, na função `atualizarBotoesAprovacao()`, encontre o corpo `if (aprovado) { ... } else { ... }` (atualmente ~6211-6227):

```javascript
  if (aprovado) {
    if (btnSalvar)  { btnSalvar.style.display  = 'none'; }
    if (btnAprovar) { btnAprovar.style.display = 'none'; }
    // Mostrar label informativo se ainda não existe
    if (!actionRow.querySelector('#label-aprovado')) {
      const label = document.createElement('span');
      label.id = 'label-aprovado';
      label.style.cssText = 'color:#f0c84a;font-size:.85rem;padding:6px 12px;border:1px solid #b8960c;border-radius:4px;background:#1a1200';
      label.innerHTML = '&#x1F512; Or&ccedil;amento aprovado &mdash; em gera&ccedil;&atilde;o de contrato';
      actionRow.appendChild(label);
    }
  } else {
    if (btnSalvar)  { btnSalvar.style.display  = ''; }
    if (btnAprovar) { btnAprovar.style.display = ''; }
    const label = actionRow.querySelector('#label-aprovado');
    if (label) label.remove();
  }
```

Substitua por (rótulo vira botão clicável que leva ao card de assinatura — etapa 7):

```javascript
  if (aprovado) {
    if (btnSalvar)  { btnSalvar.style.display  = 'none'; }
    if (btnAprovar) { btnAprovar.style.display = 'none'; }
    // Botão clicável que leva à assinatura do contrato (etapa 7 no Ciclo)
    if (!actionRow.querySelector('#btn-assinar-contrato')) {
      const btn = document.createElement('button');
      btn.id = 'btn-assinar-contrato';
      btn.style.cssText = 'color:#1a1200;background:#b8960c;border:none;font-size:.85rem;font-weight:600;padding:8px 16px;border-radius:4px;cursor:pointer';
      btn.innerHTML = '&#x1F512; Or&ccedil;amento aprovado &ndash; assinar contrato';
      btn.onclick = () => { abrirCiclo(); setTimeout(() => toggleCicloCard('7'), 300); };
      actionRow.appendChild(btn);
    }
  } else {
    if (btnSalvar)  { btnSalvar.style.display  = ''; }
    if (btnAprovar) { btnAprovar.style.display = ''; }
    const b = actionRow.querySelector('#btn-assinar-contrato');
    if (b) b.remove();
  }
```

(`abrirCiclo` e `toggleCicloCard` já existem — são os mesmos usados por `gerarContrato()` no sucesso. O destino `toggleCicloCard('7')` abre o card do contrato com o PDF e os botões de assinatura.)

- [ ] **Step 2: Verify**

- Grep: `#label-aprovado` não deve ter mais ocorrências; `#btn-assinar-contrato` deve aparecer (criação + remoção + querySelector).
- Confirme um par `<script>`/`</script>` e crases par.
- Run: `python -X utf8 -m pytest tests/ -q` → all pass (68).

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat(aprovacao): botao clicavel 'assinar contrato' leva ao card de assinatura"
```

---

## Final verification (fase /verify ao fim)

- [ ] **Run full suite:** `python -X utf8 -m pytest tests/ -q` → 68 pass.
- [ ] **Runtime drive (API):** start `python main.py`; login; `POST /api/projetos/<proj>/contrato` para um projeto com cadastro **completo** → `GET /api/projetos/<proj>/ciclo` mostra etapas **5 e 6** `concluido` e **7** `em_andamento`. Depois `POST .../ciclo/desfazer_aprovacao` (gerente) → etapas 5/6/7 ausentes (resetadas).
- [ ] **GUI drive (Playwright):** após aprovar, o botão "Orçamento aprovado – assinar contrato" aparece e, ao clicar, abre o card 7 (assinatura). A etapa 5 no Ciclo não tem botão "Marcar como Concluída".
- [ ] **Cleanup:** apagar dados de teste criados, parar o servidor.

---

## Notas de escopo (fora deste plano)
- **D** — Briefing obrigatório após criação do projeto.
- Limpeza opcional: coluna vestigial `contrato.endereco_instalacao`.
