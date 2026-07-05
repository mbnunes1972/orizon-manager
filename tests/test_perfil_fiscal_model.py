import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_modelo_perfil_fiscal(tmp_path, monkeypatch):
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
    pf = database.PerfilFiscal(
        loja_id=1, regime_tributario="simples", csosn_padrao="101",
        cfop_dentro_uf="5102", ambiente_ativo="homologacao",
        focus_token_homolog_enc="ciphertext-xyz", placeholders_json='["regime_tributario"]')
    s.add(pf); s.commit()
    lido = s.query(database.PerfilFiscal).filter_by(loja_id=1).first()
    assert lido.regime_tributario == "simples" and lido.ambiente_ativo == "homologacao"
    assert lido.focus_token_homolog_enc == "ciphertext-xyz"
    from sqlalchemy.exc import IntegrityError
    s.add(database.PerfilFiscal(loja_id=1))
    import pytest
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback(); s.close()
