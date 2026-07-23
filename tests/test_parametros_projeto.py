import pytest, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_db(db_pg_limpo):
    """Banco de teste limpo por função (Postgres — conftest.db_pg_limpo)."""
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
