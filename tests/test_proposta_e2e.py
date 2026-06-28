import os
import pytest


@pytest.fixture(autouse=True)
def _template_existe():
    # garante que o template foi gerado (Task 2); senão pula o e2e
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "modelo_proposta.docx")):
        pytest.skip("modelo_proposta.docx ausente")


def _setup_ambiente(app_db, seed):
    db = app_db.get_session()
    try:
        if not db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=seed["orcamento_l1_id"]).first():
            pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha", versao=1,
                                     nome_exibicao="Cozinha", xml_path="", ambientes_json="[]",
                                     budget_total=90000.0, order_total=40000.0)
            db.add(pa); db.flush()
            db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                            pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
            db.commit()
    finally:
        db.close()


def test_proposta_pdf_gera_e_serve(http_client_factory, app_db, seed, projetos_dir):
    _setup_ambiente(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.get("/api/orcamentos/%d/proposta/pdf" % seed["orcamento_l1_id"])
    assert st == 200
    assert body  # corpo não vazio (bytes do docx/pdf)


def test_proposta_pdf_outra_loja_404(http_client_factory, app_db, seed, projetos_dir):
    _setup_ambiente(app_db, seed)
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, _ = c.get("/api/orcamentos/%d/proposta/pdf" % seed["orcamento_l1_id"])
    assert st in (403, 404)


def test_proposta_pdf_anonimo_401(http_client_factory, seed):
    c = http_client_factory()
    st, _ = c.get("/api/orcamentos/%d/proposta/pdf" % seed["orcamento_l1_id"])
    assert st == 401
