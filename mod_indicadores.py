# -*- coding: utf-8 -*-
"""mod_indicadores.py — Snapshot de indicadores financeiros/comerciais (PURO, sem I/O).

Fórmulas clássicas sobre os agregados que o mod_contabil já produz (balanco()/dre()) e sobre
contagens comerciais levantadas pelo composition root (main.py). Toda divisão tem guarda:
denominador zero → None (a tela renderiza "—", nunca um número enganoso).

Adaptações ao plano de contas da casa (documentadas):
- Liquidez AJUSTADA: exclui do ativo circulante os DIFERIDOS (1.1.05 impostos a apropriar +
  1.1.06 custos a apropriar) — não são conversíveis em caixa; a liquidez corrente clássica os
  contaria e inflaria o índice.
- PMP usa como "fornecedores" o 2.1.01 (Fornecedores a Pagar) + 2.1.04.06 (Provisão de Custo de
  Fábrica) — no fluxo da casa, o "a pagar à fábrica" vive na provisão até o pagamento.
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _div(num, den, nd=4):
    den = _f(den)
    if abs(den) < 0.005:
        return None
    return round(_f(num) / den, nd)


def liquidez(ativo_circ, passivo_circ, caixa, diferidos):
    """Índices de liquidez + capital de giro líquido."""
    ac, pc = _f(ativo_circ), _f(passivo_circ)
    return {
        "corrente": _div(ac, pc),
        "imediata": _div(caixa, pc),
        "ajustada": _div(ac - _f(diferidos), pc),   # sem os ativos diferidos
        "capital_giro": round(ac - pc, 2),
    }


def margens(dre):
    """Margens da DRE do período (frações; a tela formata em %)."""
    rl = _f((dre or {}).get("receita_liquida"))
    return {
        "bruta": _div((dre or {}).get("lucro_bruto"), rl),
        "ebitda": _div((dre or {}).get("ebitda"), rl),
        "liquida": _div((dre or {}).get("lucro_liquido"), rl),
    }


def prazos_giro(receber, fornecedores, receita_periodo, cmv_periodo, dias):
    """PMR/PMP (dias) e giro de carteira (quantas vezes a carteira de recebíveis 'girou'
    no período = receita ÷ saldo a receber)."""
    pmr = _div(_f(receber) * _f(dias), receita_periodo, nd=1)
    pmp = _div(_f(fornecedores) * _f(dias), cmv_periodo, nd=1)
    return {
        "pmr_dias": pmr,
        "pmp_dias": pmp,
        "giro_carteira": _div(receita_periodo, receber, nd=2),
    }


def tendencia(serie):
    """Direção da série (último vs penúltimo): alta | queda | estavel (< ±1%).
    Base zero ou série curta → pct None (sem % enganoso)."""
    s = [_f(x) for x in (serie or [])]
    if len(s) < 2:
        return {"dir": "estavel", "pct": None}
    ant, ult = s[-2], s[-1]
    if abs(ant) < 0.005:
        if abs(ult) < 0.005:
            return {"dir": "estavel", "pct": None}
        return {"dir": "alta" if ult > 0 else "queda", "pct": None}
    pct = round((ult - ant) / abs(ant) * 100.0, 1)
    if abs(pct) < 1.0:
        return {"dir": "estavel", "pct": pct}
    return {"dir": "alta" if pct > 0 else "queda", "pct": pct}


def kpis_comerciais(status_counts, contratos_periodo):
    """KPIs do funil comercial. status_counts: {status: n} dos projetos;
    contratos_periodo: lista de valores (R$) dos contratos gerados no período."""
    sc = status_counts or {}
    ativos = sum(sc.get(k, 0) for k in ("quente", "morno", "frio"))
    conv, perd = sc.get("convertido", 0), sc.get("perdido", 0)
    vals = [_f(v) for v in (contratos_periodo or [])]
    return {
        "pipeline_ativo": ativos,
        "quentes": sc.get("quente", 0),
        "convertidos": conv,
        "perdidos": perd,
        "taxa_conversao": _div(conv, conv + perd),
        "n_vendas_periodo": len(vals),
        "vendas_periodo": round(sum(vals), 2),
        "ticket_medio": _div(sum(vals), len(vals), nd=2),
    }
