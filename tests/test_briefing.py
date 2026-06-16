import pytest
import sys
import os
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


def _make_cliente():
    from database import get_session, Cliente
    db = get_session()
    c = Cliente(nome="João Silva", email="joao@test.com", telefone="11999990000")
    db.add(c)
    db.commit()
    db.refresh(c)
    cliente_id = c.id
    db.close()
    return cliente_id


def test_briefing_campos_obrigatorios():
    from database import get_session, Briefing
    from datetime import datetime
    cliente_id = _make_cliente()
    db = get_session()
    b = Briefing(
        cliente_id=cliente_id,
        data_atendimento=datetime.utcnow(),
        tipo_imovel="apartamento",
        budget_declarado=50000.0,
        categoria_proposta="refinada",
        data_entrega_desejada="2026-12-01",
        flexibilidade_prazo="negociavel",
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    assert b.id is not None
    assert b.tipo_imovel == "apartamento"
    assert b.budget_declarado == 50000.0
    db.close()


def test_briefing_incompleto_levanta_erro():
    from database import get_session, Briefing
    from datetime import datetime
    cliente_id = _make_cliente()
    db = get_session()
    b = Briefing(cliente_id=cliente_id, data_atendimento=datetime.utcnow())
    db.add(b)
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_usuario_tem_campo_telefone():
    from database import Usuario
    assert hasattr(Usuario, "telefone")


def test_cliente_tem_campos_instalacao():
    from database import Cliente
    for campo in ["inst_mesmo_residencial", "inst_logradouro", "inst_numero",
                  "inst_complemento", "inst_bairro", "inst_cidade", "inst_cep", "inst_uf"]:
        assert hasattr(Cliente, campo), f"Cliente missing field: {campo}"


def test_projeto_tem_cliente_id():
    from database import Projeto
    assert hasattr(Projeto, "cliente_id")


def test_inst_mesmo_residencial_default():
    from database import get_session, Cliente
    cliente_id = _make_cliente()
    db = get_session()
    c = db.get(Cliente, cliente_id)
    assert c.inst_mesmo_residencial == 1
    db.close()


def test_briefing_dict_completo_true():
    from database import get_session, Cliente, Briefing
    from datetime import datetime
    from main import _briefing_dict
    db = get_session()
    c = Cliente(nome="Maria", email="m@t.com", telefone="11999990000")
    db.add(c); db.commit(); db.refresh(c)
    b = Briefing(
        cliente_id=c.id,
        data_atendimento=datetime.utcnow(),
        tipo_imovel="casa",
        budget_declarado=80000.0,
        categoria_proposta="exclusiva",
        data_entrega_desejada="2027-03-01",
        flexibilidade_prazo="flexivel",
    )
    db.add(b); db.commit(); db.refresh(b)
    bd = _briefing_dict(b)
    assert bd["completo"] is True
    assert bd["tipo_imovel"] == "casa"
    assert bd["budget_declarado"] == 80000.0
    db.close()


def test_briefing_dict_incompleto():
    from database import get_session, Cliente, Briefing
    from datetime import datetime
    from main import _briefing_dict
    db = get_session()
    c = Cliente(nome="Pedro", email="p@t.com", telefone="11000000001")
    db.add(c); db.commit(); db.refresh(c)
    b = Briefing(
        cliente_id=c.id,
        data_atendimento=datetime.utcnow(),
        tipo_imovel="apartamento",
        budget_declarado=0.0,       # zero = falsy → incompleto
        categoria_proposta="refinada",
        data_entrega_desejada="2027-01-01",
        flexibilidade_prazo="rigido",
    )
    db.add(b); db.commit(); db.refresh(b)
    bd = _briefing_dict(b)
    assert bd["completo"] is False   # budget_declarado = 0.0 → falsy
    db.close()
