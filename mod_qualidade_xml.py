# -*- coding: utf-8 -*-
"""mod_qualidade_xml.py — Trava de qualidade do dado de XML (PURO, sem I/O).

Spec §8. Bloqueia quando o XML não tem acréscimo (venda ≤ custo) ou tem item com
custo e sem venda. Sinais ruidosos (itens sem preço / desconto-fábrica zerado) NÃO
entram na trava (disparam em orçamento bom).
"""


def avaliar_qualidade_xml(itens, limiar_pct=5.0):
    sum_b = sum_o = sum_b_sem_acr = 0.0
    n_custo_sem_venda = 0
    for it in (itens or []):
        try:
            o = float(it.get("order_total") or 0)
            b = float(it.get("budget_total") or 0)
        except (TypeError, ValueError):
            o = b = 0.0
        if b <= 0:
            if o > 0:
                n_custo_sem_venda += 1          # paga à fábrica, não cobra
            continue
        sum_b += b
        sum_o += o
        if b <= o * 1.0001:                     # tolerância de arredondamento de float (~0,01%) para "vendido no custo"
            sum_b_sem_acr += b
    markup = (sum_b / sum_o) if sum_o > 0 else 0.0
    pct_sem = (sum_b_sem_acr / sum_b * 100.0) if sum_b > 0 else 0.0
    bloqueado = (pct_sem >= float(limiar_pct)) or (n_custo_sem_venda > 0)
    return {
        "qa_markup_xml":         round(markup, 4),
        "qa_pct_sem_acrescimo":  round(pct_sem, 2),
        "qa_custo_sem_venda":    n_custo_sem_venda,
        "qa_selo":               "bloqueado" if bloqueado else "ok",
    }
