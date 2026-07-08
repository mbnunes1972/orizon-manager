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


# ── Escopo e atribuição (puros) ───────────────────────────────────────────────
# ator = {"nivel", "loja_id", "rede_id"}; loja = {"id", "rede_id"}.

def _eh_super_admin(ator):
    return perfis.pode(ator.get("nivel"), "gerir_redes")          # só super_admin tem gerir_redes


def _eh_admin_rede(ator):
    return (perfis.pode(ator.get("nivel"), "gerir_lojas")
            and not _eh_super_admin(ator)
            and ator.get("rede_id") is not None)


def pode_ver_rede(ator, rede_id):
    """super_admin vê qualquer rede; admin_rede só a própria; demais, nenhuma.

    NOTA: o diretor NÃO é coberto aqui (não tem rede_id próprio). O caso de o diretor
    poder agir sobre a rede da PRÓPRIA loja (ex.: parceiro de abrangência 'rede') é
    resolvido no call site, que consulta loja.rede_id no banco (esta função é pura)."""
    if _eh_super_admin(ator):
        return True
    if _eh_admin_rede(ator):
        return ator.get("rede_id") == rede_id
    return False


def pode_ver_loja(ator, loja):
    """super_admin vê qualquer loja; admin_rede só lojas da sua rede;
    usuário de loja só a própria."""
    if _eh_super_admin(ator):
        return True
    if _eh_admin_rede(ator):
        return loja.get("rede_id") == ator.get("rede_id")
    if ator.get("loja_id") is not None:
        return loja.get("id") == ator.get("loja_id")
    return False


def pode_editar_dados_loja(ator, loja):
    """Precisa da capacidade editar_dados_loja E enxergar a loja no seu escopo."""
    if not perfis.pode(ator.get("nivel"), "editar_dados_loja"):
        return False
    return pode_ver_loja(ator, loja)


def pode_editar_dados_rede(ator, rede_id):
    """Editar config da rede (segredos, ambiente, perfil de emissão) exige capacidade de EDIÇÃO,
    não só de leitura — espelha `pode_editar_dados_loja`. Defensivo (auditoria A6): hoje quem enxerga
    a rede já tem `editar_dados_loja`, mas gravar segredo/virar produção não deve depender do predicado
    de leitura `pode_ver_rede`."""
    if not perfis.pode(ator.get("nivel"), "editar_dados_loja"):
        return False
    return pode_ver_rede(ator, rede_id)


def atribuir_tenant_usuario(ator, dados):
    """Decide (loja_id, rede_id) do NOVO usuário conforme quem cria.
    Retorna (loja_id, rede_id, erros). A checagem de que a loja escolhida pertence
    ao escopo do ator é feita na rota (precisa consultar o banco)."""
    erros = []
    nivel_novo = (dados.get("nivel") or "").strip()

    if _eh_super_admin(ator):
        if nivel_novo == "super_admin":
            return (None, None, erros)
        if nivel_novo == "admin_rede":
            rede_id = dados.get("rede_id")
            if not rede_id:
                erros.append("Rede é obrigatória para admin de rede.")
            return (None, rede_id, erros)
        loja_id = dados.get("loja_id")
        if not loja_id:
            erros.append("Loja é obrigatória.")
        return (loja_id, None, erros)

    if _eh_admin_rede(ator):
        if nivel_novo == "super_admin":
            erros.append("Sem permissão para criar esse perfil.")
            return (None, None, erros)
        if nivel_novo == "admin_rede":
            return (None, ator.get("rede_id"), erros)   # par na mesma rede
        loja_id = dados.get("loja_id")
        if not loja_id:
            erros.append("Loja é obrigatória.")
        return (loja_id, None, erros)

    # usuário de loja com gerir_usuarios (diretor / gerente_adm_fin): herda a própria loja
    if perfis.pode(ator.get("nivel"), "gerir_usuarios") and ator.get("loja_id") is not None:
        if nivel_novo in ("super_admin", "admin_rede"):
            erros.append("Sem permissão para criar esse perfil.")
            return (None, None, erros)
        return (ator.get("loja_id"), None, erros)

    erros.append("Sem permissão.")
    return (None, None, erros)


def perfis_atribuiveis(ator, escopo):
    """Slugs que `ator` pode atribuir em `escopo` ∈ {loja, rede, plataforma}.
    Fonte única do dropdown de perfil no modal de usuário. A checagem de que a
    loja/rede concreta está no escopo do ator é feita na rota (precisa do banco)."""
    if not perfis.pode(ator.get("nivel"), "gerir_usuarios"):
        return []
    if escopo == "plataforma":
        return ["super_admin"] if _eh_super_admin(ator) else []
    if escopo == "rede":
        if _eh_super_admin(ator) or _eh_admin_rede(ator):
            return ["admin_rede"]
        return []
    if escopo == "loja":
        return [s for s in perfis.slugs() if s not in ("super_admin", "admin_rede")]
    return []


def lojas_do_novo_usuario(ator, dados):
    """Lista de loja_ids para o novo usuário operacional (>=1) ou [] para papéis admin.
    Retorna (loja_ids, erros). A checagem de que cada loja ∈ escopo do ator é feita na rota."""
    nivel_novo = (dados.get("nivel") or "").strip()
    if nivel_novo in ("super_admin", "admin_rede"):
        return ([], [])
    ids = dados.get("loja_ids")
    if ids is None and dados.get("loja_id") is not None:
        ids = [dados.get("loja_id")]          # compat: aceita loja_id único
    limpos = []
    for x in (ids or []):
        try:
            limpos.append(int(x))
        except (TypeError, ValueError):
            return ([], ["Loja inválida."])
    ids = limpos
    if not ids:
        return ([], ["Selecione ao menos uma loja."])
    # se o ator é usuário de loja (diretor), só pode a própria loja
    if (not _eh_super_admin(ator) and not _eh_admin_rede(ator)
            and ator.get("loja_id") is not None):
        ids = [ator.get("loja_id")]
    return (ids, [])


def escopo_operacional(ator):
    """Escopo de uma operação NA LOJA: usa a loja ATIVA resolvida.

    (loja_id, None) quando há loja ativa; (None, motivo) quando não há
    (perfil administrativo, sem loja, ou header de loja inválido).
    """
    loja_id = ator.get("active_loja_id")
    if loja_id is None:
        return (None, "Sem acesso operacional (perfil administrativo, sem loja, ou loja inválida).")
    return (loja_id, None)


def resolver_loja_ativa(memberships, header_loja_id, default_loja_id):
    """Decide a loja ativa de uma requisição operacional.

    acessíveis = memberships ∪ {default}. header presente → só vale se acessível
    (senão None → 403). Sem header → default se acessível; senão membership única; senão None.
    """
    acessiveis = set(memberships or [])
    if default_loja_id is not None:
        acessiveis.add(default_loja_id)
    if header_loja_id is not None:
        return header_loja_id if header_loja_id in acessiveis else None
    if default_loja_id is not None and default_loja_id in acessiveis:
        return default_loja_id
    if len(acessiveis) == 1:
        return next(iter(acessiveis))
    return None


def modulos_ativos_da_loja(loja):
    """Conjunto de módulos de DOMÍNIO ativos na loja. NULL/"" em `modulos_ativos` = todos ligados.
    O Núcleo é sempre ativo (não entra na lista). Topologia por cliente (ARQUITETURA-MODULOS.md)."""
    import json as _json
    import modulos as _mod
    bruto = getattr(loja, "modulos_ativos", None)
    if not (bruto or "").strip():
        return set(_mod.DOMINIOS)
    try:
        lista = _json.loads(bruto)
    except (ValueError, TypeError):
        return set(_mod.DOMINIOS)
    return {d for d in _mod.DOMINIOS if d in set(lista)}


def modulo_ativo(loja, modulo):
    """True se o módulo está ativo para a loja. Núcleo é sempre True; domínio depende da topologia."""
    import modulos as _mod
    if not _mod.desligavel(modulo):
        return True
    return modulo in modulos_ativos_da_loja(loja)
