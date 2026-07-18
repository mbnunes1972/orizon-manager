"""mod_comissao.py — Comissão por papel (Fase 4). Ao concluir uma etapa operacional, prepara a
comissão do executor na folha do mês de conclusão. Base = Σ order_total dos ambientes atribuídos no
Mapa (projeto inteiro se atribuição = NULL) × % da Função. Itens em comissao_folha, somados na Folha."""
import json

import mod_folha
from database import (ComissaoFolha, Funcao, Funcionario, PoolAmbiente, AtribuicaoAmbiente, Orcamento)

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


def _ambientes_da_base(db, projeto_nome, papel, funcionario_id):
    """Ambientes (PoolAmbiente) que compõem a base de (papel, funcionario) no Mapa. Atribuição
    projeto-inteiro (pool_ambiente_id NULL) → TODOS os ambientes do projeto."""
    atrs = (db.query(AtribuicaoAmbiente)
            .filter_by(projeto_nome=projeto_nome, papel=papel, funcionario_id=funcionario_id).all())
    if not atrs:
        return []
    if any(a.pool_ambiente_id is None for a in atrs):     # projeto inteiro
        return db.query(PoolAmbiente).filter_by(projeto_id=projeto_nome).all()
    ids = {a.pool_ambiente_id for a in atrs if a.pool_ambiente_id}
    return db.query(PoolAmbiente).filter(PoolAmbiente.id.in_(ids)).all() if ids else []


def _valor_liquido_projeto(db, projeto_nome):
    """Valor Líquido da venda do projeto = maior valor_liquido (ou valor_total) entre seus orçamentos."""
    orcs = db.query(Orcamento).filter_by(projeto_id=projeto_nome).all()
    if not orcs:
        return 0.0
    return round(max((o.valor_liquido or o.valor_total or 0.0) for o in orcs), 2)


def _liq_e_bruto(db, projeto_nome):
    """(valor_liquido do projeto, Σ preço-de-venda bruto (budget_total) de TODOS os ambientes)."""
    net = _valor_liquido_projeto(db, projeto_nome)
    todos = db.query(PoolAmbiente).filter_by(projeto_id=projeto_nome).all()
    bruto = round(sum(p.budget_total or 0.0 for p in todos), 2)
    return net, bruto


def base_ambientes(db, projeto_nome, papel, funcionario_id):
    """Base = Valor Líquido da venda do projeto RATEADO pela fatia de venda (budget_total) dos ambientes
    atribuídos a (papel, funcionario). Projeto inteiro → base = Valor Líquido do projeto."""
    pools = _ambientes_da_base(db, projeto_nome, papel, funcionario_id)
    if not pools:
        return 0.0
    net, bruto = _liq_e_bruto(db, projeto_nome)
    if bruto <= 0:
        return 0.0
    atribuido = sum(p.budget_total or 0.0 for p in pools)
    return round(net * atribuido / bruto, 2)


def base_detalhe(db, item):
    """Composição da base de um item de PAPEL: [{nome, valor}] = fatia LÍQUIDA de cada ambiente atribuído
    (valor_liquido do projeto × preço-venda do ambiente ÷ preço-venda total)."""
    if item.origem != "papel" or not item.projeto_nome or not item.papel:
        return []
    pools = _ambientes_da_base(db, item.projeto_nome, item.papel, item.funcionario_id)
    if not pools:
        return []
    net, bruto = _liq_e_bruto(db, item.projeto_nome)
    if bruto <= 0:
        return [{"nome": p.nome_exibicao, "valor": 0.0} for p in pools]
    return [{"nome": p.nome_exibicao, "valor": round(net * (p.budget_total or 0.0) / bruto, 2)} for p in pools]


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
