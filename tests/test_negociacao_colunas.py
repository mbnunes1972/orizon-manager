import sqlite3

def test_orcamentos_tem_colunas_sombra(app_db):
    cols = {r[1] for r in sqlite3.connect(app_db.DB_PATH).execute("PRAGMA table_info(orcamentos)")}
    assert {"vbvo", "cfo", "vbno", "vavo", "cust_ad", "val_liq", "desc_tot_pct",
            "markup", "cust_fin", "val_cont", "prov_imp"} <= cols

def test_pool_ambientes_tem_colunas_qa(app_db):
    cols = {r[1] for r in sqlite3.connect(app_db.DB_PATH).execute("PRAGMA table_info(pool_ambientes)")}
    assert {"qa_selo", "qa_pct_sem_acrescimo", "qa_markup_xml", "qa_custo_sem_venda",
            "qa_override_por_id", "qa_override_motivo"} <= cols

def test_legado_intacto(app_db):
    cols = {r[1] for r in sqlite3.connect(app_db.DB_PATH).execute("PRAGMA table_info(orcamentos)")}
    assert {"valor_total", "valor_liquido", "margens"} <= cols   # modo sombra: nada removido
