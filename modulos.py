"""modulos.py — manifesto declarativo dos módulos (ARQUITETURA-MODULOS.md tornado executável).
Puro (sem dependências do app). Fonte da verdade de: qual arquivo/tabela/rota pertence a qual módulo,
a camada (nucleo|dominio), as dependências permitidas e se o módulo é desligável por loja (topologia)."""

# camada: "nucleo" (transversal, sempre ligado) | "dominio" (ligável/desligável por cliente)
# depende_de: módulos que ESTE pode importar além do próprio núcleo (ratchet do teste de fronteira)
# arquivos/tabelas/rotas: prefixos que identificam o dono. rotas = prefixos de path (match por startswith).
MODULOS = {
    # ── NÚCLEO / PLATAFORMA ────────────────────────────────────────────────
    "auth":        {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["auth.py", "auth_routes.py", "perfis.py", "mod_usuarios.py"],
                    "tabelas": ["usuarios", "sessoes"], "rotas": []},
    "tenancy":     {"camada": "nucleo", "depende_de": ["auth"],
                    "arquivos": ["mod_tenancy.py"],
                    "tabelas": ["redes", "lojas", "usuario_lojas", "parceiro_lojas"], "rotas": []},
    "auditoria":   {"camada": "nucleo", "depende_de": [],
                    "arquivos": [],
                    "tabelas": ["log_autorizacoes", "log_acoes_gerenciais"], "rotas": []},
    "ciclo":       {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["mod_ciclo.py"],
                    "tabelas": ["ciclo_etapas", "ciclo_documentos", "ciclo_revisoes"], "rotas": []},
    "integracoes": {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["emissor_fiscal.py", "focus_client.py", "focus_config.py",
                                 "mod_omie.py", "promob_grupos.py"],
                    "tabelas": [], "rotas": []},
    "plataforma":  {"camada": "nucleo", "depende_de": [],
                    "arquivos": ["database.py", "storage.py"],
                    "tabelas": [], "rotas": []},
    # ── DOMÍNIOS ───────────────────────────────────────────────────────────
    "cadastro":    {"camada": "dominio", "depende_de": [], "rotulo": "Cadastro", "faixa": "vendas",
                    "arquivos": ["validacao_doc.py"],
                    "tabelas": ["clientes", "parceiros"],
                    "rotas": ["/api/clientes", "/api/parceiros"]},
    "comercial":   {"camada": "dominio", "depende_de": ["cadastro"], "rotulo": "Comercial (Vendas)", "faixa": "vendas",
                    "arquivos": ["mod_orcamento_params.py", "mod_margens.py", "mod_negociacao.py",
                                 "mod_proposta.py", "mod_contrato.py", "mod_arvore.py",
                                 "contrato_editar.py", "_ler_aymore.py", "mod_fin"],
                    "tabelas": ["projetos_meta", "briefings", "pool_ambientes", "orcamentos",
                                "orcamento_ambientes", "contratos", "contratos_assinaturas"],
                    "rotas": ["/api/orcamentos", "/api/contratos"]},
    "producao":    {"camada": "dominio", "depende_de": ["cadastro", "comercial"], "rotulo": "Produção / Projetos", "faixa": "execucao_projeto",
                    "arquivos": ["mod_medicao.py", "mod_qualidade_xml.py"],
                    "tabelas": ["medicoes"],
                    "rotas": ["/api/medicoes"]},
    "fiscal":      {"camada": "dominio", "depende_de": ["cadastro", "comercial"], "rotulo": "Fiscal (NF-e/NFS-e)", "faixa": "expedicao",
                    "arquivos": ["mod_fiscal.py", "mapa_fiscal.py", "emissor_focus.py",
                                 "fiscal_cripto.py", "nfe_emissao.py", "mod_nfe.py"],
                    "tabelas": ["emitente", "perfil_emissao", "documento_fiscal"],
                    "rotas": ["/api/projetos/", "/api/admin/lojas/", "/api/admin/redes/"]},
    "financeiro":  {"camada": "dominio", "depende_de": ["comercial"], "rotulo": "Financeiro", "faixa": "financeiro",
                    "arquivos": ["mod_provisoes.py", "mod_contabil.py"],
                    "tabelas": ["provisao_registro", "conta", "lancamento", "periodo_contabil"],
                    "rotas": ["/api/provisoes", "/api/financeiro/contas", "/api/financeiro/lancamentos",
                              "/api/financeiro/eventos", "/api/financeiro/dre", "/api/financeiro/projetos-dre",
                              "/api/financeiro/reconciliar", "/api/financeiro/periodos", "/api/financeiro/balanco",
                              "/api/financeiro/repasse-fabrica", "/api/financeiro/sugerir-conta",
                              "/api/financeiro/provisoes-venda", "/api/financeiro/dashboard"]},
    # domínios NOVOS — fronteira só (stub, sem código/tabela hoje)
    "estoque":     {"camada": "dominio", "depende_de": ["cadastro", "producao"], "rotulo": "Estoque", "faixa": "expedicao",
                    "arquivos": [], "tabelas": [], "rotas": []},
    "posvenda":    {"camada": "dominio", "depende_de": ["cadastro", "fiscal", "estoque"], "rotulo": "Pós-venda", "faixa": "montagem",
                    "arquivos": [], "tabelas": [], "rotas": []},
    "expedicao":   {"camada": "dominio", "depende_de": ["producao", "estoque", "fiscal"], "rotulo": "Expedição / Logística", "faixa": "expedicao",
                    "arquivos": [], "tabelas": [], "rotas": []},
}

# Arquivos que NÃO são módulo (shell/compositor e utilitários). O teste de cobertura os ignora.
SHELL = {"main.py", "seed.py", "reset_ep07.py", "modulos.py"}

# mod_nfe é COMPARTILHADO (parser=produção, pricing=fiscal): lotado em 'fiscal' no manifesto, mas
# 'producao' também pode importá-lo. Declarado aqui para o teste de fronteira aceitar ambos.
COMPARTILHADOS = {"mod_nfe.py": ["fiscal", "producao"]}

NUCLEO = frozenset(n for n, v in MODULOS.items() if v["camada"] == "nucleo")
DOMINIOS = frozenset(n for n, v in MODULOS.items() if v["camada"] == "dominio")


def desligavel(modulo):
    """True se o módulo pode ser desligado por loja (só domínios)."""
    return MODULOS.get(modulo, {}).get("camada") == "dominio"


def modulo_de_arquivo(arquivo):
    """Nome do módulo dono do arquivo (.py ou pacote), ou None se for shell/desconhecido."""
    base = arquivo[:-3] if arquivo.endswith(".py") else arquivo
    for nome, v in MODULOS.items():
        for a in v["arquivos"]:
            if a == arquivo or (a == base):
                return nome
    return None


def modulo_de_tabela(tabela):
    for nome, v in MODULOS.items():
        if tabela in v["tabelas"]:
            return nome
    return None


def modulo_do_path(path):
    """Módulo DESLIGÁVEL dono da rota (por prefixo), ou None. Só retorna domínios — rotas de núcleo
    (login, admin de tenancy) nunca são desligáveis. Prefixos mais específicos vencem (ordem por tamanho)."""
    candidatos = []
    for nome, v in MODULOS.items():
        if v["camada"] != "dominio":
            continue
        for pref in v["rotas"]:
            if path.startswith(pref):
                candidatos.append((len(pref), nome))
    if not candidatos:
        return None
    candidatos.sort(reverse=True)
    return candidatos[0][1]


# Ordem estável dos domínios para a UI (DOMINIOS é frozenset, sem ordem).
DOMINIOS_ORDEM = ["cadastro", "comercial", "producao", "fiscal", "financeiro",
                  "estoque", "posvenda", "expedicao"]


def dominios_com_rotulo():
    """Lista ordenada dos domínios: [{'id','rotulo','depende_de'}]. Para o painel de módulos."""
    return [{"id": d, "rotulo": MODULOS[d].get("rotulo", d),
             "depende_de": list(MODULOS[d]["depende_de"])} for d in DOMINIOS_ORDEM]


def topologia_valida(ativos):
    """(True, "") se o conjunto `ativos` é coerente: todo módulo ativo tem seus depende_de (que são
    domínios) também ativos — senão (False, msg). Núcleo é sempre ativo (ignorado)."""
    ativos = set(ativos)
    for mod in ativos:
        for dep in MODULOS.get(mod, {}).get("depende_de", []):
            if dep in DOMINIOS and dep not in ativos:
                return (False, "Módulo '%s' depende de '%s', que precisa estar ativo." % (mod, dep))
    return (True, "")


# Faixas de titularidade para o hub de módulos (ordem de exibição). As 4 primeiras espelham
# mod_ciclo.FAIXA_POR_ETAPA (Governança do Ciclo); "financeiro" é transversal (dono dos gates 8/11d).
FAIXAS = [
    ("vendas",           "Vendas"),
    ("execucao_projeto", "Execução do Projeto"),
    ("expedicao",        "Logística / Expedição"),
    ("montagem",         "Pós-venda / Montagem"),
    ("financeiro",       "Financeiro"),
]


def hub_layout(ativos):
    """Layout do hub: domínios ATIVOS agrupados por faixa, na ordem de FAIXAS/DOMINIOS_ORDEM.
    Só inclui faixas com ≥1 domínio ativo. [{'faixa','rotulo','modulos':[{'id','rotulo'}]}]."""
    ativos = set(ativos)
    grupos = []
    for fid, frot in FAIXAS:
        mods = [{"id": d, "rotulo": MODULOS[d]["rotulo"]}
                for d in DOMINIOS_ORDEM
                if d in ativos and MODULOS[d].get("faixa") == fid]
        if mods:
            grupos.append({"faixa": fid, "rotulo": frot, "modulos": mods})
    return grupos
