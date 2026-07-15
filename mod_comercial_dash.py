"""mod_comercial_dash.py — métricas do painel **Comercial** (dashboard). View DERIVADA da fonte única
(projetos_meta, orcamentos, contratos, ciclo_etapas), escopada por loja. Não persiste nada; é lida sob
demanda pelo endpoint. Três blocos:
  - **funil de conversão** (marcos do ciclo): total → com Orçamento (etapa 4) → com Contrato (etapa 7);
  - **carteira** por status (projetos em aberto: quente/morno/frio);
  - **volume** contratado (contratos assinados × valor do orçamento contratado) + ticket médio.
"""
import mod_ciclo
from database import Projeto, Orcamento, Contrato, CicloEtapa

_ETAPA_ORCAMENTO = "4"   # Orçamento aprovado (marco do funil)
_ETAPA_CONTRATO = "7"    # Contrato (marco do funil)
_STATUS_ABERTO = ("quente", "morno", "frio")
_CONTRATO_ASSINADO = ("assinado", "vigente")


def _pct(parte, total):
    return round((parte / total) * 100, 1) if total else 0.0


def dashboard_comercial(db, loja_id):
    """Métricas do dashboard Comercial para a `loja_id` (None = todas as lojas). Retorna
    {funil, carteira, volume} — números puros, prontos p/ render."""
    q_proj = db.query(Projeto)
    q_cont = db.query(Contrato)
    if loja_id:
        q_proj = q_proj.filter(Projeto.loja_id == loja_id)
        q_cont = q_cont.filter(Contrato.loja_id == loja_id)
    projs = q_proj.all()
    nomes = [p.nome_safe for p in projs]

    # ciclo: etapas CONCLUÍDAS por projeto (marcos do funil)
    concl = {}
    if nomes:
        for e in db.query(CicloEtapa).filter(CicloEtapa.projeto_nome.in_(nomes)).all():
            if e.status in mod_ciclo.STATUS_CONCLUSIVOS:
                concl.setdefault(e.projeto_nome, set()).add(e.etapa_codigo)

    total = len(projs)
    com_orc = sum(1 for n in nomes if _ETAPA_ORCAMENTO in concl.get(n, ()))
    com_contrato = sum(1 for n in nomes if _ETAPA_CONTRATO in concl.get(n, ()))

    # carteira: projetos em aberto por status
    carteira = {s: 0 for s in _STATUS_ABERTO}
    for p in projs:
        if p.status in carteira:
            carteira[p.status] += 1

    # volume contratado: contratos assinados → valor do orçamento contratado
    assinados = [c for c in q_cont.all() if c.status in _CONTRATO_ASSINADO]
    volume = 0.0
    for c in assinados:
        orc = db.get(Orcamento, c.orcamento_id) if c.orcamento_id else None
        if orc:
            volume += orc.valor_total or 0.0
    n_contratos = len(assinados)
    ticket = (volume / n_contratos) if n_contratos else 0.0

    return {
        "funil": {"total": total, "com_orcamento": com_orc, "com_contrato": com_contrato,
                  "conv_orcamento_pct": _pct(com_orc, total),
                  "conv_contrato_pct": _pct(com_contrato, total)},
        "carteira": {"por_status": carteira, "total_aberto": sum(carteira.values())},
        "volume": {"contratado": round(volume, 2), "n_contratos": n_contratos,
                   "ticket_medio": round(ticket, 2)},
    }
