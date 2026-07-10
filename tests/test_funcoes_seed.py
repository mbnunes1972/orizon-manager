import seed as seed_mod
import mod_cadastro


def test_criar_funcoes_seed_idempotente_por_loja(app_db, seed):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    n1 = seed_mod.criar_funcoes_seed(db, loja); db.commit()
    assert n1 == len(seed_mod.FUNCOES_PADRAO)             # todas criadas
    # catálogo populado com os cargos-chave
    nomes = {f["nome"] for f in mod_cadastro.listar_funcoes(db, loja)}
    assert {"Medidor", "Montador", "Projetista Executivo"} <= nomes
    # re-executar não duplica
    n2 = seed_mod.criar_funcoes_seed(db, loja); db.commit()
    assert n2 == 0
    total = len(mod_cadastro.listar_funcoes(db, loja))
    assert total == len(seed_mod.FUNCOES_PADRAO)
    db.close()


def test_funcoes_seed_escopado_por_loja(app_db, seed):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    l2 = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    seed_mod.criar_funcoes_seed(db, l1); db.commit()
    # loja 2 não recebe as funções da loja 1 (isolamento F4)
    assert mod_cadastro.listar_funcoes(db, l2) == []
    seed_mod.criar_funcoes_seed(db, l2); db.commit()
    assert len(mod_cadastro.listar_funcoes(db, l2)) == len(seed_mod.FUNCOES_PADRAO)
    db.close()
