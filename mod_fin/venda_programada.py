"""
mod_fin/venda_programada.py — Venda Programada sem juros

Regras:
  - Até 12 parcelas, 0% de acréscimo
  - Última parcela deve cair em até 395 dias após a assinatura (prazo_limite_dias)
  - Datas configuráveis individualmente (para futura emissão de boleto)
  - Entrada opcional (na data de assinatura, sem juros)
"""
from datetime import timedelta
from .base import carregar_json, parse_data, linha_contrato, linha_entrada

_PRAZO_LIMITE_DIAS_PADRAO = 395
_PARCELAS_MAX_PADRAO      = 12


def _linha_vp(num: int, data, valor: float) -> dict:
    tipo = "primeira" if num == 1 else "parcela"
    return {
        "num":      num,
        "tipo":     tipo,
        "data":     data.strftime("%d/%m/%Y"),
        "data_iso": data.strftime("%Y-%m-%d"),
        "valor":    round(valor, 2),
    }


def calcular(valor_avista: float, entrada: float, n_parcelas: int,
             data_contrato: str, datas_parcelas: list = None) -> dict:
    """
    Calcula plano de Venda Programada.

    datas_parcelas: lista de strings 'AAAA-MM-DD', uma por parcela.
                   Se ausente ou incompleta, gera mensalmente (30d × n).
    Retorna erro se qualquer parcela ultrapassar prazo_limite_dias.
    """
    n      = int(n_parcelas)
    avista = float(valor_avista)
    ent    = float(entrada or 0)

    tab          = carregar_json("venda_programada")
    prazo_limite = int(tab.get("prazo_limite_dias", _PRAZO_LIMITE_DIAS_PADRAO))
    parcelas_max = int(tab.get("parcelas_max",      _PARCELAS_MAX_PADRAO))

    if n < 1 or n > parcelas_max:
        return {"ok": False, "erro": f"n_parcelas deve ser entre 1 e {parcelas_max}"}
    if ent < 0:
        return {"ok": False, "erro": "Entrada nao pode ser negativa"}
    if ent >= avista:
        return {"ok": False, "erro": "Entrada deve ser menor que o valor a vista"}

    dc     = parse_data(data_contrato)
    limite = dc + timedelta(days=prazo_limite)

    # Valor por parcela (sem juros)
    financiado    = round(avista - ent, 2)
    valor_parcela = round(financiado / n, 2)
    ajuste_ultimo = round(financiado - valor_parcela * n, 2)  # centavos residuais

    # Datas: usa fornecidas se completas, senão gera padrão mensal
    if datas_parcelas and len(datas_parcelas) >= n:
        datas = [parse_data(d) for d in datas_parcelas[:n]]
    else:
        datas = [dc + timedelta(days=30 * (i + 1)) for i in range(n)]

    # Validar prazo limite
    avisos       = []
    excede_prazo = False
    for i, dt in enumerate(datas):
        if dt > limite:
            excede_prazo = True
            dias_extra   = (dt - limite).days
            avisos.append(
                f"Parcela {i + 1}: vencimento {dt.strftime('%d/%m/%Y')} "
                f"excede o prazo limite em {dias_extra} dia(s)"
            )

    plan = [linha_contrato(dc)]
    if ent > 0:
        plan.append(linha_entrada(dc, ent))
    for i, dt in enumerate(datas):
        valor = valor_parcela + (ajuste_ultimo if i == n - 1 else 0)
        plan.append(_linha_vp(i + 1, dt, valor))

    return {
        "ok":              True,
        "valor_avista":    avista,
        "valor_negociado": avista,
        "entrada":         ent,
        "financiado":      financiado,
        "taxa_retencao_pct": 0.0,
        "valor_liberado":  avista,
        "retencao_rs":     0.0,
        "valor_parcela":   valor_parcela,
        "n_parcelas":      n,
        "total_cliente":   avista,
        "prazo_limite_dias": prazo_limite,
        "data_limite":     limite.strftime("%d/%m/%Y"),
        "data_limite_iso": limite.strftime("%Y-%m-%d"),
        "excede_prazo":    excede_prazo,
        "avisos":          avisos,
        "parcelas":        plan,
    }
