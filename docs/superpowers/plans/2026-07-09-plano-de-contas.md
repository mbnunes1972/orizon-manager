# Plano de Contas (Módulo Financeiro #1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou
> executing-plans. Passos com checkbox (`- [ ]`). **TDD** no backend.

**Goal:** Implementar o **Plano de Contas** (árvore hierárquica de contas contábeis, por owner rede|loja, seed
completo, CRUD editável com inativar-não-apagar) — sub-projeto #1 do módulo Financeiro.

**Architecture:** Novo motor `mod_contabil.py` (domínio `financeiro`) com modelo `Conta` (árvore via `pai_id`),
seed do plano-padrão (do `.docx` §2/§2.1) materializado por owner na 1ª vez, e funções puras de CRUD. `main.py`
(SHELL) roteia `/api/financeiro/contas` e delega a `mod_contabil`. A tela Financeiro (page-12) ganha abas
**Provisões** (atual) + **Plano de Contas** (árvore nova). Tenancy por owner `(rede|loja)` espelhando o Emitente.

**Tech Stack:** Python `http.server` + SQLAlchemy/SQLite; `mod_contabil.py`, `database.py`, `main.py`, `modulos.py`,
`static/index.html`; testes `pytest` (fixtures `app_db`, `http_client_factory`). **Baseline 687.** Branch:
`feat/financeiro-plano-contas`. **Mudança em Python → restart do servidor** ao testar no navegador.

**Design:** `docs/superpowers/specs/financeiro/2026-07-09-plano-de-contas-design.md`. **Fonte de verdade:**
`Especificacao_Financeiro_Orizon_v2.docx` §2/§2.1.

---

## Task 1: Modelo `Conta` + seed + resolução de owner + árvore (mod_contabil)

**Files:** Create `mod_contabil.py`; Modify `database.py`; Test `tests/test_plano_contas.py`.

- [ ] **Step 1: Teste que falha** — `tests/test_plano_contas.py`:
```python
import mod_contabil as mc

def _owner_loja_avulsa(app_db):
    db = app_db.get_session()
    l = db.get(app_db.Loja, 1)          # INSPIRIUM, rede_id=None (seed)
    ot, oid = mc.resolver_owner(db, {"loja_id": 1, "rede_id": None})
    db.close()
    return ot, oid

def test_seed_idempotente_e_grupos(app_db):
    db = app_db.get_session()
    n1 = mc.seed_plano(db, "loja", 1)   # materializa
    n2 = mc.seed_plano(db, "loja", 1)   # 2ª vez não duplica
    contas = mc.listar_contas(db, "loja", 1)   # árvore
    db.close()
    assert n1 > 60 and n2 == 0
    raizes = [c["codigo"] for c in contas]
    assert raizes == ["1", "2", "3", "4", "5"]           # 5 grupos, ordenados
    assert contas[0]["nome"].upper().startswith("ATIVO")

def test_natureza_por_grupo_e_tipo(app_db):
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 1)
    plano = {c.codigo: c for c in db.query(app_db.Conta)
             .filter_by(owner_tipo="loja", owner_id=1).all()}
    db.close()
    assert plano["1"].natureza == "devedora" and plano["5"].natureza == "devedora"
    assert plano["2"].natureza == "credora" and plano["4"].natureza == "credora"
    assert plano["5"].tipo == "sintetica"                 # tem filhos
    assert plano["5.4.01"].tipo == "analitica"            # folha (Aluguel)
    assert plano["5.4.01"].nome == "Aluguel"

def test_resolver_owner_loja_avulsa_e_rede(app_db):
    db = app_db.get_session()
    # loja 1 sem rede -> owner é a própria loja
    assert mc.resolver_owner(db, {"loja_id": 1, "rede_id": None}) == ("loja", 1)
    # usuário admin de rede -> owner é a rede
    assert mc.resolver_owner(db, {"loja_id": None, "rede_id": 7}) == ("rede", 7)
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar.** `python3 -m pytest tests/test_plano_contas.py -q` → FAIL (sem `mod_contabil`).

- [ ] **Step 3: Modelo `Conta` em `database.py`** (após `ProvisaoRegistro`, ~L432; `UniqueConstraint` já importado):
```python
class Conta(Base):
    """Conta do Plano de Contas (árvore hierárquica), por owner (rede|loja)."""
    __tablename__ = "conta"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo = Column(String(10), nullable=False)   # 'rede' | 'loja'
    owner_id   = Column(Integer,    nullable=False)
    codigo     = Column(String(20), nullable=False)
    nome       = Column(Text,       nullable=False)
    grupo      = Column(Integer,    nullable=False)    # 1..5
    tipo       = Column(String(10), nullable=False)    # 'sintetica' | 'analitica'
    natureza   = Column(String(8),  nullable=False)    # 'devedora' | 'credora'
    pai_id     = Column(Integer, ForeignKey("conta.id"), nullable=True)
    ativa      = Column(Integer, default=1)
    ordem      = Column(Integer, default=0)
    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("owner_tipo", "owner_id", "codigo", name="uq_conta_owner_codigo"),)
```
Garantir `Conta` exportado onde `app_db.Conta` é acessível nos testes (a fixture expõe o módulo `database`; `Conta`
fica no namespace do módulo — ok). `create_all` cria a tabela (nova; sem ALTER retroativo).

- [ ] **Step 4: `mod_contabil.py`** — seed + owner + árvore:
```python
"""mod_contabil.py — motor contábil (domínio financeiro). Sub-projeto #1: Plano de Contas.
Fonte de verdade: Especificacao_Financeiro_Orizon_v2.docx §2/§2.1."""
from database import get_session, Conta, Loja

# Plano-padrão (codigo, nome) — pai = prefixo; tipo/natureza derivados. Ordem = ordem contábil.
PLANO_PADRAO = [
    ("1", "ATIVO"),
    ("1.1", "Circulante"),
    ("1.1.01", "Caixa/Bancos"), ("1.1.02", "Contas a Receber (Clientes)"),
    ("1.1.03", "Estoques"), ("1.1.04", "Adiantamentos a Fornecedores"),
    ("1.2", "Não Circulante"),
    ("1.2.1", "Imobilizado"),
    ("1.2.1.01", "Itens de Informática"), ("1.2.1.02", "Veículos"),
    ("1.2.1.03", "Obras/Reforma de Loja"), ("1.2.1.04", "Show Room"),
    ("1.2.2", "Intangível"),
    ("2", "PASSIVO"),
    ("2.1", "Circulante"),
    ("2.1.01", "Fornecedores a Pagar"), ("2.1.02", "Obrigações Trabalhistas"),
    ("2.1.03", "Obrigações Tributárias"),
    ("2.1.04", "Provisões"),
    ("2.1.04.01", "Provisão de Comissão"), ("2.1.04.02", "Provisão de Montagem"),
    ("2.1.04.03", "Provisão de Garantia Técnica"), ("2.1.04.04", "Provisão de Devolução"),
    ("2.1.05", "Financiamento Total Flex a Pagar"),
    ("2.2", "Não Circulante"),
    ("2.2.01", "Financiamentos de Longo Prazo (principal)"),
    ("3", "PATRIMÔNIO LÍQUIDO"),
    ("3.1", "Capital Social"), ("3.2", "Reservas"),
    ("3.3", "Lucros/Prejuízos Acumulados"), ("3.4", "Distribuição de Lucros"),
    ("4", "RECEITAS"),
    ("4.1", "Vendas de Produtos"),
    ("4.1.01", "Receitas com Vendas"), ("4.1.02", "Receita com Vendas de Assistência"),
    ("4.2", "Serviços"),
    ("4.2.01", "Receita de Serviços"), ("4.2.02", "Prestação de Serviços para Terceiros"),
    ("4.3", "Deduções"),
    ("4.3.01", "Simples Nacional s/ Vendas"), ("4.3.02", "Devolução de Vendas"),
    ("4.4", "Outras Receitas Não Operacionais"),
    ("4.4.01", "Receita de Aluguéis"),
    ("5", "DESPESAS / CUSTOS"),
    ("5.1", "CMV"),
    ("5.1.01", "CMV Fábrica (Dal Mobile)"), ("5.1.02", "Frete Fábrica"),
    ("5.2", "Custo de Serviço"),
    ("5.2.01", "Montagem"), ("5.2.02", "Comissão Executivo de Montagem"),
    ("5.2.03", "Viagens de Pedido"), ("5.2.04", "Salários Operacionais"),
    ("5.2.05", "Ajudante Semanal"), ("5.2.06", "Combustível de Depósito"),
    ("5.2.07", "Pedágio"), ("5.2.08", "Frete Local"), ("5.2.09", "Insumos"),
    ("5.2.10", "Manutenção de Veículos"), ("5.2.11", "Viagens de Supervisão"),
    ("5.3", "Despesas Comerciais"),
    ("5.3.01", "Comissão de Vendedor"), ("5.3.02", "Comissão de Indicador"),
    ("5.3.03", "Comissão Administrativa"), ("5.3.04", "Pontos Programa de Indicação"),
    ("5.3.05", "Premiação de Vendedores"), ("5.3.06", "Salários de Vendas"),
    ("5.3.07", "Marketing/Campanhas de Divulgação"), ("5.3.08", "Salário Marketing"),
    ("5.3.09", "Site e Hospedagem"), ("5.3.10", "Combustível de Venda"),
    ("5.3.11", "Uniformes"), ("5.3.12", "Brindes"), ("5.3.13", "Suprimento a Cliente"),
    ("5.3.14", "Viagens de Especificador"),
    ("5.4", "Despesas Administrativas"),
    ("5.4.01", "Aluguel"), ("5.4.02", "Energia Elétrica"), ("5.4.03", "Água"),
    ("5.4.04", "Telefonia Fixa/Móvel e Internet"), ("5.4.05", "Contabilidade"),
    ("5.4.06", "Assessoria Jurídica"), ("5.4.07", "Consultoria"),
    ("5.4.08", "Segurança e Seguros"), ("5.4.09", "Material de Limpeza/Expediente"),
    ("5.4.10", "Sistemas (ERP, CRM, assinatura digital)"), ("5.4.11", "Salários Administrativos"),
    ("5.4.12", "Pró-labore"), ("5.4.13", "Encargos sobre Folha"),
    ("5.4.14", "Vale-Transporte"), ("5.4.15", "Sindicato"), ("5.4.16", "Rescisões"),
    ("5.4.17", "IPVA/IPTU/Licenciamentos"), ("5.4.18", "Manutenção (loja, veículos, informática)"),
    ("5.5", "Despesas Financeiras"),
    ("5.5.01", "Tarifas Bancárias"), ("5.5.02", "Juros de Empréstimos"),
    ("5.5.03", "Custo de Antecipação de Recebíveis"),
    ("5.6", "Constituição de Provisões"),
    ("5.6.01", "Constituição de Provisão"),
]

def _pai_codigo(codigo):
    return codigo.rsplit(".", 1)[0] if "." in codigo else None

def _natureza(grupo):
    return "devedora" if grupo in (1, 5) else "credora"   # Ativo/Despesa devedora; Passivo/PL/Receita credora

def resolver_owner(db, usuario):
    """(owner_tipo, owner_id) do usuário: rede da loja se houver; senão a loja; admin de rede -> rede."""
    rid = usuario.get("rede_id")
    lid = usuario.get("loja_id")
    if lid:
        loja = db.get(Loja, lid)
        if loja and loja.rede_id:
            return ("rede", loja.rede_id)
        return ("loja", lid)
    if rid:
        return ("rede", rid)
    raise ValueError("usuário sem loja nem rede para resolver owner contábil")

def seed_plano(db, owner_tipo, owner_id):
    """Materializa o plano-padrão para o owner se ele ainda não tiver contas. Retorna nº criadas (0 se já existia)."""
    existe = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).first()
    if existe:
        return 0
    codigos = {c for c, _ in PLANO_PADRAO}
    id_por_codigo = {}
    criadas = 0
    for ordem, (codigo, nome) in enumerate(PLANO_PADRAO):
        grupo = int(codigo.split(".")[0])
        tipo = "sintetica" if any(o.startswith(codigo + ".") for o in codigos) else "analitica"
        pai_cod = _pai_codigo(codigo)
        c = Conta(owner_tipo=owner_tipo, owner_id=owner_id, codigo=codigo, nome=nome,
                  grupo=grupo, tipo=tipo, natureza=_natureza(grupo),
                  pai_id=id_por_codigo.get(pai_cod), ativa=1, ordem=ordem)
        db.add(c); db.flush()
        id_por_codigo[codigo] = c.id
        criadas += 1
    db.commit()
    return criadas

def _serial(c):
    return {"id": c.id, "codigo": c.codigo, "nome": c.nome, "grupo": c.grupo,
            "tipo": c.tipo, "natureza": c.natureza, "pai_id": c.pai_id, "ativa": bool(c.ativa)}

def listar_contas(db, owner_tipo, owner_id, incluir_inativas=False):
    """Árvore (lista de raízes com 'filhos'), ordenada por 'ordem'/codigo. Seed-on-first-access."""
    seed_plano(db, owner_tipo, owner_id)
    q = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id)
    if not incluir_inativas:
        q = q.filter(Conta.ativa == 1)
    contas = q.order_by(Conta.ordem, Conta.codigo).all()
    nodes = {c.id: {**_serial(c), "filhos": []} for c in contas}
    raizes = []
    for c in contas:
        if c.pai_id and c.pai_id in nodes:
            nodes[c.pai_id]["filhos"].append(nodes[c.id])
        else:
            raizes.append(nodes[c.id])
    return raizes
```

- [ ] **Step 5: Rodar os testes.** `python3 -m pytest tests/test_plano_contas.py -q` → PASS (4 testes).
  Suíte inteira: `python3 -m pytest -q` → **691** (687 + 4).

- [ ] **Step 6: Commit.**
```bash
git add database.py mod_contabil.py tests/test_plano_contas.py
git commit -m "feat(financeiro): Plano de Contas — modelo Conta + seed padrao + arvore + owner"
```

---

## Task 2: CRUD (criar / editar / remover-ou-inativar) — mod_contabil (TDD)

**Files:** Modify `mod_contabil.py`, `tests/test_plano_contas.py`.

- [ ] **Step 1: Testes que falham** (append em `tests/test_plano_contas.py`):
```python
def test_criar_filho_torna_pai_sintetica(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    aluguel = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5.4.01").first()
    assert aluguel.tipo == "analitica"
    nova = mc.criar_conta(db, "loja", 1, pai_id=aluguel.id, nome="Aluguel Matriz")
    db.refresh(aluguel)
    assert aluguel.tipo == "sintetica"                    # virou pai
    assert nova["codigo"].startswith("5.4.01.") and nova["grupo"] == 5
    assert nova["natureza"] == "devedora" and nova["tipo"] == "analitica"
    db.close()

def test_editar_renomeia(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    c = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5.4.05").first()
    r = mc.editar_conta(db, "loja", 1, c.id, nome="Contabilidade e Auditoria")
    db.refresh(c); assert c.nome == "Contabilidade e Auditoria" and r["nome"] == c.nome
    db.close()

def test_remover_folha_apaga_pai_inativa(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    folha = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5.4.18").first()
    r1 = mc.remover_conta(db, "loja", 1, folha.id)
    assert r1["acao"] == "apagada"
    assert db.get(app_db.Conta, folha.id) is None
    grupo5 = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5").first()
    r2 = mc.remover_conta(db, "loja", 1, grupo5.id)        # tem filhos -> inativa
    db.refresh(grupo5)
    assert r2["acao"] == "inativada" and grupo5.ativa == 0
    db.close()

def test_cross_owner_barrado(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1)
    c = db.query(app_db.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo="5").first()
    import pytest
    with pytest.raises(PermissionError):
        mc.editar_conta(db, "loja", 999, c.id, nome="hack")   # owner diferente
    db.close()
```

- [ ] **Step 2: Ver falhar.** `python3 -m pytest tests/test_plano_contas.py -q` → FAIL (funções ausentes).

- [ ] **Step 3: Implementar em `mod_contabil.py`:**
```python
def _get_own(db, owner_tipo, owner_id, conta_id):
    c = db.get(Conta, conta_id)
    if c is None:
        raise ValueError("conta inexistente")
    if c.owner_tipo != owner_tipo or c.owner_id != owner_id:
        raise PermissionError("conta de outro owner")
    return c

def _tem_filhos(db, conta):
    return db.query(Conta).filter_by(owner_tipo=conta.owner_tipo, owner_id=conta.owner_id,
                                     pai_id=conta.id).first() is not None

def _tem_lancamentos(db, conta):
    return False   # sub-projeto #2 (Livro de Lançamentos) implementa de verdade

def _proximo_codigo(db, pai):
    filhos = db.query(Conta).filter_by(owner_tipo=pai.owner_tipo, owner_id=pai.owner_id,
                                       pai_id=pai.id).all()
    seq = 1
    usados = set()
    for f in filhos:
        try: usados.add(int(f.codigo.rsplit(".", 1)[-1]))
        except ValueError: pass
    while seq in usados: seq += 1
    return f"{pai.codigo}.{seq:02d}"

def criar_conta(db, owner_tipo, owner_id, pai_id, nome):
    pai = _get_own(db, owner_tipo, owner_id, pai_id)
    if not (nome or "").strip():
        raise ValueError("nome obrigatório")
    if pai.tipo == "analitica":
        pai.tipo = "sintetica"                            # pai passa a agrupar
    c = Conta(owner_tipo=owner_tipo, owner_id=owner_id, codigo=_proximo_codigo(db, pai),
              nome=nome.strip(), grupo=pai.grupo, tipo="analitica", natureza=_natureza(pai.grupo),
              pai_id=pai.id, ativa=1, ordem=999)
    db.add(c); db.commit()
    return _serial(c)

def editar_conta(db, owner_tipo, owner_id, conta_id, nome=None, ordem=None):
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    if nome is not None:
        if not nome.strip(): raise ValueError("nome obrigatório")
        c.nome = nome.strip()
    if ordem is not None:
        c.ordem = int(ordem)
    db.commit()
    return _serial(c)

def remover_conta(db, owner_tipo, owner_id, conta_id):
    """Folha sem lançamento -> apaga; senão inativa (regra do .docx)."""
    c = _get_own(db, owner_tipo, owner_id, conta_id)
    if not _tem_filhos(db, c) and not _tem_lancamentos(db, c):
        db.delete(c); db.commit()
        return {"acao": "apagada", "id": conta_id}
    c.ativa = 0; db.commit()
    return {"acao": "inativada", "id": conta_id}
```
> **Nota (reorganizar/mover):** o `pai_id`/recodificação livre fica declarado no design mas **não** entra neste
> sub-projeto (evita recodificar subárvores agora); `editar_conta` cobre nome+ordem. Mover vira item do #2/futuro.
> Registrar isso na Task 5 (não silenciar o corte).

- [ ] **Step 4: Testes verdes.** `python3 -m pytest tests/test_plano_contas.py -q` → PASS. Suíte: `python3 -m pytest -q` → **695**.

- [ ] **Step 5: Commit.**
```bash
git add mod_contabil.py tests/test_plano_contas.py
git commit -m "feat(financeiro): Plano de Contas — CRUD (criar/editar/remover-inativa) por owner"
```

---

## Task 3: API `/api/financeiro/contas` + gate + manifesto (TDD HTTP)

**Files:** Modify `main.py`, `modulos.py`; Test `tests/test_plano_contas_api.py`.

- [ ] **Step 1: Testes HTTP** — `tests/test_plano_contas_api.py`:
```python
def test_get_arvore_seed_on_first_access(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/contas")
    assert st == 200 and d["ok"] is True
    cods = [n["codigo"] for n in d["contas"]]
    assert cods == ["1", "2", "3", "4", "5"]

def test_post_cria_e_put_renomeia(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.get("/api/financeiro/contas")
    # acha o id de "5.4" (Despesas Administrativas) na árvore
    def _find(nodes, cod):
        for n in nodes:
            if n["codigo"] == cod: return n
            r = _find(n["filhos"], cod)
            if r: return r
    g54 = _find(d["contas"], "5.4")
    st, nova = c.post("/api/financeiro/contas", {"pai_id": g54["id"], "nome": "Nova Despesa"})
    assert st == 201 and nova["conta"]["grupo"] == 5
    st2, r = c.put("/api/financeiro/contas/" + str(nova["conta"]["id"]), {"nome": "Renomeada"})
    assert st2 == 200 and r["conta"]["nome"] == "Renomeada"

def test_remover_folha(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.get("/api/financeiro/contas")
    def _find(nodes, cod):
        for n in nodes:
            if n["codigo"] == cod: return n
            r = _find(n["filhos"], cod)
            if r: return r
    folha = _find(d["contas"], "5.6.01")
    st, r = c.post("/api/financeiro/contas/" + str(folha["id"]) + "/remover", {})
    assert st == 200 and r["acao"] == "apagada"

def test_sem_capability_barra_mutacao(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("con_l1", "senha123")   # consultor: sem aprovar_financeiro/editar_dados_loja
    _, d = c.get("/api/financeiro/contas")                       # GET ok (autenticado)
    g = d["contas"][0]
    st, _ = c.post("/api/financeiro/contas", {"pai_id": g["id"], "nome": "X"})
    assert st == 403
```
> Conferir os logins do seed em `tests/conftest.py`/`seed`: usar um **diretor** (tem `aprovar_financeiro` e
> `editar_dados_loja`) e um **consultor** sem essas capabilities. Ajustar os nomes de login aos reais do seed
> (ex.: `dir_l1`/`con_l1` — validar no conftest, como `test_auth_me_modulos.py`).

- [ ] **Step 2: Ver falhar.** `python3 -m pytest tests/test_plano_contas_api.py -q` → FAIL (rotas ausentes → 404).

- [ ] **Step 3: Roteamento no `main.py`.** Helper de owner+gate+capability (perto dos outros helpers, ~L260):
```python
def _contabil_ctx(handler, exige_edicao):
    """(usuario, db, owner_tipo, owner_id) ou envia erro e retorna None.
    Gate: módulo financeiro ativo na loja; edição exige aprovar_financeiro OU editar_dados_loja."""
    import mod_contabil, mod_tenancy
    usuario = get_usuario_sessao(handler)
    if not usuario:
        _send_json(handler, {"ok": False, "erro": "Não autenticado."}, 401); return None
    db = get_session()
    loja = db.get(Loja, usuario.get("loja_id")) if usuario.get("loja_id") else None
    if loja is not None and not mod_tenancy.modulo_ativo(loja, "financeiro"):
        db.close(); _send_json(handler, {"ok": False, "erro": "Módulo financeiro inativo."}, 403); return None
    if exige_edicao:
        niv = usuario.get("nivel")
        if not (perfis.pode(niv, "aprovar_financeiro") or perfis.pode(niv, "editar_dados_loja")):
            db.close(); _send_json(handler, {"ok": False, "erro": "Sem permissão."}, 403); return None
    try:
        ot, oid = mod_contabil.resolver_owner(db, usuario)
    except ValueError as e:
        db.close(); _send_json(handler, {"ok": False, "erro": str(e)}, 400); return None
    return usuario, db, ot, oid
```
Em `do_GET` (junto dos outros `_re.match`, ~após L294 auth):
```python
        if path == "/api/financeiro/contas":
            ctx = _contabil_ctx(self, exige_edicao=False)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            inc = (parse_qs(urlparse(self.path).query).get("incluir_inativas") or ["0"])[0] == "1"
            try:
                contas = mod_contabil.listar_contas(db, ot, oid, incluir_inativas=inc)
                _send_json(self, {"ok": True, "contas": contas})
            finally:
                db.close()
            return
```
Em `do_POST` (~após auth em do_POST, L1641+):
```python
        if path == "/api/financeiro/contas":
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b"{}")
                nova = mod_contabil.criar_conta(db, ot, oid, dd.get("pai_id"), dd.get("nome", ""))
                _send_json(self, {"ok": True, "conta": nova}, 201)
            except (ValueError, PermissionError) as e:
                _send_json(self, {"ok": False, "erro": str(e)}, 400 if isinstance(e, ValueError) else 403)
            finally:
                db.close()
            return
        m = _re.match(r"^/api/financeiro/contas/(\d+)/remover$", path)
        if m:
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                r = mod_contabil.remover_conta(db, ot, oid, int(m.group(1)))
                _send_json(self, {"ok": True, **r})
            except PermissionError as e:
                _send_json(self, {"ok": False, "erro": str(e)}, 403)
            except ValueError as e:
                _send_json(self, {"ok": False, "erro": str(e)}, 400)
            finally:
                db.close()
            return
```
Em `do_PUT` (L4623+):
```python
        m = _re.match(r"^/api/financeiro/contas/(\d+)$", path)
        if m:
            ctx = _contabil_ctx(self, exige_edicao=True)
            if ctx is None: return
            import mod_contabil
            usuario, db, ot, oid = ctx
            try:
                dd = json.loads(body or b"{}")
                r = mod_contabil.editar_conta(db, ot, oid, int(m.group(1)),
                                              nome=dd.get("nome"), ordem=dd.get("ordem"))
                _send_json(self, {"ok": True, "conta": r})
            except PermissionError as e:
                _send_json(self, {"ok": False, "erro": str(e)}, 403)
            except ValueError as e:
                _send_json(self, {"ok": False, "erro": str(e)}, 400)
            finally:
                db.close()
            return
```
> Confirmar imports já presentes no topo do `main.py`: `parse_qs`, `urlparse`, `json`, `_re`/`re`, `perfis`,
> `get_session`, `Loja`, `_send_json`. Se `_send_json` não existir com esse nome no main, usar o helper de JSON
> local equivalente (checar como as outras rotas respondem JSON) — **não** inventar.

- [ ] **Step 4: Manifesto `modulos.py`** — domínio `financeiro`:
```python
    "financeiro":  {"camada": "dominio", "depende_de": ["comercial"], "rotulo": "Financeiro", "faixa": "financeiro",
                    "arquivos": ["mod_provisoes.py", "mod_contabil.py"],
                    "tabelas": ["provisao_registro", "conta"],
                    "rotas": ["/api/provisoes", "/api/financeiro/contas"]},
```

- [ ] **Step 5: Testes.** `python3 -m pytest tests/test_plano_contas_api.py tests/test_arquitetura_modulos.py -q` → PASS.
  Suíte: `python3 -m pytest -q` → **699** (695 + 4). Se `test_arquitetura_modulos` reclamar de `mod_contabil` sem
  classificação, é porque o manifesto já o declara em `financeiro` — deve passar; se não, revisar a Task 4 do manifesto.

- [ ] **Step 6: Commit.**
```bash
git add main.py modulos.py tests/test_plano_contas_api.py
git commit -m "feat(financeiro): API /api/financeiro/contas (arvore/criar/editar/remover) + gate + manifesto"
```

---

## Task 4: Frontend — aba "Plano de Contas" na page-12 (árvore)

**Files:** Modify `static/index.html`. (Sem teste JS → verificação manual.)

- [ ] **Step 1: Abas na page-12.** No HTML da page-12 (~L1231-1235), envolver o painel atual e adicionar a nova aba.
  Trocar o bloco do `#loja-panel-financeiro` por:
```html
    <div class="home-tabs" style="display:flex;gap:6px;margin:12px 0 14px;flex-wrap:wrap">
      <button class="home-tab ativo" id="fintab-prov" onclick="finTab('prov')">Provisões</button>
      <button class="home-tab" id="fintab-plano" onclick="finTab('plano')">Plano de Contas</button>
    </div>
    <div id="fin-panel-prov"><div id="loja-panel-financeiro"><em style="color:var(--muted);font-size:12px">Carregando…</em></div></div>
    <div id="fin-panel-plano" style="display:none"><div id="plano-contas-box"><em style="color:var(--muted);font-size:12px">Carregando…</em></div></div>
```

- [ ] **Step 2: JS das abas + render da árvore** (perto de `adminFinanceiroCarregar`, ~L7189):
```javascript
function finTab(t){
  const prov = t === 'prov';
  document.getElementById('fin-panel-prov').style.display  = prov ? '' : 'none';
  document.getElementById('fin-panel-plano').style.display = prov ? 'none' : '';
  document.getElementById('fintab-prov').classList.toggle('ativo', prov);
  document.getElementById('fintab-plano').classList.toggle('ativo', !prov);
  if(!prov) planoContasCarregar();
}

async function planoContasCarregar(){
  const box = document.getElementById('plano-contas-box');
  if(!box) return;
  const r = await fetch('/api/financeiro/contas', {credentials:'same-origin'});
  if(r.status === 403){ box.innerHTML = '<em style="color:var(--muted)">Módulo financeiro inativo ou sem acesso.</em>'; return; }
  const d = await r.json().catch(()=>({}));
  if(!d.ok){ box.innerHTML = '<em style="color:var(--muted)">Falha ao carregar o plano.</em>'; return; }
  box.innerHTML = `<div style="margin-bottom:8px;font-size:11px;color:var(--muted)">Clique numa conta para adicionar filho, renomear ou inativar. Contas com lançamento nunca são apagadas — só inativadas.</div>`
    + d.contas.map(c => _pcNode(c, 0)).join('');
}

function _pcNode(c, nivel){
  const pad = 12 + nivel*18;
  const sint = c.tipo === 'sintetica';
  const nome = `<span style="font-weight:${sint?700:400};color:var(--text)">${esc(c.nome)}</span>`;
  const cod  = `<span style="font-family:var(--font-mono);font-size:10px;color:var(--muted);margin-right:8px">${esc(c.codigo)}</span>`;
  const acoes = `<span style="margin-left:auto;display:flex;gap:6px">
      <button class="btn btn-ghost btn-sm" onclick="pcNovo(${c.id})">+ filho</button>
      <button class="btn btn-ghost btn-sm" onclick="pcRenomear(${c.id},'${esc(c.nome).replace(/'/g,"\\'")}')">renomear</button>
      <button class="btn btn-ghost btn-sm" onclick="pcRemover(${c.id})">inativar/apagar</button>
    </span>`;
  const linha = `<div style="display:flex;align-items:center;padding:5px 10px 5px ${pad}px;border-bottom:1px solid var(--border);font-size:12px">${cod}${nome}${acoes}</div>`;
  const filhos = (c.filhos||[]).map(f => _pcNode(f, nivel+1)).join('');
  return linha + filhos;
}

async function pcNovo(paiId){
  const nome = await promptPopup ? await promptPopup('Nome da nova conta:') : prompt('Nome da nova conta:');
  if(!nome) return;
  const r = await fetch('/api/financeiro/contas', {method:'POST', headers:{'Content-Type':'application/json'},
    credentials:'same-origin', body: JSON.stringify({pai_id: paiId, nome})});
  if((await r.json().catch(()=>({}))).ok === false){ showToast('Falha ao criar', true); }
  planoContasCarregar();
}
async function pcRenomear(id, atual){
  const nome = await promptPopup ? await promptPopup('Novo nome:', atual) : prompt('Novo nome:', atual);
  if(!nome) return;
  await fetch('/api/financeiro/contas/'+id, {method:'PUT', headers:{'Content-Type':'application/json'},
    credentials:'same-origin', body: JSON.stringify({nome})});
  planoContasCarregar();
}
async function pcRemover(id){
  if(!confirm('Remover esta conta? (com filhos/lançamento será apenas inativada)')) return;
  const r = await fetch('/api/financeiro/contas/'+id+'/remover', {method:'POST', headers:{'Content-Type':'application/json'},
    credentials:'same-origin', body:'{}'});
  const d = await r.json().catch(()=>({}));
  if(d.ok) showToast(d.acao === 'apagada' ? 'Conta apagada' : 'Conta inativada');
  planoContasCarregar();
}
```
> Usar os helpers já existentes no app: `esc()`, `showToast()`, e `promptPopup`/`confirm`/`avisoPopup` conforme o
> padrão do arquivo (checar quais existem; se `promptPopup` não existir, usar `prompt` nativo — o código acima já faz
> fallback). Não hardcodar cores: usar `--text`/`--muted`/`--border`/`--font-mono`.

- [ ] **Step 3: Verificação.**
  - Balanço de chaves; `python3 -m pytest -q` → 699 (frontend não afeta backend).
  - **Manual (restart do servidor — mudou Python nas tasks 1-3):** Financeiro → aba **Plano de Contas** mostra a árvore
    (grupos 1–5 → subgrupos → analíticas); **+ filho** cria conta; **renomear** edita; **inativar/apagar** funciona
    (folha apaga, nó com filhos inativa e some). Aba **Provisões** segue intacta.

- [ ] **Step 4: Commit.**
```bash
git add static/index.html
git commit -m "feat(financeiro): tela Plano de Contas (aba na page-12, arvore add/renomear/inativar)"
```

---

## Task 5: Docs — DEV_LOG + spec status + backlog do módulo

**Files:** Modify `DEV_LOG.md`, `docs/superpowers/specs/financeiro/2026-07-09-plano-de-contas-design.md`.

- [ ] **Step 1:** No design, marcar **Status: IMPLEMENTADO** (data), e registrar o **corte consciente**: "mover conta
  (reparent/recodificar) não entra no #1 — `editar_conta` cobre nome+ordem; mover fica p/ o #2/futuro".
- [ ] **Step 2:** `DEV_LOG.md` — nota do sub-projeto #1 (modelo `Conta`, seed padrão por owner, CRUD inativar-não-apagar,
  API `/api/financeiro/contas`, aba na page-12; suíte 687→699; **restart do servidor**; próximos = #2 Livro de
  Lançamentos … #6 Reconciliação). Sinalizar que o `.docx` é a fonte de verdade do plano de contas.
- [ ] **Step 3: Commit.**
```bash
git add DEV_LOG.md docs/superpowers/specs/financeiro/2026-07-09-plano-de-contas-design.md
git commit -m "docs(financeiro): Plano de Contas implementado (sub-projeto 1) — DEV_LOG + spec status"
```

---

## Self-review do plano
- **Cobertura da spec:** modelo `Conta` (T1) · seed padrão completo do `.docx` §3 (T1, lista concreta) · CRUD +
  inativar-não-apagar (T2) · API + gate + tenancy por owner (T3) · UI abas/árvore (T4) · docs (T5). Escopo restrito
  ao #1 (lançamentos/DRE fora, declarado).
- **Sem placeholders:** modelo, `PLANO_PADRAO` completo, funções e testes com asserts concretos; rotas com regex e
  handlers reais; UI com HTML/JS completos. Contagens de teste esperadas por task (687→691→695→699).
- **Consistência de tipos:** `resolver_owner`→`(owner_tipo,owner_id)` usado em seed/listar/CRUD/API; `_serial` uniforme;
  respostas `{"ok":..,"conta"|"contas"|"acao"}` idênticas em API e consumidas no front. `remover` via **POST /remover**
  (não DELETE — o dispatch não tem `do_DELETE`).
- **Riscos:** (1) nomes exatos de helpers do `main.py` (`_send_json`) e logins do seed (`dir_l1`/`con_l1`) — o
  implementador **confirma** antes (notas nas tasks), não inventa. (2) `test_arquitetura_modulos`: `mod_contabil.py`
  já declarado no manifesto (T3) → boundary verde. (3) Frontend sem teste → verificação manual + restart obrigatório.
  (4) Corte consciente: "mover conta" fora do #1 (registrado na T5, não silenciado).
- **Fora de escopo:** sub-projetos #2–#6; `projeto_id`; regras contábeis de sinal na DRE (deduções) = #4.
