import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
from cryptography.fernet import Fernet
os.environ.setdefault("ORIZON_FISCAL_KEY", Fernet.generate_key().decode())


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def _emitente_central(app_db, rede_id):
    """Relê o Emitente central da rede via rede.emitente_central_id."""
    db = app_db.get_session()
    try:
        rede = db.get(app_db.Rede, rede_id)
        if not rede or not rede.emitente_central_id:
            return None
        return db.get(app_db.Emitente, rede.emitente_central_id)
    finally:
        db.close()


def _sem_emitente_central(app_db, rede_id):
    """Zera o Emitente central da rede (remove o registro e a FK)."""
    db = app_db.get_session()
    try:
        rede = db.get(app_db.Rede, rede_id)
        eid = rede.emitente_central_id
        rede.emitente_central_id = None
        if eid:
            em = db.get(app_db.Emitente, eid)
            if em:
                db.delete(em)
        db.commit()
    finally:
        db.close()


# ── GET ─────────────────────────────────────────────────────────────────────
def test_get_perfil_central_inexistente_devolve_padrao(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "adm_rede")
    rid = seed["rede_id"]
    _sem_emitente_central(app_db, rid)
    st, b = c.get(f"/api/admin/redes/{rid}/perfil-fiscal")
    assert st == 200 and b["existe"] is False, b
    assert b["perfil"]["regime_tributario"] == "simples"
    assert b["ambiente_ativo"] == "homologacao"
    assert b["token_homolog_definido"] is False and b["token_prod_definido"] is False


# ── PUT config ──────────────────────────────────────────────────────────────
def test_put_config_cria_central_e_persiste(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "adm_rede")
    rid = seed["rede_id"]
    _sem_emitente_central(app_db, rid)
    st, _ = c.put(f"/api/admin/redes/{rid}/perfil-fiscal",
                  {"razao_social": "CENTRAL REDE LTDA", "regime_tributario": "simples",
                   "logradouro": "Av Rede", "cidade": "Campinas", "uf": "SP",
                   "csosn_contribuinte": "500", "placeholders": []})
    assert st == 200
    # a FK do central foi setada e os campos aplicados
    em = _emitente_central(app_db, rid)
    assert em is not None
    assert em.razao_social == "CENTRAL REDE LTDA"
    assert em.logradouro == "Av Rede" and em.cidade == "Campinas" and em.uf == "SP"
    assert em.csosn_contribuinte == "500"
    # GET reflete
    st2, b = c.get(f"/api/admin/redes/{rid}/perfil-fiscal")
    assert b["existe"] is True and b["perfil"]["razao_social"] == "CENTRAL REDE LTDA"
    assert b["perfil"]["cidade"] == "Campinas" and b["perfil"]["uf"] == "SP"
    assert b["placeholders"] == []


def test_put_config_valida(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "adm_rede")
    rid = seed["rede_id"]
    st, b = c.put(f"/api/admin/redes/{rid}/perfil-fiscal", {"regime_tributario": "invalido"})
    assert st == 400 and "regime" in b["erro"]


# ── PUT segredos (write-only) ───────────────────────────────────────────────
def test_put_segredos_cifra_e_nao_ecoa(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "adm_rede")
    rid = seed["rede_id"]
    st, _ = c.put(f"/api/admin/redes/{rid}/perfil-fiscal/segredos",
                  {"focus_token_homolog": "TOKEN-CENTRAL"})
    assert st == 200
    st2, b = c.get(f"/api/admin/redes/{rid}/perfil-fiscal")
    assert b["token_homolog_definido"] is True
    assert "TOKEN-CENTRAL" not in _json.dumps(b)
    em = _emitente_central(app_db, rid)
    assert em.focus_token_homolog_enc and em.focus_token_homolog_enc != "TOKEN-CENTRAL"


# ── PUT ambiente (guarda produção) ──────────────────────────────────────────
def test_ambiente_producao_bloqueado_com_placeholder(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "adm_rede")
    rid = seed["rede_id"]
    c.put(f"/api/admin/redes/{rid}/perfil-fiscal", {"placeholders": ["regime_tributario"]})
    st, b = c.put(f"/api/admin/redes/{rid}/perfil-fiscal/ambiente", {"ambiente": "producao"})
    assert st == 400 and "produção" in b["erro"].lower()
    c.put(f"/api/admin/redes/{rid}/perfil-fiscal", {"placeholders": []})
    st2, b2 = c.put(f"/api/admin/redes/{rid}/perfil-fiscal/ambiente", {"ambiente": "producao"})
    assert st2 == 200 and b2["ambiente_ativo"] == "producao"
    assert _emitente_central(app_db, rid).ambiente_ativo == "producao"


# ── Gates ───────────────────────────────────────────────────────────────────
def test_super_admin_pode(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "super")
    rid = seed["rede_id"]
    st, b = c.get(f"/api/admin/redes/{rid}/perfil-fiscal")
    assert st == 200, b


def test_perm_consultor_403(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "cons_l1")
    rid = seed["rede_id"]
    st, _ = c.get(f"/api/admin/redes/{rid}/perfil-fiscal")
    assert st == 403


def test_nao_autenticado_401(http_client_factory, seed, app_db):
    c = http_client_factory()
    rid = seed["rede_id"]
    st, _ = c.get(f"/api/admin/redes/{rid}/perfil-fiscal")
    assert st == 401


def test_admin_rede_de_outra_rede_403(http_client_factory, seed, app_db):
    """admin_rede só enxerga a própria rede: uma 2ª rede + seu admin não pode a 1ª."""
    db = app_db.get_session()
    try:
        r2 = app_db.Rede(nome="Rede Alheia")
        db.add(r2); db.flush()
        u = app_db.Usuario(nome="Adm Rede 2", login="adm_rede2", nivel="admin_rede",
                           rede_id=r2.id, ativo=1)
        u.set_senha("senha123")
        db.add(u); db.commit()
        r2_id = r2.id
    finally:
        db.close()
    c = _login(http_client_factory, "adm_rede2")
    rid = seed["rede_id"]  # a rede do seed, NÃO a r2
    st, _ = c.get(f"/api/admin/redes/{rid}/perfil-fiscal")
    assert st == 403
    # e também no PUT
    st2, _ = c.put(f"/api/admin/redes/{rid}/perfil-fiscal", {"razao_social": "HACK"})
    assert st2 == 403
    # mas na PRÓPRIA rede funciona
    st3, _ = c.get(f"/api/admin/redes/{r2_id}/perfil-fiscal")
    assert st3 == 200
