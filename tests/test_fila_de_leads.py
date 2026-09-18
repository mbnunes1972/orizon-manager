# -*- coding: utf-8 -*-
"""docs/db/TAREFA_FILA_DE_LEADS.md, Parte 2 — a fila de "contato de fora sem dono".

Recorte (2a): TriagemEntrada pendente + Conversa externa materializada sem participante/
responsável — as duas metades, senão o item só existe por minutos e some ao materializar
(foi o que aconteceu com o Felipe em 17/09).

Gate (decisão do Marcelo, 18/09): TENANCY + quem ocupa a Função SAC da loja, NUNCA nível — o
SAC nasce Operador (medido na Parte 1: nenhuma capacidade de nível é necessária pra ler/
escrever conversa), então gatear por `ver_todas_conversas` deixaria a própria pessoa que
trabalha a fila sem enxergá-la."""
import pytest

from database import Conversa, ConversaParticipante, TriagemEntrada


def _login(f, who):
    c = f()
    c.login(who, "senha123")
    assert c.cookie
    return c


@pytest.fixture(scope="module")
def sac_l1(app_db, seed):
    """SAC Operador da loja 1 — Função SAC + Funcionário + Usuário vinculados, mesmo padrão de
    test_atendimentos_ui.py::test_resolucao_de_triagem_assume_e_marca_origem. Retorna o
    usuario_id."""
    db = app_db.get_session()
    try:
        u = app_db.Usuario(nome="SAC L1 (teste)", login="sac_l1_teste", nivel="operador",
                           loja_id=seed["loja1_id"], ativo=1)
        u.set_senha("senha123")
        db.add(u); db.flush()
        fn = app_db.Funcao(loja_id=seed["loja1_id"], nome="SAC")
        db.add(fn); db.flush()
        func = app_db.Funcionario(nome="SAC L1 (teste)", loja_id=seed["loja1_id"],
                                  funcao_id=fn.id, usuario_id=u.id, status="ativo")
        db.add(func); db.flush()
        db.commit()
        return u.id
    finally:
        db.close()


# ── Gate de leitura (GET /api/comunicacao/fila) ──────────────────────────────────────────────

def test_sac_ve_a_fila(http_client_factory, app_db, seed, sac_l1):
    db = app_db.get_session()
    try:
        ent = TriagemEntrada(loja_id=seed["loja1_id"], meio="whatsapp",
                             remetente="5512999991001", texto="oi, fila teste")
        db.add(ent); db.commit()
        eid = ent.id
    finally:
        db.close()
    c = _login(http_client_factory, "sac_l1_teste")
    st, body = c.get("/api/comunicacao/fila")
    assert st == 200 and body["ok"]
    assert any(it["tipo"] == "triagem" and it["id"] == eid for it in body["itens"])


def test_operador_nao_sac_nao_ve_a_fila(http_client_factory, seed, sac_l1):
    """cons_l1 (seed): operador da loja 1, mas NÃO ocupa a Função SAC."""
    c = _login(http_client_factory, "cons_l1")
    st, body = c.get("/api/comunicacao/fila")
    assert st == 403 and body["ok"] is False


def test_usuario_de_outra_loja_nao_ve_a_fila(http_client_factory, seed, sac_l1):
    """dir_l2 (seed): master, mas de outra loja — nível não importa, tenancy manda."""
    c = _login(http_client_factory, "dir_l2")
    st, body = c.get("/api/comunicacao/fila")
    assert st == 403 and body["ok"] is False


def test_fila_inclui_conversa_externa_ja_materializada_sem_dono(http_client_factory, app_db,
                                                                 seed, sac_l1):
    """Recorte 2a, segundo estado: conversa externa já materializada, sem participante nem
    responsável — as órfãs de 31/08-16/09 aparecem sozinhas, sem adoção manual no banco."""
    db = app_db.get_session()
    try:
        conv = Conversa(loja_id=seed["loja1_id"], tipo="grupo", titulo="Lead — Órfã Teste",
                        origem_entrada="triagem")
        db.add(conv); db.commit()
        cid = conv.id
    finally:
        db.close()
    c = _login(http_client_factory, "sac_l1_teste")
    st, body = c.get("/api/comunicacao/fila")
    assert st == 200
    assert any(it["tipo"] == "conversa" and it["id"] == cid for it in body["itens"])


# ── Ação Assumir (POST /api/comunicacao/fila/assumir) ────────────────────────────────────────

def test_assumir_triagem_materializa_e_sai_da_fila(http_client_factory, app_db, seed, sac_l1):
    db = app_db.get_session()
    try:
        ent = TriagemEntrada(loja_id=seed["loja1_id"], meio="whatsapp",
                             remetente="5512999991002", texto="quero orçamento")
        db.add(ent); db.commit()
        eid = ent.id
    finally:
        db.close()
    c = _login(http_client_factory, "sac_l1_teste")
    st, body = c.post("/api/comunicacao/fila/assumir", {"tipo": "triagem", "id": eid})
    assert st == 200 and body["ok"]
    conv_id = body["conversa_id"]
    db = app_db.get_session()
    try:
        conv = db.get(Conversa, conv_id)
        assert conv.responsavel_usuario_id == sac_l1
        part = (db.query(ConversaParticipante)
                  .filter_by(conversa_id=conv_id, usuario_id=sac_l1, removido=0).first())
        assert part is not None
        assert db.get(TriagemEntrada, eid).status == "resolvido"
    finally:
        db.close()
    st2, body2 = c.get("/api/comunicacao/fila")
    assert not any(it["id"] == eid and it["tipo"] == "triagem" for it in body2["itens"])
    assert not any(it["id"] == conv_id and it["tipo"] == "conversa" for it in body2["itens"])


def test_assumir_conversa_orfa_vira_dono_e_sai_da_fila(http_client_factory, app_db, seed, sac_l1):
    db = app_db.get_session()
    try:
        conv = Conversa(loja_id=seed["loja1_id"], tipo="grupo", titulo="Lead — Órfã Assumir",
                        origem_entrada="avulsa")
        db.add(conv); db.commit()
        cid = conv.id
    finally:
        db.close()
    c = _login(http_client_factory, "sac_l1_teste")
    st, body = c.post("/api/comunicacao/fila/assumir", {"tipo": "conversa", "id": cid})
    assert st == 200 and body["ok"] and body["conversa_id"] == cid
    db = app_db.get_session()
    try:
        conv = db.get(Conversa, cid)
        assert conv.responsavel_usuario_id == sac_l1
        part = (db.query(ConversaParticipante)
                  .filter_by(conversa_id=cid, usuario_id=sac_l1, removido=0).first())
        assert part is not None
    finally:
        db.close()
    st2, body2 = c.get("/api/comunicacao/fila")
    assert not any(it["id"] == cid and it["tipo"] == "conversa" for it in body2["itens"])


def test_assumir_bloqueado_pra_quem_nao_e_sac(http_client_factory, app_db, seed, sac_l1):
    db = app_db.get_session()
    try:
        ent = TriagemEntrada(loja_id=seed["loja1_id"], meio="whatsapp",
                             remetente="5512999991003", texto="teste bloqueio")
        db.add(ent); db.commit()
        eid = ent.id
    finally:
        db.close()
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post("/api/comunicacao/fila/assumir", {"tipo": "triagem", "id": eid})
    assert st == 403 and body["ok"] is False
    db = app_db.get_session()
    try:
        assert db.get(TriagemEntrada, eid).status == "pendente"
    finally:
        db.close()


def test_assumir_recusa_item_de_outra_loja(http_client_factory, app_db, seed, sac_l1):
    """SAC da loja 1 não assume item da loja 2 (tenancy dentro de assumir_da_fila) — 400, não
    403: o ator é legitimamente SAC, só o item não é da loja dele."""
    db = app_db.get_session()
    try:
        ent = TriagemEntrada(loja_id=seed["loja2_id"], meio="whatsapp",
                             remetente="5512999991004", texto="loja errada")
        db.add(ent); db.commit()
        eid = ent.id
    finally:
        db.close()
    c = _login(http_client_factory, "sac_l1_teste")
    st, body = c.post("/api/comunicacao/fila/assumir", {"tipo": "triagem", "id": eid})
    assert st == 400 and body["ok"] is False
    db = app_db.get_session()
    try:
        assert db.get(TriagemEntrada, eid).status == "pendente"
    finally:
        db.close()
