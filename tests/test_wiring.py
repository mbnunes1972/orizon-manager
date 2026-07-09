import sqlite3
import mod_contabil as mc


def test_evento_idempotente_por_ref(app_db):
    db = app_db.get_session()
    l1 = mc.registrar_evento(db, "loja", 40, "faturamento", 1000.0, projeto_id="P", ref="fat:NFE-P-1")
    l2 = mc.registrar_evento(db, "loja", 40, "faturamento", 1000.0, projeto_id="P", ref="fat:NFE-P-1")
    assert l1["id"] == l2["id"]                       # mesmo ref -> não duplica
    n = db.query(mc.Lancamento).filter_by(owner_tipo="loja", owner_id=40, ref="fat:NFE-P-1").count()
    assert n == 1
    db.close()


def test_ref_diferente_gera_novo(app_db):
    db = app_db.get_session()
    a = mc.registrar_evento(db, "loja", 41, "faturamento", 100.0, ref="fat:A")
    b = mc.registrar_evento(db, "loja", 41, "faturamento", 100.0, ref="fat:B")
    assert a["id"] != b["id"]
    db.close()


def test_lancamento_tem_coluna_ref(app_db):
    conn = sqlite3.connect(app_db.DB_PATH)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(lancamento)")}
    conn.close()
    assert "ref" in cols
