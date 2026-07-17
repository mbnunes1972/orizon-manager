from sqlalchemy import inspect

# introspecção via SQLAlchemy (não sqlite3.connect(DB_PATH) direto) — funciona nos dois dialetos;
# em Postgres (TEST_DATABASE_URL) o DB_PATH é None por desenho (ver tests/conftest.py).
def _cols(app_db, tabela):
    return {c["name"] for c in inspect(app_db.ENGINE).get_columns(tabela)}

def test_orcamentos_tem_colunas_sombra(app_db):
    cols = _cols(app_db, "orcamentos")
    assert {"vbvo", "cfo", "vbno", "vavo", "cust_ad", "com_arq_orc", "pro_fid_orc",
            "val_liq", "desc_tot_pct", "markup", "cust_fin", "val_cont", "prov_imp"} <= cols

def test_pool_ambientes_tem_colunas_qa(app_db):
    cols = _cols(app_db, "pool_ambientes")
    assert {"qa_selo", "qa_pct_sem_acrescimo", "qa_markup_xml", "qa_custo_sem_venda",
            "qa_override_por_id", "qa_override_motivo"} <= cols

def test_legado_intacto(app_db):
    cols = _cols(app_db, "orcamentos")
    assert {"valor_total", "valor_liquido"} <= cols   # colunas autoritativas do motor permanecem
    assert "margens" not in cols   # faxina: coluna legada duplicada Orcamento.margens removida
