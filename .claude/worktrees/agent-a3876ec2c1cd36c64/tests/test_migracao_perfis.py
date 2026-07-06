import sqlite3
import database


def _conn_com_usuarios(niveis):
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nivel TEXT)")
    # tabela vazia para a migração etapas_swap_2_3 rodar inofensiva (sem try/except em produção)
    cur.execute("CREATE TABLE ciclo_etapas (id INTEGER PRIMARY KEY, projeto_nome TEXT, etapa_codigo TEXT)")
    for i, nv in enumerate(niveis, start=1):
        cur.execute("INSERT INTO usuarios(id, nivel) VALUES (?,?)", (i, nv))
    conn.commit()
    return conn


def test_migracao_renomeia_niveis_antigos():
    conn = _conn_com_usuarios(["gerente", "admin", "diretor", "consultor"])
    database._run_migracoes(conn)
    niveis = [r[0] for r in conn.execute("SELECT nivel FROM usuarios ORDER BY id")]
    assert niveis == ["gerente_vendas", "diretor", "diretor", "consultor"]


def test_migracao_perfis_idempotente():
    conn = _conn_com_usuarios(["gerente"])
    database._run_migracoes(conn)
    database._run_migracoes(conn)   # 2ª vez não deve quebrar nem re-alterar
    niveis = [r[0] for r in conn.execute("SELECT nivel FROM usuarios ORDER BY id")]
    assert niveis == ["gerente_vendas"]
