import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_db(db_pg_limpo):
    """Banco de teste limpo por função (Postgres — conftest.db_pg_limpo)."""
    yield


def _mk_contrato(db, status="rascunho", assinaturas=()):
    from database import Contrato, ContratoAssinatura, Orcamento
    from datetime import datetime
    o = Orcamento(projeto_id="Proj_A", nome="Orçamento 1", ordem=1)
    db.add(o); db.commit(); db.refresh(o)
    c = Contrato(projeto_nome="Proj_A", orcamento_id=o.id, status=status)
    db.add(c); db.commit(); db.refresh(c)
    for parte in assinaturas:
        db.add(ContratoAssinatura(contrato_id=c.id, parte=parte, nome="X", cpf="0",
                                  assinado_em=datetime.utcnow(), hash_sha256="h"))
    db.commit()
    return c


def test_assinado_false_sem_contrato():
    from main import _contrato_assinado
    from database import get_session
    db = get_session()
    assert _contrato_assinado("Proj_Inexistente", db) is False
    db.close()


def test_assinado_false_rascunho():
    from main import _contrato_assinado
    from database import get_session
    db = get_session()
    _mk_contrato(db, status="rascunho")
    assert _contrato_assinado("Proj_A", db) is False
    db.close()


def test_assinado_true_uma_assinatura():
    from main import _contrato_assinado
    from database import get_session
    db = get_session()
    _mk_contrato(db, status="assinado_loja", assinaturas=("loja",))
    assert _contrato_assinado("Proj_A", db) is True
    db.close()


def test_assinado_true_status_vigente():
    from main import _contrato_assinado
    from database import get_session
    db = get_session()
    _mk_contrato(db, status="vigente")
    assert _contrato_assinado("Proj_A", db) is True
    db.close()


def test_totalmente_assinado_false_uma_parte():
    from main import _contrato_totalmente_assinado
    from database import get_session
    db = get_session()
    _mk_contrato(db, status="assinado_cliente", assinaturas=("cliente",))
    assert _contrato_totalmente_assinado("Proj_A", db) is False
    db.close()


def test_totalmente_assinado_true_status_assinado():
    from main import _contrato_totalmente_assinado
    from database import get_session
    db = get_session()
    _mk_contrato(db, status="assinado", assinaturas=("loja", "cliente"))
    assert _contrato_totalmente_assinado("Proj_A", db) is True
    db.close()


def test_totalmente_assinado_true_ambas_partes():
    from main import _contrato_totalmente_assinado
    from database import get_session
    db = get_session()
    _mk_contrato(db, status="assinado_loja", assinaturas=("loja", "cliente"))
    assert _contrato_totalmente_assinado("Proj_A", db) is True
    db.close()


def test_totalmente_assinado_false_sem_contrato():
    from main import _contrato_totalmente_assinado
    from database import get_session
    db = get_session()
    assert _contrato_totalmente_assinado("Proj_Inexistente", db) is False
    db.close()
