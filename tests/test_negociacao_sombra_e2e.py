# tests/test_negociacao_sombra_e2e.py
"""E2E: ao salvar a negociação de um orçamento, os derivados do motor novo
são materializados nas colunas sombra. O comportamento legado não é alterado.

Nota: o bloco sombra é não-intrusivo e roda APÓS o send_json (resposta já enviada).
Por isso aguardamos brevemente antes de verificar as colunas no banco."""


def _login(f, who):
    c = f()
    c.login(who, "senha123")
    assert c.cookie
    return c


def test_salvar_margens_materializa_derivados(http_client_factory, seed, app_db):
    import time
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]

    # Zera as colunas sombra para garantir que o endpoint as preenche (não são defaults)
    db_pre = app_db.get_session()
    o_pre = db_pre.get(app_db.Orcamento, oid)
    o_pre.vavo = None
    o_pre.val_liq = None
    o_pre.markup = None
    db_pre.commit()
    db_pre.close()

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 10})
    assert st == 200

    # O bloco sombra é não-intrusivo e corre APÓS a resposta ser enviada;
    # aguardamos para garantir que o commit sombra seja visível.
    time.sleep(0.2)

    db = app_db.get_session()
    o = db.get(app_db.Orcamento, oid)
    # derivados gravados (não-nulos — engine materializou); legado intacto
    assert o.vavo is not None and o.val_liq is not None and o.markup is not None
    assert o.valor_liquido is not None   # coluna legada continua existindo
    # consistência: val_cont == vavo + cust_fin (ambos vindos do motor, fonte única)
    if o.vavo is not None and o.cust_fin is not None and o.val_cont is not None:
        assert o.val_cont == round(o.vavo + o.cust_fin, 2)
    db.close()
