"""
mod_fin/financeira_loja.py — parcelamento próprio com parcelas editáveis

Regras:
  - Entrada mínima de 10% do valor negociado
  - Até 6 parcelas mensais (entrada + até 5 parcelas)
  - Taxa de juros: 1% ao mês, capitalizado diariamente
    taxa_diaria = (1 + taxa_mensal)^(1/30) - 1
    fator       = (1 + taxa_diaria)^(30 * n)  ==  (1 + taxa_mensal)^n
  - Parcelas 1..N-1 editáveis pelo consultor
  - Parcela N fecha o saldo automaticamente

Testes:
  python -c "
  from mod_fin.financeira_loja import calcular
  import pprint
  pprint.pprint(calcular(10000, 1000, 4, '2026-06-01'))
  "
"""
from datetime import timedelta
from .base import carregar_json, parse_data, linha_contrato, linha_entrada, linha_parcela

PARCELAS_MAX      = 6
TAXA_MENSAL_PADRAO = 0.01   # 1% ao mês
ENTRADA_MIN_PCT   = 0.10    # 10% mínimo


def _taxa_juros() -> float:
    """Lê taxa mensal do JSON. Usa 1% como padrão."""
    tab = carregar_json("financeira_loja")
    return float(tab.get("taxa_juros_mensal", TAXA_MENSAL_PADRAO)) if tab else TAXA_MENSAL_PADRAO


def _entrada_min_pct() -> float:
    """Lê percentual mínimo de entrada do JSON."""
    tab = carregar_json("financeira_loja")
    return float(tab.get("entrada_min_pct", ENTRADA_MIN_PCT)) if tab else ENTRADA_MIN_PCT


def calcular(valor_negociado: float, entrada: float, n_parcelas: int,
             data_contrato: str, valores_parcelas: list = None) -> dict:
    """
    Calcula parcelamento Financeira Loja.

    Parâmetros:
        valor_negociado  — Total do Contrato já negociado
        entrada          — Valor pago na assinatura (mínimo 10%)
        n_parcelas       — Total de parcelas (1 a 6)
        data_contrato    — Data da assinatura 'AAAA-MM-DD'
        valores_parcelas — Valores das parcelas 1..N-1 editadas pelo consultor.
                           Se vazio, usa parcela_base igual para todas.

    Retorna dict com:
        ok, financiado, taxa_juros_pct, acrescimo_pct, valor_total,
        parcela_base, ultima_parcela, saldo_remanescente,
        total_cliente, parcelas[] (com campo editavel), equilibrado
    """
    n     = int(n_parcelas)
    venda = float(valor_negociado)
    ent   = float(entrada or 0)

    # Validações
    if n < 1 or n > PARCELAS_MAX:
        return {"ok": False, "erro": f"n_parcelas deve ser entre 1 e {PARCELAS_MAX}"}

    entrada_min = round(venda * _entrada_min_pct(), 2)
    if ent < entrada_min:
        pct = _entrada_min_pct() * 100
        return {"ok": False, "erro": f"Entrada mínima de {pct:.0f}% (R$ {entrada_min:,.2f})"}

    if ent >= venda:
        return {"ok": False, "erro": "Entrada deve ser menor que o valor negociado"}

    financiado = round(venda - ent, 2)
    if financiado <= 0:
        return {"ok": False, "erro": "Valor financiado inválido"}

    # Juros: 1% a.m. capitalizado diariamente
    taxa_mensal = _taxa_juros()
    taxa_diaria = (1 + taxa_mensal) ** (1 / 30) - 1
    acrescimo_fator = round((1 + taxa_diaria) ** (30 * n), 10)

    valor_total  = round(financiado * acrescimo_fator, 2)
    acrescimo_rs = round(valor_total - financiado, 2)
    acrescimo_pct = round((acrescimo_fator - 1) * 100, 4)
    parcela_base  = round(valor_total / n, 2)

    # Parcelas editáveis (1..N-1); última fecha o saldo
    vals = list(valores_parcelas or [])
    while len(vals) < n - 1:
        vals.append(parcela_base)
    vals = [round(float(v), 2) for v in vals[:n - 1]]

    soma_anteriores    = round(sum(vals), 2)
    saldo_remanescente = round(valor_total - soma_anteriores, 2)
    ultima_parcela     = saldo_remanescente
    equilibrado        = abs(saldo_remanescente) < 0.02

    # Plano de parcelas
    dc   = parse_data(data_contrato)
    plan = [linha_contrato(dc)]
    if ent > 0:
        plan.append(linha_entrada(dc, ent))
    for i in range(1, n + 1):
        data_venc = dc + timedelta(days=30 * i)
        valor     = vals[i - 1] if i < n else ultima_parcela
        parc      = linha_parcela(i, data_venc, valor)
        parc["editavel"] = (i < n)   # últimas N-1 editáveis; última é calculada
        plan.append(parc)

    return {
        "ok":                  True,
        "valor_negociado":     venda,
        "entrada":             ent,
        "entrada_min":         entrada_min,
        "financiado":          financiado,
        "taxa_juros_pct":      round(taxa_mensal * 100, 2),
        "acrescimo_pct":       acrescimo_pct,
        "valor_total":         valor_total,
        "acrescimo_rs":        acrescimo_rs,
        "parcela_base":        parcela_base,
        "ultima_parcela":      round(ultima_parcela, 2),
        "saldo_remanescente":  round(saldo_remanescente, 2),
        "n_parcelas":          n,
        "total_cliente":       round(ent + valor_total, 2),
        "equilibrado":         equilibrado,
        "parcelas":            plan,
    }
