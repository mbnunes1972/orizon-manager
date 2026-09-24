# -*- coding: utf-8 -*-
"""mod_chat_externo.py — canais externos do chat (Fatias 6-7: e-mail e WhatsApp).

Spec: docs/superpowers/specs/_geral/2026-07-25-…-design.md (seção 6c/6d).

FUNDAÇÃO construída e testada agora: modelo EnvioExterno, resolução de destino pelo seletor
(decisão 19), roteamento de resposta de entrada (decisão 14) e o CONFIG-GATING dos transportes
(mesmo padrão da chave do modo privado). Os TRANSPORTES AO VIVO (SMTP/Meta Cloud API) são gated
por credencial de ambiente — sem elas, o envio nasce 'pendente_config' e a rede não é tocada.
Ativar é ação de deploy do usuário (variáveis por ambiente), fora deste código.
"""
import json
import os
import re
from datetime import datetime, timedelta

from database import (EnvioExterno, Conversa, ConversaMensagem, ConversaParticipante,
                      ConversaParticipanteExterno, Cliente, Parceiro, Fornecedor, Usuario,
                      UsuarioPresenca, TriagemEntrada, Loja, Projeto)

MEIOS = ("email", "whatsapp")
# Canais externos (segmentos) — 'interno' NÃO é externo.
CANAIS_EXTERNOS = ("comercial", "financeiro", "logistica", "suporte_tecnico", "sac",
                   "compras", "parceiros")

_ENV_POR_MEIO = {
    "email":    ("ORIZON_SMTP_HOST", "ORIZON_SMTP_PORT", "ORIZON_SMTP_USER",
                 "ORIZON_SMTP_PASS", "ORIZON_SMTP_FROM"),
    "whatsapp": ("ORIZON_WA_TOKEN", "ORIZON_WA_PHONE_ID"),
}


def meio_configurado(meio):
    """True se TODAS as variáveis de ambiente do transporte estão presentes. Sem elas, o envio
    ao vivo é impossível → o envio fica 'pendente_config' (nunca um 'enviado' fantasma)."""
    envs = _ENV_POR_MEIO.get(meio)
    if not envs:
        return False
    return all((os.environ.get(e) or "").strip() for e in envs)


# ── resolução de destino (decisão 19: seletor interno/parceiro/cliente/avulso) ───────────────

def _digitos(s):
    return re.sub(r"\D", "", s or "")


def resolver_destino(db, meio, destinatario_tipo, destinatario_id, avulso):
    """Retorna (destino, erro). `avulso` (número/e-mail digitado à mão) vence o cadastro. Para
    cadastro, lê do vivo (decisão 12): Cliente/Parceiro têm whatsapp+email; interno = Usuario
    (e-mail; WhatsApp de usuário interno não é padrão — erro claro se pedirem)."""
    if destinatario_tipo == "avulso":
        v = (avulso or "").strip()
        if not v:
            return None, "Informe o contato avulso (número ou e-mail)."
        if meio == "email" and "@" not in v:
            return None, "E-mail avulso inválido."
        if meio == "whatsapp" and len(_digitos(v)) < 10:
            return None, "Número de WhatsApp avulso inválido."
        return v, None
    obj = None
    if destinatario_tipo == "cliente":
        obj = db.get(Cliente, destinatario_id)
    elif destinatario_tipo == "parceiro":
        obj = db.get(Parceiro, destinatario_id)
    elif destinatario_tipo == "fornecedor":
        obj = db.get(Fornecedor, destinatario_id)   # RF-03: Compras fala com Fornecedor
    elif destinatario_tipo == "interno":
        obj = db.get(Usuario, destinatario_id)
    else:
        return None, "Tipo de destinatário inválido."
    if obj is None:
        return None, "Destinatário não encontrado."
    if meio == "email":
        v = (getattr(obj, "email", "") or "").strip()
        return (v, None) if v else (None, "%s sem e-mail no cadastro." % obj.nome)
    # whatsapp
    v = (getattr(obj, "whatsapp", "") or getattr(obj, "telefone", "") or "").strip()
    return (v, None) if v else (None, "%s sem WhatsApp no cadastro." % obj.nome)


# ── registro do envio (dispatch gated) ───────────────────────────────────────

def registrar_envio(db, mensagem, meio, canal, destinatario_tipo, destinatario_id, destino):
    """Cria o EnvioExterno de SAÍDA. Se o meio não está configurado, status 'pendente_config'
    (a rede não é tocada); configurado, 'enfileirado' (o disparo real é _despachar, isolado)."""
    status = "enfileirado" if meio_configurado(meio) else "pendente_config"
    env = EnvioExterno(mensagem_id=mensagem.id, meio=meio, direcao="saida", canal=canal,
                       destinatario_tipo=destinatario_tipo, destinatario_id=destinatario_id,
                       destino=destino, status=status)
    db.add(env)
    db.flush()
    return env


_CANAL_ROTULO = {"comercial": "Comercial", "financeiro": "Financeiro", "logistica": "Logística",
                 "suporte_tecnico": "Suporte Técnico", "sac": "SAC"}


def _env_por_canal(base, canal):
    """Override por canal (os 5 endereços/números são CONFIG, não código — spec Fatia 6):
    ORIZON_SMTP_FROM_FINANCEIRO, ORIZON_WA_PHONE_ID_SAC, etc.; fallback à base."""
    if canal:
        v = (os.environ.get("%s_%s" % (base, canal.upper())) or "").strip()
        if v:
            return v
    return (os.environ.get(base) or "").strip()


def _enviar_email(env, corpo):
    import smtplib
    from email.message import EmailMessage
    from email.utils import make_msgid
    host = (os.environ.get("ORIZON_SMTP_HOST") or "").strip()
    port = int((os.environ.get("ORIZON_SMTP_PORT") or "587").strip())
    user = (os.environ.get("ORIZON_SMTP_USER") or "").strip()
    pw   = (os.environ.get("ORIZON_SMTP_PASS") or "").strip()
    frm  = _env_por_canal("ORIZON_SMTP_FROM", env.canal)
    # Message-ID no domínio do remetente (não no hostname da máquina) — threading da decisão 14
    # + entregabilidade (filtros anti-spam olham o alinhamento do domínio do Message-ID).
    _dom = frm.split("@")[-1].strip() if "@" in (frm or "") else None
    msgid = make_msgid(domain=_dom) if _dom else make_msgid()
    msg = EmailMessage()
    msg["From"] = frm
    msg["To"] = env.destino
    msg["Subject"] = "[Orizon] %s — Projeto" % _CANAL_ROTULO.get(env.canal, "Comunicação")
    msg["Message-ID"] = msgid
    if env.id_externo_ref:                 # resposta encadeia no thread original
        msg["In-Reply-To"] = env.id_externo_ref
        msg["References"] = env.id_externo_ref
    msg.set_content(corpo or "")
    with smtplib.SMTP(host, port, timeout=15) as s:
        s.starttls()
        if user:
            s.login(user, pw)
        s.send_message(msg)
    return True, msgid, None


def enviar_email_simples(destinatario, assunto, corpo):
    """E-mail avulso (alerta operacional, não é conversa/documento) — reusa só a config SMTP
    (mesmas envs ORIZON_SMTP_*), sem o acoplamento de `_enviar_email` a um `EnvioExterno`/canal.
    Levanta a exceção pro chamador decidir (config-gated: se ORIZON_SMTP_HOST não está setado,
    levanta RuntimeError — o chamador deve capturar e tratar como fail-soft, nunca travar o
    fluxo principal por causa de e-mail)."""
    import smtplib
    from email.message import EmailMessage
    from email.utils import make_msgid
    host = (os.environ.get("ORIZON_SMTP_HOST") or "").strip()
    if not host:
        raise RuntimeError("SMTP não configurado (ORIZON_SMTP_HOST ausente)")
    port = int((os.environ.get("ORIZON_SMTP_PORT") or "587").strip())
    user = (os.environ.get("ORIZON_SMTP_USER") or "").strip()
    pw   = (os.environ.get("ORIZON_SMTP_PASS") or "").strip()
    frm  = (os.environ.get("ORIZON_SMTP_FROM") or "").strip()
    _dom = frm.split("@")[-1].strip() if "@" in (frm or "") else None
    msg = EmailMessage()
    msg["From"] = frm
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg["Message-ID"] = make_msgid(domain=_dom) if _dom else make_msgid()
    msg.set_content(corpo or "")
    with smtplib.SMTP(host, port, timeout=15) as s:
        s.starttls()
        if user:
            s.login(user, pw)
        s.send_message(msg)


def _erro_meta(he):
    """Extrai a mensagem REAL da Meta de um HTTPError (`error.message`/`error.code`) em vez do genérico
    'HTTP Error 400' — ex.: código 131047 = janela de 24h fechada, exige template (G5/RF-06)."""
    import json as _json
    try:
        d = _json.loads(he.read() or b"{}")
        err = d.get("error") or {}
        msg = (err.get("message") or "").strip()
        if msg:
            code = err.get("code")
            return "Meta %s: %s" % (code if code is not None else getattr(he, "code", "?"), msg)
    except Exception:
        pass
    return "Meta HTTP %s" % getattr(he, "code", "?")


def _enviar_whatsapp(env, corpo):
    import json as _json
    import urllib.request as _u
    import urllib.error as _ue
    token = (os.environ.get("ORIZON_WA_TOKEN") or "").strip()
    phone = _env_por_canal("ORIZON_WA_PHONE_ID", env.canal)
    url = "https://graph.facebook.com/v20.0/%s/messages" % phone
    payload = {"messaging_product": "whatsapp", "to": _digitos(env.destino),
               "type": "text", "text": {"body": corpo or ""}}
    req = _u.Request(url, data=_json.dumps(payload).encode("utf-8"), method="POST",
                     headers={"Authorization": "Bearer " + token,
                              "Content-Type": "application/json"})
    try:
        with _u.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read() or b"{}")
    except _ue.HTTPError as he:
        raise RuntimeError(_erro_meta(he))   # despachar captura e grava em EnvioExterno.erro
    wamid = ((data.get("messages") or [{}])[0]).get("id")
    return True, wamid, (None if wamid else "resposta da Meta sem id de mensagem")


def _render_template(corpo, valores):
    """Renderiza o corpo de um template ({{1}}..{{n}}) com os valores (dict 1-based — chaves int
    ou str — ou lista posicional). Validação BLOQUEANTE da spec 2026-08-04 §11 etapa 3: variável
    presente no corpo sem valor → ValueError apontando o campo pendente (nunca sai `{{n}}`
    literal). Retorna (texto_final, params_na_ordem)."""
    corpo = corpo or ""
    pos = sorted({int(m) for m in re.findall(r"\{\{(\d+)\}\}", corpo)})
    out, params = corpo, []
    for n in pos:
        v = None
        if isinstance(valores, dict):
            v = valores.get(n, valores.get(str(n)))
        elif isinstance(valores, (list, tuple)) and n <= len(valores):
            v = valores[n - 1]
        v = (str(v).strip() if v is not None else "")
        if not v:
            raise ValueError("Preencha o campo {{%d}} do modelo antes de enviar." % n)
        out = out.replace("{{%d}}" % n, v)
        params.append(v)
    return out, params


def _enviar_whatsapp_template(env, nome_meta, idioma, params):
    """Payload `"type":"template"` da Cloud API (spec 2026-08-04 §11 — fecha o gap G7 do plano de
    28/07): name + language + components/body com os parâmetros posicionais {{1}}..{{n}}. É o
    ÚNICO formato que a Meta aceita SEM janela de atendimento aberta."""
    import json as _json
    import urllib.request as _u
    import urllib.error as _ue
    token = (os.environ.get("ORIZON_WA_TOKEN") or "").strip()
    phone = _env_por_canal("ORIZON_WA_PHONE_ID", env.canal)
    url = "https://graph.facebook.com/v20.0/%s/messages" % phone
    tpl = {"name": nome_meta, "language": {"code": (idioma or "pt_BR")}}
    if params:
        tpl["components"] = [{"type": "body",
                              "parameters": [{"type": "text", "text": p} for p in params]}]
    payload = {"messaging_product": "whatsapp", "to": _digitos(env.destino),
               "type": "template", "template": tpl}
    req = _u.Request(url, data=_json.dumps(payload).encode("utf-8"), method="POST",
                     headers={"Authorization": "Bearer " + token,
                              "Content-Type": "application/json"})
    try:
        with _u.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read() or b"{}")
    except _ue.HTTPError as he:
        raise RuntimeError(_erro_meta(he))
    wamid = ((data.get("messages") or [{}])[0]).get("id")
    return True, wamid, (None if wamid else "resposta da Meta sem id de mensagem")


def despachar_template(env, template, params):
    """Disparo REAL de um envio por TEMPLATE — mesmo contrato de despachar: (ok, id_externo,
    erro), config-gated; exceção vira (False, None, erro)."""
    if not meio_configurado("whatsapp"):
        return False, None, "Transporte não configurado neste ambiente."
    try:
        return _enviar_whatsapp_template(env, template.nome_meta, template.idioma, params)
    except Exception as e:
        return False, None, str(e)


def enviar_template_conversa(db, conversa, usuario_id, template, valores,
                             destino=None, canal=None):
    """Envia um TEMPLATE aprovado ao contato externo da conversa (spec 2026-08-04 §11): renderiza
    {{n}} (validação bloqueante), grava a mensagem com o texto FINAL (histórico legível no chat),
    registra o EnvioExterno apontando o template e despacha (config-gated: sem credencial nasce
    'pendente_config'). Retorna (mensagem, envio). Não commita."""
    from . import core as _mc
    if (template.status or "") != "aprovado":
        raise ValueError("Só um template APROVADO pela Meta pode ser enviado fora da janela.")
    corpo, params = _render_template(template.corpo, valores)
    canal = canal or template.segmento or "comercial"
    if destino is None:
        e = (db.query(ConversaParticipanteExterno)
               .filter_by(conversa_id=conversa.id, meio="whatsapp", removido=0).first())
        destino = e.telefone if e is not None else None
    if not destino:
        raise ValueError("A conversa não tem contato de WhatsApp para receber o modelo.")
    msg = _mc.enviar_mensagem(db, conversa, usuario_id, corpo, canal=canal,
                              _permitir_externo=True)
    env = registrar_envio(db, msg, "whatsapp", canal, "cliente", None, destino)
    env.template_id = template.id
    if env.status == "enfileirado":
        ok, id_ext, erro = despachar_template(env, template, params)
        env.status = "enviado" if ok else "falhou"
        env.id_externo = id_ext
        env.erro = erro
    db.flush()
    return msg, env


def _enviar_whatsapp_documento(env, caminho_abs, nome, mime):
    """Documento como MÍDIA pela Cloud API (2 passos): upload em /{phone}/media (multipart) →
    mensagem type=document com o media id. Config-gated pelo chamador (despachar_documento)."""
    import json as _json
    import urllib.request as _u
    import urllib.error as _ue
    token = (os.environ.get("ORIZON_WA_TOKEN") or "").strip()
    phone = _env_por_canal("ORIZON_WA_PHONE_ID", env.canal)
    with open(caminho_abs, "rb") as f:
        binario = f.read()
    fronteira = "orizonwa%s" % abs(hash(nome))
    corpo_mp = b""
    def _campo(n, v):
        return (("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                 % (fronteira, n, v)).encode("utf-8"))
    corpo_mp += _campo("messaging_product", "whatsapp")
    corpo_mp += _campo("type", mime or "application/octet-stream")
    corpo_mp += (("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"%s\"\r\n"
                  "Content-Type: %s\r\n\r\n" % (fronteira, nome, mime or "application/octet-stream"))
                 .encode("utf-8")) + binario + b"\r\n"
    corpo_mp += ("--%s--\r\n" % fronteira).encode("utf-8")
    req = _u.Request("https://graph.facebook.com/v20.0/%s/media" % phone, data=corpo_mp,
                     method="POST",
                     headers={"Authorization": "Bearer " + token,
                              "Content-Type": "multipart/form-data; boundary=%s" % fronteira})
    try:
        with _u.urlopen(req, timeout=30) as resp:
            media = _json.loads(resp.read() or b"{}")
    except _ue.HTTPError as he:
        raise RuntimeError(_erro_meta(he))
    media_id = media.get("id")
    if not media_id:
        return False, None, "upload de mídia sem id na resposta da Meta"
    payload = {"messaging_product": "whatsapp", "to": _digitos(env.destino),
               "type": "document", "document": {"id": media_id, "filename": nome}}
    req2 = _u.Request("https://graph.facebook.com/v20.0/%s/messages" % phone,
                      data=_json.dumps(payload).encode("utf-8"), method="POST",
                      headers={"Authorization": "Bearer " + token,
                               "Content-Type": "application/json"})
    try:
        with _u.urlopen(req2, timeout=30) as resp:
            data = _json.loads(resp.read() or b"{}")
    except _ue.HTTPError as he:
        raise RuntimeError(_erro_meta(he))
    wamid = ((data.get("messages") or [{}])[0]).get("id")
    return True, wamid, (None if wamid else "resposta da Meta sem id de mensagem")


def despachar_documento(env, caminho_abs, nome, mime):
    """Disparo REAL de um DOCUMENTO por WhatsApp — só quando meio_configurado. Mesmo contrato de
    despachar: (ok, id_externo, erro); exceção vira (False, None, erro)."""
    if not meio_configurado("whatsapp"):
        return False, None, "Transporte não configurado neste ambiente."
    try:
        return _enviar_whatsapp_documento(env, caminho_abs, nome, mime)
    except Exception as e:
        return False, None, str(e)


def despachar(env, corpo):
    """Disparo REAL do envio externo — só quando meio_configurado(env.meio). SMTP (e-mail) e Meta
    Cloud API (WhatsApp). A rede é a única parte não coberta por credencial nos testes (os testes
    mockam o boundary smtplib/urlopen). Retorna (ok, id_externo, erro); exceção de rede vira
    (False, None, erro) — o chamador marca o envio como 'falhou' com a mensagem."""
    if not meio_configurado(env.meio):
        return False, None, "Transporte não configurado neste ambiente."
    try:
        if env.meio == "email":
            return _enviar_email(env, corpo)
        if env.meio == "whatsapp":
            return _enviar_whatsapp(env, corpo)
    except Exception as e:
        return False, None, str(e)
    return False, None, "Meio de envio desconhecido: %r" % env.meio


# ── roteamento da resposta de entrada (decisão 14) ───────────────────────────

def _canal_do_thread(db, conversa_id, meio, remetente):
    """Canal (segmento) do fio externo desta conversa: o do envio de SAÍDA mais recente para
    o mesmo destino/meio; fallback 'comercial'."""
    alvo = _digitos(remetente) if meio == "whatsapp" else (remetente or "").strip().lower()
    q = (db.query(EnvioExterno, ConversaMensagem.conversa_id)
           .join(ConversaMensagem, EnvioExterno.mensagem_id == ConversaMensagem.id)
           .filter(ConversaMensagem.conversa_id == conversa_id,
                   EnvioExterno.meio == meio, EnvioExterno.direcao == "saida")
           .order_by(EnvioExterno.id.desc()))
    for env, _cid in q.all():
        dnorm = _digitos(env.destino) if meio == "whatsapp" else (env.destino or "").strip().lower()
        if dnorm == alvo and env.canal:
            return env.canal
    return "comercial"


def _cliente_por_telefone(db, remetente):
    """Cliente cadastrado cujo whatsapp/telefone bate com o remetente (últimos 8 dígitos —
    tolera DDI/DDD divergente). None se não achar. Usado pra loja da entrada E pra dar nome
    ao lead automático da triagem (2026-08-05) sem depender só do perfil da Meta."""
    tail = _digitos(remetente)[-8:]
    if len(tail) != 8:
        return None
    for c in db.query(Cliente).filter(Cliente.loja_id.isnot(None)).all():
        for campo in (c.whatsapp, c.telefone):
            d = _digitos(campo)
            if len(d) >= 8 and d[-8:] == tail:
                return c
    return None


def _cliente_por_email(db, remetente):
    alvo = (remetente or "").strip().lower()
    if not alvo:
        return None
    for c in db.query(Cliente).filter(Cliente.loja_id.isnot(None)).all():
        if (c.email or "").strip().lower() == alvo:
            return c
    return None


def _lead_existente(db, loja_id, meio, remetente):
    """Lead já existente para este contato NESTA loja (TAREFA_LEAD_E_PAINEL_SAC.md, B2, item 7)
    — Lead, ao contrário de Cliente, não é global: escopado à loja que recebeu. Mesmo critério
    de match de `_cliente_por_telefone` (últimos 8 dígitos, tolera DDI/DDD). Chamado tanto na
    ENTRADA (evita criar um segundo Lead se o mesmo telefone mandar mais de uma mensagem antes
    de a triagem materializar) quanto na MATERIALIZAÇÃO (liga a conversa ao Lead que já existe,
    nunca cria um novo ali)."""
    from database import Lead
    if meio == "whatsapp":
        tail = _digitos(remetente)[-8:]
        if len(tail) != 8:
            return None
        for lead in db.query(Lead).filter_by(loja_id=loja_id).all():
            for campo in (lead.whatsapp, lead.telefone):
                d = _digitos(campo)
                if len(d) >= 8 and d[-8:] == tail:
                    return lead
        return None
    alvo = (remetente or "").strip().lower()
    if not alvo:
        return None
    for lead in db.query(Lead).filter_by(loja_id=loja_id).all():
        if (lead.email or "").strip().lower() == alvo:
            return lead
    return None


def _criar_lead_referral(db, loja_id, meio, remetente, nome, referral):
    """Lead de campanha (TAREFA_LEAD_E_PAINEL_SAC.md, B2, item 6, decisão do Marcelo 24/09):
    Lead é quem veio de campanha — o clique no anúncio (Click-to-WhatsApp da Meta) JÁ É o
    evento de lead, então nasce na ENTRADA, sem esperar a materialização da triagem. `canal`
    deriva do próprio bloco `referral` (`source_type`: 'ad'|'post' — a Meta não manda uma
    string "instagram"/"facebook" pronta aqui; ver aviso do documento sobre Google Ads não
    mandar `referral` nenhum). O bloco inteiro fica em `dados_json` sem achatar nada — mesmo
    espírito de `Funcao.beneficios_json`, `template` nomeia a forma pra quem for ler depois.
    Não commita."""
    from database import Lead
    canal = (referral or {}).get("source_type") or "meta_ads"
    lead = Lead(nome=nome, loja_id=loja_id, canal=canal,
               whatsapp=(remetente if meio == "whatsapp" else None),
               email=(remetente if meio == "email" else None),
               template="whatsapp_referral",
               dados_json=json.dumps(referral, ensure_ascii=False))
    db.add(lead); db.flush()
    return lead


def _loja_da_entrada(db, remetente=None, meio="whatsapp"):
    """Loja da entrada externa — QUEM RECEBEU decide (LP-39 passo 1, decisão do Marcelo 22/09,
    docs/db/TAREFA_LP39_ROTEAMENTO.md — reverte a ordem antiga, medida em campo entregando na
    loja errada 3 vezes: cliente cadastrado vencia o número que de fato recebeu a mensagem):

    (1) dono do NumeroConectado ÚNICO na instalação — hoje é o único jeito de saber "quem
        recebeu" sem o phone_number_id do payload da Meta (generaliza para N números no passo 2,
        fora desta tarefa; a ordem não muda quando isso entrar);
    (2) sem número conectado nenhum (ou mais de um — ambíguo do mesmo jeito, sem phone_number_id
        pra desempatar), cliente cadastrado com aquele telefone/e-mail → a loja dele. É o
        comportamento de ANTES desta tarefa, preservado como fallback explícito — instalação sem
        NumeroConectado nenhum não muda de comportamento;
    (3) primeira loja por id."""
    from database import NumeroConectado
    nums = db.query(NumeroConectado).all()
    if len(nums) == 1:
        return nums[0].loja_id
    if remetente and meio == "whatsapp":
        cli = _cliente_por_telefone(db, remetente)
        if cli is not None:
            return cli.loja_id
    elif remetente and meio == "email":
        cli = _cliente_por_email(db, remetente)
        if cli is not None:
            return cli.loja_id
    l = db.query(Loja).order_by(Loja.id.asc()).first()
    return l.id if l else None


def processar_entrada(db, meio, remetente, texto, id_externo_ref=None, id_externo=None,
                      nome=None, referral=None):
    """Recebe uma resposta EXTERNA já normalizada (o webhook faz o parse específico do provedor)
    e a persiste na conversa certa — ou no BUFFER de triagem (spec 2026-07-31: mensagem nenhuma
    é descartada em silêncio). Idempotente por `id_externo` (a Meta reentrega o mesmo webhook até
    o 200): reentrega de mensagem já roteada OU já enfileirada é no-op que devolve o mesmo
    resultado. Retorna {status: 'roteado'|'triagem', conversa_id, [triagem_id]}. Autor NULL =
    veio de fora. `nome` (2026-08-05): perfil do WhatsApp (Meta) — usado só como FALLBACK do
    nome do lead quando o telefone não bate com nenhum Cliente já cadastrado (cadastro vence).
    `referral` (TAREFA_LEAD_E_PAINEL_SAC.md, B2): bloco de Click-to-WhatsApp — quando presente
    e o telefone não bate com Cliente, o `Lead` nasce AQUI (não espera a materialização da
    triagem), porque o clique já é o evento de lead. NÃO commita (o chamador decide)."""
    from . import core as _mc
    if id_externo:
        ja = (db.query(EnvioExterno)
                .filter_by(id_externo=id_externo, direcao="entrada").first())
        if ja is not None:                        # reentrega de mensagem já ROTEADA
            m0 = db.get(ConversaMensagem, ja.mensagem_id)
            return {"status": "roteado", "conversa_id": m0.conversa_id if m0 else None}
        ent_ja = db.query(TriagemEntrada).filter_by(id_externo=id_externo).first()
        if ent_ja is not None:                    # reentrega de entrada já no BUFFER
            return {"status": ("roteado" if ent_ja.status == "resolvido" else "triagem"),
                    "conversa_id": ent_ja.conversa_id, "triagem_id": ent_ja.id}
    # LP-39 passo 1 (docs/db/TAREFA_LP39_ROTEAMENTO.md): a loja é resolvida ANTES de rotear —
    # QUEM RECEBEU decide (é a inversão que dá nome à tarefa) — e repassada ao roteamento, pra
    # filtrar candidatas de outra loja ANTES de uma conversa antiga vencer por conta própria.
    loja_id = _loja_da_entrada(db, remetente=remetente, meio=meio)
    conv, candidatos = _rotear_com_candidatos(db, meio, id_externo_ref=id_externo_ref,
                                              remetente=remetente, loja_id=loja_id)
    if conv is None:
        from . import triagem as _tri
        _rem_norm = (_digitos(remetente) if meio == "whatsapp"
                     else (remetente or "").strip().lower())
        # RF-09 (2026-08-04): remetente que JÁ está no buffer respondendo à pergunta de
        # triagem — interpreta (número/nome do segmento) na MESMA entrada, sem duplicar.
        pend = (db.query(TriagemEntrada)
                  .filter_by(meio=meio, remetente=_rem_norm, status="pendente")
                  .order_by(TriagemEntrada.id.desc()).first())
        if pend is not None:
            try:
                seg = _tri.registrar_resposta_triagem(db, pend, texto)
            except Exception:
                seg = None
            if seg:
                # 2026-08-05: segmento definido pela triagem → materializa NA HORA, sem
                # esperar humano — nasce com o segmento escolhido, SAC como responsável
                # inicial (ele distribui).
                conv2 = _tri.triagem_materializar(db, pend, seg)
                return {"status": "roteado", "conversa_id": conv2.id}
            return {"status": "triagem", "conversa_id": None, "triagem_id": pend.id,
                    "segmento_sugerido": seg}
        cli = (_cliente_por_telefone(db, remetente) if meio == "whatsapp"
               else _cliente_por_email(db, remetente))
        nome_resolvido = (cli.nome if cli else None) or nome
        # TAREFA-B (docs/db/TAREFA_LEAD_E_PAINEL_SAC.md, B2, item 6): Lead é quem veio de
        # campanha — o `referral` só chega na PRIMEIRA mensagem (é a que abriu a conversa), e é
        # exatamente esta, a que cria a TriagemEntrada. Cliente cadastrado nunca vira Lead
        # (item 48). Procura antes de criar (`_lead_existente`) — evita duplicar se este
        # telefone já tiver clicado no anúncio e mandado mensagem antes.
        if cli is None and referral:
            if _lead_existente(db, loja_id, meio, remetente) is None:
                _criar_lead_referral(db, loja_id, meio, remetente,
                                     nome_resolvido or remetente, referral)
        ent = TriagemEntrada(
            loja_id=loja_id, meio=meio,
            remetente=_rem_norm, nome_whatsapp=nome_resolvido,
            texto=texto, id_externo=id_externo, id_externo_ref=id_externo_ref,
            candidatos_json=(json.dumps(sorted(candidatos)) if candidatos else None))
        db.add(ent); db.flush()
        # RF-08 (2026-08-04): pergunta de triagem AUTOMÁTICA de volta ao contato (texto livre
        # — a janela de 24h acabou de abrir). Best-effort: nunca derruba o webhook.
        try:
            _tri.enviar_pergunta_triagem(db, ent)
        except Exception:
            pass
        return {"status": "triagem", "conversa_id": None, "triagem_id": ent.id}
    canal = _canal_do_thread(db, conv.id, meio, remetente)
    msg = _mc.enviar_mensagem(db, conv, None, texto or "(sem texto)", canal=canal,
                              _permitir_externo=True)
    ev = EnvioExterno(mensagem_id=msg.id, meio=meio, direcao="entrada", canal=canal,
                      destino=remetente, status="recebido",
                      id_externo=id_externo, id_externo_ref=id_externo_ref)
    db.add(ev); db.flush()
    # spec 2026-08-04 §8.5: nova mensagem do contato em atendimento CONCLUÍDO reabre sozinho
    # (sai de Arquivadas/Concluída e volta para Todas).
    _mc.reabrir_se_concluida(db, conv)
    return {"status": "roteado", "conversa_id": conv.id}


def iter_mensagens_whatsapp(payload):
    """Extrai as mensagens de um payload de entrada da Meta WhatsApp Cloud API, normalizadas em
    {from, texto, id, ref, nome, referral}. Tolerante à forma aninhada
    (entry[].changes[].value.messages[]).
    `nome` (2026-08-05): perfil do contato que a Meta manda em `value.contacts[]` (wa_id→nome) —
    fallback de nome do lead automático quando o telefone não bate com nenhum Cliente cadastrado.
    `referral` (TAREFA_LEAD_E_PAINEL_SAC.md, B2, item 4): o bloco que a Meta manda em
    `msg.referral` quando a mensagem veio de um clique em anúncio Click-to-WhatsApp (id do
    anúncio, `source_type`, `source_id`, `headline`, `body`) — `None` quando ausente (mensagem
    orgânica, ou anúncio do Google, que não manda este bloco). Mesma família do
    `phone_number_id` do LP-39: o sinal chegava e era jogado fora."""
    for entry in (payload or {}).get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            val = change.get("value", {}) or {}
            nomes = {c.get("wa_id"): ((c.get("profile") or {}).get("name"))
                     for c in (val.get("contacts") or []) if c.get("wa_id")}
            for msg in val.get("messages", []) or []:
                yield {"from": msg.get("from", ""),
                       "texto": ((msg.get("text") or {}).get("body")
                                 or "(mensagem sem texto)"),
                       "id": msg.get("id"),
                       "referral": msg.get("referral"),
                       "ref": (msg.get("context") or {}).get("id"),
                       "nome": nomes.get(msg.get("from"))}


# ═══ Ponte WhatsApp do funcionário (Fatia 6) ═════════════════════════════════
# A web é a casa; o WhatsApp (número da EMPRESA) alcança/recebe do funcionário pelo celular
# CADASTRADO, dentro das regras da Meta: janela de 24h (livre) ou template (fora dela). Não há
# acesso ao WhatsApp pessoal — funcionário↔funcionário não viaja pelo WhatsApp deles.
JANELA_HORAS = 24
PRESENCA_ONLINE_MIN = 5


def registrar_presenca(db, usuario_id):
    """Heartbeat da web: marca o usuário como visto agora."""
    p = db.get(UsuarioPresenca, usuario_id)
    if p is None:
        p = UsuarioPresenca(usuario_id=usuario_id, visto_em=datetime.utcnow())
        db.add(p)
    else:
        p.visto_em = datetime.utcnow()
    db.flush()
    return p


def esta_online(db, usuario_id, minutos=PRESENCA_ONLINE_MIN):
    p = db.get(UsuarioPresenca, usuario_id)
    if p is None or p.visto_em is None:
        return False
    return (datetime.utcnow() - p.visto_em) <= timedelta(minutes=minutos)


def usuario_por_telefone(db, telefone, loja_id=None):
    """Casa um número (entrada do WhatsApp) com um USUÁRIO pelo celular cadastrado (whatsapp ou
    telefone), comparando os últimos 8 dígitos (tolera DDI/DDD). Match único ou None (ambíguo)."""
    d = _digitos(telefone)
    if len(d) < 8:
        return None
    tail = d[-8:]
    achados = []
    q = db.query(Usuario).filter(Usuario.ativo == 1)
    if loja_id:
        q = q.filter(Usuario.loja_id == loja_id)
    for u in q.all():
        for campo in (u.whatsapp, u.telefone):
            du = _digitos(campo)
            if len(du) >= 8 and du[-8:] == tail:
                achados.append(u); break
    return achados[0] if len(achados) == 1 else None


def dentro_da_janela_24h(db, usuario_id):
    """True se há uma mensagem de ENTRADA do celular do usuário nas últimas 24h — nesse caso o
    envio ao vivo é livre (texto). Fora da janela, a Meta exige TEMPLATE aprovado."""
    u = db.get(Usuario, usuario_id)
    if u is None:
        return False
    tail = _digitos(u.whatsapp or u.telefone)[-8:]
    if len(tail) < 8:
        return False
    limite = datetime.utcnow() - timedelta(hours=JANELA_HORAS)
    for env in (db.query(EnvioExterno)
                  .filter(EnvioExterno.meio == "whatsapp", EnvioExterno.direcao == "entrada",
                          EnvioExterno.criado_em >= limite).all()):
        if _digitos(env.destino)[-8:] == tail:
            return True
    return False


JANELA_SEG = JANELA_HORAS * 3600


def janela_da_conversa(db, conversa):
    """RF-04: estado da janela de atendimento de 24h DESTA conversa, a partir da última mensagem de
    ENTRADA DO CLIENTE persistida NELA. Escopado pela conversa (join EnvioExterno→ConversaMensagem→
    conversa_id) — achado da Vera: NÃO varrer o histórico global casando só por telefone (vazava entre
    lojas da mesma rede com o mesmo número). 2º achado da Vera: a resposta do FUNCIONÁRIO pela ponte de
    WhatsApp (`processar_entrada_usuario`) também grava uma EnvioExterno de entrada, mas com
    `canal='interno'` — ela NÃO reabre a janela do cliente, então é excluída aqui (mantendo entradas do
    cliente com canal=segmento ou NULL). Retorna {aberta, ultima_entrada(ISO|None), restante_seg, excedido_seg}."""
    fechada = {"aberta": False, "ultima_entrada": None, "restante_seg": 0, "excedido_seg": None}
    row = (db.query(EnvioExterno.criado_em)
             .join(ConversaMensagem, EnvioExterno.mensagem_id == ConversaMensagem.id)
             .filter(ConversaMensagem.conversa_id == conversa.id,
                     EnvioExterno.meio == "whatsapp", EnvioExterno.direcao == "entrada",
                     (EnvioExterno.canal.is_(None)) | (EnvioExterno.canal != "interno"))
             .order_by(EnvioExterno.criado_em.desc()).first())
    if row is None or row[0] is None:
        return fechada
    ult = row[0]
    decorrido = (datetime.utcnow() - ult).total_seconds()
    if decorrido < JANELA_SEG:
        return {"aberta": True, "ultima_entrada": ult.isoformat(),
                "restante_seg": int(JANELA_SEG - decorrido), "excedido_seg": None}
    return {"aberta": False, "ultima_entrada": ult.isoformat(),
            "restante_seg": 0, "excedido_seg": int(decorrido - JANELA_SEG)}


def janela_por_telefone(db, loja_id, telefone):
    """Janela de atendimento p/ um telefone SEM conversa ainda (spec 2026-08-04 §11 — etapas 1/2
    do Iniciar Conversa: 'Selecionar' um contato do cadastro precisa saber se já existe janela
    aberta ANTES de a conversa ser criada). Escopada por LOJA (join até Conversa.loja_id — mesmo
    cuidado da Vera em janela_da_conversa) para não vazar entre lojas da mesma rede com o mesmo
    número. Retorna {aberta, ultima_entrada}."""
    tail = _digitos(telefone)[-8:]
    if len(tail) < 8:
        return {"aberta": False, "ultima_entrada": None}
    rows = (db.query(EnvioExterno.criado_em, EnvioExterno.destino)
              .join(ConversaMensagem, EnvioExterno.mensagem_id == ConversaMensagem.id)
              .join(Conversa, ConversaMensagem.conversa_id == Conversa.id)
              .filter(Conversa.loja_id == loja_id,
                      EnvioExterno.meio == "whatsapp", EnvioExterno.direcao == "entrada",
                      (EnvioExterno.canal.is_(None)) | (EnvioExterno.canal != "interno"))
              .order_by(EnvioExterno.criado_em.desc()).all())
    for criado_em, destino in rows:
        if _digitos(destino)[-8:] == tail:
            decorrido = (datetime.utcnow() - criado_em).total_seconds()
            if decorrido < JANELA_SEG:
                return {"aberta": True, "ultima_entrada": criado_em.isoformat()}
            return {"aberta": False, "ultima_entrada": criado_em.isoformat()}
    return {"aberta": False, "ultima_entrada": None}


def deve_notificar_usuario(db, usuario):
    """Regra da preferência + presença: 'nunca' não notifica; 'sempre' sempre; 'quando_offline'
    (default) só se estiver offline."""
    pref = (getattr(usuario, "notificar_whatsapp", None) or "quando_offline")
    if pref == "nunca":
        return False
    if pref == "sempre":
        return True
    return not esta_online(db, usuario.id)


def notificar_usuario(db, conversa, mensagem, usuario_dest, autor_nome=None):
    """Registra (config-gated) uma notificação WhatsApp para um usuário sobre uma mensagem. Dentro
    da janela 24h → ESPELHA o texto; fora → TEMPLATE (aviso 'abra o sistema'). Sem credencial Meta
    → nasce 'pendente_config' (a rede não é tocada). Retorna o EnvioExterno ou None (sem número)."""
    destino = (usuario_dest.whatsapp or usuario_dest.telefone or "").strip()
    if not destino:
        return None
    espelho = dentro_da_janela_24h(db, usuario_dest.id)
    if espelho:
        corpo = ("💬 %s: %s" % (autor_nome or "Nova mensagem", (mensagem.corpo or "").strip()
                                or "(anexo)"))
    else:
        corpo = ("Você tem uma nova mensagem no Orizon Chat. Abra o sistema para responder.")
    env = registrar_envio(db, mensagem, "whatsapp", "interno", "usuario", usuario_dest.id, destino)
    env.id_externo_ref = None
    # anota o modo no próprio registro (reusa 'erro' como nota quando pendente — não é falha)
    if env.status == "pendente_config":
        env.erro = "modo=%s (aguardando credencial Meta)" % ("espelho" if espelho else "template")
    db.flush()
    if env.status == "enfileirado":
        ok, wamid, err = despachar(env, corpo)
        env.status = "enviado" if ok else "falhou"
        env.id_externo = wamid if ok else None
        if err:
            env.erro = err
        db.flush()
    return env


def notificar_conversa(db, conversa, mensagem, autor_id):
    """Ao postar numa DIRECT/GRUPO, notifica no WhatsApp os participantes (menos o autor) conforme
    a preferência/presença de cada um. Canais públicos não notificam individualmente (audiência
    ampla). Best-effort: nunca quebra o envio da mensagem."""
    if conversa.tipo not in ("direct", "grupo"):
        return []
    dest_ids = [p.usuario_id for p in db.query(ConversaParticipante)
                .filter_by(conversa_id=conversa.id).all() if p.usuario_id != autor_id]
    enviados = []
    autor = db.get(Usuario, autor_id)
    autor_nome = autor.nome if autor else None
    for uid in dest_ids:
        u = db.get(Usuario, uid)
        if u is None or not deve_notificar_usuario(db, u):
            continue
        try:
            ev = notificar_usuario(db, conversa, mensagem, u, autor_nome=autor_nome)
            if ev is not None:
                enviados.append(ev.id)
        except Exception:
            pass   # best-effort
    return enviados


def espelhar_para_externos(db, conversa, mensagem, autor_nome=None):
    """Espelha uma mensagem da conversa para os participantes EXTERNOS (contatos WhatsApp/e-mail sem
    Usuario) — Orizon Chat 2026-07-28. Um EnvioExterno por externo, CONFIG-GATED (sem credencial →
    'pendente_config', a rede não é tocada). Best-effort: nunca quebra o envio interno. Retorna os ids
    dos envios criados."""
    externos = (db.query(ConversaParticipanteExterno)
                  .filter_by(conversa_id=conversa.id, removido=0).all())
    if not externos:
        return []
    corpo = "💬 %s: %s" % (autor_nome or "Nova mensagem",
                           (mensagem.corpo or "").strip() or "(anexo)")
    enviados = []
    for e in externos:
        destino = (e.telefone if e.meio == "whatsapp" else e.email or "").strip() if (e.telefone or e.email) else ""
        if not destino:
            continue
        env = None
        try:
            env = registrar_envio(db, mensagem, e.meio, "comercial", "avulso", e.id, destino)
            if env.status == "enfileirado":
                ok, ext_id, err = despachar(env, corpo)
                env.status = "enviado" if ok else "falhou"
                env.id_externo = ext_id if ok else None
                if err:
                    env.erro = err
                db.flush()
            enviados.append(env.id)
        except Exception as exc:
            # 2º nível de engolimento (achado do Marcelo, 18/09, TAREFA_ENTREGA_VISIVEL): best-
            # effort continua best-effort — um externo problemático não pode travar os outros do
            # laço nem a mensagem interna — mas a falha não pode só desaparecer. despachar() já
            # captura tudo e devolve (False, None, erro); isto aqui é a rede de segurança pro
            # caso raro de algo escapar dela (ex.: o próprio registrar_envio/flush). Se o
            # registro já existia, marca 'falhou' com o motivo real — sem isso,
            # entregas_por_mensagem relataria 'nao_se_aplica' quando na verdade algo quebrou.
            if env is not None:
                try:
                    env.status = "falhou"
                    env.erro = str(exc)
                    db.flush()
                    enviados.append(env.id)
                except Exception:
                    pass   # rede de segurança final — nunca quebra a mensagem interna
    return enviados


def encaminhar_documento_externo(db, conversa, documento, usuario_id, caminho_abs, mime=None):
    """Decisão 3 da spec 2026-07-31 (portas): encaminha um CicloDocumento pelo WhatsApp da
    conversa aos participantes EXTERNOS. DENTRO da janela de 24h → mídia (despachar_documento,
    config-gated: sem credencial nasce 'pendente_config'); FORA da janela a Meta exige TEMPLATE
    aprovado → erro claro (o ramo por template é a F3, pendente). Gera EVENTO inline
    'documento_encaminhado' + um EnvioExterno por externo. Não commita."""
    from . import core as _mc
    j = janela_da_conversa(db, conversa)
    if not j["aberta"]:
        raise ValueError("Janela de 24h fechada — o encaminhamento livre não é permitido pela "
                         "Meta; use um template aprovado (envio por template ainda não "
                         "disponível).")
    externos = [e for e in db.query(ConversaParticipanteExterno)
                  .filter_by(conversa_id=conversa.id, removido=0).all()
                if e.meio == "whatsapp" and (e.telefone or "").strip()]
    if not externos:
        raise ValueError("A conversa não tem contato externo de WhatsApp — adicione o contato "
                         "antes de encaminhar.")
    corpo_ev = "Documento %s encaminhado ao cliente por WhatsApp" % (
        documento.nome_original or documento.tipo)
    msg = _mc.enviar_mensagem(db, conversa, usuario_id, corpo_ev,
                              documento_ref_id=documento.id, evento="documento_encaminhado")
    canal = _canal_do_thread(db, conversa.id, "whatsapp", externos[0].telefone)
    envios = []
    for e in externos:
        env = registrar_envio(db, msg, "whatsapp", canal, "avulso", e.id, e.telefone.strip())
        if env.status == "enfileirado":
            ok, wamid, err = despachar_documento(env, caminho_abs,
                                                 documento.nome_original or "documento", mime)
            env.status = "enviado" if ok else "falhou"
            env.id_externo = wamid if ok else None
            if err:
                env.erro = err
            db.flush()
        envios.append(env)
    return msg, envios


def notificar_gerentes_email(db, mensagem, destinatarios, corpo):
    """Envia (config-gated) um e-mail a cada destinatário [{id, email}] — ex.: gerentes/diretores
    avisados das lacunas no fechamento. Sem SMTP → 'pendente_config' (nada é enviado). Retorna os
    EnvioExterno criados. Não commita."""
    envs = []
    for d in (destinatarios or []):
        email = (d.get("email") or "").strip()
        if not email:
            continue
        env = registrar_envio(db, mensagem, "email", None, "usuario", d.get("id"), email)
        if env.status == "enfileirado":
            ok, mid, err = despachar(env, corpo)
            env.status = "enviado" if ok else "falhou"
            env.id_externo = mid if ok else None
            if err:
                env.erro = err
        envs.append(env)
    db.flush()
    return envs


def processar_entrada_usuario(db, remetente, texto):
    """Resposta do FUNCIONÁRIO pelo WhatsApp: casa o número com um usuário e a posta como ELE na
    conversa da última notificação que recebeu. Retorna {status, conversa_id} ou None se não é um
    usuário conhecido (aí o chamador cai no fluxo de contato externo)."""
    from . import core as _mc
    u = usuario_por_telefone(db, remetente)
    if u is None:
        return None
    env = (db.query(EnvioExterno)
             .filter(EnvioExterno.meio == "whatsapp", EnvioExterno.direcao == "saida",
                     EnvioExterno.destinatario_tipo == "usuario",
                     EnvioExterno.destinatario_id == u.id)
             .order_by(EnvioExterno.id.desc()).first())
    if env is None:
        return {"status": "sem_conversa", "conversa_id": None, "usuario_id": u.id}
    msg0 = db.get(ConversaMensagem, env.mensagem_id)
    conv = db.get(Conversa, msg0.conversa_id) if msg0 else None
    if conv is None:
        return {"status": "sem_conversa", "conversa_id": None, "usuario_id": u.id}
    msg = _mc.enviar_mensagem(db, conv, u.id, texto or "(sem texto)", permitir_vazio=True)
    ev = EnvioExterno(mensagem_id=msg.id, meio="whatsapp", direcao="entrada", canal="interno",
                      destino=remetente, status="recebido")
    db.add(ev); db.flush()
    return {"status": "roteado", "conversa_id": conv.id, "usuario_id": u.id}


def _rotear_com_candidatos(db, meio, id_externo_ref=None, remetente=None, loja_id=None):
    """Roteamento da entrada externa com os CANDIDATOS preservados (spec 2026-07-31): retorna
    (conversa, candidatos). Ordem: (1) reply CITANDO um envio nosso (id_externo) → determinístico
    (vence inclusive projeto concluído); (2) sem citação, número/e-mail com UMA única conversa
    ATIVA → vai direto — conversa de projeto CONCLUÍDO não é reaberta sozinha, vira candidata;
    (3) várias/nenhuma ativa → (None, candidatos) e a lista NÃO se perde (vai à fila).

    `loja_id` (LP-39 passo 1, docs/db/TAREFA_LP39_ROTEAMENTO.md): quando informado, FILTRA as
    candidatas por `Conversa.loja_id` — sem isto a conversa antiga de OUTRA loja vencia antes de
    qualquer decisão de loja (era como a mensagem 113 chegou na conversa 31 da loja 15 pelo
    número da loja 1). Vale também pro ramo da citação (`id_externo_ref`): conversa citada de
    outra loja não serve — cai pro resto do fluxo (remetente), não retorna direto. `None`
    (padrão) = comportamento de antes, sem filtro nenhum."""
    if id_externo_ref:
        env = (db.query(EnvioExterno)
                 .filter(EnvioExterno.id_externo == id_externo_ref).first())
        if env is not None:
            msg = db.get(ConversaMensagem, env.mensagem_id)
            conv = db.get(Conversa, msg.conversa_id) if msg else None
            if conv is not None and (loja_id is None or conv.loja_id == loja_id):
                return conv, [conv.id]
    if not remetente:
        return None, []
    alvo_norm = _digitos(remetente) if meio == "whatsapp" else remetente.strip().lower()
    conv_ids = set()
    q = (db.query(EnvioExterno, ConversaMensagem.conversa_id)
           .join(ConversaMensagem, EnvioExterno.mensagem_id == ConversaMensagem.id)
           .filter(EnvioExterno.meio == meio))
    for env, conv_id in q.all():
        dnorm = _digitos(env.destino) if meio == "whatsapp" else (env.destino or "").strip().lower()
        if dnorm and dnorm == alvo_norm:
            conv_ids.add(conv_id)
    if not conv_ids:
        return None, []
    if loja_id is not None:
        conv_ids = {cid for cid in conv_ids
                   if getattr(db.get(Conversa, cid), "loja_id", None) == loja_id}
        if not conv_ids:
            return None, []
    ativas = []
    for cid in conv_ids:
        c = db.get(Conversa, cid)
        if c is not None and c.projeto_nome:
            p = db.query(Projeto).filter_by(nome_safe=c.projeto_nome).first()
            if p is not None and p.status == "concluido":
                continue                     # projeto encerrado → decisão humana, não reabertura
        ativas.append(cid)
    if len(ativas) == 1:
        return db.get(Conversa, ativas[0]), ativas
    return None, sorted(conv_ids)


def rotear_entrada(db, meio, id_externo_ref=None, remetente=None, loja_id=None):
    """Conversa-alvo de uma resposta EXTERNA, ou None quando é ambíguo/desconhecido (→ fila de
    triagem persistida — processar_entrada guarda os candidatos). `loja_id`: ver
    `_rotear_com_candidatos`."""
    conv, _cand = _rotear_com_candidatos(db, meio, id_externo_ref=id_externo_ref,
                                         remetente=remetente, loja_id=loja_id)
    return conv

# Re-export de compatibilidade: a fila de triagem vive em chat/triagem.py (spec de portas).
from .triagem import (serializar_triagem, triagem_listar,            # noqa: E402,F401
                      triagem_materializar, varrer_triagem_vencida,
                      listar_fila, assumir_da_fila)
