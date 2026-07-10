"""mod_folha.py — Folha de Pagamento (Modulos_Orizon_v10, §2.1). MOTOR de cálculo, não digitação.

Parte fixa: da remuneração do cadastro do Funcionário. Parte variável: soma das vendas fechadas do
consultor no período (Comercial, valor líquido) × % da faixa de meta atingida (Config → Comissão de
Vendas). Despesa lançada nas contas 5.3 já existentes (Comissão de Vendedor / Salários de Vendas).
Mesma lógica de auto-constituição já usada em Provisões.
"""
from datetime import datetime

import mod_contabil
import mod_provisoes
from database import Funcionario, Projeto, Orcamento, FolhaPagamento

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


def calcular_folha(db, loja_id, funcionario, competencia, cfg):
    """Calcula (parte_fixa, vendas_liq, faixa_pct, parte_variavel, total) — nada digitado."""
    fixa = float(funcionario.remuneracao_fixa or 0.0)
    vendas_liq = 0.0
    pct = 0.0
    variavel = 0.0
    if (funcionario.remuneracao_tipo or "") == "fixa_variavel":
        vendas_liq = vendas_liquido_consultor(db, loja_id, funcionario.usuario_id, competencia)
        pct = mod_provisoes.resolver_comissao_venda(cfg, vendas_liq, 0.0)   # % da faixa atingida
        variavel = round(vendas_liq * pct / 100.0, 2)
    return {"parte_fixa": round(fixa, 2), "vendas_liq": vendas_liq, "faixa_pct": pct,
            "parte_variavel": variavel, "total": round(fixa + variavel, 2)}


def gerar_folha(db, loja_id, competencia, cfg):
    """Gera/atualiza a folha do período — um registro por Funcionário ATIVO. Idempotente por
    (funcionario, competencia); folha já PAGA não é recalculada."""
    out = []
    for f in db.query(Funcionario).filter_by(loja_id=loja_id, status="ativo").all():
        reg = db.query(FolhaPagamento).filter_by(funcionario_id=f.id, competencia=competencia).first()
        if reg is None:
            reg = FolhaPagamento(loja_id=loja_id, funcionario_id=f.id, competencia=competencia)
            db.add(reg)
        if reg.status == "paga":
            out.append(reg); continue
        c = calcular_folha(db, loja_id, f, competencia, cfg)
        reg.parte_fixa = c["parte_fixa"]; reg.vendas_liq = c["vendas_liq"]; reg.faixa_pct = c["faixa_pct"]
        reg.parte_variavel = c["parte_variavel"]; reg.total = c["total"]; reg.status = "aberta"
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
    return {"id": reg.id, "funcionario_id": reg.funcionario_id, "funcionario": (f.nome if f else ""),
            "competencia": reg.competencia, "parte_fixa": reg.parte_fixa, "vendas_liq": reg.vendas_liq,
            "faixa_pct": reg.faixa_pct, "parte_variavel": reg.parte_variavel, "total": reg.total,
            "status": reg.status, "pagamento": _pagamento_str(f)}


def listar(db, loja_id, competencia):
    regs = (db.query(FolhaPagamento)
            .filter_by(loja_id=loja_id, competencia=competencia)
            .order_by(FolhaPagamento.id.asc()).all())
    itens = [serialize(db, r) for r in regs]
    return {"competencia": competencia, "itens": itens,
            "total_fixa": round(sum(x["parte_fixa"] or 0 for x in itens), 2),
            "total_variavel": round(sum(x["parte_variavel"] or 0 for x in itens), 2),
            "total_geral": round(sum(x["total"] or 0 for x in itens), 2)}
