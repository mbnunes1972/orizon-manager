import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_db(db_pg_limpo):
    """Banco de teste limpo por função (Postgres — conftest.db_pg_limpo)."""
    yield


def test_desconto_individual_pct_persiste():
    from database import get_session, PoolAmbiente, Orcamento, OrcamentoAmbiente
    db = get_session()
    o = Orcamento(projeto_id="Proj_X", nome="Orçamento 1", ordem=1)
    pa = PoolAmbiente(projeto_id="Proj_X", nome="Cozinha", nome_exibicao="Cozinha",
                      xml_path="x.xml", ambientes_json="[]", budget_total=100.0, order_total=100.0)
    db.add_all([o, pa]); db.commit(); db.refresh(o); db.refresh(pa)
    link = OrcamentoAmbiente(orcamento_id=o.id, pool_ambiente_id=pa.id, ordem=1,
                             desconto_individual_pct=7.5)
    db.add(link); db.commit()
    lido = db.query(OrcamentoAmbiente).filter_by(orcamento_id=o.id, pool_ambiente_id=pa.id).first()
    assert lido.desconto_individual_pct == 7.5
    db.close()


def test_desconto_individual_pct_default_zero():
    from database import get_session, PoolAmbiente, Orcamento, OrcamentoAmbiente
    db = get_session()
    o = Orcamento(projeto_id="Proj_Y", nome="Orçamento 1", ordem=1)
    pa = PoolAmbiente(projeto_id="Proj_Y", nome="Sala", nome_exibicao="Sala",
                      xml_path="s.xml", ambientes_json="[]", budget_total=50.0, order_total=50.0)
    db.add_all([o, pa]); db.commit(); db.refresh(o); db.refresh(pa)
    link = OrcamentoAmbiente(orcamento_id=o.id, pool_ambiente_id=pa.id, ordem=1)
    db.add(link); db.commit()
    lido = db.query(OrcamentoAmbiente).filter_by(orcamento_id=o.id).first()
    assert (lido.desconto_individual_pct or 0) == 0
    db.close()
