"""E2E: cadastro/edição de cliente grava e devolve tipo_dest/cnpj/inscricao_estadual.

Task 3 (Spec §5): o POST /api/clientes e o POST /api/clientes/<id>/editar aceitam os
campos fiscais; o GET /api/clientes/<id> os devolve. Nenhum é obrigatório — se tipo_dest
vier ausente/vazio, mantém o default do modelo (nao_contribuinte).
"""


def test_cria_cliente_contribuinte_persiste_campos_fiscais(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/clientes", {
        "nome": "Cliente Contribuinte",
        "email": "contrib@ex.com",
        "telefone": "(11) 99999-0001",
        "tipo_dest": "contribuinte",
        "cnpj": "12.345.678/0001-99",
        "inscricao_estadual": "123456789",
    })
    assert st == 200 and d["ok"], d
    cid = d["cliente"]["id"]
    assert d["cliente"]["tipo_dest"] == "contribuinte"
    assert d["cliente"]["cnpj"] == "12.345.678/0001-99"
    assert d["cliente"]["inscricao_estadual"] == "123456789"

    # relê via GET para confirmar persistência
    st2, d2 = c.get(f"/api/clientes/{cid}")
    assert st2 == 200 and d2["ok"], d2
    assert d2["cliente"]["tipo_dest"] == "contribuinte"
    assert d2["cliente"]["cnpj"] == "12.345.678/0001-99"
    assert d2["cliente"]["inscricao_estadual"] == "123456789"


def test_cria_cliente_sem_tipo_dest_usa_default(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/clientes", {
        "nome": "Cliente Sem Tipo",
        "email": "semtipo@ex.com",
        "telefone": "(11) 99999-0002",
    })
    assert st == 200 and d["ok"], d
    assert d["cliente"]["tipo_dest"] == "nao_contribuinte"
    assert d["cliente"]["cnpj"] == ""
    assert d["cliente"]["inscricao_estadual"] == ""


def test_editar_cliente_atualiza_campos_fiscais(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/clientes", {
        "nome": "Cliente P/ Editar",
        "email": "editar@ex.com",
        "telefone": "(11) 99999-0003",
    })
    assert st == 200 and d["ok"], d
    cid = d["cliente"]["id"]

    st2, d2 = c.post(f"/api/clientes/{cid}/editar", {
        "tipo_dest": "isento",
        "cnpj": "98.765.432/0001-10",
    })
    assert st2 == 200 and d2["ok"], d2
    assert d2["cliente"]["tipo_dest"] == "isento"
    assert d2["cliente"]["cnpj"] == "98.765.432/0001-10"

    st3, d3 = c.get(f"/api/clientes/{cid}")
    assert d3["cliente"]["tipo_dest"] == "isento"
    assert d3["cliente"]["cnpj"] == "98.765.432/0001-10"


def test_cria_cliente_nao_sincroniza_omie_por_padrao(http_client_factory, seed):
    # Omie em descontinuação (OMIE_AUTO_SYNC off por padrão): cliente novo sai 'dispensado',
    # fora da fila de sync (que inclui status NULL).
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/clientes", {"nome": "Cliente Sem Omie", "cpf": "555.666.777-88",
                                     "email": "x@x.com", "telefone": "(12) 90000-0000"})
    assert st == 200 and d["ok"], d
    assert d["cliente"]["omie_sync_status"] == "dispensado"
