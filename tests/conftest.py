import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest


@pytest.fixture(scope="module")
def app_db(tmp_path_factory):
    """Rebinda a engine de `database` para um SQLite temporário e cria o schema.
    Como get_session/init_db lêem os globais em tempo de chamada, o rebind vale
    para todo o processo (inclusive o servidor em thread)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import database

    db_file = str(tmp_path_factory.mktemp("f4db") / "test.db")
    database.DB_PATH = db_file
    database.ENGINE = create_engine(f"sqlite:///{db_file}", echo=False)
    database.Session = sessionmaker(bind=database.ENGINE)
    database.init_db()
    return database


@pytest.fixture(scope="module")
def seed(app_db):
    """2 lojas na mesma rede; 1 diretor por loja; super_admin e admin_rede;
    e dados cross-loja (1 cliente + 1 projeto em cada loja)."""
    db = app_db.get_session()
    rede = app_db.Rede(nome="Rede Teste")
    db.add(rede); db.flush()

    l1 = app_db.Loja(nome="Loja 1", rede_id=rede.id, codigo="LJ1")
    l2 = app_db.Loja(nome="Loja 2", rede_id=rede.id, codigo="LJ2")
    db.add_all([l1, l2]); db.flush()

    def mkuser(nome, login, nivel, loja_id=None, rede_id=None):
        u = app_db.Usuario(nome=nome, login=login, nivel=nivel,
                           loja_id=loja_id, rede_id=rede_id, ativo=1)
        u.set_senha("senha123")
        db.add(u)

    mkuser("Diretor L1", "dir_l1", "diretor", loja_id=l1.id)
    mkuser("Diretor L2", "dir_l2", "diretor", loja_id=l2.id)
    mkuser("Super",      "super",  "super_admin")
    mkuser("Adm Rede",   "adm_rede", "admin_rede", rede_id=rede.id)

    c1 = app_db.Cliente(nome="Cliente L1", cpf="111.111.111-11", loja_id=l1.id)
    c2 = app_db.Cliente(nome="Cliente L2", cpf="222.222.222-22", loja_id=l2.id)
    db.add_all([c1, c2]); db.flush()

    p1 = app_db.Projeto(nome_safe="Proj_L1", cliente_id=c1.id, status="quente", loja_id=l1.id)
    p2 = app_db.Projeto(nome_safe="Proj_L2", cliente_id=c2.id, status="quente", loja_id=l2.id)
    db.add_all([p1, p2])
    db.commit()

    ctx = {
        "loja1_id": l1.id, "loja2_id": l2.id,
        "cliente_l1_id": c1.id, "cliente_l2_id": c2.id,
        "projeto_l1": "Proj_L1", "projeto_l2": "Proj_L2",
    }
    db.close()
    return ctx


import json as _json
import threading
import time
import urllib.request
import urllib.error


class HttpClient:
    """Cliente HTTP fininho com cookie jar de 1 sessão (header Cookie reusado)."""
    def __init__(self, base):
        self.base = base
        self.cookie = None

    def _req(self, method, path, body=None):
        data = _json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            status, raw, headers = resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            status, raw, headers = e.code, e.read(), e.headers
        sc = headers.get("Set-Cookie")
        if sc:
            self.cookie = sc.split(";")[0]
        try:
            out = _json.loads(raw) if raw else None
        except Exception:
            out = raw
        return status, out

    def get(self, path):             return self._req("GET", path)
    def post(self, path, body=None): return self._req("POST", path, body)
    def put(self, path, body=None):  return self._req("PUT", path, body)
    def patch(self, path, body=None):return self._req("PATCH", path, body)

    def login(self, login, senha):
        return self.post("/api/auth/login", {"login": login, "senha": senha})


@pytest.fixture(scope="module")
def projetos_dir(app_db, tmp_path_factory):
    """Redireciona PROJETOS_DIR (em storage/main/mod_omie) para um diretório temporário,
    deixando o harness hermético quanto a disco — espelha o isolamento do banco."""
    import storage, main, mod_omie
    tmp = str(tmp_path_factory.mktemp("projetos"))
    for mod in (storage, main, mod_omie):
        if hasattr(mod, "PROJETOS_DIR"):
            mod.PROJETOS_DIR = tmp
    return tmp


@pytest.fixture(scope="module")
def servidor(app_db, seed, projetos_dir):
    """Sobe main.Handler numa thread, porta efêmera, usando o banco isolado+seed."""
    import main
    from http.server import HTTPServer

    httpd = HTTPServer(("127.0.0.1", 0), main.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/login", timeout=1)
            break
        except urllib.error.HTTPError:
            break
        except Exception:
            time.sleep(0.05)
    yield base
    httpd.shutdown()


@pytest.fixture
def http_client_factory(servidor):
    return lambda: HttpClient(servidor)
