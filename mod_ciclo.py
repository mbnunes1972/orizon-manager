"""
mod_ciclo.py — Ordem canônica das etapas do ciclo e regras de gating sequencial.

Fonte única da verdade (backend) para "qual é a etapa anterior" e se uma etapa
pode avançar. A ordem aqui (2=Criação do projeto, 3=Briefing) é a canônica nova;
o ETAPAS_CICLO do frontend é alinhado a ela na tarefa de frontend.
"""

# Etapas PRINCIPAIS, na ordem. Sub-etapas ("11a".."11e", "17a") NÃO entram aqui
# — elas são livres dentro do pai.
ETAPAS_PRINCIPAIS = [
    "1", "2", "3", "4", "7", "8", "9", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
]

ETAPA_NOME = {
    "1": "Cadastro do Cliente",
    "2": "Criação do projeto",
    "3": "Briefing",
    "4": "Orçamento",
    "7": "Contrato",
    "8": "Aprovação financeira I",
    "9": "Solicitação de medição",
    "10": "Medição",
    "11": "Projeto executivo",
    "12": "Implantação do pedido",
    "13": "Produção",
    "14": "Entrega no depósito",
    "15": "Emissão da NFe do cliente",
    "16": "Entrega no cliente",
    "17": "Montagem",
    "18": "Assistência pós Montagem",
    "19": "Vistoria final",
    "20": "Aprovação final",
}

# Status que contam como "etapa concluída" para fins de gating (espelha o
# conjunto de status conclusivos do handler PATCH /ciclo em main.py).
STATUS_CONCLUSIVOS = frozenset({
    "concluido", "aprovado", "assinado", "vigente",
    "implantado", "realizado", "entregue", "emitida",
})


# ── Projeto Executivo (etapa 11) — subfases enriquecidas ──────────────────────
SUBFASES_PE = {
    "11a": {"nome": "Planta de pontos de PE",       "tipo_doc": "pe_planta_pontos",
            "doc_label": "arquivo de medição",       "botao": "Encaminhar para PE",       "revisavel": False},
    "11b": {"nome": "Reunião de alinhamento",        "tipo_doc": "pe_relatorio_alinhamento",
            "doc_label": "relatório da reunião",     "botao": "Projeto Alinhado",         "revisavel": True},
    "11c": {"nome": "Revisão de PE",                 "tipo_doc": "pe_projeto_executivo",
            "doc_label": "Projeto Executivo",        "botao": "Concluído",                "revisavel": True},
    "11e": {"nome": "Aprovação do PE pelo cliente",  "tipo_doc": "pe_pe_assinado",
            "doc_label": "Projeto Executivo Assinado","botao": "Concluir Projeto Executivo","revisavel": False},
}

# Subfases que precisam estar concluídas antes de concluir o PE (11e).
PE_SUBFASES_OBRIGATORIAS = ["11a", "11b", "11c", "11d"]


def tipo_doc_de(codigo):
    sf = SUBFASES_PE.get(codigo)
    return sf["tipo_doc"] if sf else None


def guarda_conclusao(codigo, tipos_presentes, status_por_codigo):
    """(ok, erro). tipos_presentes: set de tipos de documento já carregados na subfase.
    status_por_codigo: {codigo: status} — usado no 11e para exigir 11a-11d concluídas."""
    sf = SUBFASES_PE.get(codigo)
    if not sf:
        return (False, "Subfase de PE desconhecida.")
    if sf["tipo_doc"] not in tipos_presentes:
        return (False, f"Carregue o documento ({sf['doc_label']}) antes de '{sf['botao']}'.")
    if codigo == "11e":
        faltando = [c for c in PE_SUBFASES_OBRIGATORIAS
                    if status_por_codigo.get(c) not in STATUS_CONCLUSIVOS]
        if faltando:
            return (False, "Conclua as subfases anteriores do PE: " + ", ".join(faltando) + ".")
    return (True, "")


def versao_atual(documentos, tipo):
    """documentos: lista de dicts com 'tipo' e 'enviado_em'. Última versão do tipo, ou None."""
    do_tipo = [d for d in documentos if d.get("tipo") == tipo]
    if not do_tipo:
        return None
    return max(do_tipo, key=lambda d: d["enviado_em"])


# Etapas que exigem autorização financeira (login+senha de quem pode aprovar).
ETAPAS_APROVACAO_FINANCEIRA = frozenset({"8", "11d"})


def exige_aprovacao_financeira(codigo):
    return codigo in ETAPAS_APROVACAO_FINANCEIRA


def _parse_codigo(codigo):
    """'11a' -> (11, 'a'); '2' -> (2, ''). Para ordenação e agrupamento por pai."""
    num, suf = "", ""
    for ch in str(codigo):
        if ch.isdigit() and not suf:
            num += ch
        else:
            suf += ch
    return (int(num) if num else 0, suf)


def is_principal(codigo):
    return codigo in ETAPAS_PRINCIPAIS


def etapa_pai(codigo):
    """Etapa principal de uma sub-etapa ('11a' -> '11', '17a' -> '17').
    Retorna None se o código já for principal ou não tiver pai principal."""
    num, suf = _parse_codigo(codigo)
    if not suf:                      # já é principal (sem sufixo)
        return None
    pai = str(num)
    return pai if pai in ETAPAS_PRINCIPAIS else None


def etapa_anterior(codigo):
    """Código da etapa principal imediatamente anterior, ou None."""
    if codigo not in ETAPAS_PRINCIPAIS:
        return None
    i = ETAPAS_PRINCIPAIS.index(codigo)
    return ETAPAS_PRINCIPAIS[i - 1] if i > 0 else None


def ordenar_codigos(codigos):
    """Ordena códigos numericamente, com sub-etapas logo após o pai."""
    return sorted(codigos, key=_parse_codigo)


def chave_ordenacao(codigo):
    """Key para sorted() quando se ordena objetos por etapa_codigo."""
    return _parse_codigo(codigo)


def pode_avancar(codigo, status_por_codigo):
    """
    True se a etapa pode sair de 'pendente' (iniciar/concluir).
    Sub-etapas herdam o gating da etapa-mãe (desbloqueiam junto com ela).
    Principais exigem a anterior concluída.
    status_por_codigo: dict {codigo: status}.
    """
    if codigo not in ETAPAS_PRINCIPAIS:
        pai = etapa_pai(codigo)
        if pai is None:
            return True
        return pode_avancar(pai, status_por_codigo)
    ant = etapa_anterior(codigo)
    if ant is None:
        return True
    return status_por_codigo.get(ant) in STATUS_CONCLUSIVOS


def codigos_a_resetar(codigo_alvo, codigos_existentes):
    """
    Reabertura em cascata: o próprio alvo + todos posteriores (principais e
    suas sub-etapas). Qualquer código cujo (num, sufixo) >= (num, sufixo) do alvo.
    """
    alvo = _parse_codigo(codigo_alvo)
    return [c for c in codigos_existentes if _parse_codigo(c) >= alvo]


def reabertura_bloqueada_por_contrato(codigos_a_resetar_lista, contrato_status):
    """True se a cascata desfaria a etapa 7 (Contrato) com contrato já firmado."""
    return "7" in set(codigos_a_resetar_lista) and contrato_status in ("assinado", "vigente")
