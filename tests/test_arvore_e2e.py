import pytest
from datetime import datetime


@pytest.fixture(scope="module")
def com_etapas_http(app_db, seed):
    from database import CicloEtapa
    db = app_db.get_session()
    try:
        db.add_all([
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="1",
                       status="concluido", concluido_em=datetime(2026, 1, 1)),
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="2",
                       status="pendente"),
        ])
        db.commit()
    finally:
        db.close()
    return seed


def test_super_lista_projetos_da_loja(http_client_factory, seed, com_etapas_http):
    c = http_client_factory()
    c.login("super", "senha123")
    st, body = c.get("/api/admin/lojas/%d/projetos" % seed["loja1_id"])
    assert st == 200
    assert body["ok"] is True
    assert any(p["nome_safe"] == "Proj_L1" for p in body["projetos"])


def test_super_lista_etapas_do_projeto(http_client_factory, seed, com_etapas_http):
    c = http_client_factory()
    c.login("super", "senha123")
    st, body = c.get("/api/admin/projetos/Proj_L1/etapas")
    assert st == 200
    assert body["ok"] is True
    assert [e["etapa_codigo"] for e in body["etapas"]] == ["1", "2"]


def test_operacional_recebe_403(http_client_factory, seed, com_etapas_http):
    c = http_client_factory()
    c.login("dir_l1", "senha123")
    st, _ = c.get("/api/admin/lojas/%d/projetos" % seed["loja1_id"])
    assert st == 403


def test_loja_inexistente_404(http_client_factory, com_etapas_http):
    c = http_client_factory()
    c.login("super", "senha123")
    st, _ = c.get("/api/admin/lojas/999999/projetos")
    assert st == 404


def test_projeto_inexistente_404(http_client_factory, com_etapas_http):
    c = http_client_factory()
    c.login("super", "senha123")
    st, _ = c.get("/api/admin/projetos/NaoExiste/etapas")
    assert st == 404


# ---------------------------------------------------------------------------
# Isolamento cross-rede (I1): admin_rede da Rede A não enxerga recursos da Rede B
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rede_b(app_db, seed):
    """Cria uma segunda rede com sua própria loja e projeto, isolados da Rede Teste."""
    db = app_db.get_session()
    try:
        rede = app_db.Rede(nome="Rede B")
        db.add(rede)
        db.flush()

        loja = app_db.Loja(nome="Loja B", rede_id=rede.id, codigo="LJB")
        db.add(loja)
        db.flush()

        projeto = app_db.Projeto(nome_safe="Proj_RedeB", status="quente", loja_id=loja.id)
        db.add(projeto)
        db.commit()

        return {"loja_b_id": loja.id, "projeto_b": "Proj_RedeB"}
    finally:
        db.close()


def test_admin_rede_nao_ve_loja_de_outra_rede(http_client_factory, seed, rede_b):
    """admin_rede da Rede A deve receber 403 ao acessar lojas da Rede B."""
    c = http_client_factory()
    c.login("adm_rede", "senha123")
    st, _ = c.get("/api/admin/lojas/%d/projetos" % rede_b["loja_b_id"])
    assert st == 403


def test_admin_rede_nao_ve_projeto_de_outra_rede(http_client_factory, seed, rede_b):
    """admin_rede da Rede A deve receber 403 ao acessar projetos da Rede B."""
    c = http_client_factory()
    c.login("adm_rede", "senha123")
    st, _ = c.get("/api/admin/projetos/%s/etapas" % rede_b["projeto_b"])
    assert st == 403
