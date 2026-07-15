"""mod_comercial_dash — métricas do painel Comercial (view derivada da fonte única: projetos_meta,
orcamentos, contratos, ciclo_etapas). Escopo por loja. Funil de conversão + carteira por status +
volume contratado/ticket médio."""
import mod_comercial_dash as cd
from database import Projeto, Orcamento, Contrato, CicloEtapa


def _seed_dash(db, loja):
    p = "D%d_" % loja   # nomes únicos por loja (nome_safe é PK; app_db é module-scoped)
    # P1: quente, com orçamento (etapa 4 concluída), sem contrato
    db.add(Projeto(nome_safe=p + "1", status="quente", loja_id=loja))
    db.add(CicloEtapa(projeto_nome=p + "1", etapa_codigo="4", status="concluido"))
    # P2: morno, com orçamento + contrato assinado (valor 10.000)
    db.add(Projeto(nome_safe=p + "2", status="morno", loja_id=loja))
    db.add(CicloEtapa(projeto_nome=p + "2", etapa_codigo="4", status="concluido"))
    db.add(CicloEtapa(projeto_nome=p + "2", etapa_codigo="7", status="concluido"))
    o = Orcamento(projeto_id=p + "2", nome="Orçamento 1", ordem=1, loja_id=loja, valor_total=10000.0)
    db.add(o); db.flush()
    db.add(Contrato(projeto_nome=p + "2", orcamento_id=o.id, loja_id=loja, status="assinado"))
    # P3: frio, nada
    db.add(Projeto(nome_safe=p + "3", status="frio", loja_id=loja))
    db.commit()


def test_dashboard_comercial_funil_carteira_volume(app_db):
    db = app_db.get_session()
    try:
        _seed_dash(db, 7777)
        d = cd.dashboard_comercial(db, 7777)
        assert d["funil"] == {"total": 3, "com_orcamento": 2, "com_contrato": 1,
                              "conv_orcamento_pct": 66.7, "conv_contrato_pct": 33.3}
        assert d["carteira"]["por_status"] == {"quente": 1, "morno": 1, "frio": 1}
        assert d["carteira"]["total_aberto"] == 3
        assert d["volume"] == {"contratado": 10000.0, "n_contratos": 1, "ticket_medio": 10000.0}
    finally:
        db.close()


def test_dashboard_comercial_escopo_por_loja(app_db):
    db = app_db.get_session()
    try:
        _seed_dash(db, 7778)
        db.add(Projeto(nome_safe="OUTRA", status="quente", loja_id=9001)); db.commit()
        d = cd.dashboard_comercial(db, 7778)
        assert d["funil"]["total"] == 3   # não conta a projeto da loja 9001
    finally:
        db.close()


def test_endpoint_comercial_dashboard(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/comercial/dashboard")
    assert st == 200 and d["ok"], (st, d)
    assert set(d["dashboard"].keys()) == {"funil", "carteira", "volume"}
    assert "total" in d["dashboard"]["funil"] and "por_status" in d["dashboard"]["carteira"]


def test_endpoint_comercial_dashboard_exige_login(http_client_factory):
    c = http_client_factory()
    st, _ = c.get("/api/comercial/dashboard")
    assert st == 401


def test_dashboard_comercial_vazio(app_db):
    db = app_db.get_session()
    try:
        d = cd.dashboard_comercial(db, 8888)   # loja sem projetos
        assert d["funil"]["total"] == 0 and d["funil"]["conv_orcamento_pct"] == 0
        assert d["carteira"]["total_aberto"] == 0
        assert d["volume"]["n_contratos"] == 0 and d["volume"]["ticket_medio"] == 0
    finally:
        db.close()
