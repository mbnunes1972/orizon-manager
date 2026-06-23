"""Task 4 — Trava de qualidade no upload do XML + quarentena.

Teste 1: verifica que avaliar_qualidade_xml devolve "bloqueado" para XML ruim (sanidade).
Teste 2: verifica que um PoolAmbiente com qa_selo="bloqueado" não pode ser adicionado
         a um orçamento (POST /orcamentos/<oid>/ambientes/<pid> → 409, ok=False).
"""

def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


# XML mínimo: 2 itens, ambos com ORDER==BUDGET (acréscimo zero) → 🔴
XML_RUIM = '''<PROJECT DESCRIPTION="Teste" DATE="01/01/2026"><CATEGORY DESCRIPTION="X"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="a" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="100" TOTAL="100"><MARGINS><ORDER TOTAL="100"/><BUDGET TOTAL="100"/></MARGINS></PRICE></ITEM>
<ITEM REFERENCE="B" DESCRIPTION="b" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="50" TOTAL="50"><MARGINS><ORDER TOTAL="50"/><BUDGET TOTAL="50"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


def test_upload_xml_ruim_marca_bloqueado(http_client_factory, seed, app_db, monkeypatch):
    from mod_qualidade_xml import avaliar_qualidade_xml
    from promob_grupos import ler_xml_str
    amb = ler_xml_str("ruim.xml", XML_RUIM)
    itens = [it for g in amb.get("grupos", []) for it in g.get("itens", [])]
    r = avaliar_qualidade_xml(itens)
    assert r["qa_selo"] == "bloqueado"   # sanidade do dado de teste


def test_ambiente_bloqueado_nao_entra_em_orcamento(http_client_factory, seed, app_db):
    # cria um pool ambiente 🔴 e um orçamento na loja 1; tentar vincular deve falhar
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Ruim", nome_exibicao="Ruim",
                             xml_path="x", ambientes_json="{}", budget_total=100, order_total=100,
                             qa_selo="bloqueado", qa_pct_sem_acrescimo=100.0)
    db.add(pa); db.commit(); pid = pa.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    # rota real: POST /orcamentos/<oid>/ambientes/<pid> (pid no path, sem /api, sem body)
    st, body = c.post(f"/orcamentos/{seed['orcamento_l1_id']}/ambientes/{pid}", {})
    assert body.get("ok") is False
