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
    for k, v in (d.get("defaults_negociacao", {}) or {}).items():
        if _f(v) < 0:
            erros.append(f"Default {k} não pode ser negativo.")
    cv = d.get("comissao_vendas", {}) or {}
    faixas = cv.get("faixas_comissao", [])
    if not faixas:
        erros.append("Comissão de vendas precisa de ao menos uma faixa.")
    for fx in faixas:
        if "pct" not in fx:
            erros.append("Cada faixa de comissão precisa de 'pct'.")
        elif _f(fx.get("pct")) < 0:
            erros.append("Percentual de faixa não pode ser negativo.")
    for lim in (cv.get("limitador_desconto", {}) or {}).get("limites", []):
        if _f(lim.get("redutor_pct")) < 0 or _f(lim.get("desconto_acima_de")) < 0:
            erros.append("Limite de desconto com valor negativo.")
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
