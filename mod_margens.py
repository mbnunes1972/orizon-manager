"""
mod_margens.py — Normalização de faixas de pagamento (delega para mod_fin).
"""
# == NORMALIZAÇÃO DE FAIXAS ==
# (O cálculo legado de margens `calcular_margens` foi removido na faxina — o motor
#  `mod_negociacao` é a fonte única. Restam só `_pmt`/`_normalizar_faixas`, usados pelo
#  endpoint de faixas de pagamento.)

def _pmt(taxa, n):
    """PMT de anuidade."""
    if taxa == 0:
        return 1.0 / n
    return taxa * (1 + taxa) ** n / ((1 + taxa) ** n - 1)

def _normalizar_faixas(tab):
    """Delega para mod_fin.carregar_faixas."""
    try:
        from mod_fin import carregar_faixas
        codigo = tab.get("codigo", "")
        if codigo:
            return carregar_faixas(codigo)
    except Exception:
        pass
    # Fallback inline
    tipo = tab.get("tipo", "")
    if tipo == "avista":
        return [{"parcelas": 1, "custo_pct": 0.0, "label": "À Vista"}]
    if tipo == "parcelado_proprio":
        return [{"parcelas": int(f["parcelas"]),
                 "custo_pct": float(f.get("acrescimo_pct", 0)),
                 "label": f.get("obs", "%dx" % f["parcelas"])}
                for f in tab.get("faixas", [])]
    if tipo == "financiamento_externo":
        if "faixas" in tab:
            return [{"parcelas": max(1, int(f["parcelas"])),
                     "custo_pct": float(f.get("taxa_retencao_pct", 0)),
                     "label": "%dx" % max(1, int(f["parcelas"]))}
                    for f in tab.get("faixas", [])]
        else:
            result = []
            for t in tab.get("taxas_mensais", []):
                n    = int(t["parcelas"])
                taxa = float(t["taxa_mensal_pct"]) / 100
                retencao = round((1 - (1.0 / n) / _pmt(taxa, n)) * 100, 4) if n > 0 and taxa > 0 else 0.0
                result.append({"parcelas": n, "custo_pct": retencao, "label": "%dx" % n})
            return result
    if tipo == "programado":
        return [{"parcelas": i, "custo_pct": 0.0, "label": "%dx" % i}
                for i in range(1, int(tab.get("parcelas_max", 12)) + 1)]
    if tipo == "flex":
        taxa = float(tab.get("taxa_juros_mensal_pct", 2.0))
        return [{"parcelas": i, "custo_pct": taxa, "label": "%dx" % i}
                for i in range(1, int(tab.get("parcelas_max", 12)) + 1)]
    return []
