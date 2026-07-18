"""mod_comissao.py — Comissão por papel (Fase 4). Ao concluir uma etapa operacional, prepara a
comissão do executor na folha do mês de conclusão. Base = Σ order_total dos ambientes atribuídos no
Mapa (projeto inteiro se atribuição = NULL) × % da Função. Itens em comissao_folha, somados na Folha."""
import json

import mod_folha
from database import (ComissaoFolha, Funcao, Funcionario, PoolAmbiente, AtribuicaoAmbiente)

# Etapa operacional → papel do Mapa (só estas geram comissão de papel).
PAPEL_POR_ETAPA = {
    "10": "medicao",
    "11": "projeto_executivo", "11a": "projeto_executivo", "11b": "projeto_executivo",
    "11c": "projeto_executivo", "11d": "projeto_executivo", "11e": "projeto_executivo",
    "17": "montagem",
    "18": "assistencia",
}


def papel_da_etapa(codigo):
    return PAPEL_POR_ETAPA.get(str(codigo))


def base_ambientes(db, projeto_nome, papel, funcionario_id):
    """Σ order_total dos ambientes atribuídos a (papel, funcionario) no Mapa. Atribuição projeto-inteiro
    (pool_ambiente_id NULL) → Σ de TODOS os ambientes do projeto."""
    atrs = (db.query(AtribuicaoAmbiente)
            .filter_by(projeto_nome=projeto_nome, papel=papel, funcionario_id=funcionario_id).all())
    if not atrs:
        return 0.0
    if any(a.pool_ambiente_id is None for a in atrs):     # projeto inteiro
        pools = db.query(PoolAmbiente).filter_by(projeto_id=projeto_nome).all()
        return round(sum(p.order_total or 0.0 for p in pools), 2)
    ids = {a.pool_ambiente_id for a in atrs}
    pools = db.query(PoolAmbiente).filter(PoolAmbiente.id.in_(ids)).all()
    return round(sum(p.order_total or 0.0 for p in pools), 2)


def _pct_funcao(funcao, base):
    if not funcao or not funcao.comissao_json:
        return 0.0
    try:
        com = json.loads(funcao.comissao_json)
    except (ValueError, TypeError):
        return 0.0
    return mod_folha._resolver_pct_funcao(com, base)


def _executores_do_papel(db, projeto_nome, papel):
    """funcionario_ids DISTINTOS atribuídos a esse papel no Mapa (atribuicoes_ambiente)."""
    rows = (db.query(AtribuicaoAmbiente.funcionario_id)
            .filter_by(projeto_nome=projeto_nome, papel=papel)
            .filter(AtribuicaoAmbiente.funcionario_id.isnot(None)).all())
    out = []
    for (fid,) in rows:
        if fid not in out:
            out.append(fid)
    return out


def preparar_comissao_etapa(db, loja_id, etapa):
    """Prepara a(s) comissão(ões) do(s) executor(es) da etapa concluída. O(s) executor(es) vêm do MAPA
    de Atribuições (atribuicoes_ambiente) por papel; se o Mapa estiver vazio, cai no
    responsavel_funcionario_id da etapa. A função (e o % da comissão) vem do próprio Funcionário.
    Idempotente por ref_etapa. Retorna o 1º item criado, ou None."""
    papel = papel_da_etapa(etapa.etapa_codigo)
    if not papel or not etapa.concluido_em:
        return None
    execs = _executores_do_papel(db, etapa.projeto_nome, papel)
    if not execs and etapa.responsavel_funcionario_id:
        execs = [etapa.responsavel_funcionario_id]
    comp = etapa.concluido_em.strftime("%Y-%m")
    itens = []
    for func_id in execs:
        f = db.get(Funcionario, func_id)
        funcao = db.get(Funcao, f.funcao_id) if (f and f.funcao_id) else None
        base = base_ambientes(db, etapa.projeto_nome, papel, func_id)
        pct = _pct_funcao(funcao, base)
        if pct <= 0:                    # função do executor sem comissão → sem item
            continue
        ref = "%s:%s:%d" % (etapa.projeto_nome, etapa.etapa_codigo, func_id)
        item = db.query(ComissaoFolha).filter_by(ref_etapa=ref).first()
        if item is None:
            item = ComissaoFolha(loja_id=loja_id, funcionario_id=func_id, origem="papel", papel=papel,
                                 projeto_nome=etapa.projeto_nome, etapa_codigo=etapa.etapa_codigo, ref_etapa=ref)
            db.add(item)
        if item.status == "confirmado":     # já foi para folha paga — não recalcula
            itens.append(item); continue
        base_ef = item.base_ajustada if item.base_ajustada is not None else base
        item.competencia = comp; item.base = base; item.pct = pct
        item.valor = round(float(base_ef) * pct / 100.0, 2); item.status = "previsto"
        db.flush()
        itens.append(item)
    return itens[0] if itens else None


def cancelar_comissao_etapa(db, projeto_nome, etapa_codigo, funcionario_id):
    """Cancela o item (reabertura de etapa), se não confirmado (folha não paga)."""
    ref = "%s:%s:%d" % (projeto_nome, etapa_codigo, funcionario_id)
    item = db.query(ComissaoFolha).filter_by(ref_etapa=ref).first()
    if item and item.status != "confirmado":
        item.status = "cancelado"; db.flush()
    return item


def editar_item(db, item, base_ajustada):
    """Override manual da base de um item (status != confirmado) e recalcula valor."""
    if item.status == "confirmado":
        return False, "comissão já confirmada"
    item.base_ajustada = float(base_ajustada)
    item.valor = round(float(base_ajustada) * float(item.pct or 0.0) / 100.0, 2)
    db.flush()
    return True, None
