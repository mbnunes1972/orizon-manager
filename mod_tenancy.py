# -*- coding: utf-8 -*-
"""mod_tenancy.py — Validações e decisões de escopo (PURAS) da tenancy (F2 multi-tenant).

Sem I/O e sem ORM: recebe dicts simples e devolve listas de erro / tuplas de decisão.
As rotas em main.py fazem o I/O (consultas, gravação) e chamam estas funções.
"""

import re

import perfis

_RE_CODIGO = re.compile(r"^[A-Za-z]{3}$")   # código de loja = exatamente 3 letras


def validar_rede(dados):
    """Erros (lista, vazia se válido) para criar/editar uma rede."""
    erros = []
    if not (dados.get("nome") or "").strip():
        erros.append("Nome da rede é obrigatório.")
    return erros


def validar_loja(dados, codigos_existentes):
    """Erros para criar/editar uma loja. `codigos_existentes` = códigos de OUTRAS lojas
    (na edição, exclua o código da própria loja para não acusar duplicidade)."""
    erros = []
    nome   = (dados.get("nome")   or "").strip()
    codigo = (dados.get("codigo") or "").strip()
    if not nome:
        erros.append("Nome da loja é obrigatório.")
    if not codigo:
        erros.append("Código da loja é obrigatório.")
    elif not _RE_CODIGO.match(codigo):
        erros.append("Código deve ter exatamente 3 letras.")
    existentes = {c.strip().upper() for c in (codigos_existentes or [])}
    if codigo and codigo.upper() in existentes:
        erros.append("Código já existe.")
    return erros


def validar_abrangencia_parceiro(dados):
    """Erros para a abrangência de um parceiro.
    abrangencia ∈ {loja, rede}; 'loja' exige >=1 loja em `dados['lojas']`;
    'rede' exige `dados['rede_id']`."""
    erros = []
    abr = (dados.get("abrangencia") or "loja").strip()
    if abr not in ("loja", "rede"):
        erros.append("Abrangência inválida (use 'loja' ou 'rede').")
        return erros
    if abr == "loja" and not (dados.get("lojas") or []):
        erros.append("Selecione ao menos uma loja.")
    if abr == "rede" and not dados.get("rede_id"):
        erros.append("Rede é obrigatória para abrangência de rede.")
    return erros
