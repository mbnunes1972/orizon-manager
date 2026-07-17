# Fase 2 — Funcionários no módulo Folha — Plano

> Frontend (sem teste JS → `node --check` + verificação manual). O backend `/api/funcionarios` (GET/POST via `func_serialize/func_aplicar`) **já existe** — só reexpomos a UI. Spec: `docs/superpowers/specs/2026-07-17-remuneracoes-folha-design.md`.

**Goal:** o módulo **Folha de Pagamento** ganha uma sub-aba **"Funcionários"** (as pessoas a pagar), reusando o CRUD de cadastro existente, **sem** campos de salário (vem da Função, Fase 1). O Cadastro segue sem Funcionários (item 3 mantido).

**Base:** `main`. **Estratégia:** reaproveitar o modal compartilhado (`cadEntNovo/cadEntEditar/cadEntSalvar`) + `cadEntCarregar('funcionarios')`, relocando o painel `cad-panel-funcionarios` (hoje órfão em `page-10`) para dentro da Folha.

---

## Task F2.1 (frontend): remover salário do form de Funcionário
**Files:** `static/index.html` (`_CAD_DEFS.funcionarios`).
- [ ] No `_CAD_DEFS.funcionarios.campos`, **remover** as 3 linhas de remuneração:
  ```
  {id:'remuneracao_tipo', ...}, {id:'remuneracao_fixa', ...}, {id:'remuneracao_var', ...}
  ```
  Manter nome/cpf/telefone/email/funcao_id/cargo/status + endereço + banco + `acesso:true` (a ligação Funcionário↔Usuário permanece). _(As colunas `remuneracao_*` do modelo ficam legado; a Folha lê da Função.)_
- [ ] `node --check` → JS_OK.

## Task F2.2 (frontend): sub-aba "Funcionários" no módulo Folha
**Files:** `static/index.html` (painel Folha + `page-10`).
- [ ] **Relocar o container:** remover de `page-10` o `<div id="cad-panel-funcionarios" style="display:none">…</div>` (linha ~1343; hoje órfão pois o item 3 tirou a aba do Cadastro).
- [ ] **Reestruturar o painel Folha** (`#folha-box`): novo `folhaCarregar()` (entry da seção) renderiza uma barra de **sub-abas** + dois contêineres:
  ```javascript
  let _folhaAba = 'folha';
  async function folhaCarregar(){
    const box = document.getElementById('folha-box'); if(!box) return;
    box.innerHTML =
      '<div class="home-tabs" style="display:flex;gap:6px;margin-bottom:14px">'
      +'<button class="home-tab'+(_folhaAba==='folha'?' active':'')+'" onclick="folhaAba(\'folha\')">Folha do mês</button>'
      +'<button class="home-tab'+(_folhaAba==='func'?' active':'')+'" onclick="folhaAba(\'func\')">Funcionários</button>'
      +'</div>'
      +'<div id="folha-mes-box" style="display:'+(_folhaAba==='folha'?'block':'none')+'"></div>'
      +'<div id="cad-panel-funcionarios" style="display:'+(_folhaAba==='func'?'block':'none')+'"></div>';
    if(_folhaAba==='func') cadEntCarregar('funcionarios');
    else folhaMesCarregar();
  }
  function folhaAba(a){ _folhaAba=a; folhaCarregar(); }
  ```
- [ ] **Renomear** o `folhaCarregar` ATUAL (o que faz `fetch('/api/folha…')` + `folhaRender`) para `folhaMesCarregar`, e trocar o alvo `#folha-box` → `#folha-mes-box` nele. Em `folhaRender`, trocar `#folha-box` → `#folha-mes-box`. (Os `folhaGerar`/`folhaPagar` chamam `folhaRender`/`folhaCarregar` — seguem válidos.)
- [ ] `node --check` → JS_OK.

## Task F2.3: verificação + FF
- [ ] Suíte completa `python3 -m pytest -q` verde (backend intocado; sanity).
- [ ] Verificação manual: módulo **Folha** → sub-abas "Folha do mês" | "Funcionários". Em Funcionários: listar, **novo funcionário** (nome, CPF, telefone, e-mail, **Função**, dados bancários/PIX, status — **sem** campo de salário), editar, inativar. Voltar em "Folha do mês" e gerar a folha (agora com funcionários).
- [ ] FF na `main`.

## Notas
- Reuso total do CRUD existente (modal compartilhado) → mínimo código novo.
- Fase 3 (motor calcula pela Função: fixa + Consultor variável com base editável + benefícios) = plano próprio.
