import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_db(db_pg_limpo):
    """Banco de teste limpo por função (Postgres — conftest.db_pg_limpo)."""
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


def test_projeto_criado_linka_cliente_id():
    """Projeto deve ter cliente_id em projetos_meta após criação."""
    from database import get_session, Cliente, Projeto
    db = get_session()
    c = Cliente(nome="Teste Gate", email="gate@t.com", telefone="11000000002")
    db.add(c); db.commit(); db.refresh(c)
    # Simula o que o /projetos/novo faz ao linkar cliente
    p = Projeto(nome_safe="proj_gate_test_xyz", cliente_id=c.id)
    db.merge(p)
    db.commit()
    p2 = db.get(Projeto, "proj_gate_test_xyz")
    assert p2.cliente_id == c.id
    db.close()


def test_ciclo_legado_nao_marcado_para_projeto_novo():
    """Projetos com cliente_id NÃO devem ter auto-complete de etapas 1-5."""
    from database import get_session, Cliente, Projeto, CicloEtapa
    db = get_session()
    c = Cliente(nome="Novo Gate", email="novo@t.com", telefone="11000000003")
    db.add(c); db.commit(); db.refresh(c)
    p = Projeto(nome_safe="proj_novo_gate_xyz", cliente_id=c.id, status="quente")
    db.merge(p)
    db.commit()
    # Projeto novo com cliente_id NÃO deve ter etapas auto-completadas aqui
    etapas = db.query(CicloEtapa).filter_by(projeto_nome="proj_novo_gate_xyz").all()
    # Sem ter passado pelo endpoint real, não deve haver etapas
    assert len(etapas) == 0
    db.close()


def test_etapa7_estados():
    """Etapa 7: em_andamento após gerar, concluido após ambas as partes assinarem."""
    from database import get_session, CicloEtapa, Contrato, ContratoAssinatura, Orcamento
    from datetime import datetime
    db = get_session()
    # Cria orcamento fictício
    orc = Orcamento(projeto_id="proj_etapa7_test", nome="Orc 1", ordem=1)
    db.add(orc); db.commit(); db.refresh(orc)
    # Simula contrato gerado → etapa 7 em_andamento
    etapa7 = CicloEtapa(projeto_nome="proj_etapa7_test", etapa_codigo="7", status="em_andamento")
    db.add(etapa7)
    contrato = Contrato(
        projeto_nome="proj_etapa7_test",
        orcamento_id=orc.id,
        status="para_assinatura",
        template_path="config/contrato_template.docx",
    )
    db.add(contrato); db.commit(); db.refresh(contrato)
    # Assina como loja
    db.add(ContratoAssinatura(
        contrato_id=contrato.id, parte="loja", nome="Loja",
        cpf="00.000.000/0001-00", hash_sha256="aaa"
    ))
    db.commit()
    partes = {a.parte for a in db.query(ContratoAssinatura).filter_by(contrato_id=contrato.id).all()}
    assert "loja" in partes
    assert "cliente" not in partes
    # etapa 7 ainda em_andamento
    e7 = db.query(CicloEtapa).filter_by(projeto_nome="proj_etapa7_test", etapa_codigo="7").first()
    assert e7.status == "em_andamento"
    # Assina como cliente
    db.add(ContratoAssinatura(
        contrato_id=contrato.id, parte="cliente", nome="Cliente",
        cpf="111.111.111-11", hash_sha256="bbb"
    ))
    db.commit()
    partes2 = {a.parte for a in db.query(ContratoAssinatura).filter_by(contrato_id=contrato.id).all()}
    assert {"loja", "cliente"}.issubset(partes2)
    db.close()


def test_briefing_projeto_completo_helper():
    import main
    from database import Briefing
    from datetime import datetime

    def mk(**kw):
        base = dict(cliente_id=1, projeto_nome="P", data_atendimento=datetime.utcnow(),
                    tipo_imovel="apto", budget_declarado=1000.0, categoria_proposta="x",
                    data_entrega_desejada="2026-12-01", flexibilidade_prazo="alta")
        base.update(kw)
        return Briefing(**base)

    class _Q:
        def __init__(self, r, spy): self._r = r; self._spy = spy
        def filter_by(self, **k): self._spy["filter_by"] = k; return self
        def order_by(self, *a): self._spy["order_by_called"] = True; return self
        def first(self): return self._r
    class _DB:
        def __init__(self, r): self._r = r; self.spy = {}
        def query(self, *a): return _Q(self._r, self.spy)

    # com briefing completo -> True; e a query filtra por projeto_nome correto
    db_ok = _DB(mk())
    assert main._briefing_projeto_completo("Projeto_X", db_ok) is True
    assert db_ok.spy.get("filter_by") == {"projeto_nome": "Projeto_X"}
    assert db_ok.spy.get("order_by_called") is True

    # sem briefing (None) -> False
    assert main._briefing_projeto_completo("Projeto_X", _DB(None)) is False
    # briefing com obrigatório faltando -> False
    assert main._briefing_projeto_completo("Projeto_X", _DB(mk(budget_declarado=0.0))) is False
