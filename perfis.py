# -*- coding: utf-8 -*-
"""perfis.py — Fonte única dos perfis de usuário e suas permissões.

Ao adicionar/alterar um perfil, atualize TAMBÉM docs/USUARIOS.md.
"""

PERFIS = {
    "diretor":                   {"rotulo": "Diretor",                           "desconto_max": 50.0, "ver_parametros": True,  "autorizar": True,  "gerir_usuarios": True,  "aprovar_financeiro": True,  "registrar_medicao": True,  "aprovar_medicao_reprovada": True, "editar_dados_loja": True, "executar_pe": True, "revisar_pe": True},
    "gerente_vendas":            {"rotulo": "Gerente de Vendas",                 "desconto_max": 20.0, "ver_parametros": True,  "autorizar": True,  "gerir_usuarios": False, "aprovar_medicao_reprovada": True, "executar_pe": True, "revisar_pe": True},
    "consultor":                 {"rotulo": "Consultor",                         "desconto_max": 10.0, "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "gerente_adm_fin":           {"rotulo": "Gerente Administrativo/Financeiro", "desconto_max": 0.0,  "ver_parametros": True,  "autorizar": False, "gerir_usuarios": True,  "aprovar_financeiro": True,  "aprovar_medicao_reprovada": True, "executar_pe": True, "revisar_pe": True},
    "assistente_logistico":      {"rotulo": "Assistente Logístico",              "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "conferente":                {"rotulo": "Conferente",                        "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False, "executar_pe": True},
    "supervisor_montagem":       {"rotulo": "Supervisor de Montagem",            "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "assistente_administrativo": {"rotulo": "Assistente Administrativo",         "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "projetista_executivo":      {"rotulo": "Projetista Executivo",             "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False, "executar_pe": True},
    "medidor":                   {"rotulo": "Medidor",                           "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False, "registrar_medicao": True},
    "super_admin":               {"rotulo": "Administrador da Plataforma",       "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": True,  "aprovar_financeiro": False, "registrar_medicao": False, "aprovar_medicao_reprovada": False, "gerir_redes": True,  "gerir_lojas": True,  "editar_dados_loja": True},
    "admin_rede":                {"rotulo": "Administrador de Rede",             "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": True,  "aprovar_financeiro": False, "registrar_medicao": False, "aprovar_medicao_reprovada": False, "gerir_redes": False, "gerir_lojas": True,  "editar_dados_loja": True},
}

_DEFAULT = {"rotulo": "—", "desconto_max": 0.0, "ver_parametros": False,
            "autorizar": False, "gerir_usuarios": False, "aprovar_financeiro": False,
            "registrar_medicao": False, "aprovar_medicao_reprovada": False,
            "gerir_redes": False, "gerir_lojas": False, "editar_dados_loja": False,
            "executar_pe": False, "revisar_pe": False}


def existe(slug):
    return slug in PERFIS


def slugs():
    return list(PERFIS.keys())


# Perfis (acesso) atribuíveis a um login de LOJA — exclui os de plataforma/rede. Fonte única do
# "acesso" oferecido no cadastro de Funcionário (Regras_Funcoes_Perfis_Atribuicoes §8, frente irmã).
_NAO_LOJA = frozenset({"super_admin", "admin_rede"})


def slugs_loja():
    return [s for s in PERFIS if s not in _NAO_LOJA]


def opcoes_loja():
    return [{"slug": s, "rotulo": PERFIS[s]["rotulo"]} for s in slugs_loja()]


def rotulo(slug):
    return PERFIS.get(slug, _DEFAULT)["rotulo"]


def desconto_max(slug):
    return PERFIS.get(slug, _DEFAULT)["desconto_max"]


def pode(slug, capacidade):
    return bool(PERFIS.get(slug, _DEFAULT).get(capacidade, False))


# Metadados legíveis das capacidades — dão nome/descrição aos slugs para a tela Admin › Perfis de
# Usuário FORMALIZAR o que perfis.py já governa. A fonte única de VERDADE continua sendo PERFIS; isto
# é só a camada de apresentação. Toda capacidade booleana usada em PERFIS deve ter entrada aqui.
CAPACIDADES = {
    "ver_parametros":            {"rotulo": "Ver parâmetros",             "grupo": "Comercial",
        "descricao": "Ver o painel de apoio da negociação (margens/custos internos)."},
    "autorizar":                 {"rotulo": "Autorizar desconto",         "grupo": "Comercial",
        "descricao": "Autorizar desconto acima do limite e ações que exigem gerência."},
    "aprovar_financeiro":        {"rotulo": "Aprovar financeiro",         "grupo": "Financeiro",
        "descricao": "Aprovar os gates financeiros e liberar impostos."},
    "gerir_usuarios":            {"rotulo": "Gerir usuários",             "grupo": "Administração",
        "descricao": "Criar/editar contas de usuário da loja."},
    "registrar_medicao":         {"rotulo": "Registrar medição",          "grupo": "Execução",
        "descricao": "Lançar a medição in loco (Medidor)."},
    "aprovar_medicao_reprovada": {"rotulo": "Aprovar medição reprovada",  "grupo": "Execução",
        "descricao": "Liberar medição reprovada (decisão comercial)."},
    "editar_dados_loja":         {"rotulo": "Editar dados da loja",       "grupo": "Administração",
        "descricao": "Editar o cadastro/dados da loja e emitir NF-e."},
    "executar_pe":               {"rotulo": "Executar PE",                "grupo": "Execução",
        "descricao": "Trabalhar nas subfases do Projeto Executivo."},
    "revisar_pe":                {"rotulo": "Revisar PE",                 "grupo": "Execução",
        "descricao": "Revisar/aprovar o Projeto Executivo."},
    "gerir_redes":               {"rotulo": "Gerir redes",                "grupo": "Plataforma",
        "descricao": "Criar/editar redes (plataforma)."},
    "gerir_lojas":               {"rotulo": "Gerir lojas",                "grupo": "Plataforma",
        "descricao": "Criar/editar lojas (rede/plataforma)."},
}


def matriz():
    """Perfis com capacidades resolvidas (derivado de PERFIS) — alimenta Admin › Perfis de Usuário.
    Read-only: reflete o que o código já faz, não configura nada."""
    caps = list(CAPACIDADES.keys())
    loja = set(slugs_loja())
    perfis_out = [{
        "slug": s, "rotulo": PERFIS[s]["rotulo"], "desconto_max": PERFIS[s].get("desconto_max", 0.0),
        "loja": s in loja, "capacidades": [c for c in caps if PERFIS[s].get(c)],
    } for s in slugs()]
    return {"perfis": perfis_out, "capacidades": CAPACIDADES}
