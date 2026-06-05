"""
mod_fin/financeira_loja.py — parcelamento próprio com parcelas editáveis

Regras:
  - Entrada + até 3 parcelas mensais (máx 4x total)
  - Taxa de juros: 2% ao mês compostos (configurável no JSON)
  - Parcelas 1..N-1 são editadas pelo consultor
  - Parcela N fecha o saldo automaticamente

Teste rápido:
  python3 -c "
  from mod_fin.financeira_loja import calcular
  import pprint
  pprint.pprint(calcular(10000, 0, 4, '2026-06-01', [2000, 2000, 2000]))
  "
"""
from datetime import timedelta
from .base import carregar_json, parse_data, linha_contrato, linha_entrada, linha_parcela

PARCELAS_MAX = 4
TAXA_PADRAO  = 0.02   # 2% ao mês


def _taxa_juros() -> float:
    """Lê taxa do JSON. Usa 2% como padrão."""
    tab = carregar_json("financeira_loja")
    return float(tab.get("taxa_juros_mensal", TAXA_PADRAO)) if tab else TAXA_PADRAO


def calcular(valor_negociado: float, entrada: float, n_parcelas: int,
             data_contrato: str, valores_parcelas: list = None) -> dict:
    """
    Calcula parcelamento Financeira Loja.

    Parâmetros:
        valor_negociado  — Total do Contrato já negociado
        entrada          — Valor pago na assinatura
        n_parcelas       — Total de parcelas (1 a 4)
        data_contrato    — Data da assinatura 'AAAA-MM-DD'
        valores_parcelas — Lista com os valores das parcelas 1..N-1 (editáveis)
                           Se None ou vazia, usa parcela base igual para todas

    Retorna dict com:
        ok, financiado, taxa_juros_pct, acrescimo_pct, valor_total,
        parcela_base, ultima_parcela, saldo_remanescente,
        total_cliente, parcelas[], equilibrado
    """
    n     = int(n_parcelas)
    venda = float(valor_negociado)
    ent   = float(entrada or 0)

    if n < 1 or n > PARCELAS_MAX:
        return {"ok": False, "erro": f"n_parcelas deve ser entre 1 e {PARCELAS_MAX}"}
    if ent >= venda:
        return {"ok": False, "erro": "Entrada deve ser menor que o valor negociado"}

    financiado = round(venda - ent, 2)
    taxa       = _taxa_juros()
    meses      = n   # sem carência além dos 30 dias da 1ª parcela

    # Valor total com juros compostos
    acrescimo_fator = (1 + taxa) ** meses
    valor_total     = round(financiado * acrescimo_fator, 2)
    acrescimo_rs    = round(valor_total - financiado, 2)
    acrescimo_pct   = round((acrescimo_fator - 1) * 100, 4)
    parcela_base    = round(valor_total / n, 2)

    # Parcelas editáveis (1..N-1); última fecha o saldo
    vals = list(valores_parcelas or [])
    # Preencher com parcela_base se não fornecido
    while len(vals) < n - 1:
        vals.append(parcela_base)
    vals = vals[:n - 1]   # truncar ao necessário

    soma_anteriores   = round(sum(vals), 2)
    saldo_remanescente = round(valor_total - soma_anteriores, 2)
    ultima_parcela    = saldo_remanescente
    equilibrado       = abs(saldo_remanescente) < 0.02

    # Plano de parcelas
    dc   = parse_data(data_contrato)
    plan = [linha_contrato(dc)]
    if ent > 0:
        plan.append(linha_entrada(dc, ent))
    for i in range(1, n + 1):
        data_venc = dc + timedelta(days=30 * i)
        valor     = vals[i - 1] if i < n else ultima_parcela
        plan.append(linha_parcela(i, data_venc, valor))

    return {
        "ok":                True,
        "valor_negociado":   venda,
        "entrada":           ent,
        "financiado":        financiado,
        "taxa_juros_pct":    round(taxa * 100, 2),
        "acrescimo_pct":     acrescimo_pct,
        "valor_total":       valor_total,
        "acrescimo_rs":      acrescimo_rs,
        "parcela_base":      parcela_base,
        "ultima_parcela":    round(ultima_parcela, 2),
        "saldo_remanescente": round(saldo_remanescente, 2),
        "n_parcelas":        n,
        "total_cliente":     round(ent + valor_total, 2),
        "equilibrado":       equilibrado,
        "parcelas":          plan,
    }
