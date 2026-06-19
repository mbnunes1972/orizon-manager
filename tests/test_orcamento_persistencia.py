import pytest, sys, os
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


def _escrever_projeto_json(tmp_path, nome_safe, margens):
    import json
    d = tmp_path / nome_safe
    d.mkdir(parents=True, exist_ok=True)
    (d / "projeto.json").write_text(
        json.dumps({"nome_safe": nome_safe, "margens": margens}, ensure_ascii=False),
        encoding="utf-8")
    return str(tmp_path)


def test_migracao_copia_margens_do_projeto_json(tmp_path):
    import json
    from database import get_session, Orcamento, migrar_margens_para_orcamentos
    db = get_session()
    db.add(Orcamento(projeto_id="Proj_M", nome="Orçamento 1", ordem=1)); db.commit()
    projetos_dir = _escrever_projeto_json(tmp_path, "Proj_M",
                                          {"desconto_pct": 5.0, "carga_trib": 8.0})
    n = migrar_margens_para_orcamentos(db, projetos_dir)
    assert n == 1
    o = db.query(Orcamento).filter_by(projeto_id="Proj_M").first()
    assert json.loads(o.margens)["desconto_pct"] == 5.0
    db.close()


def test_migracao_idempotente_nao_sobrescreve(tmp_path):
    import json
    from database import get_session, Orcamento, migrar_margens_para_orcamentos
    db = get_session()
    db.add(Orcamento(projeto_id="Proj_I", nome="Orçamento 1", ordem=1,
                     margens=json.dumps({"desconto_pct": 99.0}))); db.commit()
    projetos_dir = _escrever_projeto_json(tmp_path, "Proj_I", {"desconto_pct": 5.0})
    n = migrar_margens_para_orcamentos(db, projetos_dir)
    assert n == 0
    o = db.query(Orcamento).filter_by(projeto_id="Proj_I").first()
    assert json.loads(o.margens)["desconto_pct"] == 99.0
    assert migrar_margens_para_orcamentos(db, projetos_dir) == 0
    db.close()
