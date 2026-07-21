# -*- coding: utf-8 -*-
"""mod_ajustes_fabrica.py — Descontos e Acréscimos Excepcionais de Fábrica (PURO, sem I/O).

Spec: docs/superpowers/specs/financeiro/2026-07-21-descontos-acrescimos-excepcionais-fabrica-design.md

Condições excepcionais negociadas com a fábrica, aplicadas na Conferência do Pedido (etapa 12)
SOBRE o valor de fábrica padrão — o motor de negociação (mod_negociacao) NÃO participa (alcance
só financeiro, decisão 2026-07-21). Ordem FIXA (reproduz o exemplo 100.000 → 95.000 → 104.500):

  1. DESCONTOS sobre o valor conferido;
  2. ACRÉSCIMOS sobre o pós-descontos (ou sobre o conferido, se `base='valor_conferido'`).

Dois tratamentos por ajuste (semânticas contábeis distintas — quem lança é o composition root):
  - `custo`:          muda o custo econômico (CMV futuro) — ativo diferido × provisão;
  - `consumir_saldo`: custo íntegro; realiza/amortiza o saldo de um ACORDO no razão. Capado ao
                      DISPONÍVEL do acordo (contábil − pendentes de acerto); consumo parcial
                      marca `capado`; disponível zerado ⇒ acordo `esgotado`.

Arredondamento por aplicação (`round(…, 2)`); o encadeamento usa valores já arredondados.
"""
from datetime import date as _date


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def disponivel_acordo(saldo_contabil, pendentes_acerto):
    """Saldo DISPONÍVEL do acordo = saldo contábil (razão da titular) − Σ aplicações
    `pendente_acerto` (a tabela de aplicações é a ponte entre razões no intercompany).
    Nunca negativo."""
    return round(max(0.0, _f(saldo_contabil) - _f(pendentes_acerto)), 2)


def _data(v):
    if not v:
        return None
    if isinstance(v, _date):
        return v
    return _date.fromisoformat(str(v)[:10])


def vigente(ajuste, hoje=None, projeto=None):
    """Ajuste aplicável hoje/neste projeto: ativo, dentro da janela vigencia_de/ate (opcionais)
    e — se `natureza='pontual'` — vinculado ao projeto (lista `projetos`)."""
    if not ajuste.get("ativo", True):
        return False
    h = _data(hoje) or _date.today()
    de, ate = _data(ajuste.get("vigencia_de")), _data(ajuste.get("vigencia_ate"))
    if de is not None and h < de:
        return False
    if ate is not None and h > ate:
        return False
    if (ajuste.get("natureza") or "recorrente") == "pontual":
        return projeto is not None and projeto in (ajuste.get("projetos") or [])
    return True


def calcular_aplicacoes(valor_conferido, ajustes, disponiveis=None, hoje=None, projeto=None):
    """Calcula as aplicações dos ajustes vigentes sobre `valor_conferido`, na ordem da spec.

    ajustes:     [{id, tipo ('desconto'|'acrescimo'), pct, tratamento ('custo'|'consumir_saldo'),
                   acordo_id, natureza, ativo, vigencia_de, vigencia_ate, projetos, base}]
    disponiveis: {acordo_id: R$ disponível} — cap dos `consumir_saldo` (compartilhado quando dois
                 ajustes consomem o MESMO acordo). Acordo ausente do dict ⇒ disponível 0.

    Retorna {"aplicacoes": [{id, tipo, tratamento, acordo_id, pct, base_calculo, valor, capado}],
             "valor_conferido", "custo_fabrica_final" (CMV futuro — só ajustes de CUSTO),
             "a_pagar_final" (o que casa com a NF-e da fábrica),
             "acordos_esgotados": [acordo_id]}"""
    conferido = round(_f(valor_conferido), 2)
    saldo_cap = dict(disponiveis or {})
    aplicaveis = [a for a in (ajustes or []) if vigente(a, hoje=hoje, projeto=projeto)]
    descontos = [a for a in aplicaveis if a.get("tipo") == "desconto"]
    acrescimos = [a for a in aplicaveis if a.get("tipo") == "acrescimo"]

    aplicacoes, esgotados = [], []

    def _aplicar(ajuste, base_calculo):
        valor = round(base_calculo * _f(ajuste.get("pct")) / 100.0, 2)
        capado = False
        if (ajuste.get("tratamento") == "consumir_saldo"):
            disp = round(_f(saldo_cap.get(ajuste.get("acordo_id"))), 2)
            if valor > disp:
                valor = disp
                capado = True
            saldo_cap[ajuste.get("acordo_id")] = round(disp - valor, 2)
            if saldo_cap[ajuste.get("acordo_id")] <= 0.005 and ajuste.get("acordo_id") is not None:
                if ajuste["acordo_id"] not in esgotados:
                    esgotados.append(ajuste["acordo_id"])
        if valor <= 0:
            return None
        aplicacoes.append({"id": ajuste.get("id"), "tipo": ajuste.get("tipo"),
                           "tratamento": ajuste.get("tratamento"),
                           "acordo_id": ajuste.get("acordo_id"),
                           "pct": _f(ajuste.get("pct")),
                           "base_calculo": round(base_calculo, 2),
                           "valor": valor, "capado": capado})
        return valor

    # 1) descontos — SEMPRE sobre o valor conferido
    tot_desc = tot_desc_custo = 0.0
    for a in descontos:
        v = _aplicar(a, conferido)
        if v:
            tot_desc = round(tot_desc + v, 2)
            if a.get("tratamento") == "custo":
                tot_desc_custo = round(tot_desc_custo + v, 2)

    pos_descontos = round(conferido - tot_desc, 2)

    # 2) acréscimos — sobre o pós-descontos (default) ou sobre o conferido. Base nunca negativa
    # (descontos somando >100% do conferido são erro de configuração; o piso evita propagar).
    tot_acr = tot_acr_custo = 0.0
    for a in acrescimos:
        base = conferido if (a.get("base") == "valor_conferido") else max(pos_descontos, 0.0)
        v = _aplicar(a, base)
        if v:
            tot_acr = round(tot_acr + v, 2)
            if a.get("tratamento") == "custo":
                tot_acr_custo = round(tot_acr_custo + v, 2)

    return {
        "aplicacoes": aplicacoes,
        "valor_conferido": conferido,
        # CMV futuro: só os ajustes de CUSTO mudam o custo econômico
        "custo_fabrica_final": round(conferido - tot_desc_custo + tot_acr_custo, 2),
        # a pagar à fábrica: todos os descontos e acréscimos (casa com a NF-e)
        "a_pagar_final": round(conferido - tot_desc + tot_acr, 2),
        "acordos_esgotados": esgotados,
    }
