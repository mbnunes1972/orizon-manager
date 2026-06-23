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
    """Garante que POST /margens grava valor_total/valor_liquido pelo motor com
    valores não-zero (asserção significativa — o orçamento tem ambiente real)."""
    oid = seed["orcamento_l1_id"]

    # ── 1. Semear um PoolAmbiente e vinculá-lo ao orçamento ──────────────────
    db = app_db.get_session()
    orc_seed = db.get(app_db.Orcamento, oid)
    projeto_id = orc_seed.projeto_id
    pa = app_db.PoolAmbiente(
        nome="Cozinha",
        nome_exibicao="Cozinha",
        xml_path="fake/path.xml",
        ambientes_json="{}",
        projeto_id=projeto_id,
        budget_total=10000.0,
        order_total=4000.0,
    )
    db.add(pa); db.flush()
    oa = app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1)
    db.add(oa)
    db.commit()
    db.close()

    # ── 2. Salvar margens (desconto 0, sem custos) ───────────────────────────
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 0})
    assert st == 200, f"esperado 200, obtido {st}: {body}"

    # ── 3. Verificar persistência com valores reais (não-zero) ───────────────
    db2 = app_db.get_session()
    o = db2.get(app_db.Orcamento, oid)
    # VAVO deve refletir o budget_total do ambiente semeado
    assert abs((o.vavo or 0) - 10000.0) < 0.5, f"vavo={o.vavo} esperado ≈10000"
    # val_liq > 0 prova que o motor rodou com dados reais (não retornou 0 trivialmente)
    assert (o.val_liq or 0) > 0, f"val_liq={o.val_liq} deveria ser > 0"
    # valor_liquido == val_liq (consistência: motor grava autoritativamente)
    assert abs((o.valor_liquido or 0) - (o.val_liq or 0)) < 0.02, (
        f"valor_liquido={o.valor_liquido} != val_liq={o.val_liq}")
    # valor_total == val_cont (consistência)
    assert abs((o.valor_total or 0) - (o.val_cont or 0)) < 0.02, (
        f"valor_total={o.valor_total} != val_cont={o.val_cont}")
    db2.close()

def test_patch_nao_aceita_valor_total_do_frontend(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    c.patch(f"/orcamentos/{oid}/valor", {"valor_total": 999999.0, "valor_liquido": 888888.0})
    db = app_db.get_session(); o = db.get(app_db.Orcamento, oid)
    assert (o.valor_total or 0) != 999999.0      # ignorado/recalculado
    db.close()

def test_preview_ambientes_tem_id_e_vava(http_client_factory, seed, app_db):
    """O preview devolve, por ambiente, o pool_ambiente_id (para o frontend casar as
    células) e o VAVA (à vista por ambiente)."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    projeto_id = db.get(app_db.Orcamento, oid).projeto_id
    pa = app_db.PoolAmbiente(nome="Sala", nome_exibicao="Sala", xml_path="x.xml",
                             ambientes_json="{}", projeto_id=projeto_id,
                             budget_total=8000.0, order_total=3000.0)
    db.add(pa); db.flush()
    pid = pa.id
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pid, ordem=1))
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
    assert st == 200 and body["ok"]
    # robusto a poluição de seed entre testes: localiza O MEU ambiente pelo id
    mine = [a for a in body["ambientes"] if a.get("id") == pid]
    assert len(mine) == 1, f"ambiente {pid} não encontrado em {body['ambientes']}"
    assert abs(mine[0]["VAVA"] - 8000.0) < 0.5      # desconto 0 ⇒ VAVA = budget
