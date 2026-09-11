# -*- coding: utf-8 -*-
"""mod_implantacao_loja.py — perfil de implantação de loja (docs/db/TAREFA_LOJA_TESTE.md).

Uma função que APLICA, duas fontes que ALIMENTAM (mesmo padrão de `mod_contabil.
aplicar_gabarito_completo`, R15 — uma implementação, dois pontos de entrada):

    exportar_config_loja(db, loja_id)                 -> artefato   # lê do banco
    aplicar_config_loja(db, loja_destino_id, artefato) -> relatorio # escreve no banco

O clone (loja → loja no MESMO banco, Etapa 1 da tarefa) é só o caso em que o artefato não
chega a tocar o disco:

    clone       = aplicar_config_loja(db, nova_id, exportar_config_loja(db, origem_id))
    implantação = aplicar_config_loja(db_destino, nova_id, json.load(arquivo))

Regra que governa tudo: CONFIGURAÇÃO viaja, DADO não. Nunca toca: Cliente, Projeto, Orcamento,
Contrato, Aditivo, Lancamento, ProvisaoRegistro, ComissaoFolha, FolhaPagamento, Funcionario,
Usuario, Agenda, CicloDocumento — nenhuma tabela de instância.

O que o artefato NUNCA carrega (mesmo dentro do processo, antes de virar JSON):
  - segredo: `focus_token_homolog_enc`/`focus_token_prod_enc`, certificado (`cert_validade`/
    `cert_cnpj` — são identidade-adjacentes, não só segredo; ficam de fora do artefato, mesmo
    sem valor secreto neles hoje);
  - identidade (CNPJ, razão social, inscrições) viaja marcada `identidade: True` — só é
    ESCRITA por `aplicar_config_loja` se `excecoes.get("permitir_identidade")` for
    explicitamente True. Em Produção essa flag não se liga (ver docstring de `aplicar_config_loja`);
  - dado de instância;
  - a árvore contábil inteira — só a LISTA de divergências (`divergencias_gabarito`), pra
    conferência humana; o destino sempre SEMEIA (`aplicar_gabarito_completo`), nunca copia.
"""
import json
from datetime import datetime

from database import (
    Loja, PerfilAcesso, Funcao, DocumentoModelo, Emitente, Conta, CentroCusto,
)
import mod_contabil as mc

VERSAO_FORMATO = 1

# Campos de Emitente que NÃO são segredo nem identidade — viajam sempre (mesma allowlist de
# main.py:_fiscal_get/_fiscal_put_config, a fonte já existente de "o que é config fiscal não-
# secreta"). cert_validade/cert_cnpj ficam de fora aqui de propósito: são identidade-adjacentes
# (dizem de QUEM é o certificado) — mesmo sem carregar arquivo nenhum (não há certificado
# armazenado em keys/ hoje, conferido), a decisão do artefato é não misturar isso com config.
_EMITENTE_FISCAL = (
    "nome_fantasia", "regime_tributario", "csosn_padrao", "csosn_contribuinte",
    "cfop_dentro_uf", "cfop_fora_uf", "serie_nfe", "discrimina_impostos", "cnae_servico",
    "cod_servico_municipio", "aliquota_iss", "retencao_json", "municipio_ibge", "papel_cnpj",
    "logradouro", "numero", "bairro", "cidade", "uf", "cep",
)
_EMITENTE_IDENTIDADE = ("cnpj", "razao_social", "inscricao_estadual", "inscricao_municipal")

_LOJA_CONFIG = (
    "config_financeira_json", "telefone", "email", "responsavel",
    "cep", "logradouro", "numero", "complemento", "bairro", "cidade", "estado", "rede_id",
)


# ── Plano de contas / centro de custo — medir, nunca copiar a árvore ────────────────────────────

def _gabarito_centro_custo_esperado():
    return {codigo: (nome, mc._pai_codigo(codigo)) for codigo, nome in mc.CENTRO_CUSTO_PADRAO}


def _gabarito_conta_esperado():
    codigos = {c for c, _ in mc.PLANO_PADRAO}
    esperado = {}
    for codigo, nome in mc.PLANO_PADRAO:
        grupo = int(codigo.split(".")[0])
        tipo = "sintetica" if any(o.startswith(codigo + ".") for o in codigos) else "analitica"
        cc_codigo, nat_custo = mc.CLASSIFICACAO_GRUPO5_V1.get(codigo, (None, None))
        esperado[codigo] = (nome, grupo, tipo, mc._natureza(grupo), mc._pai_codigo(codigo),
                             cc_codigo, nat_custo)
    return esperado


def divergencias_gabarito(db, owner_tipo, owner_id):
    """Compara a árvore REAL de um owner com o que `aplicar_gabarito_completo` produziria HOJE
    pra um owner novo — mesma lógica de comparação de `tests/test_gabarito_migration_x_seed.py`
    (R14). Não decide nada: cada divergência pode ser configuração legítima (decisão de negócio
    tomada depois do seed) ou resíduo (renome represado — R13) — humano decide, não este código.

    Retorna lista de dicts: {tabela, codigo, gabarito, owner} — `gabarito`/`owner` são a tupla
    de campos relevantes (ou None se o código só existe do outro lado)."""
    cc_esperado = _gabarito_centro_custo_esperado()
    conta_esperado = _gabarito_conta_esperado()

    cc_rows = db.query(CentroCusto).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()
    cc_by_id = {c.id: c for c in cc_rows}
    cc_real = {c.codigo: (c.nome, cc_by_id[c.pai_id].codigo if c.pai_id else None)
               for c in cc_rows}

    conta_rows = db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()
    conta_by_id = {c.id: c for c in conta_rows}
    cc_codigo_by_id = {c.id: c.codigo for c in cc_rows}
    conta_real = {}
    for c in conta_rows:
        pai_codigo = conta_by_id[c.pai_id].codigo if c.pai_id else None
        conta_real[c.codigo] = (c.nome, c.grupo, c.tipo, c.natureza, pai_codigo,
                                 cc_codigo_by_id.get(c.centro_custo_id), c.natureza_custo)

    divergencias = []
    for codigo in sorted(set(cc_esperado) | set(cc_real)):
        if cc_esperado.get(codigo) != cc_real.get(codigo):
            divergencias.append({"tabela": "centro_custo", "codigo": codigo,
                                 "gabarito": cc_esperado.get(codigo), "owner": cc_real.get(codigo)})
    for codigo in sorted(set(conta_esperado) | set(conta_real)):
        if conta_esperado.get(codigo) != conta_real.get(codigo):
            divergencias.append({"tabela": "conta", "codigo": codigo,
                                 "gabarito": conta_esperado.get(codigo), "owner": conta_real.get(codigo)})
    return divergencias


def _aplicar_divergencias_aceitas(db, owner_tipo, owner_id, divergencias, codigos_aceitos):
    """Aplica só as divergências cujo `codigo` está em `codigos_aceitos` (decisão humana feita
    fora daqui) por cima do gabarito já semeado. Só CRIA/ATUALIZA pelo valor do `owner` de
    origem — nunca apaga (um código 'só no gabarito, ausente na origem' não vira remoção; isso
    é trabalho de `varrer_orfaos_gabarito`, decidido à parte)."""
    if not codigos_aceitos:
        return {"aplicadas": 0}
    aceitos = set(codigos_aceitos)
    aplicadas = 0
    # Duas passadas (centro_custo antes de conta) — conta pode referenciar centro_custo aceito
    # na mesma leva; senão o pai_id do centro_custo pode não existir ainda quando a conta o busca.
    cc_por_codigo = {c.codigo: c for c in
                     db.query(CentroCusto).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    for d in divergencias:
        if d["tabela"] != "centro_custo" or d["codigo"] not in aceitos or d["owner"] is None:
            continue
        nome, pai_codigo = d["owner"]
        pai = cc_por_codigo.get(pai_codigo) if pai_codigo else None
        cc = cc_por_codigo.get(d["codigo"])
        if cc is None:
            cc = CentroCusto(owner_tipo=owner_tipo, owner_id=owner_id, codigo=d["codigo"],
                             nome=nome, pai_id=pai.id if pai else None)
            db.add(cc); db.flush()
            cc_por_codigo[d["codigo"]] = cc
        else:
            cc.nome = nome
            cc.pai_id = pai.id if pai else None
        aplicadas += 1

    conta_por_codigo = {c.codigo: c for c in
                        db.query(Conta).filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    for d in divergencias:
        if d["tabela"] != "conta" or d["codigo"] not in aceitos or d["owner"] is None:
            continue
        nome, grupo, tipo, natureza, pai_codigo, cc_codigo, nat_custo = d["owner"]
        pai = conta_por_codigo.get(pai_codigo) if pai_codigo else None
        cc = cc_por_codigo.get(cc_codigo) if cc_codigo else None
        conta = conta_por_codigo.get(d["codigo"])
        if conta is None:
            conta = Conta(owner_tipo=owner_tipo, owner_id=owner_id, codigo=d["codigo"],
                          nome=nome, grupo=grupo, tipo=tipo, natureza=natureza,
                          pai_id=pai.id if pai else None,
                          centro_custo_id=cc.id if cc else None, natureza_custo=nat_custo)
            db.add(conta); db.flush()
            conta_por_codigo[d["codigo"]] = conta
        else:
            conta.nome, conta.grupo, conta.tipo, conta.natureza = nome, grupo, tipo, natureza
            conta.pai_id = pai.id if pai else None
            conta.centro_custo_id = cc.id if cc else None
            conta.natureza_custo = nat_custo
        aplicadas += 1
    return {"aplicadas": aplicadas}


# ── Criação da loja-base — mesma sequência de main.py (POST /api/admin/lojas), sem o diretor ───

def criar_loja_base(db, nome, codigo, rede_id=None):
    """Cria a Loja e semeia o baseline padrão — a MESMA sequência que main.py usa na criação de
    loja pela tela (perfis, funções, gabarito), menos a criação do usuário diretor: a Loja Teste
    (e qualquer loja implantada por este mecanismo) nasce SEM equipe — funcionários e usuários
    não fazem parte de config de loja. Reusa `perfil_store.seed_perfis_loja`, `seed.
    criar_funcoes_seed` e `mod_contabil.aplicar_gabarito_completo` — não uma cópia paralela."""
    if db.query(Loja).filter_by(codigo=codigo).first() is not None:
        raise ValueError("já existe uma loja com codigo=%r" % codigo)
    loja = Loja(nome=nome, codigo=codigo, rede_id=rede_id)
    db.add(loja)
    db.flush()   # precisa do id para os seeds abaixo

    from auth import perfil_store
    import seed as _seed
    perfil_store.seed_perfis_loja(db, loja.id)
    _seed.criar_funcoes_seed(db, loja.id)
    mc.aplicar_gabarito_completo(db, "loja", loja.id)
    db.commit()
    return loja


# ── Exportar ─────────────────────────────────────────────────────────────────────────────────

def exportar_config_loja(db, loja_id, exportado_por=None, ambiente_origem=None):
    """Lê a config de uma loja e devolve o artefato (dict JSON-serializável). Não grava nada."""
    loja = db.get(Loja, loja_id)
    if loja is None:
        raise ValueError("loja id=%r não existe" % loja_id)

    perfis = [
        {"slug": p.slug, "nome": p.nome, "base": p.base,
         "modulos": json.loads(p.modulos_json or "[]"),
         "capacidades": json.loads(p.capacidades_json or "{}"), "sistema": p.sistema}
        for p in db.query(PerfilAcesso).filter_by(loja_id=loja.id).order_by(PerfilAcesso.id).all()
    ]

    funcoes = [
        {"nome": f.nome, "status": f.status, "perfil_padrao": f.perfil_padrao,
         "atribuicoes": json.loads(f.atribuicoes_json) if f.atribuicoes_json else None,
         "remuneracao_padrao": f.remuneracao_padrao, "regime_trabalho": f.regime_trabalho,
         "regime_contratacao": f.regime_contratacao, "descricao": f.descricao,
         "salario_fixo": f.salario_fixo,
         "beneficios": json.loads(f.beneficios_json) if f.beneficios_json else None,
         "comissao": json.loads(f.comissao_json) if f.comissao_json else None,
         "usa_comissao_vendas": f.usa_comissao_vendas, "comissao_fixa": f.comissao_fixa}
        for f in db.query(Funcao).filter_by(loja_id=loja.id).order_by(Funcao.id).all()
    ]

    # Só a versão ATIVA de cada tipo — o histórico é rastro de contrato assinado, não config
    # (docstring de DocumentoModelo: imutável de propósito). Recriada com versao=1 no destino.
    documentos = [
        {"tipo": d.tipo, "nome": d.nome, "corpo_md": d.corpo_md,
         "origem_nome": d.origem_nome, "origem_sha256": d.origem_sha256}
        for d in db.query(DocumentoModelo).filter_by(loja_id=loja.id, ativo=1)
                   .order_by(DocumentoModelo.tipo).all()
    ]

    emitente = None
    if loja.emitente_id:
        em = db.get(Emitente, loja.emitente_id)
        if em is not None:
            emitente = {
                "identidade": {c: getattr(em, c) for c in _EMITENTE_IDENTIDADE},
                "fiscal": {c: getattr(em, c) for c in _EMITENTE_FISCAL},
                "placeholders": json.loads(em.placeholders_json) if em.placeholders_json else None,
                "rede_id": em.rede_id,
            }

    artefato = {
        "versao_formato": VERSAO_FORMATO,
        "ambiente_origem": ambiente_origem,
        "loja_origem": {"id": loja.id, "nome": loja.nome, "codigo": loja.codigo},
        "exportado_em": datetime.utcnow().isoformat() + "Z",
        "exportado_por": exportado_por,
        "loja": {c: getattr(loja, c) for c in _LOJA_CONFIG},
        "perfis": perfis,
        "funcoes": funcoes,
        "documentos_modelo": documentos,
        "emitente": emitente,
        "gabarito_divergencias": divergencias_gabarito(db, "loja", loja.id),
    }
    return artefato


# ── Aplicar ──────────────────────────────────────────────────────────────────────────────────

def aplicar_config_loja(db, loja_destino_id, artefato, excecoes=None):
    """Escreve a config do artefato numa loja JÁ EXISTENTE (criada por `criar_loja_base` ou
    equivalente) — de onde quer que o artefato tenha vindo (`exportar_config_loja` no mesmo
    processo, ou `json.load` de um arquivo). Idempotente: rodar duas vezes não duplica perfil,
    função nem modelo (upsert por chave natural: slug, nome, tipo).

    `excecoes`: dict opcional.
      - "permitir_identidade" (bool, default False): só com True o CNPJ/razão social/inscrições
        do Emitente são escritos. Em Produção esta flag NUNCA se liga — emitir nota no CNPJ de
        outra empresa é o que ela permitiria; é condicional a este ambiente (só credencial de
        homologação em uso), não uma regra geral do mecanismo.
      - "divergencias_gabarito_aceitas" (list[str] de códigos, default nenhum): quais códigos de
        `artefato["gabarito_divergencias"]` aplicar por cima do gabarito semeado — decisão
        humana, tomada fora desta função (ver `divergencias_gabarito`); sem a lista, NENHUMA
        divergência é aplicada (default seguro: só o gabarito).

    Retorna relatório: {"recusado": [...], "aplicado": {...}}."""
    excecoes = excecoes or {}
    permitir_identidade = bool(excecoes.get("permitir_identidade"))
    codigos_aceitos = excecoes.get("divergencias_gabarito_aceitas") or []

    loja = db.get(Loja, loja_destino_id)
    if loja is None:
        raise ValueError("loja destino id=%r não existe" % loja_destino_id)

    recusado = []
    aplicado = {}

    # ── Loja: config financeira, contato, endereço, rede — NUNCA codigo/nome (identidade do
    # destino, decidida por quem chamou criar_loja_base, nunca pelo artefato). ───────────────
    for campo, valor in artefato["loja"].items():
        setattr(loja, campo, valor)
    aplicado["loja"] = list(artefato["loja"].keys())

    # ── Perfis: upsert por slug ──────────────────────────────────────────────────────────────
    existentes = {p.slug: p for p in db.query(PerfilAcesso).filter_by(loja_id=loja.id).all()}
    perfis_criados = perfis_atualizados = 0
    for p in artefato["perfis"]:
        alvo = existentes.get(p["slug"])
        if alvo is None:
            alvo = PerfilAcesso(loja_id=loja.id, slug=p["slug"])
            db.add(alvo)
            perfis_criados += 1
        else:
            perfis_atualizados += 1
        alvo.nome = p["nome"]; alvo.base = p["base"]
        alvo.modulos_json = json.dumps(p["modulos"])
        alvo.capacidades_json = json.dumps(p["capacidades"])
        alvo.sistema = p["sistema"]
    aplicado["perfis"] = {"criados": perfis_criados, "atualizados": perfis_atualizados}

    # ── Funções: upsert por nome ─────────────────────────────────────────────────────────────
    existentes_f = {f.nome: f for f in db.query(Funcao).filter_by(loja_id=loja.id).all()}
    funcoes_criadas = funcoes_atualizadas = 0
    for f in artefato["funcoes"]:
        alvo = existentes_f.get(f["nome"])
        if alvo is None:
            alvo = Funcao(loja_id=loja.id, nome=f["nome"])
            db.add(alvo)
            funcoes_criadas += 1
        else:
            funcoes_atualizadas += 1
        alvo.status = f["status"]; alvo.perfil_padrao = f["perfil_padrao"]
        alvo.atribuicoes_json = json.dumps(f["atribuicoes"]) if f["atribuicoes"] is not None else None
        alvo.remuneracao_padrao = f["remuneracao_padrao"]
        alvo.regime_trabalho = f["regime_trabalho"]; alvo.regime_contratacao = f["regime_contratacao"]
        alvo.descricao = f["descricao"]; alvo.salario_fixo = f["salario_fixo"]
        alvo.beneficios_json = json.dumps(f["beneficios"]) if f["beneficios"] is not None else None
        alvo.comissao_json = json.dumps(f["comissao"]) if f["comissao"] is not None else None
        alvo.usa_comissao_vendas = f["usa_comissao_vendas"]; alvo.comissao_fixa = f["comissao_fixa"]
    aplicado["funcoes"] = {"criadas": funcoes_criadas, "atualizadas": funcoes_atualizadas}

    # ── Documentos-modelo: só cria a versão ativa=1 que ainda não existe (por tipo+corpo_md) ──
    existentes_d = {d.tipo: d for d in db.query(DocumentoModelo)
                    .filter_by(loja_id=loja.id, ativo=1).all()}
    docs_criados = docs_pulados = 0
    for d in artefato["documentos_modelo"]:
        ja = existentes_d.get(d["tipo"])
        if ja is not None and ja.corpo_md == d["corpo_md"]:
            docs_pulados += 1
            continue
        prox_versao = 1
        if ja is not None:
            # já existe versão ativa com corpo DIFERENTE — nunca sobrescreve (imutável); a nova
            # config vira a versão SEGUINTE, marcada ativa (mesmo fluxo de edição de modelo).
            maior = (db.query(DocumentoModelo)
                     .filter_by(loja_id=loja.id, tipo=d["tipo"])
                     .order_by(DocumentoModelo.versao.desc()).first())
            prox_versao = (maior.versao + 1) if maior else 1
            ja.ativo = 0
        db.add(DocumentoModelo(loja_id=loja.id, tipo=d["tipo"], versao=prox_versao,
                               nome=d["nome"], corpo_md=d["corpo_md"],
                               origem_nome=d["origem_nome"], origem_sha256=d["origem_sha256"],
                               ativo=1, criado_por_id=None))
        docs_criados += 1
    aplicado["documentos_modelo"] = {"criados": docs_criados, "pulados_ja_iguais": docs_pulados}

    # ── Emitente: fiscal sempre; identidade só com a flag; token/cert nunca por aqui ─────────
    if artefato.get("emitente"):
        em_art = artefato["emitente"]
        em = db.get(Emitente, loja.emitente_id) if loja.emitente_id else None
        if em is None:
            em = Emitente(rede_id=em_art.get("rede_id"))
            db.add(em); db.flush()
            loja.emitente_id = em.id
        for campo, valor in em_art["fiscal"].items():
            setattr(em, campo, valor)
        if em_art.get("placeholders") is not None:
            em.placeholders_json = json.dumps(em_art["placeholders"])
        if permitir_identidade:
            for campo, valor in em_art["identidade"].items():
                setattr(em, campo, valor)
            aplicado["emitente_identidade"] = "aplicada"
        else:
            recusado.append(
                "emitente.identidade (cnpj/razao_social/inscricoes) NÃO aplicada — "
                "permitir_identidade=False. CNPJ e razão social do destino ficam intocados.")
        # Condicional ao AMBIENTE (docs/db/TAREFA_LOJA_TESTE.md): hoje só há credencial de
        # homologação em uso — token de produção NUNCA é escrito por este mecanismo, e o
        # ambiente ativo do destino é sempre forçado pra homologação, ignorando a origem. Se
        # este mecanismo for reusado pra abrir loja de verdade em Produção, esta trava tem que
        # ser revista JUNTO com `permitir_identidade` — as duas decisões nasceram do mesmo
        # motivo (ambiente só tem credencial de homologação), não são independentes.
        em.ambiente_ativo = "homologacao"
        aplicado["emitente_fiscal"] = "aplicado"
    elif loja.emitente_id is None:
        recusado.append("artefato sem emitente — destino fica sem Emitente vinculado.")

    # ── Gabarito: sempre semeia (idempotente), nunca copia a árvore. Divergências só as
    # explicitamente aceitas em excecoes (decisão humana feita ANTES desta chamada). ─────────
    mc.aplicar_gabarito_completo(db, "loja", loja.id)
    resultado_div = _aplicar_divergencias_aceitas(
        db, "loja", loja.id, artefato.get("gabarito_divergencias") or [], codigos_aceitos)
    aplicado["gabarito_divergencias_aplicadas"] = resultado_div["aplicadas"]
    nao_decididas = len(artefato.get("gabarito_divergencias") or []) - len(codigos_aceitos)
    if nao_decididas > 0:
        recusado.append(
            "%d divergência(s) do gabarito no artefato NÃO foram aplicadas (fora de "
            "divergencias_gabarito_aceitas) — ver artefato['gabarito_divergencias']."
            % nao_decididas)

    db.commit()
    return {"recusado": recusado, "aplicado": aplicado}
