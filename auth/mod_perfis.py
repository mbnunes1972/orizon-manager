# -*- coding: utf-8 -*-
"""mod_perfis.py — validadores puros para criação/edição de perfil_acesso (sem I/O)."""
import re
import unicodedata
import modulos
from . import perfis

_PAINEIS = {"admin", "config"}
_BASES = {"master", "gerencial", "operador"}


def _slugify(txt):
    t = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")
    return t or "perfil"


def gerar_slug(nome, existentes):
    """Slug único globalmente a partir do nome (append _2, _3… se colidir)."""
    base = _slugify(nome)
    if base not in existentes:
        return base
    i = 2
    while f"{base}_{i}" in existentes:
        i += 1
    return f"{base}_{i}"


def ids_validos():
    """Conjunto de ids selecionáveis: os domínios (modulos.DOMINIOS) + os 2 painéis."""
    return set(modulos.DOMINIOS) | _PAINEIS


def validar_modulos(lista):
    if not isinstance(lista, list):
        return False, "modulos deve ser lista"
    validos = ids_validos()
    for m in lista:
        if m not in validos:
            return False, f"módulo inválido: {m}"
    return True, ""


def validar_base(base):
    return (base in _BASES), ("" if base in _BASES else "base inválida")


def validar_nome(nome):
    n = (nome or "").strip()
    return (bool(n), "" if n else "nome obrigatório")


def validar_capacidades(caps):
    """caps = dict {cap: bool} de OVERRIDES; só aceita chaves em perfis.CAPS_SELECIONAVEIS.
    Retorna (True, dict_limpo) ou (False, erro)."""
    if caps in (None, {}):
        return True, {}
    if not isinstance(caps, dict):
        return False, "capacidades deve ser objeto {cap: bool}"
    permitidas = set(perfis.CAPS_SELECIONAVEIS)
    limpo = {}
    for k, v in caps.items():
        if k not in permitidas:
            return False, f"capacidade inválida: {k}"
        limpo[k] = bool(v)
    return True, limpo
