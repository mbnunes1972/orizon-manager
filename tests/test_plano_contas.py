import mod_contabil as mc


def test_seed_idempotente_e_grupos(app_db):
    db = app_db.get_session()
    n1 = mc.seed_plano(db, "loja", 1)   # materializa
    n2 = mc.seed_plano(db, "loja", 1)   # 2ª vez não duplica
    contas = mc.listar_contas(db, "loja", 1)   # árvore (raízes)
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


def test_resolver_owner_avulsa_e_rede_admin(app_db):
    db = app_db.get_session()
    # loja inexistente (avulsa, sem rede) -> owner é a própria loja
    assert mc.resolver_owner(db, {"loja_id": 1, "rede_id": None}) == ("loja", 1)
    # usuário admin de rede (sem loja) -> owner é a rede
    assert mc.resolver_owner(db, {"loja_id": None, "rede_id": 7}) == ("rede", 7)
    db.close()


def test_resolver_owner_loja_com_rede(seed, app_db):
    db = app_db.get_session()
    # loja pertencente a uma rede -> owner é a REDE (contabilidade compartilhada)
    assert mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None}) == ("rede", seed["rede_id"])
    db.close()
