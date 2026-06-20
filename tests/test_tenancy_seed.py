from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database
import seed


def _mem_session():
    eng = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_loja_seed_id():
    db = _mem_session()
    assert database.loja_seed_id(db) is None
    loja = database.Loja(nome="X", codigo="INS")
    db.add(loja); db.commit()
    assert database.loja_seed_id(db) == loja.id


def test_criar_usuarios_seed_vincula_loja():
    db = _mem_session()
    loja = database.Loja(nome="X", codigo="INS")
    db.add(loja); db.commit()

    n = seed.criar_usuarios_seed(db, seed.USUARIOS, loja.id)

    assert n == len(seed.USUARIOS)
    usuarios = db.query(database.Usuario).all()
    assert len(usuarios) == len(seed.USUARIOS)
    assert all(u.loja_id == loja.id for u in usuarios)


def test_criar_usuarios_seed_idempotente():
    db = _mem_session()
    loja = database.Loja(nome="X", codigo="INS")
    db.add(loja); db.commit()
    seed.criar_usuarios_seed(db, seed.USUARIOS, loja.id)
    n2 = seed.criar_usuarios_seed(db, seed.USUARIOS, loja.id)   # 2ª vez não recria
    assert n2 == 0
    assert db.query(database.Usuario).count() == len(seed.USUARIOS)
