# -*- coding: utf-8 -*-
"""mod_usuarios.py — Validações (puras) para o CRUD de usuários do painel admin."""

import perfis


def validar_novo_usuario(dados, logins_existentes):
    """Retorna lista de erros (vazia se válido) para criação de usuário."""
    erros = []
    nome  = (dados.get("nome")  or "").strip()
    login = (dados.get("login") or "").strip()
    senha = (dados.get("senha") or "")
    nivel = (dados.get("nivel") or "").strip()
    if not nome:
        erros.append("Nome é obrigatório.")
    if not login:
        erros.append("Login é obrigatório.")
    if not senha:
        erros.append("Senha é obrigatória.")
    if not perfis.existe(nivel):
        erros.append("Perfil inválido.")
    existentes = {l.strip().lower() for l in (logins_existentes or [])}
    if login and login.lower() in existentes:
        erros.append("Login já existe.")
    return erros


def validar_edicao_usuario(dados):
    """Valida campos opcionais de edição (perfil, telefone, ativo, senha)."""
    erros = []
    if "nivel" in dados and not perfis.existe((dados.get("nivel") or "").strip()):
        erros.append("Perfil inválido.")
    return erros
