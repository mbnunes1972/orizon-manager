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


def _reset_perfil(app_db, loja_id):
    db = app_db.get_session()
    db.query(app_db.PerfilFiscal).filter_by(loja_id=loja_id).delete()
    db.commit(); db.close()


def test_get_perfil_inexistente_devolve_padrao(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    st, b = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert st == 200 and b["existe"] is False, b
    assert b["perfil"]["regime_tributario"] == "simples" and b["perfil"]["cfop_dentro_uf"] == "5102"
    assert "regime_tributario" in b["placeholders"]
    assert b["token_homolog_definido"] is False and b["token_prod_definido"] is False


def test_put_config_persiste(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    st, _ = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal",
                  {"razao_social": "LOJA X LTDA", "regime_tributario": "simples", "placeholders": []})
    assert st == 200
    st2, b = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert b["existe"] is True and b["perfil"]["razao_social"] == "LOJA X LTDA"
    assert b["placeholders"] == []


def test_put_config_valida(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    st, b = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal", {"regime_tributario": "invalido"})
    assert st == 400 and "regime" in b["erro"]


def test_put_segredos_cifra_e_nao_ecoa(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    st, _ = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/segredos", {"focus_token_homolog": "TOKEN-SECRETO"})
    assert st == 200
    st2, b = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert b["token_homolog_definido"] is True
    assert "TOKEN-SECRETO" not in _json.dumps(b)
    db = app_db.get_session()
    pf = db.query(app_db.PerfilFiscal).filter_by(loja_id=lid).first()
    assert pf.focus_token_homolog_enc and pf.focus_token_homolog_enc != "TOKEN-SECRETO"
    db.close()


def test_ambiente_producao_bloqueado_com_placeholder(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    c.put(f"/api/admin/lojas/{lid}/perfil-fiscal", {"placeholders": ["regime_tributario"]})
    st, b = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/ambiente", {"ambiente": "producao"})
    assert st == 400 and "produção" in b["erro"].lower()
    c.put(f"/api/admin/lojas/{lid}/perfil-fiscal", {"placeholders": []})
    st2, b2 = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/ambiente", {"ambiente": "producao"})
    assert st2 == 200 and b2["ambiente_ativo"] == "producao"


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


def test_focus_client_para_loja(http_client_factory, seed, app_db):
    import mod_fiscal, fiscal_cripto
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    db = app_db.get_session()
    db.add(app_db.PerfilFiscal(loja_id=lid, ambiente_ativo="homologacao",
                               focus_token_homolog_enc=fiscal_cripto.encrypt("TESTE-TOKEN")))
    db.commit(); db.close()
    db2 = app_db.get_session()
    cli = mod_fiscal.focus_client_para_loja(db2, lid)
    assert cli.token == "TESTE-TOKEN"
    assert cli.base_url == "https://homologacao.focusnfe.com.br"
    db2.close()


def test_focus_client_para_loja_sem_token(http_client_factory, seed, app_db):
    import mod_fiscal, pytest
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    db = app_db.get_session()
    db.add(app_db.PerfilFiscal(loja_id=lid, ambiente_ativo="producao"))
    db.commit(); db.close()
    db2 = app_db.get_session()
    with pytest.raises(ValueError):
        mod_fiscal.focus_client_para_loja(db2, lid)
    db2.close()
