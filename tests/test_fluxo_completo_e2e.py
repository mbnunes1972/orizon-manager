"""E2E do início ao fim — fluxo comercial + financeiro, contra o servidor HTTP real.

Percorre: login → negociação (motor + margem real) → Out_Forn → ciclo → contrato (Venda) →
Provisões (Venda → Rev 1 Concorda → Rev 2 Revisa) → consistência/staleness → isolamento (IDOR).

Limites do ambiente (documentados, não são lacunas do produto):
- A geração do PDF de contrato (Etapa 7) usa LibreOffice (`soffice`), ausente no CI/WSL. A etapa
  do contrato é exercida chamando o MESMO hook que o handler de geração usa após persistir o
  contrato (`main._registrar_provisao_venda`) — o efeito relevante para este fluxo (gravar a
  "Venda") é idêntico.
- O upload de XML de ambiente é coberto por `test_qualidade_upload_e2e`; aqui o ambiente é montado
  direto no banco (PoolAmbiente), como nos demais e2e financeiros.
"""
import json


def _setup_cenario(app_db, seed):
    """Cenário comercial no banco: taxas financeiras da loja, 1 ambiente com valor, forma de
    pagamento A Vista (entrada + liquidação) e desconto zero no orçamento do seed."""
    import mod_provisoes
    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, seed["loja1_id"])
        cfg = mod_provisoes.config_financeira_default()
        cfg["defaults_negociacao"]["carga_trib_pct"] = 8.0
        cfg["provisoes"]["frete_fab_pct"] = 3.0
        cfg["provisoes"]["com_adm_pct"] = 5.0
        loja.config_financeira_json = json.dumps(cfg)

        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha", versao=1,
                                 nome_exibicao="Cozinha", xml_path="", ambientes_json="[]",
                                 budget_total=90000.0, order_total=40000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                        pool_ambiente_id=pa.id, desconto_individual_pct=0.0))

        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        orc.desconto_pct = 0.0
        orc.forma_pagamento = json.dumps({
            "tipo": "avista", "nome_forma": "A Vista", "entrada_valor": 10000,
            "entrada_data": "2026-07-01", "entrada_forma": "pix", "total_cliente": 90000.0,
            "parcelas": [{"num": 1, "data": "2026-07-20", "valor": 80000.0, "forma": "pix"}]})
        db.commit()
    finally:
        db.close()


def test_fluxo_completo_inicio_ao_fim(app_db, seed, projetos_dir, http_client_factory):
    _setup_cenario(app_db, seed)
    oid = seed["orcamento_l1_id"]
    c = http_client_factory()

    # 1) Login — diretor da loja 1 (tem aprovar_financeiro)
    st, _ = c.login("dir_l1", "senha123")
    assert st == 200

    # 2) Negociação: o motor calcula a cadeia e a margem real
    st, b = c.post("/api/orcamentos/%d/negociacao-preview" % oid, {})
    assert st == 200 and b["ok"], b
    s = b["sombra"]
    assert s["VBVO"] == 90000.0 and s["CFO"] == 40000.0 and s["Num_Amb"] == 1
    assert s["Val_Liq"] > 0
    assert s["Cust_Var"] > s["CFO"]          # provisões (frete fábrica etc.) entram no Cust_Var
    assert 0 < s["Marg_Cont"] < 1

    # 3) Out_Forn editável reflete no Cust_Var
    st, b = c.put("/api/orcamentos/%d/out-forn" % oid, {"out_forn": 1500})
    assert st == 200 and b["ok"] and b["sombra"]["Out_Forn"] == 1500

    # 4) Ciclo do projeto carrega (etapas)
    st, b = c.get("/api/projetos/%s/ciclo" % seed["projeto_l1"])
    assert st == 200

    # 5) [Etapa 7 — Contrato] PDF usa LibreOffice (ausente). Exercita o MESMO hook que o handler
    #    de geração chama após persistir o contrato: grava a "Venda" das provisões.
    import main
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, oid)
        main._registrar_provisao_venda(db, orc, por_id=1)
        db.commit()
    finally:
        db.close()

    # 6) Provisões: "Venda" registrada e coerente com o cálculo atual
    st, b = c.get("/api/orcamentos/%d/provisoes" % oid)
    assert st == 200 and b["ok"], b
    prov = b["provisoes"]
    assert prov["venda"] is not None
    assert prov["rev1"] is None and prov["rev2"] is None
    assert prov["desatualizado"] is False
    itens_venda = prov["venda"]["itens"]
    assert set(itens_venda.keys()) == {
        "frete_fab", "com_adm", "com_venda", "com_med", "com_proj_exec",
        "frete_loc", "assist", "ins_loc", "prov_imp", "out_forn"}
    assert itens_venda["out_forn"] == 1500           # Out_Forn entrou na Venda
    assert itens_venda["frete_fab"] > 0              # taxa de frete fábrica da loja aplicada

    # 7) Aprovação Financeira I — Concorda: Rev 1 = cópia da Venda
    st, b = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                   {"decisao": "concorda", "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and b["ok"], b
    st, b = c.get("/api/orcamentos/%d/provisoes" % oid)
    assert b["provisoes"]["rev1"]["itens"] == b["provisoes"]["venda"]["itens"]
    assert b["provisoes"]["rev1"]["decisao"] == "concorda"
    venda_cust_var = b["provisoes"]["venda"]["cust_var"]
    venda_marg = b["provisoes"]["venda"]["marg_cont"]

    # 8) Aprovação Financeira II — Revisa: edita Out_Forn; margem recalcula da base congelada
    novos = dict(b["provisoes"]["venda"]["itens"])
    novos["out_forn"] = 5000.0
    st, b = c.post("/api/orcamentos/%d/provisoes/rev2" % oid,
                   {"decisao": "revisa", "itens": novos, "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and b["ok"], b
    st, b = c.get("/api/orcamentos/%d/provisoes" % oid)
    rev2 = b["provisoes"]["rev2"]
    assert rev2["decisao"] == "revisa"
    assert rev2["itens"]["out_forn"] == 5000.0
    assert rev2["cust_var"] > venda_cust_var          # custo maior → margem menor
    assert rev2["marg_cont"] < venda_marg

    # 9) Consistência: negociação muda APÓS a Venda → aviso de desatualizado
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, oid)
        orc.desconto_pct = 15.0
        db.commit()
    finally:
        db.close()
    st, b = c.get("/api/orcamentos/%d/provisoes" % oid)
    assert b["provisoes"]["desatualizado"] is True

    # 10) Isolamento: diretor de OUTRA loja não acessa as provisões deste orçamento
    c2 = http_client_factory()
    c2.login("dir_l2", "senha123")
    st, _ = c2.get("/api/orcamentos/%d/provisoes" % oid)
    assert st in (403, 404)
