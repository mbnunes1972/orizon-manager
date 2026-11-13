"""mod_expedicao.py — módulo de domínio Expedição (Modulos_Orizon_v5, módulo 7).

CicloLogistico: estado agregado do pedido produzido até o cliente. Referências por ID a
Projetos/Estoque/Fiscal — NUNCA duplica dado. Kanban por status_atual; prazos (planejado) entram
uma vez na criação; datas (realizado) são pré-preenchidas com hoje ao mover o card (editáveis).
"""
from datetime import date, datetime

from database import CicloLogistico, CicloLogisticoTransicao

# Estágios do Kanban = valores de status_atual, na ordem (Diagramacao_v5 §1.4).
STATUS = ["Pedido Enviado", "Em Produção", "Aguardando Recebimento",
          "Recebido no Depósito", "NFe Emitida", "Em Trânsito", "Entregue"]
STATUS_INICIAL = STATUS[0]

CAMPOS_PRAZO     = ["prazo_producao", "prazo_saida", "prazo_recebimento", "prazo_entrega"]
CAMPOS_REALIZADO = ["data_producao", "data_saida", "data_recebimento", "data_entrega"]

# Ao ENTRAR num status, estes campos "Realizado" são pré-preenchidos com hoje (editáveis antes de
# confirmar). Só há 4 pares Planejado/Realizado (Diagramacao_v5 §1.4); "NFe Emitida" e "Em Trânsito"
# são intermediários e não capturam prazo. Decisão documentada: produção concluída e saída da fábrica
# são registradas juntas ao entrar em "Aguardando Recebimento" (não há status próprio de "saída").
REALIZADO_AO_ENTRAR = {
    "Aguardando Recebimento": ["data_producao", "data_saida"],
    "Recebido no Depósito":   ["data_recebimento"],
    "Entregue":               ["data_entrega"],
}
# Prazo planejado relevante por status, para o badge de atraso ("data planejada da etapa atual").
PRAZO_POR_STATUS = {
    "Pedido Enviado":         "prazo_producao",
    "Em Produção":            "prazo_producao",
    "Aguardando Recebimento": "prazo_recebimento",
    "Recebido no Depósito":   "prazo_entrega",
    "NFe Emitida":            "prazo_entrega",
    "Em Trânsito":            "prazo_entrega",
    "Entregue":               None,
}


def parse_date(s):
    """'YYYY-MM-DD' -> date, ou None."""
    if not s:
        return None
    if isinstance(s, date):
        return s
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _iso(d):
    return d.isoformat() if d else None


def esta_atrasado(card, hoje=None):
    """True se a data planejada da etapa atual já passou e o pedido não foi entregue."""
    hoje = hoje or date.today()
    if card.status_atual == "Entregue":
        return False
    campo = PRAZO_POR_STATUS.get(card.status_atual)
    prazo = getattr(card, campo, None) if campo else None
    return bool(prazo and prazo < hoje)


def registrar_transicao(db, card, de, para, usuario_id, quando=None):
    db.add(CicloLogisticoTransicao(ciclo_logistico_id=card.id, de_status=de,
                                   para_status=para, usuario_id=usuario_id,
                                   quando=quando or datetime.utcnow()))


def criar_ciclo(db, loja_id, projeto_nome, numero_pedido, prazos, usuario_id, quando=None):
    """Cria o card no status inicial. `prazos` = dict com CAMPOS_PRAZO ('YYYY-MM-DD' ou date)."""
    card = CicloLogistico(loja_id=loja_id, projeto_nome=projeto_nome,
                          numero_pedido=(numero_pedido or None), status_atual=STATUS_INICIAL,
                          criado_em=quando or datetime.utcnow(), criado_por_id=usuario_id)
    for campo in CAMPOS_PRAZO:
        setattr(card, campo, parse_date((prazos or {}).get(campo)))
    db.add(card)
    db.flush()
    registrar_transicao(db, card, None, STATUS_INICIAL, usuario_id, quando)
    return card


def mover(db, card, novo_status, realizados, usuario_id, quando=None):
    """Move o card para `novo_status`, aplicando as datas 'Realizado' informadas (já editadas na tela).
    Retorna (ok, erro). Registra a transição no histórico."""
    if novo_status not in STATUS:
        return False, "Status inválido."
    de = card.status_atual
    for campo, valor in (realizados or {}).items():
        if campo in CAMPOS_REALIZADO:
            setattr(card, campo, parse_date(valor))
    if novo_status != de:
        card.status_atual = novo_status
        registrar_transicao(db, card, de, novo_status, usuario_id, quando)
    return True, None


def atualizar_detalhe(db, card, dados):
    """Atualiza prazos e transporte a partir do painel de Detalhe (não muda status)."""
    for campo in CAMPOS_PRAZO + CAMPOS_REALIZADO:
        if campo in dados:
            setattr(card, campo, parse_date(dados.get(campo)))
    for campo in ("transportadora", "cte", "rastreio", "numero_pedido"):
        if campo in dados:
            setattr(card, campo, (dados.get(campo) or None))


def card_kanban(card, cliente_nome, hoje=None):
    """Payload leve p/ o card no Kanban (só leitura): projeto/cliente + pedido + atraso."""
    return {
        "id": card.id,
        "projeto_nome": card.projeto_nome,
        "cliente": cliente_nome or "",
        "numero_pedido": card.numero_pedido or "",
        "status_atual": card.status_atual,
        "atrasado": esta_atrasado(card, hoje),
    }


def card_detalhe(db, card, cliente_nome):
    """Payload completo p/ o painel de Detalhe: identificação, prazos, transporte, histórico."""
    trans = (db.query(CicloLogisticoTransicao)
             .filter_by(ciclo_logistico_id=card.id)
             .order_by(CicloLogisticoTransicao.id.asc()).all())
    return {
        "id": card.id,
        "projeto_nome": card.projeto_nome,
        "cliente": cliente_nome or "",
        "numero_pedido": card.numero_pedido or "",
        "status_atual": card.status_atual,
        "prazos": {c: _iso(getattr(card, c)) for c in CAMPOS_PRAZO},
        "realizados": {c: _iso(getattr(card, c)) for c in CAMPOS_REALIZADO},
        "transporte": {"transportadora": card.transportadora or "",
                       "cte": card.cte or "", "rastreio": card.rastreio or ""},
        "nfe_id": card.nfe_id,
        "historico": [{"de": t.de_status, "para": t.para_status,
                       "usuario_id": t.usuario_id,
                       "quando": t.quando.isoformat() if t.quando else None} for t in trans],
    }
