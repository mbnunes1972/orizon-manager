# -*- coding: utf-8 -*-
"""ACHADO-70 (docs/db/ACHADOS_CONTABEIS.md) — cancelamento de envelope ligado para Aprovação do
PE e Solicitação de Medição, que até 13/09 deixavam um envelope ClickSign órfão quando a decisão
por trás dele mudava (reprovação da AF2; regeração do documento com envelope ainda pendente).

Três propriedades exigidas (não só "chamou a função"), pra cada evento ligado:
  1. o envelope é cancelado (e o signatário avisado) QUANDO o evento acontece;
  2. chamar duas vezes, ou sobre um documento nunca enviado, não explode;
  3. ClickSign fora do ar NÃO impede o evento de negócio (reprovar / regerar continuam ok)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
from cryptography.fernet import Fernet
os.environ["ORIZON_FISCAL_KEY"] = Fernet.generate_key().decode()


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


class _FakeClickSignClient:
    def __init__(self):
        self._seq = 0
        self.envelope_id = None
        self.envelope_status = "running"
        self.signatarios = {}
        self.cancelados = []

    def criar_envelope(self, nome):
        self._seq += 1
        self.envelope_id = "env-%d" % self._seq
        return self.envelope_id

    def adicionar_documento(self, envelope_id, pdf_bytes, nome_arquivo):
        self._seq += 1
        return "doc-%d" % self._seq

    def adicionar_signatario(self, envelope_id, email, nome, cpf=None):
        self._seq += 1
        signer_id = "signer-%d-%d" % (self._seq, len(self.signatarios) + 1)
        self.signatarios[signer_id] = {"email": email, "nome": nome, "signed_at": None}
        return signer_id

    def adicionar_requisito_assinatura(self, *a, **k):
        return {"ok": True}

    def adicionar_requisito_autenticacao(self, *a, **k):
        return {"ok": True}

    def ativar_envelope(self, envelope_id):
        return {"ok": True}

    def consultar_envelope(self, envelope_id):
        included = [{"type": "signers", "id": sid, "attributes": {
                        "email": info["email"], "name": info["nome"],
                        "signed_at": info["signed_at"]}}
                    for sid, info in self.signatarios.items()]
        return {"data": {"id": envelope_id, "attributes": {"status": self.envelope_status}}, "included": included}

    def cancelar_envelope(self, envelope_id):
        self.cancelados.append(envelope_id)
        return {"ok": True}


class _EmailEspiao:
    """Espiona mod_chat_externo.enviar_email_simples sem depender de SMTP de verdade."""
    def __init__(self):
        self.enviados = []

    def __call__(self, email, assunto, corpo):
        self.enviados.append((email, assunto, corpo))


def _instalar_config_clicksign(app_db, loja_id):
    from integracoes import cripto_segredos
    db = app_db.get_session()
    try:
        cfg = db.query(app_db.IntegracaoClickSign).filter_by(loja_id=loja_id).first()
        if cfg is None:
            cfg = app_db.IntegracaoClickSign(loja_id=loja_id, ambiente_ativo="sandbox")
            db.add(cfg)
        cfg.token_sandbox_enc = cripto_segredos.encrypt("tok-sandbox")
        cfg.webhook_secret_enc = cripto_segredos.encrypt("whs-teste")
        cfg.ambiente_ativo = "sandbox"
        db.commit()
    finally:
        db.close()


# ── Aprovação do PE ──────────────────────────────────────────────────────────────────────────

def _limpar_aprovacao_anterior(app_db, projeto_nome):
    db = app_db.get_session()
    try:
        for aprov in db.query(app_db.AprovacaoPE).filter_by(projeto_nome=projeto_nome).all():
            for a in list(aprov.assinaturas):
                db.delete(a)
            db.delete(aprov)
        db.commit()
    finally:
        db.close()


def _instalar_modelo_aprovacao_pe(app_db, loja_id):
    db = app_db.get_session()
    try:
        db.query(app_db.DocumentoModelo).filter_by(loja_id=loja_id, tipo="aprovacao_pe").delete()
        db.add(app_db.DocumentoModelo(loja_id=loja_id, tipo="aprovacao_pe", versao=1,
                                      corpo_md="Aprovação do projeto executivo.", ativo=1))
        db.commit()
    finally:
        db.close()


def _criar_aprovacao_enviada(app_db, seed, monkeypatch, tmp_path):
    """AprovacaoPE já no canal ClickSign — devolve (aprov_id, fake, envelope_id)."""
    import mod_clicksign, main
    db = app_db.get_session()
    try:
        pdf = tmp_path / "aprovacao_pe.pdf"
        pdf.write_bytes(b"%PDF-fake")
        aprov = app_db.AprovacaoPE(projeto_nome=seed["projeto_l1"], contrato_id=seed["contrato_l1_id"],
                                   loja_id=seed["loja1_id"], status="para_assinatura", pdf_path=str(pdf))
        db.add(aprov); db.commit()
        aid = aprov.id
    finally:
        db.close()
    fake = _FakeClickSignClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    db = app_db.get_session()
    try:
        aprov = db.get(app_db.AprovacaoPE, aid)
        main._enviar_aprovacao_pe_para_clicksign(
            db, aprov, None, email_loja="loja@teste.com", nome_loja="Loja 1",
            email_cliente="cliente@teste.com", nome_cliente="Cliente L1", cpf_cliente="11144477735")
        db.commit()
        envelope_id = aprov.clicksign_envelope_id
    finally:
        db.close()
    return aid, fake, envelope_id


def test_reprovacao_cancela_envelope_orfao_e_avisa(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Propriedade 1: o evento (reprovar a AF2) cancela o envelope e reseta o canal."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    aid, fake, envelope_id = _criar_aprovacao_enviada(app_db, seed, monkeypatch, tmp_path)
    espiao = _EmailEspiao()
    import mod_chat_externo
    monkeypatch.setattr(mod_chat_externo, "enviar_email_simples", espiao)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{seed['projeto_l1']}/ciclo/11d/reprovar",
                      {"login": "dir_l1", "senha": "senha123", "motivo": "ACHADO-70: teste"})
    assert st == 200 and body["ok"], body

    assert fake.cancelados == [envelope_id], "reprovar tem que cancelar o envelope na ClickSign"
    emails_avisados = {e[0] for e in espiao.enviados}
    assert emails_avisados == {"loja@teste.com", "cliente@teste.com"}, (
        "reprovar tem que avisar os dois signatários: %r" % espiao.enviados)

    db = app_db.get_session()
    try:
        aprov = db.get(app_db.AprovacaoPE, aid)
        assert aprov.assinatura_canal == "interno"
        assert aprov.clicksign_envelope_id is None
        assert aprov.clicksign_signatarios_json is None
        assert aprov.clicksign_enviado_em is None
    finally:
        db.close()


def test_reprovacao_sem_envelope_nao_explode(app_db, seed, http_client_factory):
    """Propriedade 2 (metade 'nunca enviado'): reprovar sem NENHUMA AprovacaoPE (ou uma no canal
    interno) não pode levantar nada — hoje isto já era assim (reprovar nunca olhava a linha),
    a entrega não pode ter mudado isso."""
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{seed['projeto_l1']}/ciclo/11d/reprovar",
                      {"login": "dir_l1", "senha": "senha123", "motivo": "sem aprovacao alguma"})
    assert st == 200 and body["ok"], body


def test_cancelar_chamado_duas_vezes_nao_explode(app_db, seed, monkeypatch, tmp_path):
    """Propriedade 2 (metade 'já cancelado'): chamar a função de cancelamento duas vezes seguidas
    sobre o MESMO objeto (envelope já cancelado da primeira vez) não pode levantar nada — direto
    na função, sem depender de o call site já resetar o canal antes da 2ª chamada."""
    import mod_clicksign, main
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    aid, fake, envelope_id = _criar_aprovacao_enviada(app_db, seed, monkeypatch, tmp_path)
    db = app_db.get_session()
    try:
        aprov = db.get(app_db.AprovacaoPE, aid)
        main._notificar_signatarios_clicksign_cancelamento_aprovacao_pe(db, aprov, lid, "em_revisao")
        main._notificar_signatarios_clicksign_cancelamento_aprovacao_pe(db, aprov, lid, "em_revisao")
    finally:
        db.close()
    assert fake.cancelados == [envelope_id, envelope_id]   # chamou 2x, nenhuma explodiu


def test_reprovacao_acontece_mesmo_com_clicksign_fora_do_ar(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Propriedade 3: ClickSign indisponível não pode impedir a reprovação em si."""
    import mod_clicksign
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    aid, fake, envelope_id = _criar_aprovacao_enviada(app_db, seed, monkeypatch, tmp_path)

    def _fora_do_ar(cfg):
        raise RuntimeError("ClickSign indisponível (simulado)")
    monkeypatch.setattr(mod_clicksign, "client_de", _fora_do_ar)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{seed['projeto_l1']}/ciclo/11d/reprovar",
                      {"login": "dir_l1", "senha": "senha123", "motivo": "fail-soft ACHADO-70"})
    assert st == 200 and body["ok"], body

    db = app_db.get_session()
    try:
        et = db.query(app_db.CicloEtapa).filter_by(
            projeto_nome=seed["projeto_l1"], etapa_codigo="11d").first()
        assert et is not None and et.status == "reprovado", (
            "a reprovação tem que acontecer mesmo com a ClickSign fora do ar")
    finally:
        db.close()


def test_regeracao_da_aprovacao_pe_cancela_envelope_pendente(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Achado independente da reprovação: regerar o PDF com um envelope ainda pendente (nunca
    assinado) deixava esse envelope órfão — a rota só bloqueava regerar um JÁ assinado."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_aprovacao_anterior(app_db, seed["projeto_l1"])
    _instalar_modelo_aprovacao_pe(app_db, lid)
    aid, fake, envelope_id = _criar_aprovacao_enviada(app_db, seed, monkeypatch, tmp_path)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{seed['projeto_l1']}/aprovacao-pe", {})
    assert st == 200 and body["ok"], body

    assert fake.cancelados == [envelope_id]
    assert body["aprovacao"]["assinatura_canal"] == "interno"


# ── Solicitação de Medição ───────────────────────────────────────────────────────────────────

def _limpar_solicitacao_anterior(app_db, projeto_nome):
    db = app_db.get_session()
    try:
        for sol in db.query(app_db.SolicitacaoMedicao).filter_by(projeto_nome=projeto_nome).all():
            for a in list(sol.assinaturas):
                db.delete(a)
            db.delete(sol)
        db.commit()
    finally:
        db.close()


def _instalar_modelo_solicitacao(app_db, loja_id):
    db = app_db.get_session()
    try:
        db.query(app_db.DocumentoModelo).filter_by(loja_id=loja_id, tipo="solicitacao_medicao").delete()
        db.add(app_db.DocumentoModelo(loja_id=loja_id, tipo="solicitacao_medicao", versao=1,
                                      corpo_md="Solicito a medição: [AMBIENTES_MEDICAO]", ativo=1))
        db.commit()
    finally:
        db.close()


def _preparar_contrato_assinado(app_db, seed):
    db = app_db.get_session()
    try:
        ct = db.get(app_db.Contrato, seed["contrato_l1_id"])
        ct.status = "assinado"
        db.commit()
    finally:
        db.close()


def _criar_solicitacao_enviada(app_db, seed, monkeypatch, tmp_path):
    import mod_clicksign, main
    db = app_db.get_session()
    try:
        pdf = tmp_path / "solicitacao_medicao.pdf"
        pdf.write_bytes(b"%PDF-fake")
        sol = app_db.SolicitacaoMedicao(projeto_nome=seed["projeto_l1"], loja_id=seed["loja1_id"],
                                        status="para_assinatura", pdf_path=str(pdf))
        db.add(sol); db.commit()
        sid = sol.id
    finally:
        db.close()
    fake = _FakeClickSignClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    db = app_db.get_session()
    try:
        sol = db.get(app_db.SolicitacaoMedicao, sid)
        main._enviar_solicitacao_medicao_para_clicksign(
            db, sol, None, email_loja="loja@teste.com", nome_loja="Loja 1",
            email_cliente="cliente@teste.com", nome_cliente="Cliente L1", cpf_cliente="11144477735")
        db.commit()
        envelope_id = sol.clicksign_envelope_id
    finally:
        db.close()
    return sid, fake, envelope_id


def test_regeracao_da_solicitacao_medicao_cancela_envelope_pendente(app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Propriedade 1 pra Solicitação de Medição: sem verbo de reprovação próprio, o único evento
    disponível é a regeração — mesma razão da Aprovação do PE."""
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    _instalar_modelo_solicitacao(app_db, lid)
    _preparar_contrato_assinado(app_db, seed)
    sid, fake, envelope_id = _criar_solicitacao_enviada(app_db, seed, monkeypatch, tmp_path)
    espiao = _EmailEspiao()
    import mod_chat_externo
    monkeypatch.setattr(mod_chat_externo, "enviar_email_simples", espiao)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/gerar", {})
    assert st == 200 and body["ok"], body

    assert fake.cancelados == [envelope_id]
    assert espiao.enviados, "regerar tem que avisar o signatário por e-mail"
    assert body["solicitacao"]["assinatura_canal"] == "interno"


def test_regeracao_da_solicitacao_sem_envelope_nao_explode(app_db, seed, http_client_factory):
    """Propriedade 2: 1ª geração (nunca houve envelope) não pode explodir — é o caminho comum."""
    lid = seed["loja1_id"]
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    _instalar_modelo_solicitacao(app_db, lid)
    _preparar_contrato_assinado(app_db, seed)
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/gerar", {})
    assert st == 200 and body["ok"], body
    assert body["solicitacao"]["assinatura_canal"] == "interno"


def test_regeracao_da_solicitacao_acontece_mesmo_com_clicksign_fora_do_ar(
        app_db, seed, monkeypatch, http_client_factory, tmp_path):
    """Propriedade 3 pra Solicitação de Medição: ClickSign fora do ar não pode impedir a
    regeração do documento."""
    import mod_clicksign
    lid = seed["loja1_id"]
    _instalar_config_clicksign(app_db, lid)
    _limpar_solicitacao_anterior(app_db, seed["projeto_l1"])
    _instalar_modelo_solicitacao(app_db, lid)
    _preparar_contrato_assinado(app_db, seed)
    sid, fake, envelope_id = _criar_solicitacao_enviada(app_db, seed, monkeypatch, tmp_path)

    def _fora_do_ar(cfg):
        raise RuntimeError("ClickSign indisponível (simulado)")
    monkeypatch.setattr(mod_clicksign, "client_de", _fora_do_ar)

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/projetos/{seed['projeto_l1']}/medicao/solicitacao/gerar", {})
    assert st == 200 and body["ok"], (
        "a regeração tem que acontecer mesmo com a ClickSign fora do ar: %r" % (body,))
    # o canal ainda reseta pra "interno" mesmo com a ClickSign indisponível (o reset é
    # incondicional, fora do try/except do cancelamento em si).
    assert body["solicitacao"]["assinatura_canal"] == "interno"
