# Passo 2 (migração visual) — Item 7: toggle de tema claro/escuro persistido por usuário

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou
> executing-plans. Passos com checkbox (`- [ ]`). Segue **TDD** no backend (Python).

**Goal:** Permitir que cada usuário alterne entre **tema claro e escuro**, com a preferência **persistida no
backend por usuário** (não por `localStorage` nem preferência do SO). Corresponde ao **item 7 da seção 5** do padrão
(`docs/design/backlog-migracao-design.md`; fonte de verdade = o `.docx`). É o **último item do passo 2**.

**Architecture:** A paleta clara **já existe** desde o item 1 (`static/index.html` → `:root[data-theme="light"]`);
falta (a) uma coluna `tema` no `Usuario`, (b) expô-la no dict do usuário e num endpoint de gravação, e (c) no
frontend, **aplicar** o tema no boot e um **toggle** que alterna + persiste. O serializador central é
**`auth._usuario_dict(u)`** (auth.py:167) — usado tanto pelo login quanto por `validar_sessao` (logo, por
`/api/auth/me`) — então incluir `tema` ali cobre os dois caminhos. O front lê `_usuarioAtual = d.usuario` em
`carregarUsuarioAutenticado` (index.html ~L2063); aplicar `data-theme` logo após isso. `claro` ⇒
`document.documentElement.setAttribute('data-theme','light')`; `escuro` ⇒ remover o atributo (o default do `:root`
é escuro). Persistência via novo `POST /api/auth/preferencias` (auth-scoped), que chama uma função testável
`auth.set_tema(usuario_id, tema)`.

**Tech Stack:** `database.py` (modelo + migração idempotente), `auth.py` (dict + `set_tema`), `auth_routes.py`
(endpoint), `static/index.html` (toggle + apply). **Mudança em Python exige RESTART do servidor** (`main.py` é lido só
no start; o `index.html` é lido a cada request). Teste backend: `python3 -m pytest -q` — **baseline 681**, deve subir
com os testes novos. Frontend **sem teste JS/visual** → verificação manual. Branch: `feat/design-toggle-tema`.

**Escopo = SÓ item 7.** NÃO reescreve a paleta clara (já pronta). NÃO usa `localStorage`/preferência do SO como fonte
(o backend é a fonte; um "flash" curto de escuro antes do `/me` para quem usa claro é **aceito**). `login.html` fica
**escuro** (sem usuário autenticado ainda). NÃO renomeia o copy "Promob → Omie". **Achados fora de escopo (registrar,
não corrigir):** hardcodes verdes remanescentes descobertos perto da âncora do toggle — avatar `color:#0d160d`
(index.html ~L510) e o `#modal-perfil` (`background:#111d11;border:1px solid #1e2e1e`, ~L527) — são resíduos de paleta
não cobertos pelo item 1 (aliases só no `:root`); virar `var(--…)` é um follow-up de higiene de marca.

**Ler antes:** `database.py:29-44` (modelo `Usuario`) e `:651-661` (bloco de migração de `usuarios`); `auth.py:167-182`
(`_usuario_dict`); `auth_routes.py:65-96` (me) e `:101-136` (post/login/logout — onde inserir o endpoint);
`static/index.html:2057-2065` (boot do usuário) e `:499-521` (rodapé da sidebar, âncora do toggle);
`tests/test_usuarios_colunas.py` (template de teste com a fixture `app_db`). **`git add`** só os arquivos de cada task.

---

## Task 1: Backend — coluna `tema`, dict, `set_tema` e endpoint (TDD)

**Files:**
- Modify: `database.py`, `auth.py`, `auth_routes.py`
- Test: `tests/test_tema_usuario.py` (novo)

- [ ] **Step 1: Escrever os testes que falham.** Criar `tests/test_tema_usuario.py`:
```python
import sqlite3
import auth

def test_usuarios_tem_coluna_tema(app_db):
    conn = sqlite3.connect(app_db.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(usuarios)")}
    conn.close()
    assert "tema" in cols

def test_usuario_dict_inclui_tema_default_escuro(app_db):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Tema", login="tema1", nivel="consultor")
    u.set_senha("x"); db.add(u); db.commit(); uid = u.id; db.close()
    db2 = app_db.get_session()
    lido = db2.get(app_db.Usuario, uid); db2.close()
    d = auth._usuario_dict(lido)
    assert d["tema"] == "escuro"

def test_set_tema_atualiza_e_valida(app_db):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Tema2", login="tema2", nivel="consultor")
    u.set_senha("x"); db.add(u); db.commit(); uid = u.id; db.close()
    assert auth.set_tema(uid, "claro") is True
    db2 = app_db.get_session()
    assert db2.get(app_db.Usuario, uid).tema == "claro"; db2.close()
    # valor inválido é rejeitado e não altera
    assert auth.set_tema(uid, "roxo") is False
    db3 = app_db.get_session()
    assert db3.get(app_db.Usuario, uid).tema == "claro"; db3.close()
    # id inexistente → False (sem exceção)
    assert auth.set_tema(999999, "escuro") is False
```
> Se a fixture `app_db` não expuser `DB_PATH`/`get_session`/`Usuario` exatamente assim, ajustar aos nomes reais
> (espelhar `tests/test_usuarios_colunas.py`, que usa `app_db.DB_PATH`, `app_db.get_session()`, `app_db.Usuario`).

- [ ] **Step 2: Rodar e ver falhar.** `python3 -m pytest tests/test_tema_usuario.py -q` → FAIL
  (`tema` inexistente / `set_tema` não definido).

- [ ] **Step 3: Modelo + migração (`database.py`).**
  - No modelo `Usuario` (após a linha `ativo = Column(Integer, default=1)`, ~L41), adicionar:
```python
    tema          = Column(String(10),  default="escuro")   # 'claro' | 'escuro'
```
  - No `_migrar_colunas`, no bloco de `usuarios` (após o loop que adiciona email/cpf/whatsapp, ~L661), adicionar:
```python
        if "tema" not in usr_cols:
            cur.execute("ALTER TABLE usuarios ADD COLUMN tema VARCHAR(10) DEFAULT 'escuro'")
```

- [ ] **Step 4: Dict + `set_tema` (`auth.py`).**
  - Em `_usuario_dict` (~L167), acrescentar ao dict retornado (ex.: após `"nivel": u.nivel,`):
```python
        "tema":              getattr(u, "tema", None) or "escuro",
```
  - Adicionar a função testável (perto dos helpers, após `_usuario_dict`):
```python
def set_tema(usuario_id: int, tema: str) -> bool:
    """Persiste a preferência de tema do usuário. Retorna False p/ tema inválido ou usuário inexistente."""
    if tema not in ("claro", "escuro"):
        return False
    db = get_session()
    try:
        u = db.get(Usuario, usuario_id)
        if not u:
            return False
        u.tema = tema
        db.commit()
        return True
    finally:
        db.close()
```
  > Conferir se `get_session` e `Usuario` já estão importados no topo de `auth.py` (o `fazer_login` os usa → devem
  > estar). Se não, importar de `database`.

- [ ] **Step 5: Endpoint (`auth_routes.py`).** Em `handle_auth_post`, junto dos outros `if path == ...` (ex.: após o
  bloco `/api/auth/logout`, ~L136):
```python
    if path == "/api/auth/preferencias":
        usuario = get_usuario_sessao(handler)
        if not usuario:
            _send_json(handler, {"ok": False, "erro": "Não autenticado."}, 401)
            return True
        try:
            dados = json.loads(body)
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400)
            return True
        tema = dados.get("tema")
        import auth as _auth
        if not _auth.set_tema(usuario["id"], tema):
            _send_json(handler, {"ok": False, "erro": "tema inválido."}, 400)
            return True
        _send_json(handler, {"ok": True, "tema": tema})
        return True
```
  > `get_usuario_sessao`, `_send_json` e `json` já estão em `auth_routes.py` (usados pelas rotas vizinhas). Confirmar.

- [ ] **Step 6: Rodar os testes.** `python3 -m pytest tests/test_tema_usuario.py -q` → **PASS** (4 testes).
  Depois a suíte inteira: `python3 -m pytest -q` → **≥ 685** (baseline 681 + 4 novos), tudo verde.

- [ ] **Step 7: Commit.**
```bash
git add database.py auth.py auth_routes.py tests/test_tema_usuario.py
git commit -m "feat(design): item 7 backend — coluna tema no usuario + set_tema + POST /api/auth/preferencias"
```

---

## Task 2: Frontend — aplicar tema no boot + toggle na sidebar (index.html)

**Files:** Modify `static/index.html`. (Frontend: sem teste JS → verificação manual.)

- [ ] **Step 1: Funções de tema.** Logo antes de `async function carregarUsuarioAutenticado(){` (~L2057), adicionar:
```javascript
function aplicarTema(tema){
  // 'claro' => paleta clara (:root[data-theme="light"]); 'escuro' => default do :root (sem atributo)
  const root = document.documentElement;
  if(tema === 'claro') root.setAttribute('data-theme','light');
  else                  root.removeAttribute('data-theme');
  const ic = document.getElementById('sb-tema-icone');
  const lb = document.getElementById('sb-tema-label');
  if(ic) ic.innerHTML  = (tema === 'claro') ? '&#x2600;' : '&#x1F319;';   // ☀ / 🌙
  if(lb) lb.textContent = (tema === 'claro') ? 'Tema claro' : 'Tema escuro';
}

async function alternarTema(){
  const atual = (_usuarioAtual && _usuarioAtual.tema) || 'escuro';
  const novo  = (atual === 'claro') ? 'escuro' : 'claro';
  if(_usuarioAtual) _usuarioAtual.tema = novo;
  aplicarTema(novo);                              // UI reflete já
  try {
    await fetch('/api/auth/preferencias', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ tema: novo })
    });
  } catch(e){ /* persistência best-effort; a UI já mudou */ }
}
```

- [ ] **Step 2: Aplicar no boot.** Em `carregarUsuarioAutenticado`, logo após `_usuarioAtual = d.usuario;` (~L2063),
  adicionar:
```javascript
    aplicarTema(_usuarioAtual.tema || 'escuro');
```

- [ ] **Step 3: Toggle na sidebar.** Inserir **logo após** o `</div>` que fecha o `#sb-user-btn` (a linha `    </div>`
  na ~L519, imediatamente antes de `    <div id="seletor-loja-wrap"`):
```html
    <div id="sb-tema-btn" onclick="alternarTema()" title="Alternar tema claro/escuro"
         style="display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:8px;cursor:pointer;
                margin-top:6px;font-size:11px;color:var(--muted);border:1px solid var(--border);transition:.15s"
         onmouseover="this.style.borderColor='var(--accent)'"
         onmouseout="this.style.borderColor='var(--border)'">
      <span id="sb-tema-icone">&#x1F319;</span><span id="sb-tema-label">Tema escuro</span>
    </div>
```

- [ ] **Step 4: Verificação.**
  - `python3 -m pytest -q` → mesmo total da Task 1 (frontend não afeta backend).
  - **Manual (essencial — Ctrl+F5, NÃO precisa restart p/ mudança de HTML):** (a) o toggle aparece no rodapé da
    sidebar; (b) clicar → o app inteiro vira **claro** (fundo branco, texto escuro, accent petróleo escuro), rótulo vira
    "Tema claro" ☀; clicar de novo → volta ao **escuro** 🌙; (c) **recarregar a página** (F5) → o tema escolhido
    **persiste** (veio do backend via `/api/auth/me`); (d) verificar em outra sessão/navegador logando o mesmo usuário
    que a preferência acompanha (é por usuário, não por máquina). Conferir legibilidade nas telas principais no claro.

- [ ] **Step 5: Commit.**
```bash
git add static/index.html
git commit -m "feat(design): item 7 frontend — toggle de tema na sidebar + aplica preferencia no boot"
```

---

## Task 3: Docs — checklist + DEV_LOG (fecha o passo 2)

**Files:** Modify `docs/design/backlog-migracao-design.md`, `DEV_LOG.md`.

- [ ] **Step 1:** Em `backlog-migracao-design.md`, marcar **item 7 como CONCLUÍDO** (`✅ feito 2026-07-08`): toggle na
  sidebar; preferência **persistida por usuário** no backend (coluna `Usuario.tema`, `POST /api/auth/preferencias`,
  `set_tema`), **não** localStorage/SO; aplicado no boot via `/api/auth/me`; paleta clara reaproveitada do item 1.
  Registrar que o **passo 2 está 100% concluído** (itens 1–7). Manter o aviso "checklist derivado, fonte = `.docx`".
- [ ] **Step 2:** `DEV_LOG.md` — nota do passo 2 item 7 (backend: coluna/endpoint/set_tema + testes; frontend: toggle
  + apply; **restart do servidor** feito; verificação visual com o usuário). Anotar o **fim do passo 2** e que restam
  como follow-ups: copy "Promob → Omie" (title/login), `#c8a84b` decorativo, e os hardcodes verdes do avatar/modal-perfil
  descobertos nesta frente. Próximo do alinhamento = **passo 3** (templates de diagramação, doc 4 Parte 1).
- [ ] **Step 3: Commit.**
```bash
git add docs/design/backlog-migracao-design.md DEV_LOG.md
git commit -m "docs(design): item 7 do backlog concluido (toggle de tema persistido) — passo 2 completo"
```

---

## Self-review do plano
- **Cobertura:** item 7 = T1 (coluna `tema` + migração + dict + `set_tema` + endpoint, com TDD) + T2 (aplicar no boot +
  toggle) + T3 (docs, fecha passo 2). Escopo restrito ao item 7.
- **Sem placeholders:** código completo para modelo, migração, `set_tema`, endpoint, as 3 peças de JS e o HTML do
  toggle, com âncoras/linhas exatas e contagens/asserts de teste.
- **Consistência:** `set_tema` (auth.py) é chamado pelo endpoint (auth_routes) e testado no T1; `_usuario_dict` expõe
  `tema` → chega ao front em `_usuarioAtual.tema`; `aplicarTema('claro')` casa com o seletor CSS `:root[data-theme=
  "light"]` já existente; `'escuro'` remove o atributo (default). Valores canônicos `'claro'|'escuro'` em todas as
  camadas (modelo default, validação do `set_tema`, validação do endpoint, JS).
- **Riscos:** (1) **Python mudou → restart do servidor** (senão o endpoint dá 404 e o `me` não traz `tema`); anotado em
  T1/T2. (2) **Flash de escuro** antes do `/me` para quem usa claro — aceito (não usar localStorage p/ respeitar
  "persistido por usuário, não SO"). (3) Fixture `app_db`: ajustar nomes se divergir do template. (4) Sem teste
  visual → verificação manual obrigatória em T2, incluindo o **round-trip de persistência** (F5) e o caráter **por
  usuário** (outra máquina). Se algo no tema claro ficar ilegível, é ajuste pontual da paleta clara (item 1), não do
  toggle.
- **Fora de escopo:** copy "Promob → Omie"; `#c8a84b` decorativo; hardcodes verdes do avatar/`#modal-perfil` (follow-up
  de higiene); passo 3 (diagramação).
