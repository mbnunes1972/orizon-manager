# tests/test_cutover_e2e.py
# Task 2: testes E2E para o endpoint POST /api/orcamentos/<id>/negociacao-preview
# Task 3: _recalcular_orcamento + persistência autoritativa

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


# ── Task 3 ─────────────────────────────────────────────────────────────────────

def test_save_margens_grava_valor_do_motor(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    st, _ = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 10})
    assert st == 200
    db = app_db.get_session(); o = db.get(app_db.Orcamento, oid)
    # valor_liquido == Val_Liq do motor (== val_liq sombra); valor_total == Val_Cont (== val_cont)
    assert abs((o.valor_liquido or 0) - (o.val_liq or 0)) < 0.02
    assert abs((o.valor_total or 0) - (o.val_cont or 0)) < 0.02
    db.close()

def test_patch_nao_aceita_valor_total_do_frontend(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    c.patch(f"/orcamentos/{oid}/valor", {"valor_total": 999999.0, "valor_liquido": 888888.0})
    db = app_db.get_session(); o = db.get(app_db.Orcamento, oid)
    assert (o.valor_total or 0) != 999999.0      # ignorado/recalculado
    db.close()
