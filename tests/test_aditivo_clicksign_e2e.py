# -*- coding: utf-8 -*-
"""ACHADO-69, Passo 3 (13/09) — Termo Aditivo como quarto caso do mecanismo comum de assinatura
ClickSign (mod_assinatura.py). Cobre o envio/verificação/reenvio, a reconciliação como 4º
documento do registro, o cancelamento de envelope na regeração (ACHADO-70), e — o aceite que
importa mais que todos os outros — a IGUALDADE CONTÁBIL entre os dois canais: a assinatura que
completa o Aditivo tem que constituir as MESMAS provisões (mesmas contas, mesmos valores),
não importa por qual canal ela chegou.

A igualdade é provada COMPARANDO OS LANÇAMENTOS reais de duas rodadas independentes (uma
concluída pelo canal interno via /aditivo/assinar, outra pelo canal ClickSign via
/aditivo/clicksign/enviar + reconciliação) — nunca por inspeção de código nem por "chamou a
mesma função"."""
import json
import sys, os
import hmac as _hmac
import hashlib as _hashlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from cryptography.fernet import Fernet
os.environ.setdefault("ORIZON_FISCAL_KEY", Fernet.generate_key().decode())

from tests.test_complemento_pe_e2e import _login, _setup, _upsert_compl
from tests.test_solicitacao_medicao_e2e import (
    _FakeClickSignClient, _instalar_config_clicksign, _post_raw)
from tests.test_achado70_cancelamento_envelope import (
    _FakeClickSignClient as _FakeCancelClient,
    _instalar_config_clicksign as _instalar_config_clicksign_cancel,
    _EmailEspiao)

_PLANO = json.dumps({"tipo": "avista", "entrada_valor": 1.0})


def _limpar_aditivos_e_complementos(app_db, nome):
    """`test_complemento_pe_e2e._setup` não limpa aditivos/complementos de rodadas anteriores
    (seus próprios testes nunca completam uma assinatura) — este arquivo completa, então cada
    teste precisa partir de um estado limpo, senão "Termo aditivo já assinado" de um teste
    anterior vaza pro próximo (mesmo projeto reaproveitado em todo o módulo, como em
    tests/test_conciliacao_pe_e2e.py)."""
    db = app_db.get_session()
    try:
        aditivos = [a.id for a in db.query(app_db.Aditivo).filter_by(projeto_nome=nome).all()]
        if aditivos:
            db.query(app_db.AditivoAssinatura).filter(
                app_db.AditivoAssinatura.aditivo_id.in_(aditivos)).delete(synchronize_session=False)
            db.query(app_db.Aditivo).filter(
                app_db.Aditivo.id.in_(aditivos)).delete(synchronize_session=False)
        compls = [o.id for o in db.query(app_db.Orcamento)
                    .filter_by(projeto_id=nome, complemento_pe=1).all()]
        if compls:
            db.query(app_db.Recebivel).filter(
                app_db.Recebivel.orcamento_id.in_(compls)).delete(synchronize_session=False)
            db.query(app_db.OrcamentoAmbiente).filter(
                app_db.OrcamentoAmbiente.orcamento_id.in_(compls)).delete(synchronize_session=False)
            db.query(app_db.Orcamento).filter(
                app_db.Orcamento.id.in_(compls)).delete(synchronize_session=False)
        db.query(app_db.Lancamento).filter(
            app_db.Lancamento.ref.like("prov:aditivo:%")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _lancamentos_normalizados(app_db, aditivo_id):
    """Lançamentos constituídos pela assinatura QUE COMPLETA este aditivo (ref
    'prov:aditivo:<id>:...'), agrupados por (conta_debito_id, conta_credito_id, origem) → valor —
    sem id/data/ref/historico, que legitimamente variam entre rodadas (ref carrega o id do
    aditivo; historico pode citar o número do documento)."""
    db = app_db.get_session()
    try:
        rows = (db.query(app_db.Lancamento)
                  .filter(app_db.Lancamento.ref.like("prov:aditivo:%d:%%" % aditivo_id)).all())
        out = {}
        for r in rows:
            chave = (r.conta_debito_id, r.conta_credito_id, r.origem)
            out[chave] = out.get(chave, 0.0) + r.valor
        return out
    finally:
        db.close()


def _assert_lancamentos_equivalentes(a, b):
    """Mesmas contas debitadas/creditadas, mesma origem, mesmo valor — tolerância de 1 centavo
    pra ruído de arredondamento entre duas cadeias de cálculo independentes (não é o MESMO
    número de ponto flutuante refeito duas vezes, são duas rodadas de negociação distintas que
    precisam chegar no mesmo resultado contábil)."""
    assert set(a) == set(b), (
        "contas/origem divergem entre os dois canais\ninterno:   %r\nclicksign: %r" % (a, b))
    for chave in a:
        assert abs(a[chave] - b[chave]) < 0.02, (
            "valor diverge em %r: interno=%.2f clicksign=%.2f" % (chave, a[chave], b[chave]))


def _gerar_aditivo(c, nome, novo=False):
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {"novo": True} if novo else {})
    assert st == 200 and body["ok"], body
    return body["aditivo"]["id"]


def test_assinatura_completa_via_clicksign_constitui_as_mesmas_provisoes_do_canal_interno(
        http_client_factory, seed, app_db, monkeypatch):
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")

    # ── Rodada 1: canal interno ──────────────────────────────────────────────────────────────
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    valor_r1 = body["orcamento"]["valor_total"]
    assert valor_r1 > 0

    aditivo_1 = _gerar_aditivo(c, nome)
    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "loja", "nome": "Rep Loja", "cpf": "111.444.777-35"})
    assert st == 200 and body["status"] == "assinado_loja", body
    st, body = c.post(f"/api/projetos/{nome}/aditivo/assinar",
                      {"parte": "cliente", "nome": "Cliente L1", "cpf": "222.333.444-05",
                       "forma_pagamento": _PLANO})
    assert st == 200 and body["status"] == "assinado", body

    lancs_interno = _lancamentos_normalizados(app_db, aditivo_1)
    assert lancs_interno, "assinatura completa do aditivo (canal interno) deveria constituir provisão(ões)"

    # ── Rodada 2: canal ClickSign, MESMA diferença negociada ──────────────────────────────────
    # ACHADO-21 6-b: a diferença À VISTA é calculada contra o que já foi CONTRATADO (contrato +
    # aditivos JÁ ASSINADOS) — reaplicar o MESMO XML de complemento daria diferença zero na 2ª
    # rodada (a 1ª já "consumiu" aquele incremento). Venda +4.000 reproduz o MESMO incremento
    # sobre a base agora deslocada (+4.000/0,9 = +4.444,44, idêntico à rodada 1 — mesma
    # aritmética que tests/test_complemento_pe_e2e.py mede pra este cenário). O CFO, medido:
    # NÃO segue essa mesma regra — a provisão de custo de fábrica sai de `orc_aj.cfo` direto,
    # sempre contra o CFO ORIGINAL do contrato (nunca contra os aditivos já assinados) — por
    # isso o cfo do XML fica o MESMO da rodada 1 (32.000), não somado de novo.
    _upsert_compl(app_db, nome, pid, venda=88000.0, cfo=32000.0)
    st, body = c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    assert st == 200 and body["ok"], body
    valor_r2 = body["orcamento"]["valor_total"]
    assert body["orcamento"]["id"] != None
    assert abs(valor_r2 - valor_r1) < 0.02, (
        "as duas rodadas partem do MESMO XML de complemento — a diferença negociada "
        "tem que ser idêntica, senão a comparação contábil não prova nada")

    aditivo_2 = _gerar_aditivo(c, nome, novo=True)
    assert aditivo_2 != aditivo_1

    _instalar_config_clicksign(app_db, seed["loja1_id"])
    import mod_clicksign
    fake = _FakeClickSignClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)

    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/enviar",
                      {"forma_pagamento": _PLANO, "email_loja": "loja@teste.com", "email_cliente": "cliente@teste.com"})
    assert st == 200 and body["ok"], body
    assert body["assinatura_canal"] == "clicksign"

    # Nesta versão da API ClickSign, `signed_at` do signer nunca vem preenchido — o sinal de
    # conclusão é o envelope fechado (mod_assinatura.reconciliar_clicksign, medido 2026-08-20).
    fake.fechar_envelope()
    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/verificar", {})
    assert st == 200 and body["ok"], body
    assert body["status"] == "assinado", body

    lancs_clicksign = _lancamentos_normalizados(app_db, aditivo_2)
    assert lancs_clicksign, "assinatura completa do aditivo (canal ClickSign) deveria constituir provisão(ões)"

    _assert_lancamentos_equivalentes(lancs_interno, lancs_clicksign)


def test_enviar_exige_forma_pagamento(http_client_factory, seed, app_db, monkeypatch):
    """ACHADO-21 6-c: sem outro instante síncrono na conclusão remota, a forma de pagamento
    tem que ser exigida JÁ no envio — não pode passar pro ClickSign e só falhar na reconciliação."""
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    _gerar_aditivo(c, nome)
    _instalar_config_clicksign(app_db, seed["loja1_id"])
    import mod_clicksign
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: _FakeClickSignClient())

    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/enviar", {})
    assert st == 400 and not body["ok"] and "forma de pagamento" in body["erro"].lower(), body


def test_enviar_recusa_plano_sem_recebivel_nenhum(http_client_factory, seed, app_db, monkeypatch):
    """ACHADO-24 (F2-1): mesma checagem do canal interno — um plano que não gera recebível
    nenhum não pode ser aceito só porque o canal mudou."""
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    _gerar_aditivo(c, nome)
    _instalar_config_clicksign(app_db, seed["loja1_id"])
    import mod_clicksign
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: _FakeClickSignClient())

    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/enviar",
                      {"forma_pagamento": json.dumps({"tipo": "avista", "entrada_valor": 0,
                                                       "parcelas": []})})
    assert st == 400 and not body["ok"] and "recebível" in body["erro"], body


def test_cpf_invalido_do_cliente_nao_completa_a_assinatura_via_clicksign(
        http_client_factory, seed, app_db, monkeypatch):
    """ACHADO-28 (F2-6): CPF inválido continua recusado nos dois canais — via reconciliação, a
    falha é por-parte (fail-soft: não trava os outros signatários), então a assinatura da parte
    com CPF ruim simplesmente NÃO se registra."""
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    aditivo_id = _gerar_aditivo(c, nome)

    db = app_db.get_session()
    cliente = db.query(app_db.Cliente).filter_by(loja_id=seed["loja1_id"]).first()
    cpf_original = cliente.cpf
    cliente.cpf = "111.111.111-11"    # dígito verificador inválido de propósito
    db.commit()
    db.close()

    try:
        _instalar_config_clicksign(app_db, seed["loja1_id"])
        import mod_clicksign
        fake = _FakeClickSignClient()
        monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)

        st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/enviar",
                          {"forma_pagamento": _PLANO, "email_loja": "loja@teste.com", "email_cliente": "cliente@teste.com"})
        assert st == 200 and body["ok"], body

        fake.fechar_envelope()
        st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/verificar", {})
        assert st == 200 and body["ok"], body
        assert body["status"] == "assinado_loja", (
            "CPF inválido do cliente não pode completar a assinatura: %r" % body)

        db = app_db.get_session()
        aditivo = db.get(app_db.Aditivo, aditivo_id)
        partes = {a.parte for a in aditivo.assinaturas}
        db.close()
        assert partes == {"loja"}
    finally:
        # não vazar o CPF inválido pros testes seguintes (Cliente L1 é reaproveitado no módulo).
        db = app_db.get_session()
        cliente = db.query(app_db.Cliente).filter_by(loja_id=seed["loja1_id"]).first()
        cliente.cpf = cpf_original
        db.commit()
        db.close()


def test_reenviar_convite_clicksign(http_client_factory, seed, app_db, monkeypatch):
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    _gerar_aditivo(c, nome)
    _instalar_config_clicksign(app_db, seed["loja1_id"])
    import mod_clicksign
    fake = _FakeClickSignClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/enviar",
                      {"forma_pagamento": _PLANO, "email_loja": "loja@teste.com", "email_cliente": "cliente@teste.com"})
    assert st == 200 and body["ok"], body

    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/reenviar", {})
    assert st == 200 and body["ok"], body


def test_webhook_reconcilia_aditivo_como_quarto_documento(
        http_client_factory, seed, app_db, monkeypatch):
    """O aditivo tem que estar alcançável pelo despacho por registro (mod_assinatura.documentos())
    que o webhook usa — não é um 4º bloco hardcoded, é o mesmo laço que já serve os outros três."""
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    aditivo_id = _gerar_aditivo(c, nome)
    webhook_secret = "whs-aditivo"
    _instalar_config_clicksign(app_db, seed["loja1_id"], webhook_secret=webhook_secret)
    import mod_clicksign
    fake = _FakeClickSignClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/enviar",
                      {"forma_pagamento": _PLANO, "email_loja": "loja@teste.com", "email_cliente": "cliente@teste.com"})
    assert st == 200 and body["ok"], body

    db = app_db.get_session()
    aditivo = db.get(app_db.Aditivo, aditivo_id)
    envelope_id = aditivo.clicksign_envelope_id
    db.close()

    fake.fechar_envelope()
    payload = json.dumps({"data": {"attributes": {"envelope_id": envelope_id}}}).encode()
    calc = "sha256=" + _hmac.new(webhook_secret.encode(), payload, _hashlib.sha256).hexdigest()
    st = _post_raw(c, "/webhooks/clicksign", payload,
                   {"Content-Type": "application/json", "Content-Hmac": calc})
    assert st == 200

    db = app_db.get_session()
    aditivo = db.get(app_db.Aditivo, aditivo_id)
    status_final = aditivo.status
    db.close()
    assert status_final == "assinado", (
        "o webhook tem que reconciliar o Termo Aditivo como qualquer outro documento do "
        "registro: %r" % status_final)


# ── ACHADO-70 aplicado ao Aditivo: regerar com envelope pendente não pode deixá-lo órfão ────────
# Mesmas três propriedades exigidas em tests/test_achado70_cancelamento_envelope.py (Aprovação
# do PE/Solicitação de Medição): o evento cancela o envelope; chamar sobre um documento nunca
# enviado não explode; ClickSign fora do ar não pode impedir a regeração em si.

def test_regeracao_do_aditivo_cancela_envelope_pendente(
        http_client_factory, seed, app_db, monkeypatch):
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    _gerar_aditivo(c, nome)

    _instalar_config_clicksign_cancel(app_db, seed["loja1_id"])
    import mod_clicksign
    fake = _FakeCancelClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    espiao = _EmailEspiao()
    import mod_chat_externo
    monkeypatch.setattr(mod_chat_externo, "enviar_email_simples", espiao)

    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/enviar",
                      {"forma_pagamento": _PLANO, "email_loja": "loja@teste.com",
                       "email_cliente": "cliente@teste.com"})
    assert st == 200 and body["ok"], body
    db = app_db.get_session()
    aditivo = db.query(app_db.Aditivo).filter_by(projeto_nome=nome).order_by(
        app_db.Aditivo.id.desc()).first()
    envelope_id = aditivo.clicksign_envelope_id
    db.close()
    assert envelope_id is not None

    # regera com o envelope AINDA pendente (nunca assinado) — mesmo achado independente medido
    # pra Aprovação do PE: só o guard de "já assinado" bloqueava, isto aqui passava batido.
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body

    assert fake.cancelados == [envelope_id]
    assert espiao.enviados, "regerar tem que avisar os signatários por e-mail"
    assert body["aditivo"]["assinatura_canal"] == "interno"

    db = app_db.get_session()
    aditivo = db.get(app_db.Aditivo, aditivo.id)
    assert aditivo.clicksign_envelope_id is None
    assert aditivo.clicksign_signatarios_json is None
    assert aditivo.clicksign_enviado_em is None
    db.close()


def test_regeracao_do_aditivo_sem_envelope_nao_explode(http_client_factory, seed, app_db):
    """Propriedade 2: a 1ª geração (nunca houve envelope) é o caminho comum — não pode explodir."""
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], body
    assert body["aditivo"]["assinatura_canal"] == "interno"


def test_regeracao_do_aditivo_acontece_mesmo_com_clicksign_fora_do_ar(
        http_client_factory, seed, app_db, monkeypatch):
    """Propriedade 3: ClickSign indisponível não pode impedir a regeração do documento em si."""
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    _gerar_aditivo(c, nome)

    _instalar_config_clicksign_cancel(app_db, seed["loja1_id"])
    import mod_clicksign
    fake = _FakeCancelClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/enviar",
                      {"forma_pagamento": _PLANO, "email_loja": "loja@teste.com",
                       "email_cliente": "cliente@teste.com"})
    assert st == 200 and body["ok"], body

    def _fora_do_ar(cfg):
        raise RuntimeError("ClickSign indisponível (simulado)")
    monkeypatch.setattr(mod_clicksign, "client_de", _fora_do_ar)

    st, body = c.post(f"/api/projetos/{nome}/aditivo", {})
    assert st == 200 and body["ok"], (
        "a regeração tem que acontecer mesmo com a ClickSign fora do ar: %r" % (body,))
    # o reset pro canal interno é incondicional, fora do try/except do cancelamento em si.
    assert body["aditivo"]["assinatura_canal"] == "interno"


def test_job_reconciliar_alcanca_o_aditivo_como_quarto_documento(
        http_client_factory, seed, app_db, monkeypatch):
    """Aceite 8 do ACHADO-69: o job `/internal/clicksign/reconciliar` cobre os QUATRO documentos
    via `mod_assinatura.documentos()` — este teste falha se o Aditivo ficar de fora do registro
    (regressão pra três blocos hardcoded, ou um `pendentes_para_reconciliar` que esqueça a
    classe). Cobertura complementar à do webhook (teste acima): rotas de entrada DIFERENTES,
    mesma garantia de fundo."""
    import urllib.request, urllib.error
    monkeypatch.setenv("ORIZON_INTERNAL_JOB_TOKEN", "job-secret-teste-aditivo")
    nome, pid, oid = _setup(app_db, seed)
    _limpar_aditivos_e_complementos(app_db, nome)
    _upsert_compl(app_db, nome, pid, venda=84000.0, cfo=32000.0)
    c = _login(http_client_factory, "dir_l1")
    c.post(f"/api/projetos/{nome}/pe/complemento/orcamento", {})
    aditivo_id = _gerar_aditivo(c, nome)

    _instalar_config_clicksign(app_db, seed["loja1_id"])
    import mod_clicksign
    fake = _FakeClickSignClient()
    monkeypatch.setattr(mod_clicksign, "client_de", lambda cfg: fake)
    st, body = c.post(f"/api/projetos/{nome}/aditivo/clicksign/enviar",
                      {"forma_pagamento": _PLANO, "email_loja": "loja@teste.com",
                       "email_cliente": "cliente@teste.com"})
    assert st == 200 and body["ok"], body

    from datetime import datetime as _dt, timedelta as _td
    db = app_db.get_session()
    aditivo = db.get(app_db.Aditivo, aditivo_id)
    aditivo.clicksign_enviado_em = _dt.utcnow() - _td(minutes=30)   # além da carência do job
    db.commit()
    db.close()
    fake.fechar_envelope()

    req = urllib.request.Request(c.base + "/internal/clicksign/reconciliar",
                                 data=b"", method="POST")
    req.add_header("X-Internal-Job-Token", "job-secret-teste-aditivo")
    resp = urllib.request.urlopen(req, timeout=5)
    assert resp.status == 200
    job_body = json.loads(resp.read())
    assert job_body["contratos_atualizados"] >= 1, job_body

    db = app_db.get_session()
    status_final = db.get(app_db.Aditivo, aditivo_id).status
    db.close()
    assert status_final == "assinado", (
        "o job tem que reconciliar o Termo Aditivo como qualquer outro documento do "
        "registro: %r" % status_final)
