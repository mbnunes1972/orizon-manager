import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def _cli(c, **extra):
    body = {"nome": "X", "email": "x@x.com", "telefone": "(12) 90000-0000"}; body.update(extra)
    return c.post("/api/clientes", body)

def test_cliente_cpf_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="111.444.777-00")
    assert st == 400 and "cpf" in d.get("erro","").lower()

def test_cliente_cpf_repetido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="111.111.111-11")
    assert st == 400

def test_cliente_cpf_valido_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="390.533.447-05")
    assert st == 200 and d["ok"], d

def test_cliente_sem_cpf_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c)   # sem cpf -> permitido (opcional)
    assert st == 200 and d["ok"], d

def test_cliente_cnpj_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, tipo_dest="contribuinte", cnpj="11.222.333/0001-00")
    assert st == 400 and "cnpj" in d.get("erro","").lower()

def test_cliente_editar_cpf_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="168.995.350-09"); cid = d["cliente"]["id"]
    st2, d2 = c.post(f"/api/clientes/{cid}/editar", {"cpf": "111.444.777-00"})
    assert st2 == 400
