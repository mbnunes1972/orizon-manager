# Cadastro Completo na Aprovação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exigir cadastro mínimo (nome/e-mail/telefone) na criação do cliente e, na aprovação do orçamento, bloquear a geração do contrato com um popup "Cadastro Incompleto" (lista vinda do backend) que leva ao painel de cadastro — sem o modal de aprovação editar dados do cliente.

**Architecture:** O backend `validar_cliente_para_contrato` (já existente, do Sub-projeto A) é a autoridade única sobre o que falta para o contrato; o endpoint de contrato já retorna HTTP 400 com `campos_faltando`. Esta entrega adiciona a validação mínima na criação de cliente (backend + frontend) e reescreve o modal de aprovação para parar de editar dados do cliente e tratar o `campos_faltando` num popup que abre o cadastro.

**Tech Stack:** Python 3 + `http.server` (sem framework), SQLAlchemy, pytest; frontend HTML/CSS/JS vanilla em `static/index.html` (sem harness JS → verificação manual).

**Spec:** `docs/superpowers/specs/2026-06-17-cadastro-completo-aprovacao-design.md`
**Branch:** `feat/cadastro-completo-aprovacao` (já criada).

---

## Nota de reconciliação (spec × código atual)

O spec (Seção 1) assume que o frontend só precisa "marcar e-mail e telefone como obrigatórios". Ao inspecionar o código, descobri que:
- **Backend `POST /api/clientes`** (`main.py:1068`) exige **apenas `nome`** → precisa passar a exigir nome+email+telefone (Task 1).
- **Frontend `cliSalvar`** (`static/index.html:5503`) **já exige** nome+email+telefone **e também CPF** (`:5513`). Como o ponto 5 / spec dizem "CPF opcional na criação", a Task 2 **relaxa** a exigência de CPF (mantendo a regra de homônimo que exige CPF para desambiguar). E-mail e telefone continuam obrigatórios (já são).

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `main.py` (mod.) | `validar_cadastro_minimo(req)` + uso no handler `POST /api/clientes` |
| `tests/test_cliente.py` (novo) | testes da validação mínima de criação |
| `static/index.html` (mod.) | `cliSalvar`: CPF não obrigatório na criação; modal de aprovação para de editar cliente + popup "Cadastro Incompleto" |

---

## Task 1: Backend — `/api/clientes` exige nome + e-mail + telefone

**Files:**
- Modify: `main.py` (novo helper perto de `_cliente_dict` ~`main.py:2267`; uso no handler `elif path == "/api/clientes":` ~`main.py:1068`)
- Test: `tests/test_cliente.py` (novo)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cliente.py`:

```python
import main


def test_cadastro_minimo_completo_sem_faltas():
    assert main.validar_cadastro_minimo(
        {"nome": "Ana", "email": "ana@x.com", "telefone": "(12) 99999-0000"}) == []


def test_cadastro_minimo_falta_email_e_telefone():
    faltando = main.validar_cadastro_minimo({"nome": "Ana"})
    assert "E-mail" in faltando
    assert "Telefone" in faltando
    assert "Nome" not in faltando


def test_cadastro_minimo_cpf_nao_exigido():
    # CPF é opcional na criação — não deve aparecer como faltando.
    faltando = main.validar_cadastro_minimo(
        {"nome": "Ana", "email": "ana@x.com", "telefone": "1"})
    assert faltando == []


def test_cadastro_minimo_strip():
    # Espaços em branco contam como vazio.
    faltando = main.validar_cadastro_minimo(
        {"nome": "Ana", "email": "  ", "telefone": "1"})
    assert faltando == ["E-mail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -X utf8 -m pytest tests/test_cliente.py -v`
Expected: FAIL with `AttributeError: module 'main' has no attribute 'validar_cadastro_minimo'`

- [ ] **Step 3: Add the helper in `main.py`**

Insert this function immediately BEFORE `def _cliente_dict(c) -> dict:` (currently `main.py:2267`):

```python
def validar_cadastro_minimo(req: dict) -> list:
    """Campos mínimos obrigatórios para criar um cliente: nome, e-mail, telefone.
    Retorna a lista de rótulos faltando (vazia se ok). CPF/endereço são opcionais
    na criação — a completude para o contrato é cobrada na aprovação."""
    faltando = []
    for campo, rotulo in [("nome", "Nome"), ("email", "E-mail"), ("telefone", "Telefone")]:
        if not (req.get(campo) or "").strip():
            faltando.append(rotulo)
    return faltando
```

- [ ] **Step 4: Use the helper in the `POST /api/clientes` handler**

In `main.py`, find the handler (currently `main.py:1068-1073`):

```python
        elif path == "/api/clientes":
            req  = json.loads(body) if body else {}
            nome = (req.get("nome") or "").strip()
            if not nome:
                self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                return
```

Replace it with:

```python
        elif path == "/api/clientes":
            req  = json.loads(body) if body else {}
            faltando = validar_cadastro_minimo(req)
            if faltando:
                self.send_json({"ok": False,
                                "erro": "Campos obrigatórios faltando: " + ", ".join(faltando)})
                return
            nome = (req.get("nome") or "").strip()
```

(The `nome` variable is still used below for the duplicate-CPF check and the `Cliente(...)` construction, so keep that line.)

- [ ] **Step 5: Run tests to verify they pass + suite green**

Run: `python -X utf8 -m pytest tests/test_cliente.py -v`
Expected: PASS (4 passed)
Run: `python -X utf8 -m pytest tests/ -q`
Expected: all pass.
Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"` → ok

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_cliente.py
git commit -m "feat(cadastro): /api/clientes exige nome+email+telefone na criacao"
```

---

## Task 2: Frontend — CPF deixa de ser obrigatório na criação do cliente

**Files:**
- Modify: `static/index.html` — `cliSalvar` (`:5503`), especificamente a checagem de CPF em `:5513`

Background: `cliSalvar` valida hoje (linhas 5508–5514): nome, e-mail, CPF, telefone — todos obrigatórios para qualquer save (criação e edição). O ponto 5 quer **CPF opcional na criação**. A regra de homônimo (`:5527-5534`) que exige CPF+e-mail para desambiguar permanece intacta.

- [ ] **Step 1: Remove the unconditional CPF requirement**

In `static/index.html`, find these lines inside `cliSalvar` (`:5509-5514`):

```javascript
  const email = document.getElementById('cli-email').value.trim();
  const cpf   = document.getElementById('cli-cpf').value.trim();
  const tel   = document.getElementById('cli-tel').value.trim();
  if(!email){ erro.textContent = 'E-mail é obrigatório.'; document.getElementById('cli-email').focus(); return; }
  if(!cpf)  { erro.textContent = 'CPF é obrigatório.';   document.getElementById('cli-cpf').focus();   return; }
  if(!tel)  { erro.textContent = 'Telefone é obrigatório.'; document.getElementById('cli-tel').focus(); return; }
```

Replace with (delete the `cpf` const and the CPF `if`):

```javascript
  const email = document.getElementById('cli-email').value.trim();
  const tel   = document.getElementById('cli-tel').value.trim();
  if(!email){ erro.textContent = 'E-mail é obrigatório.'; document.getElementById('cli-email').focus(); return; }
  if(!tel)  { erro.textContent = 'Telefone é obrigatório.'; document.getElementById('cli-tel').focus(); return; }
```

Note: `cpf` is re-read later (inside the homônimo block at `:5528` and in the `payload` at `:5538`), so removing this early `const cpf`/`if` does not break those — verify by reading `cliSalvar` after the edit that the homônimo block still declares its own `const cpf` and the payload still reads `document.getElementById('cli-cpf').value`.

- [ ] **Step 2: Verify JS integrity**

- Confirm there is no remaining stray reference to the deleted early `cpf` const between the deletion point and the homônimo block. (The homônimo block at `:5527` declares its own `const cpf`.)
- Confirm one `<script>`/`</script>` pair intact and backtick balance even (the edit removes plain lines, no backticks).
- Run `python -X utf8 -m pytest tests/ -q` (frontend change shouldn't affect Python tests; expect all pass).

- [ ] **Step 3: Manual verification**

Start `python main.py`, open the app:
- New client form: saving with nome+e-mail+telefone but **no CPF** → succeeds (no "CPF é obrigatório" block).
- Saving without e-mail or without telefone → still blocked.
- Homônimo (mesmo nome existente) → ainda exige CPF+e-mail.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(cadastro): CPF opcional na criacao do cliente (email/telefone seguem obrigatorios)"
```

---

## Task 3: Frontend — modal de aprovação para de editar cliente + popup "Cadastro Incompleto"

**Files:**
- Modify: `static/index.html` — template do modal de aprovação (`:6880-6911`) e a função `gerarContrato` (`:7078-7170` aprox.)

- [ ] **Step 1: Replace the "Dados do Cliente" + "Endereço de Instalação" blocks with a read-only client block**

In `static/index.html`, find this exact block (currently `:6880-6911`):

```javascript
      <h3 style="margin:0 0 2px;color:#f0c84a;font-size:1rem">&#x2713; Aprovar Or&ccedil;amento</h3>
      <p style="color:var(--muted);font-size:.8rem;margin:0 0 18px">
        Confirme os dados do cliente e preencha os campos obrigat&oacute;rios para emitir o contrato.
      </p>

      <div style="border:1px solid var(--border);border-radius:6px;padding:12px 14px;margin-bottom:14px">
        <div style="font-size:.75rem;color:#f0c84a;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">
          Dados do Cliente
        </div>
        ${_campo('apr-nome', 'Nome', c.nome, 'text', 'Nome completo', true)}
        ${_campo('apr-cpf',  'CPF', c.cpf,  'text', '000.000.000-00', true)}
        ${_campo('apr-telefone', 'Telefone', c.telefone, 'text', '(00) 00000-0000', false)}
        ${_campo('apr-email', 'E-mail', c.email, 'email', 'email@exemplo.com', false)}
      </div>

      <div style="border:1px solid var(--border);border-radius:6px;padding:12px 14px;margin-bottom:14px">
        <div style="font-size:.75rem;color:#f0c84a;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px">
          Endere&ccedil;o de Instala&ccedil;&atilde;o
        </div>
        <div style="display:flex;gap:6px;margin-bottom:8px">
          <input id="apr-end" type="text" value="${endCliente.replace(/"/g,'&quot;')}"
            placeholder="Rua, n&ordm; &ndash; Bairro &ndash; Cidade/UF"
            style="flex:1;background:var(--input,#0d1a0d);border:1px solid var(--border);
            color:var(--fg);padding:7px;border-radius:4px;font-size:.88rem">
          ${endCliente ? `<button onclick="document.getElementById('apr-end').value='${endCliente.replace(/'/g,"\\'")}'"
            style="background:none;border:1px solid var(--border);color:var(--muted);
            padding:4px 8px;border-radius:4px;cursor:pointer;font-size:.78rem;white-space:nowrap">= Cliente</button>` : ''}
        </div>
        <p style="color:var(--muted);font-size:.78rem;margin:0">
          Se diferente do endere&ccedil;o do cliente, preencha acima.
        </p>
      </div>
```

Replace it with (read-only client block; no editable client fields, no install-address field):

```javascript
      <h3 style="margin:0 0 2px;color:#f0c84a;font-size:1rem">&#x2713; Aprovar Or&ccedil;amento</h3>
      <p style="color:var(--muted);font-size:.8rem;margin:0 0 18px">
        Confirme o pagamento e gere o contrato. Os dados do cliente v&ecirc;m do cadastro.
      </p>

      <div style="border:1px solid var(--border);border-radius:6px;padding:12px 14px;margin-bottom:14px">
        <div style="font-size:.75rem;color:#f0c84a;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">
          Cliente
        </div>
        <div style="font-size:.92rem;color:var(--fg)">${c.nome || '&mdash;'}</div>
        <p style="color:var(--muted);font-size:.76rem;margin:6px 0 0">
          Dados e endere&ccedil;o v&ecirc;m do cadastro do cliente. Se algo faltar, o sistema avisar&aacute; ao gerar o contrato.
        </p>
      </div>
```

Note: this removes the only uses of `apr-nome`, `apr-cpf`, `apr-telefone`, `apr-email`, `apr-end`, and the `_campo(...)`/`endCliente` references inside this template. The locals `semCpf`/`semEnd`/`endCliente` (declared ~`:6870-6871` and above) may become unused — that is harmless; leave them unless trivially removable without touching other logic.

- [ ] **Step 2: Rewrite `gerarContrato` to not edit client data and to handle `campos_faltando`**

Find the entire `async function gerarContrato() { ... }` (currently starts `:7078`) and replace the WHOLE function with:

```javascript
async function gerarContrato() {
  const adendo        = (document.getElementById('apr-adendo')?.value || '').trim();
  const entrada       = parseMoeda(document.getElementById('apr-entrada')?.value);
  const parcelas      = (document.getElementById('apr-parcelas')?.value || '').trim();
  const formaEntrada  = document.getElementById('apr-forma-entrada')?.value || 'pix';
  const formaParcelas = document.getElementById('apr-forma-parcelas')?.value || 'boleto';

  if (!_orcamentoAtivoId) {
    mostrarErroModal('Nenhum orçamento ativo.\nVolte à negociação e selecione o orçamento a aprovar.');
    return;
  }

  const btn = document.querySelector('#modal-aprovacao-overlay button[onclick="gerarContrato()"]');
  if (btn) { btn.disabled = true; btn.textContent = 'Gerando...'; }

  const pagamento = _capturarPagamento(formaEntrada, formaParcelas);

  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/contrato`, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        orcamento_id:       _orcamentoAtivoId,
        entrada_valor:      entrada,
        parcelas_descricao: parcelas,
        adendo:             adendo,
        forma_entrada:      formaEntrada,
        forma_parcelas:     formaParcelas,
        pagamento_json:     JSON.stringify(pagamento),
      }),
    });
    const d = await r.json();
    if (!d.ok) {
      if (btn) { btn.disabled = false; btn.textContent = 'Gerar Contrato'; }
      // Cadastro incompleto: o backend devolve a lista exata em campos_faltando.
      if (Array.isArray(d.campos_faltando) && d.campos_faltando.length) {
        const cliId = projetoAtivo?.cliente_id;
        mostrarErroComAcao(
          'Cadastro Incompleto\n\n' +
          'Faltam estes dados do cliente para emitir o contrato:\n\n• ' +
          d.campos_faltando.join('\n• ') +
          '\n\nAbra o cadastro do cliente para completar.',
          'Abrir Cadastro',
          () => { if (cliId) cliAbrirModal(cliId); }
        );
      } else {
        mostrarErroModal('Erro ao gerar contrato:\n\n' + (d.erro || 'Falha desconhecida'));
      }
      return;
    }
    document.getElementById('modal-aprovacao-overlay')?.remove();
    abrirCiclo();
    setTimeout(() => { toggleCicloCard('7'); }, 300);
    if (d.aviso) {
      setTimeout(() => mostrarErroModal('Contrato gerado (Word):\n\n' + d.aviso), 400);
    } else {
      showToast('Contrato gerado! Revise e assine na aba Etapas do Projeto.', false);
    }
  } catch(e) {
    mostrarErroModal('Erro de rede ao gerar contrato:\n\n' + e.message);
    if (btn) { btn.disabled = false; btn.textContent = 'Gerar Contrato'; }
  }
}
```

Key differences from the old version: no reads of `apr-nome/apr-cpf/apr-telefone/apr-email/apr-end`; no `camposFaltando` pre-check; no `PATCH /api/clientes`; no `endereco_instalacao` in the POST body; and a new `campos_faltando` branch showing the "Cadastro Incompleto" popup.

- [ ] **Step 3: Verify JS integrity**

- Grep to confirm the removed ids are gone from the approval flow: `apr-nome`, `apr-cpf`, `apr-telefone`, `apr-email`, `apr-end` should have **no** remaining occurrences in `static/index.html` (search the file).
- Confirm exactly one `<script>`/`</script>` pair and even backtick parity.
- Re-read the edited `gerarContrato` and the modal template region for balanced braces/backticks/template literals.
- Run `python -X utf8 -m pytest tests/ -q` → all pass (Python unaffected).

- [ ] **Step 4: Manual verification**

Start `python main.py`. Use a project whose client is missing structured address:
- Click "Aprovar Orçamento" → "Gerar Contrato": a popup **"Cadastro Incompleto"** lists the missing fields (from backend, e.g. "CPF", "Logradouro (residencial)", "Cidade (residencial)"…) with an **"Abrir Cadastro"** button that opens the client modal.
- Complete the client (contact + residential address, and installation if different) in the cadastro panel, save.
- Re-open approval and generate → contract is created (etapa 7 card opens), no popup.
- The approval modal no longer shows editable client fields — only the read-only client name + payment/adendo.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(aprovacao): modal nao edita cliente; popup Cadastro Incompleto via campos_faltando"
```

---

## Final verification

- [ ] **Run full test suite**

Run: `python -X utf8 -m pytest tests/ -q`
Expected: all pass (existing + `tests/test_cliente.py`).

- [ ] **Smoke import**

Run: `python -c "import main; print(main.validar_cadastro_minimo({'nome':'a','email':'','telefone':'1'}))"`
Expected: `['E-mail']`

---

## Notas de escopo (fora deste plano)
- **C** — semântica de "Aprovar Orçamento" (concluir Revisão+Aprovação), 1º orçamento por XML, renomear botão de contrato.
- **D** — Briefing obrigatório.
- Limpeza opcional: remover a coluna vestigial `contrato.endereco_instalacao` e os locais `semCpf`/`semEnd`/`endCliente` se ficarem órfãos.
