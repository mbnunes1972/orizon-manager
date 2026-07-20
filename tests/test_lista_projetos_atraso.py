"""Fatia 4 (spec §6) — GET /projetos anota `atrasado` (sinal GERAL: qualquer etapa aberta com
previsão vencida, ou entrega vencida com a "16" aberta) e serializa `data_entrega` na lista."""
from datetime import datetime, timedelta


def _reset(app_db, proj):
    """Estado limpo por teste: o seed é módulo-scoped e os testes deste arquivo mexem em
    CicloEtapa/status/data_entrega do MESMO projeto — sem reset a ordem de execução vazaria."""
    db = app_db.get_session()
    db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj).delete()
    p = db.get(app_db.Projeto, proj)
    p.status = None
    p.data_entrega = None
    db.commit()
    db.close()


def _projeto_na_lista(c, proj):
    st, d = c.get("/projetos")
    assert st == 200 and d["ok"], (st, d)
    por_nome = {p.get("nome_safe"): p for p in d["projetos"]}
    assert proj in por_nome, sorted(por_nome)
    return por_nome[proj]


def test_lista_atrasado_true_com_etapa_aberta_vencida(http_client_factory, seed, app_db, projetos_dir):
    proj = seed["projeto_l1"]
    _reset(app_db, proj)
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo="9",
                             data_prevista_conclusao=datetime.utcnow() - timedelta(days=3)))
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    assert _projeto_na_lista(c, proj)["atrasado"] is True


def test_lista_atrasado_false_em_dia(http_client_factory, seed, app_db, projetos_dir):
    proj = seed["projeto_l1"]
    _reset(app_db, proj)
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo="9",
                             data_prevista_conclusao=datetime.utcnow() + timedelta(days=10)))
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    assert _projeto_na_lista(c, proj)["atrasado"] is False


def test_lista_atrasado_false_etapa_vencida_mas_concluida(http_client_factory, seed, app_db, projetos_dir):
    proj = seed["projeto_l1"]
    _reset(app_db, proj)
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo="9",
                             data_prevista_conclusao=datetime.utcnow() - timedelta(days=3),
                             concluido_em=datetime.utcnow() - timedelta(days=1)))
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    assert _projeto_na_lista(c, proj)["atrasado"] is False


def test_lista_serializa_data_entrega(http_client_factory, seed, app_db, projetos_dir):
    proj = seed["projeto_l1"]
    _reset(app_db, proj)
    db = app_db.get_session()
    db.get(app_db.Projeto, proj).data_entrega = datetime(2028, 1, 1)
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    item = _projeto_na_lista(c, proj)
    assert (item["data_entrega"] or "").startswith("2028-01-01")
    assert item["atrasado"] is False   # entrega futura, sem etapa vencida


def test_lista_atrasado_entrega_vencida_sem_16_concluida(http_client_factory, seed, app_db, projetos_dir):
    proj = seed["projeto_l1"]
    _reset(app_db, proj)
    db = app_db.get_session()
    db.get(app_db.Projeto, proj).data_entrega = datetime.utcnow() - timedelta(days=5)
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    assert _projeto_na_lista(c, proj)["atrasado"] is True


def test_lista_projeto_perdido_nunca_atrasado(http_client_factory, seed, app_db, projetos_dir):
    proj = seed["projeto_l1"]
    _reset(app_db, proj)
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo="9",
                             data_prevista_conclusao=datetime.utcnow() - timedelta(days=3)))
    db.get(app_db.Projeto, proj).status = "perdido"
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    assert _projeto_na_lista(c, proj)["atrasado"] is False


def test_lista_projeto_fechado_em_execucao_ACENDE(http_client_factory, seed, app_db, projetos_dir):
    """"fechado" = contrato assinado, ciclo em EXECUÇÃO (etapas 8-20) — a população-alvo do sinal.
    Regressão do achado da Vera (QA Fatia 4): tratar "fechado" como terminal mata a feature."""
    proj = seed["projeto_l1"]
    _reset(app_db, proj)
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo="9",
                             data_prevista_conclusao=datetime.utcnow() - timedelta(days=3)))
    db.get(app_db.Projeto, proj).status = "fechado"
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    assert _projeto_na_lista(c, proj)["atrasado"] is True


def test_lista_projeto_concluido_ou_cancelado_nunca_atrasado(http_client_factory, seed, app_db, projetos_dir):
    proj = seed["projeto_l1"]
    for status in ("concluido", "cancelado"):
        _reset(app_db, proj)
        db = app_db.get_session()
        db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo="9",
                                 data_prevista_conclusao=datetime.utcnow() - timedelta(days=3)))
        db.get(app_db.Projeto, proj).status = status
        db.commit(); db.close()
        c = http_client_factory(); c.login("dir_l1", "senha123")
        assert _projeto_na_lista(c, proj)["atrasado"] is False, status
