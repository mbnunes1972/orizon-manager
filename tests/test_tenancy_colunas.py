import sqlite3
import database

_TABELAS_LEGADO = [
    "clientes", "usuarios", "projetos_meta", "contratos",
    "orcamentos", "orcamento_ambientes", "briefings", "parceiros",
]


def _db_legado(path):
    """Cria um DB 'antigo': as tabelas existem mas sem as colunas de tenant."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    for t in _TABELAS_LEGADO:
        cur.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()


def test_migrar_colunas_adiciona_tenant(tmp_path, monkeypatch):
    db = str(tmp_path / "legado.db")
    _db_legado(db)
    monkeypatch.setattr(database, "DB_PATH", db)

    database._migrar_colunas()

    conn = sqlite3.connect(db)
    def cols(t):
        return {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
    assert {"loja_id", "rede_id"} <= cols("usuarios")
    assert "loja_id" in cols("clientes")
    assert "loja_id" in cols("projetos_meta")
    assert "loja_id" in cols("orcamentos")
    assert "loja_id" in cols("contratos")
    assert {"rede_id", "abrangencia"} <= cols("parceiros")
    conn.close()


def test_migrar_colunas_idempotente(tmp_path, monkeypatch):
    db = str(tmp_path / "legado.db")
    _db_legado(db)
    monkeypatch.setattr(database, "DB_PATH", db)
    database._migrar_colunas()
    database._migrar_colunas()   # 2ª vez não pode quebrar
    conn = sqlite3.connect(db)
    assert "loja_id" in {r[1] for r in conn.execute("PRAGMA table_info(clientes)")}
    conn.close()
