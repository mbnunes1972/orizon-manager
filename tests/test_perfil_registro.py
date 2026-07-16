from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database
from auth import perfil_store, perfis


def _bind_mem(monkeypatch):
    eng = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    db = S()
    db.add(database.Loja(id=1, nome="L1"))
    db.commit()
    perfil_store.seed_perfis_loja(db, 1)
    db.close()
    monkeypatch.setattr(database, "Session", S)
    perfis.recarregar()
    return S


def test_acessa_modulo_do_registro(monkeypatch):
    _bind_mem(monkeypatch)
    assert perfis.acessa_modulo("operador", "fiscal") is True
    assert perfis.acessa_modulo("operador", "financeiro") is False
    assert perfis.acessa_modulo("master", "financeiro") is True
    assert perfis.acessa_modulo("operador", "auth") is True  # núcleo nunca bloqueia


def test_acessa_painel_do_registro(monkeypatch):
    _bind_mem(monkeypatch)
    assert perfis.acessa_painel("master", "admin") is True
    assert perfis.acessa_painel("gerencial", "admin") is False
    assert perfis.acessa_painel("operador", "config") is False


def test_base_resolve_caps_finas(monkeypatch):
    _bind_mem(monkeypatch)
    assert perfis.pode("operador", "gerir_usuarios") is False
    assert perfis.pode("master", "gerir_usuarios") is True


def test_slugs_da_loja(monkeypatch):
    _bind_mem(monkeypatch)
    assert set(perfis.slugs_da_loja(1)) == {"master", "gerencial", "operador"}


def test_plataforma_fallback_sem_registro(monkeypatch):
    _bind_mem(monkeypatch)
    assert perfis.acessa_painel("super_admin", "admin") is True
    assert perfis.pode("super_admin", "gerir_lojas") is True


def test_override_de_capacidade_fina(monkeypatch):
    import json, database
    from auth import perfil_store
    S = _bind_mem(monkeypatch)
    db = S()
    db.add(database.PerfilAcesso(loja_id=1, slug="operador_plus", nome="Operador+",
        base="operador", modulos_json=json.dumps(["comercial", "fiscal"]),
        capacidades_json=json.dumps({"aprovar_financeiro": True, "registrar_medicao": False}), sistema=0))
    db.commit(); db.close()
    perfis.recarregar()
    assert perfis.pode("operador_plus", "aprovar_financeiro") is True
    assert perfis.pode("operador_plus", "registrar_medicao") is False
    assert perfis.pode("operador_plus", "gerir_usuarios") is False
    assert perfis.desconto_max("operador_plus") == 10.0
