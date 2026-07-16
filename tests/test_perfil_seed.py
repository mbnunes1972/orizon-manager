import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database
from auth import perfil_store


def _sess():
    eng = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    db = S()
    db.add(database.Loja(id=1, nome="L1"))
    db.add(database.Loja(id=2, nome="L2"))
    db.commit()
    return db


def test_seed_cria_3_perfis_por_loja():
    db = _sess()
    perfil_store.seed_perfis_loja(db, 1)
    perfil_store.seed_perfis_loja(db, 2)
    p1 = db.query(database.PerfilAcesso).filter_by(loja_id=1).all()
    assert {p.slug for p in p1} == {"master", "gerencial", "operador"}
    assert all(p.sistema == 1 for p in p1)
    master = next(p for p in p1 if p.slug == "master")
    mods = set(json.loads(master.modulos_json))
    assert {"admin", "config", "financeiro", "fiscal"} <= mods
    operador = next(p for p in p1 if p.slug == "operador")
    omods = set(json.loads(operador.modulos_json))
    assert "fiscal" in omods and "financeiro" not in omods and "admin" not in omods


def test_seed_idempotente():
    db = _sess()
    perfil_store.seed_perfis_loja(db, 1)
    perfil_store.seed_perfis_loja(db, 1)
    assert db.query(database.PerfilAcesso).filter_by(loja_id=1).count() == 3
