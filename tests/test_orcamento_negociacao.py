import pytest, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_db(db_pg_limpo):
    """Banco de teste limpo por função (Postgres — conftest.db_pg_limpo)."""
    yield


def test_negociacao_json_persiste():
    from database import get_session, Orcamento
    snap = {"codigo": "total_flex", "n_parcelas": 10,
            "tf_datas": ["2026-07-18", "2026-08-17"]}
    db = get_session()
    o = Orcamento(projeto_id="Proj_N", nome="Orçamento 1", ordem=1,
                  negociacao_json=json.dumps(snap, ensure_ascii=False))
    db.add(o); db.commit(); db.refresh(o)
    lido = db.get(Orcamento, o.id)
    assert json.loads(lido.negociacao_json)["codigo"] == "total_flex"
    assert json.loads(lido.negociacao_json)["tf_datas"] == ["2026-07-18", "2026-08-17"]
    db.close()


def test_negociacao_json_default_none():
    from database import get_session, Orcamento
    db = get_session()
    o = Orcamento(projeto_id="Proj_N2", nome="Orçamento 1", ordem=1)
    db.add(o); db.commit(); db.refresh(o)
    assert db.get(Orcamento, o.id).negociacao_json is None
    db.close()
