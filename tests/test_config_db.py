"""DATABASE_URL por instância: DB_PATH deve seguir uma URL `sqlite:///…`, porque as
migrações sqlite3 de init_db usam DB_PATH diretamente — se DB_PATH ficasse no
`orizon.db` default enquanto o engine usa outro arquivo, a instância B (pré-homologação)
contaminaria o banco da instância A (integração). Ver Plano de Testes / instância B."""
import database


def test_sem_database_url_usa_default():
    dbp, url = database._resolver_config_db(None, "/base/orizon.db")
    assert dbp == "/base/orizon.db"
    assert url == "sqlite:////base/orizon.db"


def test_sqlite_url_absoluta_db_path_segue():
    dbp, url = database._resolver_config_db("sqlite:////srv/orizon_homolog.db", "/base/orizon.db")
    assert dbp == "/srv/orizon_homolog.db"          # DB_PATH segue o arquivo do engine
    assert url == "sqlite:////srv/orizon_homolog.db"


def test_sqlite_url_relativa_db_path_segue():
    dbp, url = database._resolver_config_db("sqlite:///homolog.db", "/base/orizon.db")
    assert dbp == "homolog.db"
    assert url == "sqlite:///homolog.db"


def test_postgres_url_mantem_default_db_path():
    dbp, url = database._resolver_config_db("postgresql+psycopg2://u:p@h/orizon", "/base/orizon.db")
    assert dbp == "/base/orizon.db"                 # não-sqlite: migrações sqlite3 são puladas
    assert url == "postgresql+psycopg2://u:p@h/orizon"
