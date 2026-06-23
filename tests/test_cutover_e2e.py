# tests/test_cutover_e2e.py
# Task 2: testes E2E para o endpoint POST /api/orcamentos/<id>/negociacao-preview

def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c

def test_preview_devolve_valores_do_motor(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    st, body = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
    assert st == 200 and body["ok"]
    s = body["sombra"]
    # chaves da cadeia completa presentes
    for k in ("VBVO", "VAVO", "Val_Liq", "Markup", "Desc_Tot", "Com_Arq", "Pro_Fid", "Cust_Ad", "Val_Cont"):
        assert k in s
    assert "ambientes" in body

def test_preview_fora_do_escopo_404(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")           # loja 2
    st, body = c.post(f"/api/orcamentos/{seed['orcamento_l1_id']}/negociacao-preview", {})
    assert st == 404 and body.get("ok") is False
