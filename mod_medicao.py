# -*- coding: utf-8 -*-
"""mod_medicao.py — Validações (puras) do parecer de medição."""

PARECERES = {"aprovado", "reprovado", "parcial"}


def validar_parecer(parecer, ambientes_aprovados):
    """Lista de erros (vazia se ok). 'parcial' exige ambientes_aprovados não vazio."""
    erros = []
    p = (parecer or "").strip().lower()
    if p not in PARECERES:
        erros.append("Parecer inválido (use aprovado, reprovado ou parcial).")
    if p == "parcial" and not (ambientes_aprovados or "").strip():
        erros.append("Informe os ambientes aprovados para parecer parcial.")
    return erros
