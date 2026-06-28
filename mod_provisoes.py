# -*- coding: utf-8 -*-
"""mod_provisoes.py — Provisões pós-fechamento e margem real (PURO, sem I/O).

Recebe as siglas do motor (mod_negociacao) + a config financeira da loja e devolve
as provisões por orçamento, Cust_Var e Marg_Cont. Percentuais em número-percent
(10 = 10%), divididos por 100 aqui — mesma convenção do mod_negociacao.
Fórmulas fechadas: docs/modulos/financeiro/PROVISOES_E_VARIAVEIS.md.
"""

_PROV_KEYS = ("frete_fab_pct", "com_adm_pct", "com_med_pct", "com_proj_exec_pct",
              "frete_loc_pct", "assist_pct", "ins_loc_pct")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def config_financeira_default():
    return {
        "defaults_negociacao": {"comissao_arq_pct": 0.0, "fidelidade_pct": 0.0, "carga_trib_pct": 0.0},
        "provisoes": {k: 0.0 for k in _PROV_KEYS},
        "comissao_vendas": {
            "meta_mensal": 0.0,
            "faixas_comissao": [{"venda_ate": None, "pct": 0.0}],
            "limitador_desconto": {"ativo": False, "base_desconto": "Desc_Orc", "limites": []},
        },
    }


def validar_config_financeira(dados):
    erros = []
    d = dados or {}
    prov = d.get("provisoes", {})
    for k in _PROV_KEYS:
        if _f(prov.get(k)) < 0:
            erros.append(f"Provisão {k} não pode ser negativa.")
        elif _f(prov.get(k)) > 100:
            erros.append(f"Provisão {k} não pode passar de 100%.")
    for k, v in (d.get("defaults_negociacao", {}) or {}).items():
        if _f(v) < 0:
            erros.append(f"Default {k} não pode ser negativo.")
        elif _f(v) > 100:
            erros.append(f"Default {k} não pode passar de 100%.")
    cv = d.get("comissao_vendas", {}) or {}
    faixas = cv.get("faixas_comissao", [])
    if not faixas:
        erros.append("Comissão de vendas precisa de ao menos uma faixa.")
    for fx in faixas:
        if "pct" not in fx:
            erros.append("Cada faixa de comissão precisa de 'pct'.")
        elif _f(fx.get("pct")) < 0:
            erros.append("Percentual de faixa não pode ser negativo.")
        elif _f(fx.get("pct")) > 100:
            erros.append("Percentual de faixa não pode passar de 100%.")
    for lim in (cv.get("limitador_desconto", {}) or {}).get("limites", []):
        if _f(lim.get("redutor_pct")) < 0 or _f(lim.get("desconto_acima_de")) < 0:
            erros.append("Limite de desconto com valor negativo.")
        if _f(lim.get("redutor_pct")) > 100:
            erros.append("Limite de desconto fora de 0–100%.")
        if _f(lim.get("desconto_acima_de")) > 100:
            erros.append("Limite de desconto fora de 0–100%.")
    return erros


def resolver_comissao_venda(cfg, val_liq_mes, desc_orc_pct):
    cv = (cfg or {}).get("comissao_vendas", {}) or {}
    faixas = cv.get("faixas_comissao", []) or []
    pct = 0.0
    for fx in faixas:
        ate = fx.get("venda_ate")
        if ate is None or _f(val_liq_mes) < _f(ate):
            pct = _f(fx.get("pct"))
            break
    else:
        pct = _f(faixas[-1].get("pct")) if faixas else 0.0
    lim = cv.get("limitador_desconto", {}) or {}
    if lim.get("ativo"):
        redutor = 0.0
        for L in sorted(lim.get("limites", []) or [], key=lambda x: _f(x.get("desconto_acima_de"))):
            if _f(desc_orc_pct) > _f(L.get("desconto_acima_de")):
                redutor = _f(L.get("redutor_pct"))
        pct = pct * (1 - redutor / 100.0)
    return round(pct, 4)


# IMPORTANTE: estas 10 rubricas são exatamente os addendos de Cust_Var em provisoes_orcamento
# (CFO + out_forn + as 8 rubricas % + Prov_Imp). cust_var_marg_cont recalcula Cust_Var como
# CFO + Σ(itens) — então, ao adicionar/remover uma rubrica do motor, atualize ESTE mapa também,
# senão as duas fórmulas de Cust_Var divergem silenciosamente.
_RUBRICAS = {
    "frete_fab": "Frete_Fab_Orc", "com_adm": "Com_Adm_Orc", "com_venda": "Com_Venda_Orc",
    "com_med": "Com_Med_Orc", "com_proj_exec": "Com_Proj_Exec_Orc", "frete_loc": "Frete_Loc_Orc",
    "assist": "Assist_Orc", "ins_loc": "Ins_Loc_Orc", "prov_imp": "Prov_Imp", "out_forn": "Out_Forn",
}


def itens_provisao(siglas):
    """Extrai as 10 rubricas de provisão do breakdown do motor (dict {rubrica: valor R$})."""
    s = siglas or {}
    return {k: round(_f(s.get(v)), 2) for k, v in _RUBRICAS.items()}


def cust_var_marg_cont(cfo, val_liq, itens):
    """Recalcula (Cust_Var, Marg_Cont) a partir de itens (possivelmente editados).
    Cust_Var = CFO + Σ itens (os itens já incluem out_forn e prov_imp)."""
    cust_var = round(_f(cfo) + sum(_f(v) for v in (itens or {}).values()), 2)
    vl = _f(val_liq)
    marg = round((vl - cust_var) / vl, 4) if vl else 0.0
    return cust_var, marg


def provisoes_orcamento(siglas, cfg, out_forn=0.0, com_venda_pct=0.0):
    s = siglas or {}
    CFO = _f(s.get("CFO")); Val_Liq = _f(s.get("Val_Liq"))
    VAVO = _f(s.get("VAVO")); Prov_Imp = _f(s.get("Prov_Imp"))
    prov = (cfg or {}).get("provisoes", {}) or {}
    out_forn = _f(out_forn)

    frete_fab = _f(prov.get("frete_fab_pct")) / 100.0 * CFO
    com_adm   = _f(prov.get("com_adm_pct"))   / 100.0 * Val_Liq
    com_venda = _f(com_venda_pct)             / 100.0 * Val_Liq
    com_med   = _f(prov.get("com_med_pct"))   / 100.0 * Val_Liq
    com_proj  = _f(prov.get("com_proj_exec_pct")) / 100.0 * Val_Liq
    frete_loc = _f(prov.get("frete_loc_pct")) / 100.0 * VAVO
    assist    = _f(prov.get("assist_pct"))    / 100.0 * VAVO
    ins_loc   = _f(prov.get("ins_loc_pct"))   / 100.0 * VAVO

    cust_var = (CFO + out_forn + frete_fab + com_adm + com_venda + com_med
                + com_proj + frete_loc + assist + ins_loc + Prov_Imp)
    marg_cont = ((Val_Liq - cust_var) / Val_Liq) if Val_Liq else 0.0
    return {
        "Frete_Fab_Orc": round(frete_fab, 2), "Com_Adm_Orc": round(com_adm, 2),
        "Com_Venda_Orc": round(com_venda, 2), "Com_Med_Orc": round(com_med, 2),
        "Com_Proj_Exec_Orc": round(com_proj, 2), "Frete_Loc_Orc": round(frete_loc, 2),
        "Assist_Orc": round(assist, 2), "Ins_Loc_Orc": round(ins_loc, 2),
        "Out_Forn": round(out_forn, 2),
        "Cust_Var": round(cust_var, 2), "Marg_Cont": round(marg_cont, 4),
    }
