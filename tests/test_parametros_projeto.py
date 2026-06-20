import pytest, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    import database
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", db_file)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    monkeypatch.setattr(database, "ENGINE", engine)
    monkeypatch.setattr(database, "Session", sessionmaker(bind=engine))
    database.init_db()
    yield


def test_parametros_json_persiste():
    from database import get_session, Projeto
    db = get_session()
    p = Projeto(nome_safe="Proj_P", parametros_json=json.dumps({"carga_trib": 8.0, "brinde": 300}))
    db.add(p); db.commit()
    lido = db.get(Projeto, "Proj_P")
    assert json.loads(lido.parametros_json)["brinde"] == 300
    db.close()


def test_parametros_json_default_none():
    from database import get_session, Projeto
    db = get_session()
    p = Projeto(nome_safe="Proj_P2")
    db.add(p); db.commit()
    assert db.get(Projeto, "Proj_P2").parametros_json is None
    db.close()


def test_migracao_copia_estruturais_do_orcamento():
    import json
    from database import get_session, Orcamento, Projeto, migrar_parametros_para_projeto
    db = get_session()
    db.add(Projeto(nome_safe="Proj_M", status="quente"))
    db.add(Orcamento(projeto_id="Proj_M", nome="Orçamento 1", ordem=1,
                     margens=json.dumps({"desconto_pct": 5.0, "carga_trib": 8.0,
                                         "comissao_arq_pct": 10.0, "brinde": 200})))
    db.commit()
    n = migrar_parametros_para_projeto(db)
    assert n == 1
    p = db.get(Projeto, "Proj_M")
    par = json.loads(p.parametros_json)
    assert par["comissao_arq_pct"] == 10.0 and par["brinde"] == 200
    assert "desconto_pct" not in par
    db.close()


def test_migracao_parametros_idempotente():
    import json
    from database import get_session, Orcamento, Projeto, migrar_parametros_para_projeto
    db = get_session()
    db.add(Projeto(nome_safe="Proj_I", status="quente",
                   parametros_json=json.dumps({"comissao_arq_pct": 99.0})))
    db.add(Orcamento(projeto_id="Proj_I", nome="Orçamento 1", ordem=1,
                     margens=json.dumps({"comissao_arq_pct": 10.0})))
    db.commit()
    assert migrar_parametros_para_projeto(db) == 0     # já tem parametros → não toca
    assert json.loads(db.get(Projeto, "Proj_I").parametros_json)["comissao_arq_pct"] == 99.0
    db.close()
