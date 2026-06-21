# tests/test_tenancy_bootstrap.py
import sqlite3
import database


def _conn_usuarios():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY, nome TEXT, login TEXT, senha_hash TEXT,
        nivel TEXT, ativo INTEGER, loja_id INTEGER, rede_id INTEGER)""")
    # sem tabela 'lojas': a migração tenancy_v1 é pulada pelo guard _tabela_existe,
    # isolando este teste no comportamento da tenancy_v2 (super_admin).
    conn.commit()
    return conn


def test_cria_super_admin_bootstrap():
    conn = _conn_usuarios()
    database._run_migracoes(conn)
    rows = conn.execute(
        "SELECT login, nivel, loja_id, rede_id, senha_hash FROM usuarios "
        "WHERE nivel='super_admin'").fetchall()
    assert len(rows) == 1
    login, nivel, loja_id, rede_id, senha_hash = rows[0]
    assert login == database._SEED_SA_LOGIN
    assert loja_id is None and rede_id is None
    assert senha_hash


def test_bootstrap_idempotente():
    conn = _conn_usuarios()
    database._run_migracoes(conn)
    database._run_migracoes(conn)
    n = conn.execute("SELECT COUNT(*) FROM usuarios WHERE nivel='super_admin'").fetchone()[0]
    assert n == 1


def test_bootstrap_respeita_super_admin_existente():
    conn = _conn_usuarios()
    conn.execute("INSERT INTO usuarios(nome, login, senha_hash, nivel, ativo) "
                 "VALUES ('Já', 'outro_sa', 'h', 'super_admin', 1)")
    conn.commit()
    database._run_migracoes(conn)
    n = conn.execute("SELECT COUNT(*) FROM usuarios WHERE nivel='super_admin'").fetchone()[0]
    assert n == 1
