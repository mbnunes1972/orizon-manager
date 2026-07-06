# -*- coding: utf-8 -*-
"""perfis.py — Fonte única dos perfis de usuário e suas permissões.

Ao adicionar/alterar um perfil, atualize TAMBÉM docs/USUARIOS.md.
"""

PERFIS = {
    "diretor":                   {"rotulo": "Diretor",                           "desconto_max": 50.0, "ver_parametros": True,  "autorizar": True,  "gerir_usuarios": True,  "aprovar_financeiro": True,  "registrar_medicao": True,  "aprovar_medicao_reprovada": True},
    "gerente_vendas":            {"rotulo": "Gerente de Vendas",                 "desconto_max": 20.0, "ver_parametros": True,  "autorizar": True,  "gerir_usuarios": False, "aprovar_medicao_reprovada": True},
    "consultor":                 {"rotulo": "Consultor",                         "desconto_max": 10.0, "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "gerente_adm_fin":           {"rotulo": "Gerente Administrativo/Financeiro", "desconto_max": 0.0,  "ver_parametros": True,  "autorizar": False, "gerir_usuarios": True,  "aprovar_financeiro": True,  "aprovar_medicao_reprovada": True},
    "assistente_logistico":      {"rotulo": "Assistente Logístico",              "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "conferente":                {"rotulo": "Conferente",                        "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "supervisor_montagem":       {"rotulo": "Supervisor de Montagem",            "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "assistente_administrativo": {"rotulo": "Assistente Administrativo",         "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "projetista_executivo":      {"rotulo": "Projetista Executivo",             "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "medidor":                   {"rotulo": "Medidor",                           "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False, "registrar_medicao": True},
}

_DEFAULT = {"rotulo": "—", "desconto_max": 0.0, "ver_parametros": False,
            "autorizar": False, "gerir_usuarios": False, "aprovar_financeiro": False,
            "registrar_medicao": False, "aprovar_medicao_reprovada": False}


def existe(slug):
    return slug in PERFIS


def slugs():
    return list(PERFIS.keys())


def rotulo(slug):
    return PERFIS.get(slug, _DEFAULT)["rotulo"]


def desconto_max(slug):
    return PERFIS.get(slug, _DEFAULT)["desconto_max"]


def pode(slug, capacidade):
    return bool(PERFIS.get(slug, _DEFAULT).get(capacidade, False))
