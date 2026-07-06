"""
mod_margens.py — Cálculo de margens comerciais e normalização de faixas.
"""
import os
from storage import _BASE_DIR

# == LÓGICA DE MARGENS ==
# Sequência: bruto → desconto → viagem → arq → fidelidade → financeiro
# Função pura — sem side effects, pronta para testes unitários.
# Para nuvem: pode ser extraída para microserviço sem alterar assinatura.

def calcular_margens(valor_bruto, desconto_pct=0.0, fora_da_sede=False,
                     custo_viagem=0.0, comissao_arq_pct=0.0, comissao_arq_ativa=False,
                     fidelidade_pct=0.0, fidelidade_ativa=False,
                     custo_financeiro_pct=0.0,
                     brinde=0.0, brinde_ativo=False) -> dict:
    """
    Ordem de cálculo:
      1. Bruto × (1 − desconto%)              → saldo_desc
      2. saldo_desc * (1 − custo_fin%)        → saldo_fin  (gross-up: cobre a taxa retida)
      3a. saldo_fin − custo_viagem (rateado)   → saldo_viagem (só se fora_da_sede)
      3b. saldo_viagem − brinde (fixo/amb)     → saldo_brinde (só se brinde_ativo)
      4. saldo_brinde × (1 − arq%)            → saldo_arq   (só se comissao_arq_ativa)
      5. saldo_arq × (1 − fid%)               → saldo_fid   = Valor final
    """
    valor_bruto          = float(valor_bruto or 0)
    desconto_pct         = float(desconto_pct or 0)
    custo_financeiro_pct = float(custo_financeiro_pct or 0)
    custo_viagem         = float(custo_viagem or 0)
    brinde               = float(brinde or 0)
    comissao_arq_pct     = float(comissao_arq_pct or 0)
    fidelidade_pct       = float(fidelidade_pct or 0)

    saldo_desc   = round(valor_bruto * (1 - desconto_pct / 100), 2)
    div_fin  = 1 - custo_financeiro_pct / 100
    saldo_fin    = round(saldo_desc / div_fin, 2) if div_fin > 0 else saldo_desc
    saldo_viagem = round(saldo_fin   - (custo_viagem if fora_da_sede else 0), 2)
    saldo_brinde = round(saldo_viagem - (brinde if brinde_ativo else 0), 2)
    saldo_arq    = round(saldo_brinde * (1 - (comissao_arq_pct / 100 if comissao_arq_ativa else 0)), 2)
    saldo_fid    = round(saldo_arq    * (1 - (fidelidade_pct   / 100 if fidelidade_ativa   else 0)), 2)

    return {
        "valor_bruto":           round(valor_bruto, 2),
        "saldo_apos_desconto":   saldo_desc,
        "saldo_apos_financeiro": saldo_fin,
        "custo_financeiro":      round(saldo_fin - saldo_desc, 2),   # acrescimo positivo (gross-up)
        "saldo_apos_viagem":     saldo_viagem,
        "brinde_aplicado":       round(brinde if brinde_ativo else 0, 2),
        "saldo_apos_brinde":     saldo_brinde,
        "saldo_apos_arq":        saldo_arq,
        "saldo_apos_fidelidade": saldo_fid,
        "valor_liquido_avista":  saldo_fid,
        "total_deducoes":        round(valor_bruto - saldo_fid, 2),
        "acrescimo_financeiro":  round(saldo_fin - saldo_desc, 2),
        "valor_final":           saldo_fid,
    }

# == NORMALIZAÇÃO DE FAIXAS ==
# Delegado para mod_fin — mantido aqui apenas _pmt para calcular_margens

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
