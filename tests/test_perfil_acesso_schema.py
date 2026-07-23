from sqlalchemy import create_engine, inspect
import database


from conftest import _test_database_url, _reset_schema_pg


def _eng_pg():
    """Engine no Postgres de teste com schema recém-criado (herdeiro do sqlite :memory:)."""
    eng = create_engine(_test_database_url())
    _reset_schema_pg(eng)
    database.Base.metadata.create_all(eng)
    return eng

def _mem():
    return _eng_pg()


def test_tabela_perfil_acesso_existe():
    insp = inspect(_mem())
    assert "perfil_acesso" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("perfil_acesso")}
    assert {"id", "loja_id", "slug", "nome", "base", "modulos_json",
            "capacidades_json", "sistema", "criado_em"} <= cols


def test_funcao_tem_perfil_padrao():
    insp = inspect(_mem())
    cols = {c["name"] for c in insp.get_columns("funcoes")}
    assert "perfil_padrao" in cols


def test_log_acesso_delegado_existe():
    insp = inspect(_mem())
    assert "log_acesso_delegado" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("log_acesso_delegado")}
    assert {"id", "solicitante_id", "autorizador_id", "recurso", "criado_em"} <= cols
