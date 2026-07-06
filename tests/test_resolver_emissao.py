import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_fiscal


def _setup(app_db):
    db = app_db.get_session()
    ec = app_db.Emitente(cnpj="CENTRAL"); es = app_db.Emitente(cnpj="LOJA"); db.add_all([ec, es]); db.flush()
    rede = app_db.Rede(nome="Orizon", emitente_central_id=ec.id); db.add(rede); db.flush()
    loja = app_db.Loja(nome="Inspirium", rede_id=rede.id, emitente_id=es.id); db.add(loja); db.flush()
    db.add(app_db.PerfilEmissao(owner_tipo="rede", owner_id=rede.id, tipo_doc="produto", emitente_id=ec.id))
    db.commit()
    return db, loja, ec, es


def test_resolver_produto_default_rede(app_db):
    db, loja, ec, es = _setup(app_db)
    assert mod_fiscal.resolver_emitente(db, loja, "produto").id == ec.id   # rede default
    assert mod_fiscal.resolver_emitente(db, loja, "servico").id == es.id   # self (sem política)
    db.close()


def test_resolver_override_loja(app_db):
    db, loja, ec, es = _setup(app_db)
    db.add(app_db.PerfilEmissao(owner_tipo="loja", owner_id=loja.id, tipo_doc="produto", emitente_id=es.id)); db.commit()
    assert mod_fiscal.resolver_emitente(db, loja, "produto").id == es.id   # override da loja vence
    db.close()


def test_resolver_avulsa_self(app_db):
    db = app_db.get_session()
    e = app_db.Emitente(cnpj="AV"); db.add(e); db.flush()
    loja = app_db.Loja(nome="Avulsa", rede_id=None, emitente_id=e.id); db.add(loja); db.commit()
    assert mod_fiscal.resolver_emitente(db, loja, "produto").id == e.id
    assert mod_fiscal.resolver_emitente(db, loja, "servico").id == e.id
    db.close()


def test_resolver_sem_emitente_erra(app_db):
    import pytest
    db = app_db.get_session()
    loja = app_db.Loja(nome="Sem", rede_id=None, emitente_id=None); db.add(loja); db.commit()
    with pytest.raises(ValueError):
        mod_fiscal.resolver_emitente(db, loja, "produto")
    db.close()


def test_resolver_plano_conta_docs(app_db):
    db = app_db.get_session()
    e = app_db.Emitente(cnpj="X"); db.add(e); db.flush()
    loja = app_db.Loja(nome="L", emitente_id=e.id); db.add(loja); db.flush()
    proj = app_db.Projeto(nome_safe="P", loja_id=loja.id); db.add(proj); db.commit()
    tipos = lambda **kw: [x["tipo_doc"] for x in mod_fiscal.resolver_plano(db, proj, **kw)]
    assert tipos(tem_produto=True, tem_servico=False) == ["produto"]
    assert tipos(tem_produto=True, tem_servico=True) == ["produto", "servico"]
    assert tipos(tem_produto=False, tem_servico=False) == []
    db.close()


def test_focus_client_para_emitente_usa_token_do_ambiente(app_db):
    import fiscal_cripto
    db = app_db.get_session()
    e = app_db.Emitente(cnpj="X", ambiente_ativo="homologacao",
                        focus_token_homolog_enc=fiscal_cripto.encrypt("TOKHOMOLOG"))
    db.add(e); db.commit()
    client = mod_fiscal.focus_client_para_emitente(db, e.id)
    assert client.token == "TOKHOMOLOG" and "homologacao" in client.base_url
    db.close()
