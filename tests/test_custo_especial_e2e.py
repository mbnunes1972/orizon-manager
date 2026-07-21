"""E2E HTTP do Custo Especial (Sessão 87/89): o parâmetro sobrevive ao POST de
parâmetros (merge não descarta as chaves novas) e o motor o inclui no Val_Cont
persistido — exatamente a cadeia que um servidor com Python defasado quebra em
silêncio (o bug de campo 'ignorado' reportado em 2026-07-21 era processo antigo).
"""


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _seed_amb(app_db, oid, budget=50000.0):
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    projeto_id = orc.projeto_id
    pa = app_db.PoolAmbiente(nome="Sala", nome_exibicao="Sala", xml_path="fake/sala.xml",
                             ambientes_json="{}", projeto_id=projeto_id,
                             budget_total=budget, order_total=20000.0)
    db.add(pa); db.flush()
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit()
    nome = projeto_id
    db.close()
    return nome


def test_custo_especial_persiste_e_entra_no_val_cont(http_client_factory, seed, app_db):
    oid = seed["orcamento_l1_id"]
    nome_safe = _seed_amb(app_db, oid, budget=50000.0)
    c = _login(http_client_factory, "dir_l1")

    # salva parâmetros com Custo Especial ativo e repassado (incluir_custos ON)
    st, body = c.post(f"/api/projetos/{nome_safe}/parametros",
                      {"incluir_custos": True, "custo_especial": 1000.0,
                       "custo_especial_ativo": True, "carga_trib": 0})
    assert st == 200, f"esperado 200, obtido {st}: {body}"

    # round-trip: o GET devolve as chaves (merge NÃO pode descartá-las)
    st, body = c.get(f"/api/projetos/{nome_safe}/parametros")
    assert st == 200
    par = body["parametros"]
    assert par["custo_especial"] == 1000.0 and par["custo_especial_ativo"] is True

    # preview do motor: Cust_Esp presente e Val_Cont = ambiente + custo especial
    st, body = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
    assert st == 200
    s = body["sombra"]
    assert abs(s["Cust_Esp"] - 1000.0) < 0.01
    assert abs(s["Val_Cont"] - 51000.0) < 0.5, f"Val_Cont={s['Val_Cont']} esperado ≈51000"

    # persistência autoritativa: valor_total do orçamento também inclui
    db = app_db.get_session()
    o = db.get(app_db.Orcamento, oid)
    assert abs((o.valor_total or 0) - 51000.0) < 0.5, f"valor_total={o.valor_total}"
    db.close()
