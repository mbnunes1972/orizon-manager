from sqlalchemy import create_engine, inspect
import database


from conftest import _test_database_url, _reset_schema_pg


def _eng_pg():
    """Engine no Postgres de teste com schema recém-criado (herdeiro do sqlite :memory:)."""
    eng = create_engine(_test_database_url())
    _reset_schema_pg(eng)
    database.Base.metadata.create_all(eng)
    return eng

def _insp():
    return inspect(_eng_pg())


def test_tabelas_de_tenancy_criadas():
    insp = _insp()
    tabelas = set(insp.get_table_names())
    assert {"redes", "lojas", "parceiro_lojas"} <= tabelas


def test_colunas_de_tenant_nas_entidades_de_topo():
    insp = _insp()
    def cols(t):
        return {c["name"] for c in insp.get_columns(t)}
    assert {"loja_id", "rede_id"} <= cols("usuarios")
    assert "loja_id" in cols("clientes")
    assert "loja_id" in cols("projetos_meta")
    assert "loja_id" in cols("orcamentos")
    assert "loja_id" in cols("contratos")
    assert {"rede_id", "abrangencia"} <= cols("parceiros")
    assert {"parceiro_id", "loja_id", "comissao_padrao_pct", "ativo"} <= cols("parceiro_lojas")
