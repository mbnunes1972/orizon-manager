import sqlite3
import database


def _conn_tenancy():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE lojas (
        id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT, codigo TEXT,
        telefone TEXT, email TEXT,
        testemunha1_nome TEXT, testemunha1_cpf TEXT,
        testemunha2_nome TEXT, testemunha2_cpf TEXT, ativo INTEGER)""")
    cur.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nivel TEXT, loja_id INTEGER)")
    cur.execute("CREATE TABLE clientes (id INTEGER PRIMARY KEY, loja_id INTEGER)")
    cur.execute("CREATE TABLE projetos_meta (nome_safe TEXT PRIMARY KEY, loja_id INTEGER)")
    cur.execute("CREATE TABLE orcamentos (id INTEGER PRIMARY KEY, loja_id INTEGER)")
    cur.execute("CREATE TABLE contratos (id INTEGER PRIMARY KEY, loja_id INTEGER)")
    cur.execute("""CREATE TABLE parceiros (
        id INTEGER PRIMARY KEY, comissao_padrao_pct REAL, abrangencia TEXT, rede_id INTEGER)""")
    cur.execute("""CREATE TABLE parceiro_lojas (
        id INTEGER PRIMARY KEY, parceiro_id INTEGER, loja_id INTEGER,
        comissao_padrao_pct REAL, ativo INTEGER)""")
    conn.commit()
    return conn


def test_cria_loja_seed_e_backfill():
    conn = _conn_tenancy()
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios(id, nivel) VALUES (1, 'diretor')")
    cur.execute("INSERT INTO clientes(id) VALUES (1)")
    cur.execute("INSERT INTO projetos_meta(nome_safe) VALUES ('proj_a')")
    cur.execute("INSERT INTO orcamentos(id) VALUES (1)")
    cur.execute("INSERT INTO contratos(id) VALUES (1)")
    cur.execute("INSERT INTO parceiros(id, comissao_padrao_pct) VALUES (1, 5.0)")
    conn.commit()

    database._run_migracoes(conn)

    lojas = conn.execute("SELECT id, codigo, cnpj FROM lojas").fetchall()
    assert len(lojas) == 1
    loja_id, codigo, cnpj = lojas[0]
    assert codigo == "INS"
    assert cnpj == "19.152.134/0001-56"

    for tbl in ("usuarios", "clientes", "orcamentos", "contratos"):
        nulos = conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE loja_id IS NULL").fetchone()[0]
        assert nulos == 0, tbl
    assert conn.execute("SELECT loja_id FROM projetos_meta").fetchone()[0] == loja_id

    vinc = conn.execute(
        "SELECT parceiro_id, loja_id, comissao_padrao_pct FROM parceiro_lojas").fetchall()
    assert vinc == [(1, loja_id, 5.0)]
    assert conn.execute("SELECT abrangencia FROM parceiros WHERE id=1").fetchone()[0] == "loja"


def test_idempotente():
    conn = _conn_tenancy()
    conn.execute("INSERT INTO parceiros(id, comissao_padrao_pct) VALUES (1, 5.0)")
    conn.commit()
    database._run_migracoes(conn)
    database._run_migracoes(conn)
    assert conn.execute("SELECT COUNT(*) FROM lojas").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM parceiro_lojas").fetchone()[0] == 1


def test_nao_sobrescreve_abrangencia_existente():
    conn = _conn_tenancy()
    conn.execute(
        "INSERT INTO parceiros(id, comissao_padrao_pct, abrangencia) VALUES (1, 5.0, 'rede')")
    conn.commit()
    database._run_migracoes(conn)
    assert conn.execute("SELECT abrangencia FROM parceiros WHERE id=1").fetchone()[0] == "rede"
