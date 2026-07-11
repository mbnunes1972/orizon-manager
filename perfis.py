# -*- coding: utf-8 -*-
"""perfis.py — Fonte única dos perfis de usuário e suas permissões.

Ao adicionar/alterar um perfil, atualize TAMBÉM docs/USUARIOS.md.
"""

# Perfil = NÍVEL DE ACESSO (Regras_Funcoes_Perfis_Atribuicoes rev2 §2): 4 perfis de LOJA definidos por
# acesso a módulo/painel (acesso_*), + os 2 de plataforma/rede. Os CARGOS (Diretor, Medidor, …) saíram
# daqui e viraram Função (tabela Funcao). Capacidades operacionais mapeadas de forma grosseira p/ não
# quebrar os gates vigentes; a precisão fina por Função é frente posterior.
PERFIS = {
    "diretoria": {"rotulo": "Diretoria", "desconto_max": 50.0,
        "acesso_operacional": True, "acesso_financeiro": True, "acesso_fiscal": True,
        "acesso_admin": True, "acesso_config": True,
        "ver_parametros": True, "autorizar": True, "aprovar_financeiro": True,
        "aprovar_medicao_reprovada": True, "gerir_usuarios": True, "editar_dados_loja": True,
        "executar_pe": True, "revisar_pe": True, "registrar_medicao": True},
    "gerencial": {"rotulo": "Gerencial", "desconto_max": 20.0,
        "acesso_operacional": True, "acesso_financeiro": False, "acesso_fiscal": False,
        "acesso_admin": True, "acesso_config": True,
        "ver_parametros": True, "autorizar": True, "aprovar_financeiro": False,
        "aprovar_medicao_reprovada": True, "gerir_usuarios": True, "editar_dados_loja": True,
        "executar_pe": True, "revisar_pe": True, "registrar_medicao": True},
    "consultor": {"rotulo": "Consultor", "desconto_max": 10.0,
        "acesso_operacional": True, "acesso_financeiro": False, "acesso_fiscal": False,
        "acesso_admin": False, "acesso_config": False,
        "ver_parametros": False, "autorizar": False, "aprovar_financeiro": False,
        "aprovar_medicao_reprovada": False, "gerir_usuarios": False, "editar_dados_loja": False,
        "executar_pe": True, "revisar_pe": False, "registrar_medicao": True},
    "suporte": {"rotulo": "Suporte", "desconto_max": 0.0,
        "acesso_operacional": False, "acesso_financeiro": False, "acesso_fiscal": False,
        "acesso_admin": True, "acesso_config": True,
        "ver_parametros": False, "autorizar": False, "aprovar_financeiro": False,
        "aprovar_medicao_reprovada": False, "gerir_usuarios": True, "editar_dados_loja": True,
        "executar_pe": False, "revisar_pe": False, "registrar_medicao": False},
    # ── Plataforma/Rede (fora dos 4 de loja) — inalterados no papel; ganham só os acesso_* de painel ──
    "super_admin": {"rotulo": "Administrador da Plataforma", "desconto_max": 0.0,
        "acesso_operacional": False, "acesso_financeiro": False, "acesso_fiscal": False,
        "acesso_admin": True, "acesso_config": True,
        "gerir_usuarios": True, "editar_dados_loja": True, "gerir_redes": True, "gerir_lojas": True},
    "admin_rede": {"rotulo": "Administrador de Rede", "desconto_max": 0.0,
        "acesso_operacional": False, "acesso_financeiro": False, "acesso_fiscal": False,
        "acesso_admin": True, "acesso_config": True,
        "gerir_usuarios": True, "editar_dados_loja": True, "gerir_redes": False, "gerir_lojas": True},
}

_DEFAULT = {"rotulo": "—", "desconto_max": 0.0, "ver_parametros": False,
            "autorizar": False, "gerir_usuarios": False, "aprovar_financeiro": False,
            "registrar_medicao": False, "aprovar_medicao_reprovada": False,
            "gerir_redes": False, "gerir_lojas": False, "editar_dados_loja": False,
            "executar_pe": False, "revisar_pe": False,
            "acesso_operacional": False, "acesso_financeiro": False, "acesso_fiscal": False,
            "acesso_admin": False, "acesso_config": False}

# Acesso a MÓDULO/PAINEL (matriz rev2 §2) — mapeia id de módulo → capacidade acesso_* do perfil.
_MODULOS_OPERACIONAIS = frozenset({"captacao", "cadastro", "comercial", "producao",
                                   "estoque", "expedicao", "montagem", "assistencias"})
_MODULO_ACESSO = {"financeiro": "acesso_financeiro", "folha": "acesso_financeiro",
                  "fiscal": "acesso_fiscal"}


def acessa_modulo(slug, modulo_id):
    """True se o perfil `slug` pode abrir o módulo de domínio `modulo_id` (matriz §2)."""
    if modulo_id in _MODULO_ACESSO:
        return pode(slug, _MODULO_ACESSO[modulo_id])
    if modulo_id in _MODULOS_OPERACIONAIS:
        return pode(slug, "acesso_operacional")
    return True   # módulos de núcleo / desconhecidos não são bloqueados por esta matriz


def acessa_painel(slug, painel):
    """True se o perfil abre o painel 'admin' (page-07) ou 'config' (page-09)."""
    return pode(slug, "acesso_admin" if painel == "admin" else "acesso_config")


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
    "acesso_operacional":        {"rotulo": "Módulos operacionais",       "grupo": "Acesso",
        "descricao": "Abrir os módulos operacionais (Cadastro, Comercial, Projetos, Expedição…)."},
    "acesso_financeiro":         {"rotulo": "Financeiro / Folha",         "grupo": "Acesso",
        "descricao": "Abrir os módulos Financeiro e Folha de Pagamento."},
    "acesso_fiscal":             {"rotulo": "Fiscal",                     "grupo": "Acesso",
        "descricao": "Abrir o módulo Fiscal (NF-e/NFS-e)."},
    "acesso_admin":              {"rotulo": "Painel Admin",               "grupo": "Acesso",
        "descricao": "Abrir o painel de Administração (identidade e acesso)."},
    "acesso_config":             {"rotulo": "Painel Config",              "grupo": "Acesso",
        "descricao": "Abrir o painel de Config (parâmetros de negócio)."},
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
