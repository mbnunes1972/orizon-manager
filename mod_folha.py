"""mod_folha.py — Folha de Pagamento (Modulos_Orizon_v10, §2.1). MOTOR de cálculo, não digitação.

Parte fixa: da remuneração do cadastro do Funcionário. Parte variável: soma das vendas fechadas do
consultor no período (Comercial, valor líquido) × % da faixa de meta atingida (Config → Comissão de
Vendas). Despesa lançada nas contas 5.3 já existentes (Comissão de Vendedor / Salários de Vendas).
Mesma lógica de auto-constituição já usada em Provisões.
"""
import json
from datetime import datetime

import mod_contabil
import mod_provisoes
import mod_adiantamento
from database import (Funcionario, Funcao, Projeto, Orcamento, FolhaPagamento, ComissaoFolha,
                      AdiantamentoFuncionario)

_STATUS_VENDA = ("fechado", "convertido")   # projeto considerado "venda fechada"


def vendas_liquido_consultor(db, loja_id, usuario_id, competencia):
    """Σ do valor líquido das vendas FECHADAS no mês `competencia` (AAAA-MM) atribuídas ao consultor
    (projetos_meta.criado_por_id == usuario_id). Por projeto usa o maior valor_liquido dos orçamentos."""
    if not usuario_id:
        return 0.0
    projs = (db.query(Projeto)
             .filter(Projeto.loja_id == loja_id,
                     Projeto.criado_por_id == usuario_id,
                     Projeto.status.in_(_STATUS_VENDA)).all())
    total = 0.0
    for p in projs:
        sa = p.status_at
        if sa is None or sa.strftime("%Y-%m") != competencia:
            continue    # só as fechadas dentro do período
        orcs = db.query(Orcamento).filter_by(projeto_id=p.nome_safe).all()
        if orcs:
            total += max((o.valor_liquido or o.valor_total or 0.0) for o in orcs)
    return round(total, 2)


def _resolver_pct_funcao(com, base):
    """% da comissão de uma função NÃO-consultor, dado o `com` (comissao_json) e a base.
    por_meta=True → resolve pela lista de faixas (venda_ate crescente; None = topo/última).
    por_meta=False → pct fixo."""
    com = com or {}
    if not com.get("por_meta"):
        return round(float(com.get("pct") or 0.0), 4)
    faixas = com.get("faixas") or []
    for fx in faixas:
        ate = fx.get("venda_ate")
        if ate is None or float(base) < float(ate):
            return round(float(fx.get("pct") or 0.0), 4)
    return round(float(faixas[-1].get("pct") or 0.0), 4) if faixas else 0.0


def _beneficios_total(funcao):
    """Σ dos benefícios ATIVOS da função (AT/VA/PS) a partir de beneficios_json."""
    try:
        b = json.loads(funcao.beneficios_json) if funcao and funcao.beneficios_json else {}
    except (ValueError, TypeError):
        b = {}
    total = 0.0
    for k in ("at", "va", "ps"):
        item = b.get(k) or {}
        if item.get("on"):
            total += float(item.get("valor") or 0.0)
    return round(total, 2)


def calcular_folha(db, loja_id, funcionario, competencia, cfg, base_override=None):
    """Calcula a remuneração a partir da FUNÇÃO do funcionário — nada digitado (exceto a base editável).
    Retorna parte_fixa, vendas_liq, base_comissao, faixa_pct, parte_variavel, beneficios, total.
    `base_override` (se não None) força a base da comissão — usado ao editar a base na Folha."""
    funcao = db.get(Funcao, funcionario.funcao_id) if funcionario.funcao_id else None
    fixa = float(funcao.salario_fixo or 0.0) if funcao else 0.0
    comissao_fixa = float(getattr(funcao, "comissao_fixa", 0.0) or 0.0) if funcao else 0.0
    beneficios = _beneficios_total(funcao)
    vendas_liq = 0.0
    base = 0.0
    pct = 0.0
    if funcao and funcao.usa_comissao_vendas:
        vendas_liq = vendas_liquido_consultor(db, loja_id, funcionario.usuario_id, competencia)
        base = vendas_liq if base_override is None else float(base_override)
        pct = mod_provisoes.resolver_comissao_venda(cfg, base, 0.0)   # % da faixa atingida (comissão de vendas da loja)
    elif funcao and funcao.comissao_json:
        try:
            com = json.loads(funcao.comissao_json)
        except (ValueError, TypeError):
            com = {}
        base = float(com.get("base") or 0.0) if base_override is None else float(base_override)
        pct = _resolver_pct_funcao(com, base)
    variavel = round(base * pct / 100.0, 2)
    return {"parte_fixa": round(fixa, 2), "vendas_liq": round(vendas_liq, 2),
            "base_comissao": round(base, 2), "faixa_pct": pct, "parte_variavel": variavel,
            "beneficios": beneficios, "comissao_fixa": round(comissao_fixa, 2),
            "total": round(fixa + variavel + beneficios + comissao_fixa, 2)}


def editar_base(db, loja_id, reg, base, cfg):
    """Reedita a base da comissão de um registro de folha (status != 'paga') e recalcula
    faixa_pct/parte_variavel/total. Parte fixa e benefícios vêm da Função. Retorna (ok, erro)."""
    if reg.status == "paga":
        return False, "folha já paga"
    f = db.get(Funcionario, reg.funcionario_id)
    c = calcular_folha(db, loja_id, f, reg.competencia, cfg, base_override=base)
    reg.parte_fixa = c["parte_fixa"]; reg.base_comissao = c["base_comissao"]
    reg.faixa_pct = c["faixa_pct"]; reg.parte_variavel = c["parte_variavel"]
    reg.beneficios = c["beneficios"]; reg.comissao_fixa = c["comissao_fixa"]; reg.total = c["total"]
    db.flush()
    return True, None


def _total_itens_comissao(db, loja_id, funcionario_id, competencia):
    """Σ valor dos itens de comissão (comissao_folha) do funcionário na competência (exclui cancelados)."""
    itens = (db.query(ComissaoFolha)
             .filter_by(loja_id=loja_id, funcionario_id=funcionario_id, competencia=competencia)
             .filter(ComissaoFolha.status != "cancelado").all())
    return round(sum(float(i.valor or 0.0) for i in itens), 2)


def _upsert_item_venda(db, loja_id, f, competencia, cfg):
    """Consultor: garante um item origem='venda' com a comissão de vendas do mês (idempotente por ref)."""
    funcao = db.get(Funcao, f.funcao_id) if f.funcao_id else None
    if not (funcao and funcao.usa_comissao_vendas):
        return
    base = vendas_liquido_consultor(db, loja_id, f.usuario_id, competencia)
    pct = mod_provisoes.resolver_comissao_venda(cfg, base, 0.0)
    ref = "venda:%d:%s" % (f.id, competencia)
    item = db.query(ComissaoFolha).filter_by(ref_etapa=ref).first()
    if item is None:
        item = ComissaoFolha(loja_id=loja_id, funcionario_id=f.id, competencia=competencia,
                             origem="venda", papel="venda", ref_etapa=ref)
        db.add(item)
    if item.status == "confirmado":
        return
    base_ef = item.base_ajustada if item.base_ajustada is not None else base
    item.competencia = competencia; item.base = base; item.pct = pct
    item.valor = round(base_ef * pct / 100.0, 2); item.status = "previsto"
    db.flush()


def gerar_folha(db, loja_id, competencia, cfg):
    """Gera/atualiza a folha do período — um registro por Funcionário ATIVO. Idempotente por
    (funcionario, competencia); folha já PAGA não é recalculada. A parte variável = Σ itens
    comissao_folha (comissão do Consultor entra como item origem='venda')."""
    out = []
    for f in db.query(Funcionario).filter_by(loja_id=loja_id, status="ativo").all():
        reg = db.query(FolhaPagamento).filter_by(funcionario_id=f.id, competencia=competencia).first()
        if reg is None:
            reg = FolhaPagamento(loja_id=loja_id, funcionario_id=f.id, competencia=competencia)
            db.add(reg)
        if reg.status == "paga":
            out.append(reg); continue
        _upsert_item_venda(db, loja_id, f, competencia, cfg)
        folha_cfg = (cfg or {}).get("folha", {}) or {}
        if folha_cfg.get("adiantamento_oficial_ativo"):   # oficial: 40% do fixo (carteira), auto
            mod_adiantamento.upsert_oficial(db, loja_id, f, competencia,
                                            folha_cfg.get("adiantamento_oficial_pct") or 0.0)
        c = calcular_folha(db, loja_id, f, competencia, cfg)   # fixa + benefícios (variável tratada via itens)
        variavel = _total_itens_comissao(db, loja_id, f.id, competencia)
        reg.parte_fixa = c["parte_fixa"]; reg.vendas_liq = c["vendas_liq"]; reg.faixa_pct = c["faixa_pct"]
        reg.base_comissao = c["base_comissao"]; reg.parte_variavel = variavel
        reg.beneficios = c["beneficios"]; reg.comissao_fixa = c["comissao_fixa"]
        reg.total = round((c["parte_fixa"] or 0.0) + variavel + (c["beneficios"] or 0.0)
                          + (c["comissao_fixa"] or 0.0), 2)
        reg.status = "aberta"
        db.flush()
        out.append(reg)
    return out


def pagar(db, owner_tipo, owner_id, reg):
    """Paga a folha: posta a despesa (fixa→5.3.06, variável→5.3.01) e marca 'paga'. Idempotente por ref.
    Usa os Dados Bancários/PIX já cadastrados (nada redigitado). Retorna (ok, erro)."""
    if reg.status == "paga":
        return True, None
    ref = "folha:%d" % reg.id
    if (reg.parte_fixa or 0) > 0:
        mod_contabil.registrar_evento(db, owner_tipo, owner_id, "folha_fixa", reg.parte_fixa, ref=ref + ":fixa")
    if (reg.parte_variavel or 0) > 0:
        mod_contabil.registrar_evento(db, owner_tipo, owner_id, "folha_variavel", reg.parte_variavel, ref=ref + ":var")
    if (reg.beneficios or 0) > 0:
        mod_contabil.registrar_evento(db, owner_tipo, owner_id, "folha_beneficios", reg.beneficios, ref=ref + ":ben")
    mod_adiantamento.quitar_da_competencia(db, reg.funcionario_id, reg.competencia)   # baixa os adiantamentos abatidos
    reg.status = "paga"; reg.ref_lancamento = ref; reg.pago_em = datetime.utcnow()
    return True, None


def _pagamento_str(f):
    if f is None:
        return ""
    if f.pix:
        return "PIX: " + f.pix
    if f.agencia or f.conta:
        return ("%s Ag %s C/C %s" % (f.banco_nome or "", f.agencia or "", f.conta or "")).strip()
    return ""


def serialize(db, reg):
    f = db.get(Funcionario, reg.funcionario_id)
    itens_com = (db.query(ComissaoFolha)
                 .filter_by(funcionario_id=reg.funcionario_id, competencia=reg.competencia)
                 .filter(ComissaoFolha.status != "cancelado")
                 .order_by(ComissaoFolha.id.asc()).all())
    comissoes = [{"id": i.id, "origem": i.origem, "papel": i.papel, "projeto": i.projeto_nome,
                  "etapa": i.etapa_codigo, "base": i.base, "base_ajustada": i.base_ajustada,
                  "pct": i.pct, "valor": i.valor, "status": i.status} for i in itens_com]
    ads = (db.query(AdiantamentoFuncionario)
           .filter_by(funcionario_id=reg.funcionario_id)
           .order_by(AdiantamentoFuncionario.id.asc()).all())
    adiantamentos = [{"id": a.id, "tipo": a.tipo, "competencia": a.competencia, "valor": a.valor,
                      "abater": bool(a.abater), "competencia_abate": a.competencia_abate,
                      "quitado": bool(a.quitado), "observacao": a.observacao} for a in ads]
    abat = mod_adiantamento.abatimentos_competencia(db, reg.funcionario_id, reg.competencia)
    saldo = mod_adiantamento.saldo_debito(db, reg.funcionario_id)
    liquido = round((reg.total or 0.0) - abat, 2)
    return {"id": reg.id, "funcionario_id": reg.funcionario_id, "funcionario": (f.nome if f else ""),
            "competencia": reg.competencia, "parte_fixa": reg.parte_fixa, "vendas_liq": reg.vendas_liq,
            "base_comissao": reg.base_comissao, "faixa_pct": reg.faixa_pct,
            "parte_variavel": reg.parte_variavel, "beneficios": reg.beneficios,
            "comissao_fixa": reg.comissao_fixa, "total": reg.total,
            "comissoes": comissoes, "adiantamentos": adiantamentos, "abatimentos": abat,
            "liquido_pagar": liquido, "saldo_debito": saldo,
            "status": reg.status, "pagamento": _pagamento_str(f)}


def listar(db, loja_id, competencia):
    regs = (db.query(FolhaPagamento)
            .filter_by(loja_id=loja_id, competencia=competencia)
            .order_by(FolhaPagamento.id.asc()).all())
    itens = [serialize(db, r) for r in regs]
    return {"competencia": competencia, "itens": itens,
            "total_fixa": round(sum(x["parte_fixa"] or 0 for x in itens), 2),
            "total_variavel": round(sum(x["parte_variavel"] or 0 for x in itens), 2),
            "total_beneficios": round(sum(x["beneficios"] or 0 for x in itens), 2),
            "total_liquido": round(sum(x["liquido_pagar"] or 0 for x in itens), 2),
            "total_geral": round(sum(x["total"] or 0 for x in itens), 2)}
