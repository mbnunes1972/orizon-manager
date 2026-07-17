import mod_cadastro
import mod_folha
import mod_provisoes


def test_funcao_serialize_aplicar_comissao_fixa(app_db):
    db = app_db.get_session()
    loja = app_db.Loja(nome="L CF"); db.add(loja); db.flush()
    f = app_db.Funcao(loja_id=loja.id, nome="Func CF", status="ativo"); db.add(f); db.flush()
    mod_cadastro.funcao_aplicar(db, f, {"comissao_fixa": 350.0}, loja.id); db.flush()
    assert f.comissao_fixa == 350.0
    assert mod_cadastro.funcao_serialize(f)["comissao_fixa"] == 350.0
    db.close()


def test_calcular_folha_soma_comissao_fixa_no_total(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Reg CF", salario_fixo=2000.0, comissao_fixa=300.0,
                       usa_comissao_vendas=0, status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="R", funcao_id=fn.id, status="ativo"); db.add(f); db.commit()
    c = mod_folha.calcular_folha(db, loja, f, "2026-07", mod_provisoes.config_financeira_default())
    assert c["parte_fixa"] == 2000.0
    assert c["comissao_fixa"] == 300.0
    assert c["total"] == 2300.0        # fixa 2000 + comissão fixa 300 (isenta de encargos)
    db.close()


def test_gerar_folha_persiste_e_serializa_comissao_fixa(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="CF2", salario_fixo=1000.0, comissao_fixa=200.0,
                       usa_comissao_vendas=0, status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="G", funcao_id=fn.id, status="ativo"); db.add(f); db.commit()
    mod_folha.gerar_folha(db, loja, "2026-07", mod_provisoes.config_financeira_default()); db.commit()
    reg = db.query(app_db.FolhaPagamento).filter_by(funcionario_id=f.id, competencia="2026-07").first()
    assert reg.comissao_fixa == 200.0
    assert reg.total == 1200.0
    d = mod_folha.serialize(db, reg)
    assert d["comissao_fixa"] == 200.0
    db.close()
