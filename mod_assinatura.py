# -*- coding: utf-8 -*-
"""mod_assinatura.py — ACHADO-69 (docs/db/TAREFA_ACHADO69_ASSINATURA_UNIFICADA.md), Passo 1.

Registro único dos documentos que oferecem assinatura por ClickSign — hoje: Contrato, Aprovação
do PE e Solicitação de medição. `main.py` tinha essa lista repetida em dois lugares (o webhook e
o job `/internal/clicksign/reconciliar`), cada um com um bloco quase idêntico por classe — a
duplicação que o pacote nomeou pra unificar.

Passo 1 NÃO muda comportamento nenhum: cada entrada aqui só referencia as funções
`_enviar_*_para_clicksign`/`_reconciliar_*_clicksign` que já existiam em `main.py`, intocadas —
o que muda é o DESPACHO (qual classe, para qual envelope; quais linhas entram na varredura do
job), nunca a lógica de enviar/reconciliar em si. `main.py` popula o registro (nunca o contrário
— `mod_assinatura` não importa `main`, pra não criar import circular); só ele conhece as funções
concretas de cada documento.

Cancelamento de envelope (ACHADO-70, `docs/db/ACHADOS_CONTABEIS.md`): até 13/09, só o Contrato
tinha. Ligado nos outros dois em commit PRÓPRIO (depois das três migrações do Passo 2, suíte
verde em cada uma) — é a primeira mudança de COMPORTAMENTO deste trabalho, deliberadamente
separada da extração de mecanismo. Ver `cancelar_e_notificar_clicksign` abaixo (o núcleo comum,
generalizado a partir de `_notificar_signatarios_clicksign_cancelamento`, que só existia pro
Contrato e tinha o texto do e-mail hardcoded) e os três wrappers em `main.py`
(`_notificar_signatarios_clicksign_cancelamento*`) para saber QUANDO cada documento dispara."""

import json
import logging
import os
from collections import namedtuple
from datetime import datetime

from database import Loja

RegistroDocumento = namedtuple("RegistroDocumento", [
    "nome",          # rótulo curto (logs/erros) — "contrato", "aprovacao_pe", "solicitacao_medicao"
    "modelo",        # classe SQLAlchemy (ex.: Contrato) — precisa ter assinatura_canal, status,
                     # clicksign_envelope_id, clicksign_enviado_em com esses nomes exatos
    "enviar",        # função(db, doc, cfg, **kwargs) -> None (não commita — igual às atuais)
    "reconciliar",   # função(db, doc, cfg) -> None (não commita — igual às atuais)
    "cancelar",      # função(db, doc, loja_id, status_final) -> None, ou None (não suportado hoje)
])

STATUS_PENDENTES_CLICKSIGN = ("para_assinatura", "assinado_loja", "assinado_cliente")

_registro = []


def registrar(nome, modelo, enviar, reconciliar, cancelar=None):
    """Chamado por `main.py` (nunca por este módulo) — uma vez por classe, no import."""
    _registro.append(RegistroDocumento(nome, modelo, enviar, reconciliar, cancelar))


def documentos():
    """Cópia da lista — iterar à vontade, nunca mutar o registro por fora de `registrar`."""
    return list(_registro)


def registro_de(modelo):
    """RegistroDocumento cujo `modelo` é exatamente esta classe (ex.: `Contrato`), ou `None` se
    nenhuma classe registrada bater — usado por quem precisa da capacidade de um documento
    específico (ex.: cancelamento) sem repetir a referência direta à função concreta."""
    for reg in _registro:
        if reg.modelo is modelo:
            return reg
    return None


def achar_por_envelope(db, envelope_id):
    """(doc, registro) do primeiro documento conhecido com este `clicksign_envelope_id`, na
    ordem de registro (hoje: Contrato, Aprovação do PE, Solicitação de medição — mesma ordem que
    o webhook original consultava em série). `(None, None)` se nenhuma classe conhecida bater —
    o chamador decide o que fazer (o webhook de hoje faz ack sem processar)."""
    for reg in _registro:
        doc = db.query(reg.modelo).filter_by(clicksign_envelope_id=envelope_id).first()
        if doc is not None:
            return doc, reg
    return None, None


def pendentes_para_reconciliar(db, reg, limite):
    """Linhas de `reg.modelo` prontas pra reconciliação: canal ClickSign, status ainda não
    terminal, enviadas há mais que a carência (`limite` = agora − carência, calculado pelo
    chamador). Mesmo filtro que os três blocos de `/internal/clicksign/reconciliar` já faziam,
    um por um."""
    m = reg.modelo
    return (db.query(m)
            .filter(m.assinatura_canal == "clicksign",
                    m.status.in_(STATUS_PENDENTES_CLICKSIGN),
                    m.clicksign_enviado_em.isnot(None),
                    m.clicksign_enviado_em <= limite)
            .all())


# ── ACHADO-69 Passo 2 — o núcleo comum de envio/reconciliação ──────────────────────────────────
# Extraído de `_enviar_contrato_para_clicksign`/`_enviar_solicitacao_medicao_para_clicksign`
# (main.py), que eram idênticas a menos de: mensagem de erro de PDF ausente, nome do arquivo,
# título do envelope, e suporte a testemunhas (só Contrato). Cada documento migra chamando ISTO
# com seus próprios textos/flags — a função em si nunca muda mais depois que um documento migra.
# `_enviar_*_para_clicksign`/`_reconciliar_*_clicksign` em main.py continuam existindo como os
# nomes que o registro (mod_assinatura.registrar) e as rotas HTTP já conhecem — por documento
# migrado, viram wrappers finos que só preenchem os textos e chamam as funções abaixo.

def enviar_para_clicksign(doc, cfg, *, titulo, nome_arquivo, pdf_path, erro_pdf_ausente,
                          email_loja, nome_loja, email_cliente, nome_cliente, cpf_cliente,
                          testemunhas=None):
    """Cria envelope, sobe o PDF, cadastra signatários (loja, cliente, e testemunhas opcionais
    com e-mail — item de `testemunhas` sem e-mail é ignorado, sem erro), liga cada um ao
    documento (requisito de assinatura + de autenticação), ativa o envelope (dispara os
    convites). Grava as 4 colunas de rastreio em `doc` — NÃO commita, o chamador decide.
    `pdf_path`: o caminho já lido do documento (cada modelo usa `doc.pdf_path`, mas quem chama
    decide — evita este módulo precisar saber o nome do atributo)."""
    if not email_loja or not email_cliente:
        raise ValueError("E-mail da loja e do cliente são obrigatórios para assinatura eletrônica (ClickSign).")
    if not pdf_path or not os.path.exists(pdf_path):
        raise ValueError(erro_pdf_ausente)
    import mod_clicksign
    cli = mod_clicksign.client_de(cfg)
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    envelope_id = cli.criar_envelope(titulo)
    doc_id = cli.adicionar_documento(envelope_id, pdf_bytes, nome_arquivo)
    sig_loja_id    = cli.adicionar_signatario(envelope_id, email_loja, nome_loja)
    sig_cliente_id = cli.adicionar_signatario(envelope_id, email_cliente, nome_cliente, cpf=cpf_cliente)
    signatarios = {
        "loja":    {"signer_id": sig_loja_id,    "email": email_loja,    "nome": nome_loja},
        "cliente": {"signer_id": sig_cliente_id, "email": email_cliente, "nome": nome_cliente,
                    "cpf": cpf_cliente},
    }
    signer_ids = [sig_loja_id, sig_cliente_id]
    for i, t in enumerate(testemunhas or [], start=1):
        email_t = (t.get("email") or "").strip()
        if not email_t:
            continue
        sid = cli.adicionar_signatario(envelope_id, email_t, t.get("nome") or "", cpf=t.get("cpf") or None)
        signer_ids.append(sid)
        signatarios["testemunha%d" % i] = {"signer_id": sid, "email": email_t,
                                           "nome": t.get("nome") or "", "cpf": t.get("cpf") or ""}
    for signer_id in signer_ids:
        cli.adicionar_requisito_assinatura(envelope_id, doc_id, signer_id)
        cli.adicionar_requisito_autenticacao(envelope_id, doc_id, signer_id)
    cli.ativar_envelope(envelope_id)
    doc.clicksign_envelope_id = envelope_id
    doc.clicksign_signatarios_json = json.dumps(signatarios, ensure_ascii=False)
    doc.assinatura_canal     = "clicksign"
    doc.clicksign_enviado_em = datetime.utcnow()


def reconciliar_clicksign(db, doc, cfg, *, nome_doc, registrar_assinatura):
    """Reconsulta a ClickSign com credenciais próprias (nunca confia no payload do webhook) e
    registra, via `registrar_assinatura` (idempotente do lado de quem a fornece), a assinatura
    de quem já assinou e ainda não está registrada localmente. Envelope fechado (`status:
    "closed"`) é o sinal de conclusão — `signed_at` do signer nunca vem preenchido nesta versão
    da API ClickSign (achado do usuário 2026-08-20). `registrar_assinatura`: função(db, doc,
    parte, nome, cpf, ip_origem) — quem chama já fecha os parâmetros extras que só o próprio
    documento sabe (ex.: `loja_id` do Contrato) antes de passar pra cá. CPF inválido vindo de
    fora não trava a reconciliação dos outros signatários — só loga (ACHADO-28)."""
    import mod_clicksign
    cli = mod_clicksign.client_de(cfg)
    dados = cli.consultar_envelope(doc.clicksign_envelope_id)
    envelope_fechado = (dados.get("data") or {}).get("attributes", {}).get("status") == "closed"
    incluidos = dados.get("included") or []
    signers = {s.get("id"): s.get("attributes", {}) for s in incluidos if s.get("type") == "signers"}
    signatarios = json.loads(doc.clicksign_signatarios_json or "{}")
    for parte, info in signatarios.items():
        attrs = signers.get(info.get("signer_id")) or {}
        if not (attrs.get("signed_at") or envelope_fechado):
            continue
        try:
            registrar_assinatura(db, doc, parte, info.get("nome") or "", info.get("cpf") or "",
                                  attrs.get("last_seen_ip") or "")
        except ValueError as e:
            logging.getLogger(__name__).warning(
                "ClickSign %s %s, parte %r: %s", nome_doc, doc.id, parte, e)
    return doc.status


# ── ACHADO-70 (docs/db/ACHADOS_CONTABEIS.md) — cancelamento de envelope, extraído de
# `_notificar_signatarios_clicksign_cancelamento` (main.py), que só existia pro Contrato ────────
# Medido antes de generalizar (13/09): a função original tinha o texto do e-mail HARDCODED
# ("O contrato do projeto...") — reusar verbatim pra Aprovação do PE/Solicitação de medição
# mandaria e-mail ERRADO ("contrato" quando o documento é outro). Por isso os textos viram
# parâmetro — mesmo padrão de `enviar_para_clicksign` (`titulo`/`nome_arquivo`/`erro_pdf_ausente`
# já eram parâmetro por razão idêntica).

def cancelar_e_notificar_clicksign(db, doc, loja_id, status_final, *,
                                   assunto_cancelado, corpo_cancelado,
                                   assunto_revisao, corpo_revisao):
    """Avisa (e-mail) quem já tinha recebido `doc` pra assinatura eletrônica quando ele é
    cancelado ou devolvido pra revisão ANTES de assinar, e tenta (best-effort) cancelar o
    envelope na própria ClickSign. `corpo_cancelado`/`corpo_revisao`: template com UM `%s`
    (recebe `doc.projeto_nome`).

    FAIL-SOFT por construção, medido no Contrato antes de generalizar: e-mail de cada
    signatário e a tentativa de cancelar o envelope são cada um seu PRÓPRIO try/except — nenhuma
    falha aqui pode impedir o evento de negócio que motivou a chamada (reprovação, regeração,
    cancelamento) — que por isso precisa já estar committado ANTES desta função rodar, nunca
    depois. "Não pode explodir" (não é o mesmo que "livre de efeito colateral duplicado"):
    chamar sobre um documento nunca enviado (`clicksign_signatarios_json`/`clicksign_envelope_id`
    vazios) é no-op silencioso nos blocos correspondentes; chamar duas vezes sobre o MESMO
    envelope já avisado reenviaria os e-mails (mesma característica que o Contrato já tinha,
    preservada aqui — o Contrato nunca dependeu de dedupe, os chamadores é que evitam repetir)."""
    import mod_chat_externo as _mce
    try:
        signatarios = json.loads(doc.clicksign_signatarios_json or "{}")
    except Exception:
        signatarios = {}
    if signatarios:
        if status_final == "cancelado":
            assunto, corpo = assunto_cancelado, corpo_cancelado % doc.projeto_nome
        else:
            assunto, corpo = assunto_revisao, corpo_revisao % doc.projeto_nome
        for parte, info in signatarios.items():
            email = (info.get("email") or "").strip()
            if not email:
                continue
            try:
                _mce.enviar_email_simples(email, assunto, corpo)
            except Exception as _e:
                logging.getLogger(__name__).warning(
                    "e-mail de %s (ClickSign) p/ %s <%s> (doc=%s) falhou: %s",
                    status_final, parte, email, doc.id, _e)
    if doc.clicksign_envelope_id:
        try:
            import mod_clicksign
            loja_obj = db.get(Loja, loja_id)
            cfg = mod_clicksign.resolver_config(db, loja_obj) if loja_obj else None
            if cfg is not None:
                mod_clicksign.client_de(cfg).cancelar_envelope(doc.clicksign_envelope_id)
        except Exception as _e:
            logging.getLogger(__name__).warning(
                "cancelamento do envelope ClickSign (doc=%s, envelope=%s) falhou: %s",
                doc.id, doc.clicksign_envelope_id, _e)
