"""mod_assistencias.py — módulo de domínio Assistências (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6).

Atendimento pós-execução com DUAS dimensões independentes por caso:
  - sub_tipo: Assistência Montagem × Assistência Pós-Conclusão
  - tipo_custo: Paga (cliente) · Loja · Fábrica — DERIVADO do motivo (tabela abaixo)

Realizar um caso dispara o lançamento contábil (motor v7 §6):
  Loja    -> realiza a Provisão de Assistência Técnica (execucao_assistencia)
  Fábrica -> realiza a Provisão de Garantia (execucao_reparo_garantia) + relatório "a cobrar da fábrica"
  Paga    -> gera venda ao cliente (venda_assistencia), sem tocar provisão
"""
from datetime import datetime

import mod_contabil
from database import AssistenciaCaso

SUB_TIPOS = {"montagem": "Assistência Montagem", "pos_conclusao": "Assistência Pós-Conclusão"}

# motivo -> (rótulo, tipo_custo). Tabela do doc (Modulos_Orizon_v5 módulo 10 / Financeiro v7 §6).
MOTIVOS = {
    "alteracao_projeto":  ("Alteração de projeto solicitada pelo cliente", "paga"),
    "complemento":        ("Complemento", "paga"),
    "erro_projeto":       ("Erro de projeto", "loja"),
    "erro_montagem":      ("Erro de montagem", "loja"),
    "defeito_fabricacao": ("Defeito de fabricação", "fabrica"),
    "empenamento":        ("Empenamento / mau funcionamento", "fabrica"),
}
TIPO_CUSTO_LABEL = {"paga": "Paga (cliente)", "loja": "Loja", "fabrica": "Fábrica"}

# tipo_custo -> evento contábil (mod_contabil.EVENTOS)
EVENTO_POR_CUSTO = {
    "loja":    "execucao_assistencia",
    "fabrica": "execucao_reparo_garantia",
    "paga":    "venda_assistencia",
}


def tipo_custo_de(motivo):
    m = MOTIVOS.get(motivo)
    return m[1] if m else None


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def criar_caso(db, loja_id, projeto_nome, sub_tipo, motivo, descricao, valor, usuario_id, quando=None):
    tc = tipo_custo_de(motivo)
    if sub_tipo not in SUB_TIPOS:
        raise ValueError("sub_tipo inválido")
    if tc is None:
        raise ValueError("motivo inválido")
    caso = AssistenciaCaso(loja_id=loja_id, projeto_nome=(projeto_nome or None), sub_tipo=sub_tipo,
                           motivo=motivo, tipo_custo=tc, descricao=(descricao or None),
                           valor=_num(valor), status="aberto",
                           criado_em=quando or datetime.utcnow(), criado_por_id=usuario_id)
    db.add(caso)
    db.flush()
    return caso


def realizar_caso(db, owner_tipo, owner_id, caso, valor=None, quando=None):
    """Executa/conclui o caso: posta o lançamento conforme o tipo de custo e marca 'realizado'.
    Idempotente por ref ('assist:<id>'). Retorna (ok, erro)."""
    if caso.status == "realizado":
        return True, None
    nv = _num(valor)
    if nv is not None:
        caso.valor = nv
    if not caso.valor or caso.valor <= 0:
        return False, "Informe o valor do caso antes de realizar."
    evento = EVENTO_POR_CUSTO[caso.tipo_custo]
    ref = "assist:%d" % caso.id
    motivo = caso.motivo if caso.tipo_custo == "fabrica" else None   # §6.2: motivo carimba o reparo em garantia
    mod_contabil.registrar_evento(db, owner_tipo, owner_id, evento, caso.valor,
                                  projeto_id=caso.projeto_nome, ref=ref, motivo=motivo)
    caso.status = "realizado"
    caso.ref_lancamento = ref
    caso.realizado_em = quando or datetime.utcnow()
    return True, None


def serialize(caso):
    return {
        "id": caso.id, "projeto_nome": caso.projeto_nome or "",
        "sub_tipo": caso.sub_tipo, "sub_tipo_label": SUB_TIPOS.get(caso.sub_tipo, caso.sub_tipo),
        "motivo": caso.motivo, "motivo_label": (MOTIVOS.get(caso.motivo) or ["", ""])[0],
        "tipo_custo": caso.tipo_custo, "tipo_custo_label": TIPO_CUSTO_LABEL.get(caso.tipo_custo, caso.tipo_custo),
        "descricao": caso.descricao or "", "valor": caso.valor,
        "status": caso.status, "reembolsado_fabrica": bool(caso.reembolsado_fabrica),
    }


def listar(db, loja_id, tipo=None):
    q = db.query(AssistenciaCaso).filter_by(loja_id=loja_id)
    if tipo in ("paga", "loja", "fabrica"):
        q = q.filter(AssistenciaCaso.tipo_custo == tipo)
    return [serialize(c) for c in q.order_by(AssistenciaCaso.id.desc()).all()]


def a_cobrar_fabrica(db, loja_id):
    """Relatório 'a cobrar da fábrica' (v7 §6.2): casos de tipo Fábrica ainda não reembolsados, com o
    custo real documentado. NÃO é Contas a Receber formal — controle p/ negociação com a fábrica."""
    casos = [c for c in db.query(AssistenciaCaso).filter_by(loja_id=loja_id, tipo_custo="fabrica").all()
             if not c.reembolsado_fabrica]
    return {"total": round(sum(c.valor or 0 for c in casos), 2), "qtd": len(casos),
            "itens": [serialize(c) for c in casos]}


def meta():
    return {
        "sub_tipos": [{"id": k, "label": v} for k, v in SUB_TIPOS.items()],
        "motivos": [{"id": k, "label": v[0], "tipo_custo": v[1]} for k, v in MOTIVOS.items()],
        "tipo_custo_label": TIPO_CUSTO_LABEL,
    }
