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

    # guarda os globais originais para restaurar no teardown — assim este módulo
    # não deixa `database` apontando para um banco temp (já deletado) e quebrando
    # um futuro teste que use get_session() sem isolamento próprio.
    orig = (database.DB_PATH, database.ENGINE, database.Session)

    db_file = str(tmp_path_factory.mktemp("f4db") / "test.db")
    database.DB_PATH = db_file
    database.ENGINE = create_engine(f"sqlite:///{db_file}", echo=False)
    database.Session = sessionmaker(bind=database.ENGINE)
    database.init_db()
    yield database

    database.ENGINE.dispose()
    database.DB_PATH, database.ENGINE, database.Session = orig


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

    # Emitente próprio de cada loja (identidade fiscal — Task 1/2/4). loja.emitente_id = self.
    def mk_emitente(cnpj, razao, uf="SP"):
        em = app_db.Emitente(cnpj=cnpj, razao_social=razao, regime_tributario="simples",
                             csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102",
                             inscricao_estadual="ISENTO", logradouro="Rua Emit", numero="1",
                             bairro="Centro", cidade="Sao Paulo", uf=uf, cep="01000-000",
                             ambiente_ativo="homologacao")
        db.add(em); db.flush()
        return em
    em1 = mk_emitente("11111111000111", "EMITENTE LOJA 1 LTDA")
    em2 = mk_emitente("22222222000122", "EMITENTE LOJA 2 LTDA")
    l1.emitente_id = em1.id
    l2.emitente_id = em2.id
    db.flush()

    def mkuser(nome, login, nivel, loja_id=None, rede_id=None):
        u = app_db.Usuario(nome=nome, login=login, nivel=nivel,
                           loja_id=loja_id, rede_id=rede_id, ativo=1)
        u.set_senha("senha123")
        db.add(u)

    mkuser("Diretor L1", "dir_l1", "master", loja_id=l1.id)   # Perfil-4: master (era 'diretoria')
    mkuser("Diretor L2", "dir_l2", "master", loja_id=l2.id)
    # NOTA: mantido como 'consultor' (não 'operador') deliberadamente — perfis.py resolve
    # 'consultor' -> base 'operador' via _ALIAS_BASE para toda checagem de capacidade
    # (pode()/desconto_max()/acessa_*), então o comportamento de novo modelo é idêntico.
    # main.py:7547 (_PERFIS_ESCOPO_PROPRIO) ainda faz match LITERAL de string 'consultor'
    # (fora do alias de perfis.py) para a regra "consultor só vê os projetos que criou";
    # trocar para 'operador' aqui quebraria essa regra sem tocar em main.py (fora do
    # escopo desta migração de testes/seed). Ver relatório da Task 1b.
    mkuser("Consultor L1", "cons_l1", "consultor", loja_id=l1.id)
    mkuser("Super",      "super",  "super_admin")
    mkuser("Adm Rede",   "adm_rede", "admin_rede", rede_id=rede.id)

    c1 = app_db.Cliente(nome="Cliente L1", cpf="111.444.777-35", loja_id=l1.id)
    c2 = app_db.Cliente(nome="Cliente L2", cpf="222.222.222-22", loja_id=l2.id)
    db.add_all([c1, c2]); db.flush()

    p1 = app_db.Projeto(nome_safe="Proj_L1", cliente_id=c1.id, status="quente", loja_id=l1.id)
    p2 = app_db.Projeto(nome_safe="Proj_L2", cliente_id=c2.id, status="quente", loja_id=l2.id)
    db.add_all([p1, p2]); db.flush()

    o1 = app_db.Orcamento(projeto_id=p1.nome_safe, nome="Orçamento 1", ordem=1, loja_id=l1.id)
    o2 = app_db.Orcamento(projeto_id=p2.nome_safe, nome="Orçamento 1", ordem=1, loja_id=l2.id)
    db.add_all([o1, o2]); db.flush()
    ct1 = app_db.Contrato(projeto_nome=p1.nome_safe, orcamento_id=o1.id, loja_id=l1.id)
    ct2 = app_db.Contrato(projeto_nome=p2.nome_safe, orcamento_id=o2.id, loja_id=l2.id)
    db.add_all([ct1, ct2]); db.flush()

    # Briefing completo para Proj_L2 (necessário para criar orçamentos via POST)
    from datetime import datetime as _dt
    bf2 = app_db.Briefing(
        cliente_id=c2.id,
        projeto_nome=p2.nome_safe,
        data_atendimento=_dt(2026, 1, 1),
        tipo_imovel="apartamento",
        budget_declarado=50000.0,
        categoria_proposta="completo",
        data_entrega_desejada="2026-12-01",
        flexibilidade_prazo="sim",
    )
    db.add(bf2)
    db.commit()

    ctx = {
        "rede_id": rede.id,
        "loja1_id": l1.id, "loja2_id": l2.id,
        "emitente_l1_id": em1.id, "emitente_l2_id": em2.id,
        "cliente_l1_id": c1.id, "cliente_l2_id": c2.id,
        "projeto_l1": "Proj_L1", "projeto_l2": "Proj_L2",
        "orcamento_l1_id": o1.id, "orcamento_l2_id": o2.id,
        "contrato_l1_id": ct1.id,
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
def projetos_dir(app_db, seed, tmp_path_factory):
    """Redireciona PROJETOS_DIR (em storage/main/mod_omie) para um diretório temporário,
    deixando o harness hermético quanto a disco — espelha o isolamento do banco.
    Também cria no disco os projetos do seed: a lista de `/projetos` vem do disco e é
    cruzada com `projetos_meta.loja_id`, então o filtro por loja só é exercitável de fato
    se os dois projetos existirem em disco (o de loja 1 deve ser filtrado para a loja 2).
    Depende de `app_db` para garantir que `import main` ocorra após o rebind do banco."""
    import json as _json2
    import storage, main, mod_omie
    tmp = str(tmp_path_factory.mktemp("projetos"))
    for mod in (storage, main, mod_omie):
        if hasattr(mod, "PROJETOS_DIR"):
            mod.PROJETOS_DIR = tmp
    for nome in (seed["projeto_l1"], seed["projeto_l2"]):
        pasta = os.path.join(tmp, nome)
        os.makedirs(pasta, exist_ok=True)
        with open(os.path.join(pasta, "projeto.json"), "w", encoding="utf-8") as f:
            _json2.dump({"nome_safe": nome, "ambientes": []}, f)
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
