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
    "cadastro":    {"camada": "dominio", "depende_de": [],
                    "arquivos": ["validacao_doc.py"],
                    "tabelas": ["clientes", "parceiros"],
                    "rotas": ["/api/clientes", "/api/parceiros"]},
    "comercial":   {"camada": "dominio", "depende_de": ["cadastro"],
                    "arquivos": ["mod_orcamento_params.py", "mod_margens.py", "mod_negociacao.py",
                                 "mod_proposta.py", "mod_contrato.py", "mod_arvore.py",
                                 "contrato_editar.py", "_ler_aymore.py", "mod_fin"],
                    "tabelas": ["projetos_meta", "briefings", "pool_ambientes", "orcamentos",
                                "orcamento_ambientes", "contratos", "contratos_assinaturas"],
                    "rotas": ["/api/orcamentos", "/api/contratos"]},
    "producao":    {"camada": "dominio", "depende_de": ["cadastro", "comercial"],
                    "arquivos": ["mod_medicao.py", "mod_qualidade_xml.py"],
                    "tabelas": ["medicoes"],
                    "rotas": ["/api/medicoes"]},
    "fiscal":      {"camada": "dominio", "depende_de": ["cadastro", "comercial"],
                    "arquivos": ["mod_fiscal.py", "mapa_fiscal.py", "emissor_focus.py",
                                 "fiscal_cripto.py", "nfe_emissao.py", "mod_nfe.py"],
                    "tabelas": ["emitente", "perfil_emissao", "documento_fiscal"],
                    "rotas": ["/api/projetos/", "/api/admin/lojas/", "/api/admin/redes/"]},
    "financeiro":  {"camada": "dominio", "depende_de": ["comercial"],
                    "arquivos": ["mod_provisoes.py"],
                    "tabelas": ["provisao_registro"],
                    "rotas": ["/api/provisoes"]},
    # domínios NOVOS — fronteira só (stub, sem código/tabela hoje)
    "estoque":     {"camada": "dominio", "depende_de": ["cadastro", "producao"],
                    "arquivos": [], "tabelas": [], "rotas": []},
    "posvenda":    {"camada": "dominio", "depende_de": ["cadastro", "fiscal", "estoque"],
                    "arquivos": [], "tabelas": [], "rotas": []},
    "expedicao":   {"camada": "dominio", "depende_de": ["producao", "estoque", "fiscal"],
                    "arquivos": [], "tabelas": [], "rotas": []},
}

# Arquivos que NÃO são módulo (shell/compositor e utilitários). O teste de cobertura os ignora.
SHELL = {"main.py", "seed.py", "reset_ep07.py"}

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
