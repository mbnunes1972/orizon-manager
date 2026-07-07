"""mapa_fiscal.py — mapa fiscal: preview (Fase 1) + Emitente (identidade fiscal, pode ≠ loja) +
Cliente (destinatário) -> payload da NF-e da Focus. Puro: sem DB, sem rede. Regime Simples primeiro."""
import json
import re

REGIME_FOCUS = {"simples": 1, "simples_excesso": 2, "mei": 1, "normal": 3}
PIS_CST_SIMPLES = "49"
COFINS_CST_SIMPLES = "49"

# CSOSN default no código (override opcional no Emitente): contribuinte -> crédito de ICMS;
# demais (isento/não contribuinte) -> sem crédito.
CSOSN_CONTRIBUINTE = "101"
CSOSN_SEM_CREDITO = "102"

# Indicador de IE do destinatário (SEFAZ): 1 contribuinte, 2 isento, 9 não contribuinte.
_INDICADOR_IE = {"contribuinte": 1, "isento": 2, "nao_contribuinte": 9}


def _so_digitos(v):
    """CPF/CNPJ/CEP para a SEFAZ vão só com dígitos (sem pontuação). None/'' preservados."""
    return re.sub(r"\D", "", v) if v else v


def _dest_fiscal(cliente):
    """Ramifica o destinatário por `tipo_dest`: retorna
    (doc_tipo, doc, indicador_ie, ie, consumidor_final). Default -> nao_contribuinte."""
    tipo = getattr(cliente, "tipo_dest", None) or "nao_contribuinte"
    indicador = _INDICADOR_IE.get(tipo, 9)
    if indicador == 9:
        doc_tipo, doc = "cpf", getattr(cliente, "cpf", None)
    else:
        doc_tipo, doc = "cnpj", getattr(cliente, "cnpj", None)
    ie = getattr(cliente, "inscricao_estadual", None) if indicador == 1 else None
    consumidor_final = 0 if indicador == 1 else 1
    return doc_tipo, doc, indicador, ie, consumidor_final


def montar_nota(emitente, cliente, itens_preview, ref, data_emissao,
                natureza="Venda de mercadoria"):
    """Assembla o dict neutro `nota` a partir dos modelos (recebe objetos; sem DB).
    Emitente = objeto `Emitente` (cnpj/endereço/razão/IE/regime + csosn/cfop — pode ≠ loja
    vendedora); destinatário = Cliente (CPF -> PF consumidor final; CNPJ -> PJ, via getattr
    para cobrir modelo futuro)."""
    doc_tipo, doc, indicador_ie, ie_dest, consumidor_final = _dest_fiscal(cliente)
    csosn = (getattr(emitente, "csosn_contribuinte", None) or CSOSN_CONTRIBUINTE) if indicador_ie == 1 \
            else (getattr(emitente, "csosn_padrao", None) or CSOSN_SEM_CREDITO)
    return {
        "ref": ref,
        "natureza_operacao": natureza,
        "data_emissao": data_emissao,
        "emitente": {
            "doc_tipo": "cnpj" if getattr(emitente, "cnpj", None) else "cpf",
            "doc": _so_digitos(getattr(emitente, "cnpj", None)),
            "nome": getattr(emitente, "razao_social", None),
            "regime": REGIME_FOCUS.get(getattr(emitente, "regime_tributario", None), 1),
            "ie": getattr(emitente, "inscricao_estadual", None),
            "logradouro": emitente.logradouro, "numero": emitente.numero, "bairro": emitente.bairro,
            "municipio": emitente.cidade, "uf": emitente.uf, "cep": _so_digitos(emitente.cep),
        },
        "destinatario": {
            "nome": cliente.nome, "doc_tipo": doc_tipo, "doc": _so_digitos(doc),
            "indicador_ie": indicador_ie, "ie": ie_dest, "consumidor_final": consumidor_final,
            "logradouro": cliente.logradouro, "numero": cliente.numero, "bairro": cliente.bairro,
            "municipio": cliente.cidade, "uf": cliente.estado, "cep": _so_digitos(cliente.cep),
        },
        # TODO Fase 4: PIS/COFINS CST "49" e o CSOSN são do SIMPLES. Para regime normal/presumido,
        # ramificar aqui (CST próprios + alíquotas ICMS destacadas) com os valores do contador.
        "fiscal": {
            "csosn": csosn, "cfop_dentro": emitente.cfop_dentro_uf,
            "cfop_fora": emitente.cfop_fora_uf, "pis_cst": PIS_CST_SIMPLES,
            "cofins_cst": COFINS_CST_SIMPLES,
        },
        "itens": list(itens_preview),
    }


def montar_payload(nota):
    """Converte o dict neutro `nota` no payload JSON da Focus NFe (bloco fiscal por item)."""
    emit = nota["emitente"]
    dest = nota["destinatario"]
    fisc = nota["fiscal"]
    # Compat p/ notas montadas à mão (sem os campos do destinatário ramificado): deriva do doc_tipo.
    indicador_ie = dest.get("indicador_ie", 9)
    consumidor_final = dest.get("consumidor_final", 0 if dest["doc_tipo"] == "cnpj" else 1)
    ie_dest = dest.get("ie")
    # UF normalizada (evita 'sp'/'SP '/None cair em interestadual por engano — A3 da auditoria).
    # A prontidão do emitente (mod_fiscal) já barra UF vazia antes de chegar aqui.
    _uf_emit = (emit.get("uf") or "").strip().upper()
    _uf_dest = (dest.get("uf") or "").strip().upper()
    dentro = bool(_uf_emit) and _uf_emit == _uf_dest
    cfop = fisc["cfop_dentro"] if dentro else fisc["cfop_fora"]

    items = []
    for i, it in enumerate(nota["itens"], start=1):
        qtd = it["qCom"]
        vun = it["preco_venda_unit"]
        items.append({
            "numero_item": i,
            "codigo_produto": it["cProd"],
            "descricao": it["xProd"],
            "cfop": cfop,
            "codigo_ncm": it["ncm"],
            "unidade_comercial": it.get("uCom") or "UN",
            "quantidade_comercial": qtd,
            "valor_unitario_comercial": vun,
            "valor_bruto": round(qtd * vun, 2),
            "icms_origem": "0",
            "icms_situacao_tributaria": fisc["csosn"],
            "pis_situacao_tributaria": fisc["pis_cst"],
            "cofins_situacao_tributaria": fisc["cofins_cst"],
        })

    payload = {
        "natureza_operacao": nota["natureza_operacao"],
        "data_emissao": nota["data_emissao"],
        "tipo_documento": 1,
        "finalidade_emissao": 1,
        "consumidor_final": consumidor_final,   # contribuinte = 0; isento/não contribuinte = 1
        "presenca_comprador": 1,
        "modalidade_frete": 9,   # 9 = sem ocorrência de transporte (default; obrigatório p/ SEFAZ). Revisitar (CIF/FOB config).
        "nome_emitente": emit["nome"],
        "regime_tributario_emitente": emit["regime"],
        "inscricao_estadual_emitente": emit["ie"],
        "logradouro_emitente": emit["logradouro"],
        "numero_emitente": emit["numero"],
        "bairro_emitente": emit["bairro"],
        "municipio_emitente": emit["municipio"],
        "uf_emitente": emit["uf"],
        "cep_emitente": emit["cep"],
        "nome_destinatario": dest["nome"],
        "indicador_inscricao_estadual_destinatario": indicador_ie,
        "logradouro_destinatario": dest["logradouro"],
        "numero_destinatario": dest["numero"],
        "bairro_destinatario": dest["bairro"],
        "municipio_destinatario": dest["municipio"],
        "uf_destinatario": dest["uf"],
        "cep_destinatario": dest["cep"],
        "pais_destinatario": "Brasil",
        "items": items,
    }
    if emit["doc_tipo"] == "cnpj":
        payload["cnpj_emitente"] = emit["doc"]
    else:
        payload["cpf_emitente"] = emit["doc"]
    if dest["doc_tipo"] == "cnpj":
        payload["cnpj_destinatario"] = dest["doc"]
    else:
        payload["cpf_destinatario"] = dest["doc"]
    # IE do destinatário só faz sentido (e SEFAZ só aceita) para contribuinte com IE.
    if indicador_ie == 1 and ie_dest:
        payload["inscricao_estadual_destinatario"] = ie_dest
    return payload


# ------------------------------------------------------------------------------------------------
# NFS-e de serviço (municipal). Espelha o caminho do NF-e de produto, mas a nota é ISS/serviço:
# prestador (Emitente) + tomador (Cliente) + servico (valor/alíquota/discriminação/código).
# ------------------------------------------------------------------------------------------------

def _iss_retido(emitente):
    """Lê `retencao_json` do Emitente (se houver) -> iss_retido (bool). Default False."""
    raw = getattr(emitente, "retencao_json", None)
    if not raw:
        return False
    try:
        dados = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        return False
    return bool(isinstance(dados, dict) and dados.get("iss_retido"))


def _tributacao_nfse(emitente):
    """Bloco de tributação da NFS-e derivado do regime do Emitente. Descoberto no smoke real de
    SJC (2026-07-07): a prefeitura rejeita (E188) se o Simples Nacional não vier coerente com o
    Regime Especial de Tributação. `optante_simples_nacional` vem do regime; RET 6 = ME/EPP do
    Simples (caso da INSPIRIUM; MEI seria 5 — refinar quando o Emitente distinguir). `natureza_operacao`
    1 = tributação no município (montagem prestada no local do cliente, ISS devido no município)."""
    optante = (getattr(emitente, "regime_tributario", None) or "").lower() == "simples"
    return {
        "optante_simples_nacional": optante,
        "regime_especial_tributacao": "6" if optante else None,
        "natureza_operacao": "1",
    }


def montar_nota_nfse(emitente, cliente, valor_servico, ref, data_emissao, discriminacao):
    """Assembla o dict neutro `nota_nfse` (sem DB/rede): prestador (do Emitente), tomador (do
    cliente via `_dest_fiscal`), servico (valor/ISS/código de serviço). Docs só-dígitos."""
    doc_tipo, doc, _indicador, _ie, _consumidor = _dest_fiscal(cliente)
    return {
        "ref": ref,
        "data_emissao": data_emissao,
        # tributação (Simples/RET/natureza) — vai ao topo do payload; ver _tributacao_nfse.
        "tributacao": _tributacao_nfse(emitente),
        "prestador": {
            "cnpj": _so_digitos(getattr(emitente, "cnpj", None)),
            "inscricao_municipal": getattr(emitente, "inscricao_municipal", None),
            "codigo_municipio": getattr(emitente, "municipio_ibge", None),
            "razao_social": getattr(emitente, "razao_social", None),
        },
        "tomador": {
            "doc_tipo": doc_tipo, "doc": _so_digitos(doc),
            "razao_social": cliente.nome,
            "logradouro": cliente.logradouro, "numero": cliente.numero, "bairro": cliente.bairro,
            "municipio": cliente.cidade, "uf": cliente.estado, "cep": _so_digitos(cliente.cep),
            # IBGE do tomador — sem ele a prefeitura marca "Tomador Não Identificado" (L999).
            "codigo_municipio": getattr(cliente, "municipio_ibge", None),
        },
        "servico": {
            "valor_servicos": valor_servico,
            "aliquota": getattr(emitente, "aliquota_iss", None),
            "discriminacao": discriminacao,
            "iss_retido": _iss_retido(emitente),
            # item_lista_servico = código do serviço no município (LC 116); codigo_tributario = CNAE.
            "item_lista_servico": getattr(emitente, "cod_servico_municipio", None),
            "codigo_tributario_municipio": getattr(emitente, "cnae_servico", None),
        },
    }


def montar_payload_nfse(nota):
    """Converte o dict neutro `nota_nfse` no payload JSON da Focus `/v2/nfse`.
    Nomes de campo próximos à doc da Focus NFS-e (validar no smoke estrutural)."""
    pr = nota["prestador"]
    to = nota["tomador"]
    sv = nota["servico"]
    trib = nota.get("tributacao") or {}
    endereco = {
        "logradouro": to["logradouro"], "numero": to["numero"], "bairro": to["bairro"],
        "municipio": to["municipio"], "uf": to["uf"], "cep": to["cep"],
    }
    if to.get("codigo_municipio"):
        endereco["codigo_municipio"] = to["codigo_municipio"]
    tomador = {"razao_social": to["razao_social"], "endereco": endereco}
    if to["doc_tipo"] == "cnpj":
        tomador["cnpj"] = to["doc"]
    else:
        tomador["cpf"] = to["doc"]
    payload = {
        "data_emissao": nota["data_emissao"],
        # tributação no topo do objeto NFS-e (Focus). optante sempre; RET só quando aplicável.
        "optante_simples_nacional": bool(trib.get("optante_simples_nacional")),
        "natureza_operacao": trib.get("natureza_operacao", "1"),
        "prestador": {
            "cnpj": pr["cnpj"],
            "inscricao_municipal": pr["inscricao_municipal"],
            "codigo_municipio": pr["codigo_municipio"],
        },
        "tomador": tomador,
        "servico": {
            "valor_servicos": sv["valor_servicos"],
            "aliquota": sv["aliquota"],
            "iss_retido": sv["iss_retido"],
            "item_lista_servico": sv["item_lista_servico"],
            "codigo_tributario_municipio": sv["codigo_tributario_municipio"],
            "discriminacao": sv["discriminacao"],
        },
    }
    if trib.get("regime_especial_tributacao"):
        payload["regime_especial_tributacao"] = trib["regime_especial_tributacao"]
    return payload
