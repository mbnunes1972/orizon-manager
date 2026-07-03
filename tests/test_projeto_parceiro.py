"""Etapa 'Criação do Projeto': associar/remover parceiro (arquiteto), travado após a
assinatura do contrato. E enriquecimento do bloco cliente com dados vivos do cadastro."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_enriquecer_cliente_do_projeto_usa_dados_vivos(app_db):
    import main
    db = app_db.get_session()
    try:
        c = app_db.Cliente(nome="Ana", telefone="111", email="a@x", loja_id=1)
        db.add(c); db.flush()
        proj = {"cliente_id": c.id, "cliente": {"id": c.id, "nome": "Ana", "telefone": "OLD"}}
        c.telefone = "999-NOVO"; db.commit()
        main._enriquecer_cliente_do_projeto(proj, db)
    finally:
        db.close()
    assert proj["cliente"]["telefone"] == "999-NOVO"   # snapshot atualizado com o cadastro vivo


def _cria_parceiro_loja(app_db, loja_id):
    db = app_db.get_session()
    parc = app_db.Parceiro(nome="Arq X", abrangencia="loja")
    db.add(parc); db.flush()
    db.add(app_db.ParceiroLoja(parceiro_id=parc.id, loja_id=loja_id, ativo=1))
    db.commit()
    pid = parc.id
    db.close()
    return pid


def test_associar_parceiro_ok(app_db, seed, projetos_dir, http_client_factory):
    pid = _cria_parceiro_loja(app_db, seed["loja1_id"])
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/parceiro", {"parceiro_id": pid})
    assert st == 200 and b.get("ok"), b
    assert b["parceiro"]["id"] == pid
    # persistiu no projeto.json
    import mod_omie
    proj = mod_omie._carregar_projeto(seed["projeto_l1"])
    assert proj.get("parceiro_id") == pid
    # remover
    st2, b2 = c.post(f"/api/projetos/{seed['projeto_l1']}/parceiro", {"parceiro_id": None})
    assert st2 == 200 and b2.get("ok")
    assert mod_omie._carregar_projeto(seed["projeto_l1"]).get("parceiro_id") is None


def test_associar_parceiro_bloqueado_apos_assinatura(app_db, seed, projetos_dir, http_client_factory):
    pid = _cria_parceiro_loja(app_db, seed["loja1_id"])
    # marca o contrato do Proj_L1 como assinado
    db = app_db.get_session()
    ct = db.get(app_db.Contrato, seed["contrato_l1_id"])
    ct.status = "assinado"
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, b = c.post(f"/api/projetos/{seed['projeto_l1']}/parceiro", {"parceiro_id": pid})
    assert b.get("ok") is False and "assinado" in (b.get("erro") or "").lower()
