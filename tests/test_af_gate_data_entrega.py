"""Gate independente da sequência (bug de teste manual): a AF (etapa 8/11d) só FECHA quando a data de
entrega está DEFINIDA **e** o contrato está totalmente assinado. Cobre o furo em que um projeto assinado
ANTES do gate da assinatura (data_entrega) chegava à AF sem a data — a trava vivia só na assinatura."""
from datetime import datetime

from database import Projeto, Contrato, CicloEtapa


def _prep(app_db, nome, *, data_entrega, contrato_status, contrato_id):
    """Estado mínimo p/ tentar concluir a etapa 8: etapa 7 concluída (pode_avancar), contrato num
    status dado e data_entrega dada. Cada teste fixa o estado COMPLETO → independe da ordem."""
    db = app_db.get_session()
    try:
        db.get(Projeto, nome).data_entrega = data_entrega
        db.get(Contrato, contrato_id).status = contrato_status
        e7 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="7").first()
        if not e7:
            e7 = CicloEtapa(projeto_nome=nome, etapa_codigo="7"); db.add(e7)
        e7.status = "concluido"
        e8 = db.query(CicloEtapa).filter_by(projeto_nome=nome, etapa_codigo="8").first()
        if e8:
            e8.status = "pendente"; e8.concluido_em = None
        db.commit()
    finally:
        db.close()


def _patch_af(c, nome):
    return c.patch("/api/projetos/%s/ciclo/8" % nome,
                   {"status": "concluido", "login": "dir_l1", "senha": "senha123"})


def test_af_bloqueia_sem_data_entrega(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _prep(app_db, nome, data_entrega=None, contrato_status="assinado",
          contrato_id=seed["contrato_l1_id"])
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _patch_af(c, nome)
    assert st == 400, (st, d)
    assert "data de entrega" in (d.get("erro", "").lower()), d


def test_af_bloqueia_contrato_nao_assinado(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _prep(app_db, nome, data_entrega=datetime(2028, 1, 1), contrato_status="para_assinatura",
          contrato_id=seed["contrato_l1_id"])
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _patch_af(c, nome)
    assert st == 400, (st, d)
    assert "contrato" in (d.get("erro", "").lower()), d


def test_af_fecha_com_data_e_contrato_assinado(app_db, seed, http_client_factory):
    nome = seed["projeto_l1"]
    _prep(app_db, nome, data_entrega=datetime(2028, 1, 1), contrato_status="assinado",
          contrato_id=seed["contrato_l1_id"])
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _patch_af(c, nome)
    assert st == 200 and d["ok"], (st, d)
    assert d["status"] == "concluido"
