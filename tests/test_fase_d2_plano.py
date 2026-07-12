"""FASE D2 · Fase 1 — Plano de Contas: grupo 1.1.06 "Custos a Apropriar" (ativo diferido, espelho de
2.1.04.x/1.1.05) + 2.1.06 renomeada de "Adiantamento de Clientes" para "Receita a Realizar" (novo seed)
com migração PONTUAL idempotente para bancos existentes (só renomeia o default antigo)."""
import sqlite3
import mod_contabil as mc
import database


# subcontas de 1.1.06 — espelho das rubricas provisionadas (2.1.04.x), exceto impostos (.13 usa 1.1.05)
SUB_1106 = {
    "1.1.06.02": "Montagem a Apropriar",
    "1.1.06.03": "Garantia a Apropriar",
    "1.1.06.05": "Assistência Técnica a Apropriar",
    "1.1.06.06": "Custo de Fábrica a Apropriar",
    "1.1.06.07": "Frete de Fábrica a Apropriar",
    "1.1.06.08": "Frete Local a Apropriar",
    "1.1.06.09": "Insumos Locais a Apropriar",
    "1.1.06.10": "Comissão de Medidor a Apropriar",
    "1.1.06.11": "Comissão de Projeto/Executivo a Apropriar",
    "1.1.06.12": "Retenção de Comissão de Vendas a Apropriar",
    "1.1.06.14": "Outros Fornecedores a Apropriar",
}


def _contas(db, ot, oid):
    return {c.codigo: c for c in db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid).all()}


def test_seed_cria_grupo_1106_custos_a_apropriar(app_db):
    db = app_db.get_session(); ot, oid = "loja", 700
    mc.seed_plano(db, ot, oid)
    cs = _contas(db, ot, oid)
    # o pai 1.1.06 existe, é sintético e pendura em 1.1 (Circulante)
    assert "1.1.06" in cs and cs["1.1.06"].nome == "Custos a Apropriar"
    assert cs["1.1.06"].tipo == "sintetica" and cs["1.1.06"].pai_id == cs["1.1"].id
    # as 11 subcontas espelho, ativo/devedora, penduradas em 1.1.06
    for cod, nome in SUB_1106.items():
        assert cod in cs, "faltou %s" % cod
        assert cs[cod].nome == nome
        assert cs[cod].grupo == 1 and cs[cod].natureza == "devedora"
        assert cs[cod].pai_id == cs["1.1.06"].id
    db.close()


def test_2106_vira_receita_a_realizar_no_seed_novo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 701
    mc.seed_plano(db, ot, oid)
    cs = _contas(db, ot, oid)
    assert cs["2.1.06"].nome == "Receita a Realizar"
    db.close()


# ── Migração PONTUAL (dados, idempotente, schema_migrations) ─────────────────
def _mk_conta_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE conta (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                 "owner_tipo TEXT, owner_id INTEGER, codigo TEXT, nome TEXT)")
    return conn


def test_migracao_renomeia_2106_default():
    conn = _mk_conta_db()
    conn.execute("INSERT INTO conta(owner_tipo,owner_id,codigo,nome) VALUES('loja',1,'2.1.06','Adiantamento de Clientes')")
    conn.commit()
    database._run_migracoes(conn)
    nome = conn.execute("SELECT nome FROM conta WHERE codigo='2.1.06'").fetchone()[0]
    assert nome == "Receita a Realizar"
    assert conn.execute("SELECT 1 FROM schema_migrations WHERE id='conta_2106_receita_a_realizar_2026'").fetchone() is not None


def test_migracao_2106_preserva_nome_customizado():
    conn = _mk_conta_db()
    conn.execute("INSERT INTO conta(owner_tipo,owner_id,codigo,nome) VALUES('loja',1,'2.1.06','Adiantamento do Cliente X')")
    conn.commit()
    database._run_migracoes(conn)
    nome = conn.execute("SELECT nome FROM conta WHERE codigo='2.1.06'").fetchone()[0]
    assert nome == "Adiantamento do Cliente X"   # customizado pelo owner → não mexe


def test_migracao_2106_idempotente():
    conn = _mk_conta_db()
    conn.execute("INSERT INTO conta(owner_tipo,owner_id,codigo,nome) VALUES('loja',1,'2.1.06','Adiantamento de Clientes')")
    conn.commit()
    database._run_migracoes(conn)
    database._run_migracoes(conn)
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE id='conta_2106_receita_a_realizar_2026'").fetchone()[0] == 1
