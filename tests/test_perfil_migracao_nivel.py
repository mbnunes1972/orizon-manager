import sqlite3
import database


def _conn():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE lojas (id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT, codigo TEXT,
        telefone TEXT, email TEXT, testemunha1_nome TEXT, testemunha1_cpf TEXT,
        testemunha2_nome TEXT, testemunha2_cpf TEXT, ativo INTEGER)""")
    cur.execute("INSERT INTO lojas(id, nome) VALUES (1, 'L1')")
    cur.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nivel TEXT, loja_id INTEGER, funcionario_id INTEGER, funcao_id INTEGER)")
    cur.execute("CREATE TABLE funcoes (id INTEGER PRIMARY KEY, loja_id INTEGER, nome TEXT, status TEXT, perfil_padrao TEXT)")
    for i, niv in enumerate(("diretoria", "gerencial", "consultor", "suporte", "super_admin"), start=1):
        cur.execute("INSERT INTO usuarios(id, nivel, loja_id) VALUES (?,?,1)", (i, niv))
    conn.commit()
    return conn


def test_migra_nivel_para_bases():
    conn = _conn()
    database._run_migracoes(conn)
    got = dict(conn.execute("SELECT id, nivel FROM usuarios").fetchall())
    assert got[1] == "master"      # diretoria
    assert got[2] == "gerencial"   # inalterado
    assert got[3] == "operador"    # consultor
    assert got[4] == "operador"    # suporte
    assert got[5] == "super_admin" # plataforma inalterada


def test_idempotente():
    conn = _conn()
    database._run_migracoes(conn)
    database._run_migracoes(conn)
    got = dict(conn.execute("SELECT id, nivel FROM usuarios").fetchall())
    assert got[1] == "master"
