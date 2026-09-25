# -*- coding: utf-8 -*-
"""chat/triagem.py — resolução SEMPRE AUTOMÁTICA da triagem (revisão 2026-08-05, substitui a
fila humana da spec _geral/2026-07-31-triagem-pipeline-entrada-design.md: não existe mais
painel de vincular/criar/descartar). A persistência do buffer acontece em
externo.processar_entrada (idempotente por wamid); aqui vive a materialização: resposta
reconhecida no menu → conversa nasce com esse segmento; sem resposta em 2min
(varrer_triagem_vencida) → nasce com segmento='triagem' (selo próprio) e cai pro SAC
distribuir — SAC transfere pra quem deve atender, e a transferência resolve."""
import json
from datetime import datetime, timedelta

from database import EnvioExterno, Conversa, Funcionario, Lead, TriagemEntrada

from .externo import (_canal_do_thread, _cliente_por_telefone, _cliente_por_email,
                      _lead_existente, registrar_envio)  # noqa: F401  (canal do fio externo)

SEGMENTO_TRIAGEM = "triagem"   # selo próprio (não é um dos 7 de SEGMENTOS) — SAC distribui
# TAREFA-A (docs/db/TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md, item 5): sentinela INTERNO — nunca um
# segmento real do catálogo, nunca sai pro cliente, nunca persiste em `segmento_sugerido` fora
# desta função. Sinaliza pra `triagem_materializar` que o projeto foi CONFIRMADO em P3 ("sim")
# e a entrada deve entrar na conversa do PROJETO (`dialogo_json["projeto"]`), não virar grupo
# novo. "comercial" (um segmento real) sinaliza o ramo do comercial — materializa normal.
SEGMENTO_PROJETO_DEFINIDO = "_projeto_confirmado"
_PROJETO_STATUS_TERMINAL = ("perdido", "concluido", "cancelado")   # o resto conta como ATIVO
MINUTOS_SWEEP = 2
# Teto da fila (18/09, achado da revisão pós-suíte): listar_fila/listar_conversas_sem_dono não
# tinham LIMIT — uma união sem teto é defeito por si só (todo poll de 45s de todo SAC de toda
# loja carregaria a tabela inteira). 300 por estado é folga generosa pro uso real (a Inspirium
# tem 7-8 órfãs hoje); estourar isso é sintoma de outro problema (fila sem trabalhar há muito
# tempo), não motivo pra a tela não abrir — por isso trunca, não recusa.
LIMITE_FILA = 300


def serializar_triagem(e):
    return {"id": e.id, "meio": e.meio, "remetente": e.remetente, "texto": e.texto,
            "status": e.status,
            "candidatos": (json.loads(e.candidatos_json) if e.candidatos_json else []),
            "segmento_sugerido": e.segmento_sugerido,
            "conversa_id": e.conversa_id,
            "criado_em": e.criado_em.isoformat() if e.criado_em else None}


def triagem_listar(db, loja_id, status="pendente"):
    """Entradas do buffer da LOJA (tenancy), mais antigas primeiro (ordem de chegada) — uso
    interno/depuração; não tem mais tela própria (a resolução é automática)."""
    q = db.query(TriagemEntrada).filter_by(loja_id=loja_id)
    if status:
        q = q.filter(TriagemEntrada.status == status)
    return [serializar_triagem(e) for e in q.order_by(TriagemEntrada.id.asc()).all()]


def listar_fila(db, loja_id):
    """Fila de leads sem dono (TAREFA_FILA_DE_LEADS, 18/09): "contato de fora sem dono", os dois
    estados — TriagemEntrada pendente (ainda não materializou) e Conversa externa já
    materializada sem participante/responsável (as órfãs de 31/08-16/09). Recorte deliberado:
    só triagem pendente perderia o item no instante em que materializa (foi o que aconteceu com
    o Felipe em 17/09 — saiu da triagem e virou conversa invisível). Mais antigo primeiro."""
    from . import core as _mc
    itens = [{"tipo": "triagem", "id": e.id,
              "nome": e.nome_whatsapp or e.remetente, "remetente": e.remetente,
              "meio": e.meio, "texto": e.texto,
              "criado_em": e.criado_em.isoformat() if e.criado_em else None}
             for e in (db.query(TriagemEntrada)
                         .filter_by(loja_id=loja_id, status="pendente")
                         .order_by(TriagemEntrada.criado_em.asc())
                         .limit(LIMITE_FILA).all())]
    itens += [{"tipo": "conversa", "id": c.id, "nome": c.titulo,
               "origem_entrada": c.origem_entrada,
               "criado_em": c.criado_em.isoformat() if c.criado_em else None}
              for c in _mc.listar_conversas_sem_dono(db, loja_id, limite=LIMITE_FILA)]
    itens.sort(key=lambda it: it["criado_em"] or "")
    return itens[:LIMITE_FILA]


def assumir_da_fila(db, loja_id, usuario_id, tipo, item_id):
    """Ação Assumir (2b): materializa a triagem se ainda for o caso, depois adiciona quem assumiu
    como participante e responsável — regra dos irmãos: reusa core.transferir_responsavel
    (mesma trilha da Transferência manual §7.1-A) em vez de duplicar a lógica de participante.
    Não commita."""
    from . import core as _mc
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        raise ValueError("Item inválido.")
    if tipo == "triagem":
        entrada = db.get(TriagemEntrada, item_id)
        if entrada is None or entrada.loja_id != loja_id:
            raise ValueError("Entrada de triagem não encontrada nesta loja.")
        if entrada.status != "pendente":
            raise ValueError("Esta entrada já foi resolvida.")
        conv = triagem_materializar(db, entrada, SEGMENTO_TRIAGEM)
    elif tipo == "conversa":
        conv = db.get(Conversa, item_id)
        if conv is None or conv.loja_id != loja_id:
            raise ValueError("Conversa não encontrada nesta loja.")
    else:
        raise ValueError("Tipo inválido (triagem|conversa).")
    _mc.transferir_responsavel(db, conv, usuario_id, usuario_id)
    return conv


def _triagem_marcar(db, entrada, conversa_id):
    entrada.status = "resolvido"
    entrada.resolvido_em = datetime.utcnow()
    entrada.conversa_id = conversa_id
    db.flush()


def _triagem_postar_na_conversa(db, entrada, conversa):
    """Entrega a mensagem original na conversa (autor NULL = externa) + EnvioExterno de entrada
    com o wamid (mantém idempotência e janela). Não commita."""
    from . import core as _mc
    canal = _canal_do_thread(db, conversa.id, entrada.meio, entrada.remetente)
    msg = _mc.enviar_mensagem(db, conversa, None, entrada.texto or "(sem texto)", canal=canal,
                              _permitir_externo=True)
    db.add(EnvioExterno(mensagem_id=msg.id, meio=entrada.meio, direcao="entrada", canal=canal,
                        destino=entrada.remetente, status="recebido",
                        id_externo=entrada.id_externo, id_externo_ref=entrada.id_externo_ref))
    db.flush()
    return msg


def _sac_usuario_id(db, loja_id):
    """Usuário (conta de login) do Funcionário com Função 'SAC' da loja — responsável inicial
    de todo atendimento que sai da triagem automática (2026-08-05: SAC recebe e DISTRIBUI;
    quem recebe a transferência assume de verdade). None se ninguém tem essa Função na loja,
    ou tem mas sem conta de login — a conversa nasce sem responsável (só Oversight enxerga até
    alguém assumir manualmente), não trava a materialização."""
    from . import core as _mc
    fid = _mc.responsavel_sac(db, loja_id)
    if not fid:
        return None
    f = db.get(Funcionario, fid)
    return f.usuario_id if f else None


def triagem_materializar(db, entrada, segmento):
    """Resolução ÚNICA e sempre automática: se o telefone/e-mail bate com um Cliente já
    cadastrado, a conversa segue para ele normalmente (`conv.cliente_id` gravado — TAREFA-B,
    B1 item 2: a informação já estava na mão e era descartada). `segmento` é o escolhido pelo
    cliente no menu (já validado em interpretar_resposta_triagem) OU SEGMENTO_TRIAGEM quando
    ninguém respondeu a tempo. Nome: cadastro > perfil do WhatsApp (Meta) > o próprio
    remetente, nessa ordem (pedido 2026-08-05). Título é o NOME puro, sem prefixo — o selo
    Lead/Cliente/Contato é DERIVADO em `serializar_conversa` (TAREFA-B, B1 item 3), nunca mais
    escrito aqui. Não commita.

    TAREFA-B (docs/db/TAREFA_LEAD_E_PAINEL_SAC.md, B2, decisão do Marcelo 24/09): Lead deixou
    de nascer aqui incondicionalmente pra todo contato sem Cliente — **Lead é quem veio de
    campanha** (`referral` da Meta). Quando há, `processar_entrada` (chat/externo.py) já criou
    o `Lead` NA ENTRADA (o clique no anúncio já é o evento) — aqui só PROCURA por
    (telefone, loja) e liga `conv.lead_id`, nunca cria um segundo (dedup: a mesma pessoa pode
    mandar várias mensagens antes de materializar). Sem `referral` nenhum (nem agora, nem
    antes) e telefone desconhecido: **nenhum Lead nasce** — a conversa é atendimento comum do
    SAC, selo "Contato", até alguém promover a Lead manualmente (botão, fora desta tarefa).

    REVERSÃO DA "DECISÃO 12" (14/09/2026, PLANO_SEMANA_1.md — reversão deliberada, registrada
    com data e motivo por pedido do Marcelo): a decisão original ("contato vira cadastro") fazia
    todo contato inbound sem match virar `Cliente` direto, sem estágio de qualificação — o
    motivo de existir do `Lead` (Captação provisória) evaporava se o principal ponto de entrada
    continuasse criando Cliente direto. Continua valendo: nunca cria `Cliente` aqui.
    Dedup de contato repetido não muda: `_rotear_com_candidatos` (chat/externo.py) já resolve
    mensagens subsequentes do mesmo número/e-mail pela conversa existente (via
    ConversaParticipanteExterno), independente de ela estar ancorada em Cliente, Lead ou
    nenhum dos dois — este caminho só roda na PRIMEIRA mensagem de um contato sem conversa
    nenhuma.

    TAREFA-A (docs/db/TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md, item 5): `segmento ==
    SEGMENTO_PROJETO_DEFINIDO` + `dialogo_json["projeto"]` setado (P3 confirmado "sim" —
    `chat/triagem.py::_registrar_resposta_dialogo`) é o ramo "projeto definido" — entra na
    conversa do PROJETO (`_mc.get_or_create_conversa_projeto`, que já resolve o responsável
    pelo `Projeto.criado_por_id`), nunca cria grupo novo nem Lead. Qualquer outro segmento
    (incluindo "comercial", o ramo do comercial reconciliado com o SAC central) segue o
    caminho de sempre abaixo — "comercial" não é especial aqui, é só mais um segmento."""
    if entrada.status != "pendente":
        raise ValueError("Esta entrada já foi resolvida.")
    from . import core as _mc
    dialogo = json.loads(entrada.dialogo_json) if entrada.dialogo_json else None
    if segmento == SEGMENTO_PROJETO_DEFINIDO and dialogo and dialogo.get("projeto"):
        cli_proj = (_cliente_por_telefone(db, entrada.remetente) if entrada.meio == "whatsapp"
                   else _cliente_por_email(db, entrada.remetente))
        nome_proj = (cli_proj.nome if cli_proj else None) or entrada.nome_whatsapp or entrada.remetente
        conv = _mc.get_or_create_conversa_projeto(db, entrada.loja_id, dialogo["projeto"],
                                                  cliente_id=(cli_proj.id if cli_proj else None))
        conv.origem_entrada = "triagem"
        db.flush()
        _mc.adicionar_externo(db, conv, nome_proj,
                              telefone=(entrada.remetente if entrada.meio == "whatsapp" else None),
                              email=(entrada.remetente if entrada.meio == "email" else None),
                              meio=entrada.meio, criado_por_id=conv.responsavel_usuario_id)
        _triagem_postar_na_conversa(db, entrada, conv)
        db.flush()
        _triagem_marcar(db, entrada, conv.id)
        return conv
    cli = (_cliente_por_telefone(db, entrada.remetente) if entrada.meio == "whatsapp"
           else _cliente_por_email(db, entrada.remetente))
    nome = (cli.nome if cli else None) or entrada.nome_whatsapp or entrada.remetente
    sac_uid = _sac_usuario_id(db, entrada.loja_id)
    lead = None
    if cli is None:
        lead = _lead_existente(db, entrada.loja_id, entrada.meio, entrada.remetente)
    if sac_uid:
        conv = _mc.criar_grupo(db, entrada.loja_id, sac_uid, nome, [sac_uid],
                               exige_dois=False)
    else:
        conv = Conversa(loja_id=entrada.loja_id, tipo="grupo", titulo=nome)
        db.add(conv); db.flush()
    if lead is not None:
        conv.lead_id = lead.id
    elif cli is not None:
        conv.cliente_id = cli.id
    _mc.adicionar_externo(db, conv, nome,
                          telefone=(entrada.remetente if entrada.meio == "whatsapp" else None),
                          email=(entrada.remetente if entrada.meio == "email" else None),
                          meio=entrada.meio, criado_por_id=sac_uid)
    _triagem_postar_na_conversa(db, entrada, conv)
    conv.segmento = segmento
    conv.origem_entrada = "triagem"
    db.flush()
    _triagem_marcar(db, entrada, conv.id)
    return conv


def varrer_triagem_vencida(db, loja_id, minutos=MINUTOS_SWEEP):
    """Checagem PREGUIÇOSA (sem job em background — mesmo padrão da janela de 24h): entradas
    pendentes há mais de `minutos` sem segmento reconhecido materializam com
    SEGMENTO_TRIAGEM (cliente não respondeu / resposta não reconhecida / número ambíguo —
    qualquer caso sem resolução direta cai pro SAC distribuir). Chamada no GET do inbox, então
    "2 minutos" é best-effort (só vence quando alguém carrega a tela de novo), não um timer de
    verdade — aceito pelo pedido original. Não commita; o chamador decide. Best-effort: uma
    entrada problemática não derruba a leitura do inbox de todo mundo."""
    limite = datetime.utcnow() - timedelta(minutes=minutos)
    pendentes = (db.query(TriagemEntrada)
                   .filter(TriagemEntrada.loja_id == loja_id,
                           TriagemEntrada.status == "pendente",
                           TriagemEntrada.criado_em < limite).all())
    for ent in pendentes:
        try:
            triagem_materializar(db, ent, SEGMENTO_TRIAGEM)
        except Exception:
            pass


# ── RF-08/09 — triagem AUTOMÁTICA (2026-08-04): pergunta ao contato + leitura da resposta ────
# O contato acabou de escrever → janela de 24h ABERTA → a pergunta sai como texto livre (sem
# template). A resolução é sempre automática (2026-08-05, triagem_materializar acima): resposta
# reconhecida → materializa na hora com o segmento; sem resposta em 2min → SEGMENTO_TRIAGEM.

_SEG_ROTULOS = {"comercial": "Comercial", "financeiro": "Financeiro", "logistica": "Logística",
                "suporte_tecnico": "Suporte Técnico", "sac": "SAC", "compras": "Compras",
                "parceiros": "Projeto Executivo"}   # chave legada `parceiros` (renomeado 2026-08-04)


def opcoes_pergunta(db, loja_id):
    """[{segmento, rotulo}] ATIVOS, na ordem da pergunta: TriagemConfig.itens_json quando
    configurada; senão o DEFAULT de triagem (rótulos longos, ordem própria, Compras desligado —
    o mesmo que a tela de config mostra), respeitando desativações do SegmentoConfig (RF-02)."""
    from .core import _triagem_default
    from database import SegmentoConfig, TriagemConfig
    cfg = db.query(TriagemConfig).filter_by(loja_id=loja_id).first() if loja_id else None
    if cfg and cfg.itens_json:
        try:
            itens = [i for i in json.loads(cfg.itens_json) if i.get("ativo", True)]
            if itens:
                return [{"segmento": i["segmento"],
                         "rotulo": i.get("rotulo") or _SEG_ROTULOS.get(i["segmento"], i["segmento"])}
                        for i in itens]
        except (ValueError, KeyError, TypeError):
            pass
    rows = (db.query(SegmentoConfig).filter_by(loja_id=loja_id).all()) if loja_id else []
    cfg_por_seg = {r.segmento: r for r in rows}
    out = []
    for it in _triagem_default()["itens"]:
        if not it["ativo"]:
            continue
        r = cfg_por_seg.get(it["segmento"])
        if r is not None and not r.ativo:
            continue
        out.append({"segmento": it["segmento"],
                    "rotulo": (r.rotulo if (r and r.rotulo) else it["rotulo"])})
    return out


def montar_pergunta_triagem(db, loja_id):
    """(texto, opcoes) da pergunta de triagem. Formato 'livre' usa a mensagem configurada
    (atendente roteia depois); 'lista' numera os segmentos ativos."""
    from database import TriagemConfig
    cfg = db.query(TriagemConfig).filter_by(loja_id=loja_id).first() if loja_id else None
    ops = opcoes_pergunta(db, loja_id)
    if cfg and cfg.formato == "livre" and (cfg.mensagem_livre or "").strip():
        return cfg.mensagem_livre.strip(), ops
    linhas = "\n".join("%d. %s" % (i + 1, o["rotulo"]) for i, o in enumerate(ops))
    texto = ("Olá! 👋 Recebemos sua mensagem. Para agilizar seu atendimento, responda com o "
             "NÚMERO do assunto:\n%s" % linhas)
    return texto, ops


def _normalizar_txt(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", (t or "").strip().lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def interpretar_resposta_triagem(texto, opcoes):
    """Segmento escolhido pelo cliente, ou None: aceita o NÚMERO da lista ('2', '2.', '2 -')
    ou o NOME/rótulo (sem acento/caixa). Ambíguo/não reconhecido → None (fica pro humano)."""
    t = _normalizar_txt(texto)
    if not t or not opcoes:
        return None
    digitos = "".join(c for c in t if c.isdigit())
    if digitos and t.replace(".", "").replace("-", "").replace(")", "").strip() == digitos:
        n = int(digitos)
        if 1 <= n <= len(opcoes):
            return opcoes[n - 1]["segmento"]
        return None
    for o in opcoes:
        if t == _normalizar_txt(o["rotulo"]) or t == _normalizar_txt(o["segmento"]):
            return o["segmento"]
    return None


def _enviar_texto_triagem(db, entrada, corpo):
    """Envio externo de SISTEMA vinculado à entrada de triagem (sem conversa/mensagem ainda).
    Config-gated como todo envio: sem credencial nasce 'pendente_config'; erro fica gravado.
    Best-effort — NUNCA derruba o processamento do webhook. Não commita."""
    from database import EnvioExterno
    from . import externo as _ext
    env = EnvioExterno(mensagem_id=None, triagem_id=entrada.id, meio=entrada.meio,
                       direcao="saida", destinatario_tipo="cliente",
                       destino=entrada.remetente,
                       status=("enfileirado" if _ext.meio_configurado(entrada.meio)
                               else "pendente_config"))
    db.add(env); db.flush()
    if env.status == "enfileirado":
        ok, id_ext, erro = _ext.despachar(env, corpo)
        env.status = "enviado" if ok else "falhou"
        env.id_externo = id_ext
        env.erro = erro
    db.flush()
    return env


def enviar_pergunta_triagem(db, entrada):
    """RF-08: pergunta de triagem ao contato recém-chegado na fila."""
    corpo, _ops = montar_pergunta_triagem(db, entrada.loja_id)
    return _enviar_texto_triagem(db, entrada, corpo)


def _texto_p1():
    """P1 (TAREFA-A, docs/db/TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md): reconhecimento do Cliente
    cadastrado — não recebe o menu de segmentos, recebe esta pergunta."""
    return ("Olá! 👋 Vi que você já é nosso cliente. É sobre o seu projeto em andamento, ou "
            "outro assunto? Responda com o NÚMERO:\n1. Meu projeto\n2. Outro assunto")


def enviar_reconhecimento_cliente(db, entrada):
    """TAREFA-A: P1 pro Cliente já cadastrado NESTA loja — irmã de `enviar_pergunta_triagem`
    (mesmo `_enviar_texto_triagem` por baixo), chamada por `processar_entrada` no lugar dela
    quando o telefone bate com Cliente da loja resolvida (LP-39)."""
    return _enviar_texto_triagem(db, entrada, _texto_p1())


def ja_reformulou(db, entrada):
    """True quando a pergunta de triagem já foi reformulada uma vez para esta `entrada`
    (TAREFA_TRIAGEM_E_CONTADOR.md, Item 1, decisão de 21/09/2026: derivar em vez de abrir
    coluna nova — R1 proíbe DDL fora de migração).

    Não existe onde guardar "já reformulei" em `TriagemEntrada`, então isso é CONTADO: cada
    envio de saída da triagem grava um `EnvioExterno.triagem_id` ligado a esta entrada
    (`_enviar_texto_triagem` é o ÚNICO escritor desse campo — medido em 21/09/2026). A
    pergunta original conta 1; a reformulação, se já mandada, conta 2 — daí o corte em `>= 2`.
    O corte pressupõe a pergunta original GRAVADA: `enviar_pergunta_triagem` roda dentro de
    try/except em `chat/externo.py`, então se ela estourar antes do `db.add` (falha de despacho
    não conta — a linha já nasceu 'falhou'/'pendente_config') a contagem começa em 0 e o robô
    reformula duas vezes. Degradação aceita e limitada: nunca vira loop.
    Essa contagem só é confiável enquanto for verdade que ninguém mais escreve
    `EnvioExterno.triagem_id`: `test_ja_reformulou_escritores_fixos` fixa os escritores de
    hoje — um escritor novo tem que aparecer como teste vermelho ali, nunca como contagem
    errada em produção.

    Usada só no fluxo de HOJE (número desconhecido, `entrada.dialogo_json is None`). TAREFA-A
    (docs/db/TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md, item 4) precisa de "reformulei uma vez" POR
    ESTADO (P1/P2/P3 ramificam — contar globalmente não diz QUAL pergunta foi feita), então o
    diálogo do Cliente reconhecido rastreia isso dentro do próprio `dialogo_json` (chave
    `"reformulado"`, resetada a cada troca de estado — ver `_dialogo_falhar` abaixo), não por
    esta contagem."""
    return (db.query(EnvioExterno)
              .filter_by(triagem_id=entrada.id, direcao="saida")
              .count()) >= 2


def _texto_reformulacao_triagem(ops):
    """Texto da SEGUNDA (e última) tentativa — decisão 18/09, Item 1 da
    TAREFA_TRIAGEM_E_CONTADOR: mesmas opções, deixando explícito o formato esperado (o que
    faltou na resposta livre que não casou)."""
    linhas = "\n".join("%d. %s" % (i + 1, o["rotulo"]) for i, o in enumerate(ops))
    return ("Desculpe, não entendi sua resposta 🙏 Pra eu te direcionar certinho, responda só "
            "com o NÚMERO do assunto:\n%s" % linhas)


# ── TAREFA-A — diálogo de reconhecimento do Cliente cadastrado ───────────────────────────────
# docs/db/TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md. Estado em `entrada.dialogo_json` (migração
# a518e96c1cee): P1 (projeto × outro assunto) → P2 (escolha, se 2+ projetos ativos) → P3
# (confirmação do consultor) → o menu de segmentos de sempre, se "outro assunto" ou 0 projetos
# ativos. Reformulação é POR ESTADO (chave "reformulado" dentro do próprio dialogo_json,
# resetada a cada troca de estado — `ja_reformulou`, acima, não serve aqui: conta GLOBAL, e a
# sequência agora ramifica).

def _projetos_ativos_do_cliente(db, cliente_id, loja_id):
    """Projetos do Cliente que ainda estão em andamento, NESTA loja (LP-39: quem recebeu
    decide a loja — projeto do cliente em outra loja da rede não entra aqui). "Ativo" = status
    fora do conjunto TERMINAL (medido em main.py: perdido/concluido/cancelado); quente/morno/
    frio/em_revisao/fechado/NULL contam. Ordem estável (nome_safe) — a mesma lista precisa
    reaparecer idêntica quando a resposta a P2 for interpretada."""
    from database import Projeto
    return [p for p in (db.query(Projeto)
                          .filter_by(cliente_id=cliente_id, loja_id=loja_id)
                          .order_by(Projeto.nome_safe.asc()).all())
            if (p.status or "") not in _PROJETO_STATUS_TERMINAL]


def _interpretar_p1(texto):
    """'projeto' | 'outro' | None. Aceita número (1/2) ou palavra-chave — mais tolerante que o
    menu de segmentos porque a pergunta é livre, não numerada por catálogo."""
    t = _normalizar_txt(texto)
    if not t:
        return None
    digitos = "".join(c for c in t if c.isdigit())
    if digitos and t.replace(".", "").replace("-", "").replace(")", "").strip() == digitos:
        if digitos == "1":
            return "projeto"
        if digitos == "2":
            return "outro"
        return None
    if "projeto" in t or "obra" in t or "andamento" in t:
        return "projeto"
    if "outro" in t or "assunto" in t:
        return "outro"
    return None


def _texto_p2(projetos):
    linhas = "\n".join("%d. %s" % (i + 1, p.nome_safe.replace("_", " "))
                       for i, p in enumerate(projetos))
    return "Você tem mais de um projeto com a gente. Qual deles é?\n%s" % linhas


def _interpretar_p2(texto, projetos):
    """O Projeto escolhido, ou None — mesma lista, na MESMA ordem que gerou `_texto_p2`
    (recalculada fresca a cada chamada, nunca guardada em dialogo_json — mesmo espírito de
    `opcoes_pergunta`, que também não persiste o menu que já mandou)."""
    t = _normalizar_txt(texto)
    if not t or not projetos:
        return None
    digitos = "".join(c for c in t if c.isdigit())
    if digitos and t.replace(".", "").replace("-", "").replace(")", "").strip() == digitos:
        n = int(digitos)
        if 1 <= n <= len(projetos):
            return projetos[n - 1]
        return None
    for p in projetos:
        if t == _normalizar_txt(p.nome_safe.replace("_", " ")):
            return p
    return None


def _texto_p3(nome_consultor):
    return ("Seu consultor é %s, certo? Responda com o NÚMERO:\n1. Sim\n2. Não"
            % (nome_consultor or "o consultor do seu projeto"))


def _interpretar_p3(texto):
    """True (sim) | False (não) | None."""
    t = _normalizar_txt(texto)
    if not t:
        return None
    digitos = "".join(c for c in t if c.isdigit())
    if digitos and t.replace(".", "").replace("-", "").replace(")", "").strip() == digitos:
        if digitos == "1":
            return True
        if digitos == "2":
            return False
        return None
    if t in ("sim", "s", "yes", "isso", "correto", "certo"):
        return True
    if t in ("nao", "n", "no"):
        return False
    return None


def _dialogo_salvar(entrada, dialogo):
    entrada.dialogo_json = json.dumps(dialogo, ensure_ascii=False)


def _dialogo_falhar(db, entrada, dialogo, texto_pergunta):
    """Resposta não reconhecida no estado atual (TAREFA-A, item 4 — mesma regra de sempre:
    reformula UMA vez, agora por ESTADO). Primeira falha neste estado → reenvia a MESMA
    pergunta, com um pedido de desculpas na frente; segunda falha → não reenvia nada, a entrada
    segue 'pendente' até a varredura de 2min vencer (item 5, vale em qualquer estado)."""
    if dialogo.get("reformulado"):
        _dialogo_salvar(entrada, dialogo)
        db.flush()
        return
    dialogo["reformulado"] = True
    _dialogo_salvar(entrada, dialogo)
    _enviar_texto_triagem(db, entrada, "Desculpe, não entendi sua resposta 🙏 " + texto_pergunta)
    db.flush()


def _dialogo_ir_para_segmento(db, entrada, dialogo):
    """'Outro assunto' (ou 0 projetos ativos, que é 'outro assunto' por definição — item 2 da
    regra) → o menu de segmentos de sempre. Não vira Lead: já é Cliente (item 3)."""
    dialogo["estado"] = "aguardando_segmento"
    dialogo.pop("reformulado", None)
    _dialogo_salvar(entrada, dialogo)
    corpo, _ops = montar_pergunta_triagem(db, entrada.loja_id)
    _enviar_texto_triagem(db, entrada, corpo)
    db.flush()
    return None


def _dialogo_enviar_p2(db, entrada, dialogo, projetos):
    dialogo["estado"] = "aguardando_projeto"
    dialogo.pop("reformulado", None)
    _dialogo_salvar(entrada, dialogo)
    _enviar_texto_triagem(db, entrada, _texto_p2(projetos))
    db.flush()
    return None


def _dialogo_projeto_definido(db, entrada, dialogo, projeto):
    """Projeto identificado (1 ativo, ou escolhido em P2) — item 4: COM consultor, pergunta P3
    e espera confirmação; SEM consultor, não há o que confirmar — vai direto pro ramo do
    comercial (retorna "comercial" já, resolvido)."""
    dialogo["projeto"] = projeto.nome_safe
    dialogo.pop("reformulado", None)
    if not projeto.criado_por_id:
        entrada.segmento_sugerido = "comercial"
        _dialogo_salvar(entrada, dialogo)
        db.flush()
        return "comercial"
    from database import Usuario
    consultor = db.get(Usuario, projeto.criado_por_id)
    dialogo["estado"] = "aguardando_consultor"
    dialogo["consultor_usuario_id"] = projeto.criado_por_id
    _dialogo_salvar(entrada, dialogo)
    _enviar_texto_triagem(db, entrada, _texto_p3(consultor.nome if consultor else None))
    db.flush()
    return None


def _registrar_resposta_dialogo(db, entrada, texto, dialogo):
    """Interpreta a resposta conforme `dialogo["estado"]`. Retorna o segmento a materializar
    (ou o sentinela `SEGMENTO_PROJETO_DEFINIDO`) quando resolvido, `None` enquanto ainda
    espera (reformulada ou não). Não commita — `registrar_resposta_triagem` decide."""
    estado = dialogo.get("estado")

    if estado == "aguardando_reconhecimento":
        resp = _interpretar_p1(texto)
        if resp is None:
            _dialogo_falhar(db, entrada, dialogo, _texto_p1())
            return None
        if resp == "outro":
            return _dialogo_ir_para_segmento(db, entrada, dialogo)
        cli = (_cliente_por_telefone(db, entrada.remetente) if entrada.meio == "whatsapp"
               else _cliente_por_email(db, entrada.remetente))
        projetos = _projetos_ativos_do_cliente(db, cli.id, entrada.loja_id) if cli else []
        if not projetos:
            return _dialogo_ir_para_segmento(db, entrada, dialogo)
        if len(projetos) == 1:
            return _dialogo_projeto_definido(db, entrada, dialogo, projetos[0])
        return _dialogo_enviar_p2(db, entrada, dialogo, projetos)

    if estado == "aguardando_projeto":
        cli = (_cliente_por_telefone(db, entrada.remetente) if entrada.meio == "whatsapp"
               else _cliente_por_email(db, entrada.remetente))
        projetos = _projetos_ativos_do_cliente(db, cli.id, entrada.loja_id) if cli else []
        escolhido = _interpretar_p2(texto, projetos)
        if escolhido is None:
            _dialogo_falhar(db, entrada, dialogo, _texto_p2(projetos))
            return None
        return _dialogo_projeto_definido(db, entrada, dialogo, escolhido)

    if estado == "aguardando_consultor":
        resp = _interpretar_p3(texto)
        if resp is None:
            from database import Usuario
            consultor = db.get(Usuario, dialogo.get("consultor_usuario_id"))
            _dialogo_falhar(db, entrada, dialogo, _texto_p3(consultor.nome if consultor else None))
            return None
        if resp is True:
            entrada.segmento_sugerido = SEGMENTO_PROJETO_DEFINIDO
            _dialogo_salvar(entrada, dialogo)
            db.flush()
            return SEGMENTO_PROJETO_DEFINIDO
        entrada.segmento_sugerido = "comercial"                # "não" → ramo do comercial
        _dialogo_salvar(entrada, dialogo)
        db.flush()
        return "comercial"

    if estado == "aguardando_segmento":
        ops = opcoes_pergunta(db, entrada.loja_id)
        seg = interpretar_resposta_triagem(texto, ops)
        if seg is None:
            corpo, _ops = montar_pergunta_triagem(db, entrada.loja_id)
            _dialogo_falhar(db, entrada, dialogo, corpo)
            return None
        entrada.segmento_sugerido = seg
        _dialogo_salvar(entrada, dialogo)
        rotulo = next((o["rotulo"] for o in ops if o["segmento"] == seg), seg)
        _enviar_texto_triagem(db, entrada,
                              "Perfeito! ✅ Encaminhei você para %s — em instantes alguém "
                              "da equipe continua o atendimento por aqui." % rotulo)
        db.flush()
        return seg

    # Estado desconhecido/corrompido nunca deveria acontecer — trata como "outro assunto" pra
    # nunca travar o contato (mesma filosofia de "mensagem nenhuma é descartada em silêncio").
    return _dialogo_ir_para_segmento(db, entrada, dialogo)


def registrar_resposta_triagem(db, entrada, texto):
    """RF-09: interpreta a resposta do contato que JÁ está na fila.

    TAREFA-A (docs/db/TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md): quando `entrada.dialogo_json` está
    preenchido (Cliente cadastrado NESTA loja — ver `processar_entrada`), a interpretação passa
    inteira por `_registrar_resposta_dialogo` (P1 → P2/P3/menu). `dialogo_json is None` (número
    desconhecido, ou entrada anterior a esta tarefa) é o fluxo de HOJE, inalterado abaixo:
    reconheceu → grava `segmento_sugerido` + confirma; não reconheceu → anexa o texto (nada se
    descarta) e, se ainda não tinha reformulado (`ja_reformulou`), reformula UMA vez; na segunda
    falha, o robô para — a entrada segue 'pendente' (listar_fila/triagem_listar já a mostram),
    pra um humano resolver (decisão 18/09/2026, TAREFA_TRIAGEM_E_CONTADOR.md Item 1). A PRIMEIRA
    mensagem de um contato nunca passa por aqui — ela cria a `TriagemEntrada` e recebe a
    pergunta original (`enviar_pergunta_triagem`/`enviar_reconhecimento_cliente`); só uma
    RESPOSTA que não casou conta como falha. Retorna o segmento (ou o sentinela
    `SEGMENTO_PROJETO_DEFINIDO`) ou None."""
    _texto = (texto or "").strip()
    if entrada.segmento_sugerido:                      # já escolhido antes: só anexa
        entrada.texto = ((entrada.texto or "") + "\n" + _texto).strip()
        db.flush()
        return entrada.segmento_sugerido
    dialogo = json.loads(entrada.dialogo_json) if entrada.dialogo_json else None
    if dialogo is not None:
        entrada.texto = ((entrada.texto or "") + "\n" + _texto).strip()
        db.flush()
        return _registrar_resposta_dialogo(db, entrada, _texto, dialogo)
    ops = opcoes_pergunta(db, entrada.loja_id)
    seg = interpretar_resposta_triagem(_texto, ops)
    if seg:
        entrada.segmento_sugerido = seg
        rotulo = next((o["rotulo"] for o in ops if o["segmento"] == seg), seg)
        _enviar_texto_triagem(db, entrada,
                              "Perfeito! ✅ Encaminhei você para %s — em instantes alguém "
                              "da equipe continua o atendimento por aqui." % rotulo)
    else:
        entrada.texto = ((entrada.texto or "") + "\n" + _texto).strip()
        if not ja_reformulou(db, entrada):
            _enviar_texto_triagem(db, entrada, _texto_reformulacao_triagem(ops))
    db.flush()
    return seg

