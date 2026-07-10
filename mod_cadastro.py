"""mod_cadastro.py — módulo Cadastro (Modulos_Orizon_v9, módulo 2): Funcionário, Fornecedor, Terceiro.

Fronteira obrigatória: Funcionário (RH) ≠ Usuário (conta de login, Admin/Núcleo). Ligados por
referência (Usuario.funcionario_id / Funcionario.usuario_id), NUNCA duplicando dado pessoal.
"""
import re
from database import Funcionario, Fornecedor, Terceiro, Usuario

REMUNERACAO_TIPOS = ("fixa", "fixa_variavel")
FORN_CATEGORIAS   = ("materia_prima", "transportadora", "servicos", "outro")
TERC_SERVICOS     = ("montador", "outros")
PERFIS_ACESSO     = ("consultor", "gerente", "diretor")   # "Perfil de Usuário" (nivel)


def _s(v):
    v = ("" if v is None else str(v)).strip()
    return v or None


def _f(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _digitos(s):
    return re.sub(r"\D", "", s or "")


# ── Funcionário ──────────────────────────────────────────────────────────────
def func_serialize(f, db=None):
    d = {"id": f.id, "nome": f.nome, "cpf": f.cpf or "", "telefone": f.telefone or "",
         "email": f.email or "", "cargo": f.cargo or "",
         "remuneracao_tipo": f.remuneracao_tipo or "fixa",
         "remuneracao_fixa": f.remuneracao_fixa, "remuneracao_var": f.remuneracao_var,
         "status": f.status or "ativo", "usuario_id": f.usuario_id,
         "acesso": {"tem_acesso": False, "email": f.email or "", "perfil": "consultor"}}
    if db is not None and f.usuario_id:
        u = db.get(Usuario, f.usuario_id)
        if u and u.ativo:
            d["acesso"] = {"tem_acesso": True, "email": u.email or u.login, "perfil": u.nivel}
    return d


def func_aplicar(db, f, req, loja_id):
    if f.loja_id is None:
        f.loja_id = loja_id
    if _s(req.get("nome")):
        f.nome = _s(req.get("nome"))
    for campo in ("cpf", "telefone", "email", "cargo"):
        if campo in req:
            setattr(f, campo, _s(req.get(campo)))
    if "remuneracao_tipo" in req:
        f.remuneracao_tipo = (_s(req.get("remuneracao_tipo")) or "fixa")
    if "remuneracao_fixa" in req:
        f.remuneracao_fixa = _f(req.get("remuneracao_fixa"))
    if "remuneracao_var" in req:
        f.remuneracao_var = _f(req.get("remuneracao_var"))
    if "status" in req:
        f.status = (_s(req.get("status")) or "ativo")


def func_sync_acesso(db, f, req):
    """Cria/atualiza/desativa a conta de login (Usuário) vinculada ao Funcionário — a fronteira.
    `req['acesso'] = {tem_acesso, email, perfil}`. Retorna (ok, erro)."""
    ac = req.get("acesso") or {}
    tem = bool(ac.get("tem_acesso"))
    if not tem:
        if f.usuario_id:
            u = db.get(Usuario, f.usuario_id)
            if u:
                u.ativo = 0                      # desativa (nunca apaga — preserva histórico/sessões)
        return True, None
    email = _s(ac.get("email")) or _s(f.email)
    perfil = _s(ac.get("perfil")) or "consultor"
    if not email:
        return False, "Informe o e-mail de acesso do funcionário."
    if perfil not in PERFIS_ACESSO:
        return False, "Perfil de acesso inválido."
    # e-mail (login) não pode colidir com outro usuário
    conflito = (db.query(Usuario)
                .filter(Usuario.login == email, Usuario.id != (f.usuario_id or -1)).first())
    if conflito is not None:
        return False, "Já existe uma conta com este e-mail."
    if f.usuario_id:
        u = db.get(Usuario, f.usuario_id)
        if u:
            u.login = email; u.email = email; u.nivel = perfil; u.ativo = 1
            u.nome = f.nome; u.cpf = f.cpf; u.loja_id = f.loja_id
            return True, None
    # cria conta nova ligada — senha inicial = dígitos do CPF (ou 'orizon123' se sem CPF)
    u = Usuario(nome=f.nome, login=email, email=email, cpf=f.cpf, nivel=perfil,
                loja_id=f.loja_id, ativo=1, funcionario_id=f.id)
    u.set_senha(_digitos(f.cpf) or "orizon123")
    db.add(u); db.flush()
    f.usuario_id = u.id
    return True, None


# ── Fornecedor ───────────────────────────────────────────────────────────────
def forn_serialize(f, db=None):
    return {"id": f.id, "tipo_pessoa": f.tipo_pessoa or "pj", "nome": f.nome,
            "cnpj_cpf": f.cnpj_cpf or "", "telefone": f.telefone or "", "email": f.email or "",
            "categoria": f.categoria or "", "prazo_pagamento": f.prazo_pagamento,
            "dados_bancarios": f.dados_bancarios or "", "status": f.status or "ativo"}


def forn_aplicar(db, f, req, loja_id):
    if f.loja_id is None:
        f.loja_id = loja_id
    if _s(req.get("nome")):
        f.nome = _s(req.get("nome"))
    for campo in ("cnpj_cpf", "telefone", "email", "categoria", "dados_bancarios"):
        if campo in req:
            setattr(f, campo, _s(req.get(campo)))
    if "tipo_pessoa" in req:
        f.tipo_pessoa = (_s(req.get("tipo_pessoa")) or "pj")
    if "prazo_pagamento" in req:
        f.prazo_pagamento = _i(req.get("prazo_pagamento"))
    if "status" in req:
        f.status = (_s(req.get("status")) or "ativo")


# ── Terceiro (sempre PF) ─────────────────────────────────────────────────────
def terc_serialize(t, db=None):
    return {"id": t.id, "nome": t.nome, "cpf": t.cpf or "", "telefone": t.telefone or "",
            "tipo_servico": t.tipo_servico or "montador", "pix": t.pix or "",
            "dados_bancarios": t.dados_bancarios or "", "condicao": t.condicao or "",
            "status": t.status or "ativo"}


def terc_aplicar(db, t, req, loja_id):
    if t.loja_id is None:
        t.loja_id = loja_id
    if _s(req.get("nome")):
        t.nome = _s(req.get("nome"))
    for campo in ("cpf", "telefone", "pix", "dados_bancarios", "condicao"):
        if campo in req:
            setattr(t, campo, _s(req.get(campo)))
    if "tipo_servico" in req:
        t.tipo_servico = (_s(req.get("tipo_servico")) or "montador")
    if "status" in req:
        t.status = (_s(req.get("status")) or "ativo")


# ── Listagem genérica (Lista/Tabela: filtro por status + busca nome/documento) ─
def listar(db, Model, serialize, loja_id, q=None, status=None):
    rows = db.query(Model).filter_by(loja_id=loja_id).order_by(Model.id.desc()).all()
    out = [serialize(r, db) for r in rows]
    if status in ("ativo", "inativo"):
        out = [x for x in out if x.get("status") == status]
    if q:
        ql = q.strip().lower()
        qd = _digitos(q)
        def match(x):
            doc = x.get("cpf") or x.get("cnpj_cpf") or ""
            return (ql and ql in (x.get("nome", "").lower())) or (qd and qd in _digitos(doc))
        out = [x for x in out if match(x)]
    return out


META = {
    "remuneracao_tipos": list(REMUNERACAO_TIPOS),
    "fornecedor_categorias": list(FORN_CATEGORIAS),
    "terceiro_servicos": list(TERC_SERVICOS),
    "perfis_acesso": list(PERFIS_ACESSO),
}
