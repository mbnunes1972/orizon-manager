# -*- coding: utf-8 -*-
"""docs/db/TAREFA_ENTREGA_VISIVEL.md — Conserto 1: a informação de entrega para de ser jogada
fora. Os TRÊS call sites de `espelhar_para_externos` hoje (`main.py`: POST .../mensagens, POST
.../anexos, POST /api/projetos/<nome>/conversa/mensagens) continuam respondendo `{"ok": true}`
quando a mensagem interna é salva — o que muda é que a resposta agora também conta o destino
real da ponte externa (`entrega_estado`/`entrega_motivo`), nunca escondendo uma recusa da Meta.

Mocka `urllib.request.urlopen` no boundary da rede — mesmo padrão de
tests/test_orizon_chat_meta.py (G5) — nunca chama a Meta de verdade."""
import io
import json
import urllib.error
import urllib.request

import mod_chat
from database import ConversaMensagem, EnvioExterno, Projeto


def _login(f, who):
    c = f()
    c.login(who, "senha123")
    assert c.cookie
    return c


def _conversa_com_externo(app_db, seed, titulo):
    db = app_db.get_session()
    try:
        crid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, titulo, [], exige_dois=False)
        mod_chat.adicionar_externo(db, conv, "Cliente Externo", telefone="11912345678",
                                   meio="whatsapp", criado_por_id=crid)
        db.commit()
        return conv.id
    finally:
        db.close()


# O HttpClient de teste (conftest.py) TAMBÉM usa urllib.request.urlopen pra falar com o
# servidor local de verdade — mockar sem filtrar por host quebraria o próprio login/POST do
# teste. Só intercepta a chamada pra Meta (graph.facebook.com); tudo o mais vai pro urlopen real.
_urlopen_real = urllib.request.urlopen


def _mock_meta_falha(monkeypatch, codigo=None, mensagem="recusado"):
    def _boom(req, timeout=15):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "graph.facebook.com" not in url:
            return _urlopen_real(req, timeout=timeout)
        err = {"message": mensagem}
        if codigo is not None:
            err["code"] = codigo
        raise urllib.error.HTTPError(url, 400, "Bad Request", {},
                                     io.BytesIO(json.dumps({"error": err}).encode()))
    monkeypatch.setattr(urllib.request, "urlopen", _boom)


def _mock_meta_sucesso(monkeypatch, wamid="wamid.TESTE123"):
    def _ok(req, timeout=15):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if "graph.facebook.com" not in url:
            return _urlopen_real(req, timeout=timeout)
        class _R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _R(json.dumps({"messages": [{"id": wamid}]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", _ok)


def _configurar_whatsapp(monkeypatch):
    monkeypatch.setenv("ORIZON_WA_TOKEN", "token-teste")
    monkeypatch.setenv("ORIZON_WA_PHONE_ID", "123456")


# ── Call site 2/3 — POST /api/comunicacao/conversas/<id>/mensagens ──────────────────────────

def test_envio_recusado_pela_meta_mensagem_persiste_e_serializacao_diz_que_falhou(
        http_client_factory, app_db, seed, monkeypatch):
    _configurar_whatsapp(monkeypatch)
    _mock_meta_falha(monkeypatch, codigo=131026, mensagem="Recipient number not on WhatsApp")
    cid = _conversa_com_externo(app_db, seed, "Lead — Recusa Meta")
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "Oi!"})
    assert st == 201 and body["ok"], body
    assert body["mensagem"]["entrega_estado"] == "falhou"
    assert "Recipient number not on WhatsApp" in (body["mensagem"]["entrega_motivo"] or "")

    # a mensagem interna PERSISTIU — o ponto do Conserto 1 é não perder informação, não estourar
    db = app_db.get_session()
    try:
        msg = db.query(ConversaMensagem).filter_by(conversa_id=cid, corpo="Oi!").first()
        assert msg is not None
        env = db.query(EnvioExterno).filter_by(mensagem_id=msg.id, direcao="saida").first()
        assert env is not None and env.status == "falhou"
    finally:
        db.close()


def test_codigo_131047_mostra_texto_proprio_de_janela_fechada(
        http_client_factory, app_db, seed, monkeypatch):
    _configurar_whatsapp(monkeypatch)
    _mock_meta_falha(monkeypatch, codigo=131047,
                     mensagem="Message failed to send because more than 24 hours have passed")
    cid = _conversa_com_externo(app_db, seed, "Lead — Janela Fechada")
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "Oi!"})
    assert st == 201 and body["ok"]
    assert body["mensagem"]["entrega_estado"] == "falhou"
    motivo = body["mensagem"]["entrega_motivo"] or ""
    assert "Janela de 24h fechada" in motivo
    assert "outro canal" in motivo
    # texto PRÓPRIO — não o texto cru da Meta (esse é o ponto: o mais comum merece tradução)
    assert "more than 24 hours" not in motivo


def test_envio_bem_sucedido_nao_muda_bolha_normal(http_client_factory, app_db, seed, monkeypatch):
    _configurar_whatsapp(monkeypatch)
    _mock_meta_sucesso(monkeypatch)
    cid = _conversa_com_externo(app_db, seed, "Lead — Envio OK")
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "Oi!"})
    assert st == 201 and body["ok"]
    assert body["mensagem"]["entrega_estado"] == "entregue"
    assert body["mensagem"]["entrega_motivo"] is None


def test_mensagem_sem_ponte_externa_nao_se_aplica(http_client_factory, app_db, seed):
    """Chat Interno (sem participante externo) — não regride: entrega 'nao_se_aplica', não
    'falhou' por engano."""
    db = app_db.get_session()
    try:
        crid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], crid, "Interno — sem externo", [],
                                    exige_dois=False)
        db.commit()
        cid = conv.id
    finally:
        db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/comunicacao/conversas/%d/mensagens" % cid, {"corpo": "so a equipe"})
    assert st == 201 and body["ok"]
    assert body["mensagem"]["entrega_estado"] == "nao_se_aplica"
    assert body["mensagem"]["entrega_motivo"] is None


# ── Call site 1/3 — POST /api/comunicacao/conversas/<id>/anexos ─────────────────────────────

def test_call_site_anexos_recusado_pela_meta(http_client_factory, app_db, seed, monkeypatch):
    _configurar_whatsapp(monkeypatch)
    _mock_meta_falha(monkeypatch, mensagem="Anexo recusado")
    cid = _conversa_com_externo(app_db, seed, "Lead — Anexo Recusado")
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post_multipart("/api/comunicacao/conversas/%d/anexos" % cid,
                                {"arquivo": ("nota.txt", b"conteudo")}, {"corpo": "segue anexo"})
    assert st == 201 and body["ok"], body
    assert body["mensagem"]["entrega_estado"] == "falhou"
    assert "Anexo recusado" in (body["mensagem"]["entrega_motivo"] or "")


# ── Call site 3/3 — POST /api/projetos/<nome>/conversa/mensagens ────────────────────────────

def test_call_site_conversa_de_projeto_recusado_pela_meta(http_client_factory, app_db, seed,
                                                          monkeypatch):
    _configurar_whatsapp(monkeypatch)
    _mock_meta_falha(monkeypatch, mensagem="Projeto recusado")
    db = app_db.get_session()
    try:
        conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], seed["projeto_l1"])
        mod_chat.adicionar_externo(db, conv, "Cliente do Projeto", telefone="11987654321",
                                   meio="whatsapp")
        db.commit()
    finally:
        db.close()
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/projetos/%s/conversa/mensagens" % seed["projeto_l1"],
                      {"corpo": "Atualização do projeto"})
    assert st == 201 and body["ok"], body
    assert body["mensagem"]["entrega_estado"] == "falhou"
    assert "Projeto recusado" in (body["mensagem"]["entrega_motivo"] or "")
