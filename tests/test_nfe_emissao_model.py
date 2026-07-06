import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_modelo_nfe_emissao(tmp_path, monkeypatch):
    import database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    dbf = str(tmp_path / "t.db")
    engine = create_engine(f"sqlite:///{dbf}")
    monkeypatch.setattr(database, "DB_PATH", dbf)
    monkeypatch.setattr(database, "ENGINE", engine)
    monkeypatch.setattr(database, "Session", sessionmaker(bind=engine))
    database.init_db()
    s = database.Session()
    e = database.NfeEmissao(ref="TESTE-1", projeto_nome="Proj_L2", loja_id=1,
                            status="autorizado", chave_nfe="CH", numero="10", serie="1",
                            fabrica_doc_id=7)
    s.add(e); s.commit()
    lido = s.query(database.NfeEmissao).filter_by(ref="TESTE-1").first()
    assert lido.status == "autorizado" and lido.chave_nfe == "CH" and lido.etapa_codigo == "15"
    assert lido.fabrica_doc_id == 7
    from sqlalchemy.exc import IntegrityError
    import pytest
    s.add(database.NfeEmissao(ref="TESTE-1"))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback(); s.close()
