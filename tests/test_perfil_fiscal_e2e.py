import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
from cryptography.fernet import Fernet
os.environ["ORIZON_FISCAL_KEY"] = Fernet.generate_key().decode()


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def _emitente(app_db, loja_id):
    """Relê o Emitente da loja via loja.emitente_id."""
    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, loja_id)
        return db.get(app_db.Emitente, loja.emitente_id) if loja and loja.emitente_id else None
    finally:
        db.close()


def _sem_emitente(app_db, loja_id):
    """Deixa a loja sem Emitente (emitente_id None e remove o registro)."""
    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, loja_id)
        eid = loja.emitente_id
        loja.emitente_id = None
        if eid:
            em = db.get(app_db.Emitente, eid)
            if em:
                db.delete(em)
        db.commit()
    finally:
        db.close()


def test_get_perfil_inexistente_devolve_padrao(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _sem_emitente(app_db, lid)
    st, b = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert st == 200 and b["existe"] is False, b
    assert b["perfil"]["regime_tributario"] == "simples" and b["perfil"]["cfop_dentro_uf"] == "5102"
    assert b["perfil"]["csosn_contribuinte"] == "101"
    assert "regime_tributario" in b["placeholders"]
    assert b["ambiente_ativo"] == "homologacao"
    assert b["token_homolog_definido"] is False and b["token_prod_definido"] is False


def test_put_config_persiste(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    st, _ = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal",
                  {"razao_social": "LOJA X LTDA", "regime_tributario": "simples",
                   "logradouro": "Av Central", "cidade": "Campinas", "uf": "SP",
                   "csosn_contribuinte": "500", "placeholders": []})
    assert st == 200
    st2, b = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert b["existe"] is True and b["perfil"]["razao_social"] == "LOJA X LTDA"
    assert b["perfil"]["logradouro"] == "Av Central" and b["perfil"]["cidade"] == "Campinas"
    assert b["perfil"]["uf"] == "SP" and b["perfil"]["csosn_contribuinte"] == "500"
    assert b["placeholders"] == []
    # relê o Emitente da loja e confere os campos aplicados
    em = _emitente(app_db, lid)
    assert em is not None
    assert em.razao_social == "LOJA X LTDA"
    assert em.logradouro == "Av Central" and em.cidade == "Campinas" and em.uf == "SP"
    assert em.csosn_contribuinte == "500"


def test_put_config_cria_emitente_se_faltar(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _sem_emitente(app_db, lid)
    st, _ = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal",
                  {"razao_social": "NOVA LOJA LTDA", "cidade": "Sorocaba", "placeholders": []})
    assert st == 200
    em = _emitente(app_db, lid)
    assert em is not None and em.razao_social == "NOVA LOJA LTDA" and em.cidade == "Sorocaba"


def test_put_config_valida(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    st, b = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal", {"regime_tributario": "invalido"})
    assert st == 400 and "regime" in b["erro"]


def test_put_segredos_cifra_e_nao_ecoa(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    st, _ = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/segredos", {"focus_token_homolog": "TOKEN-SECRETO"})
    assert st == 200
    st2, b = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert b["token_homolog_definido"] is True
    assert "TOKEN-SECRETO" not in _json.dumps(b)
    em = _emitente(app_db, lid)
    assert em.focus_token_homolog_enc and em.focus_token_homolog_enc != "TOKEN-SECRETO"


def test_put_segredos_vazio_mantem(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/segredos", {"focus_token_homolog": "MANTEM"})
    enc_antes = _emitente(app_db, lid).focus_token_homolog_enc
    # vazio → não sobrescreve
    c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/segredos", {"focus_token_homolog": ""})
    assert _emitente(app_db, lid).focus_token_homolog_enc == enc_antes


def test_ambiente_producao_bloqueado_com_placeholder(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    c.put(f"/api/admin/lojas/{lid}/perfil-fiscal", {"placeholders": ["regime_tributario"]})
    st, b = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/ambiente", {"ambiente": "producao"})
    assert st == 400 and "produção" in b["erro"].lower()
    c.put(f"/api/admin/lojas/{lid}/perfil-fiscal", {"placeholders": []})
    st2, b2 = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/ambiente", {"ambiente": "producao"})
    assert st2 == 200 and b2["ambiente_ativo"] == "producao"
    assert _emitente(app_db, lid).ambiente_ativo == "producao"


def test_perm_consultor_403(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "cons_l1")
    lid = seed["loja1_id"]
    st, _ = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert st == 403


def test_perm_outra_loja_403(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja1_id"]
    st, _ = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert st == 403


def test_nao_autenticado_401(http_client_factory, seed, app_db):
    c = http_client_factory()
    lid = seed["loja2_id"]
    st, _ = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert st == 401
