"""mapa_fiscal.py — mapa fiscal: preview (Fase 1) + PerfilFiscal/Loja (emitente) + Cliente
(destinatário) -> payload da NF-e da Focus. Puro: sem DB, sem rede. Regime Simples primeiro."""

REGIME_FOCUS = {"simples": 1, "simples_excesso": 2, "mei": 1, "normal": 3}
PIS_CST_SIMPLES = "49"
COFINS_CST_SIMPLES = "49"


def montar_nota(perfil, loja, cliente, itens_preview, ref, data_emissao,
                natureza="Venda de mercadoria"):
    """Assembla o dict neutro `nota` a partir dos modelos (recebe objetos; sem DB).
    Emitente = Loja (cnpj/endereço) + perfil (razão social/IE/regime); destinatário = Cliente
    (CPF -> PF consumidor final; CNPJ -> PJ, via getattr para cobrir modelo futuro)."""
    cli_cnpj = getattr(cliente, "cnpj", None)
    if cli_cnpj:
        doc_tipo, doc = "cnpj", cli_cnpj
    else:
        doc_tipo, doc = "cpf", getattr(cliente, "cpf", None)
    return {
        "ref": ref,
        "natureza_operacao": natureza,
        "data_emissao": data_emissao,
        "emitente": {
            "doc_tipo": "cnpj" if getattr(loja, "cnpj", None) else "cpf",
            "doc": getattr(loja, "cnpj", None),
            "nome": getattr(perfil, "razao_social", None) or getattr(loja, "nome", None),
            "regime": REGIME_FOCUS.get(getattr(perfil, "regime_tributario", None), 1),
            "ie": getattr(perfil, "inscricao_estadual", None),
            "logradouro": loja.logradouro, "numero": loja.numero, "bairro": loja.bairro,
            "municipio": loja.cidade, "uf": loja.estado, "cep": loja.cep,
        },
        "destinatario": {
            "nome": cliente.nome, "doc_tipo": doc_tipo, "doc": doc,
            "logradouro": cliente.logradouro, "numero": cliente.numero, "bairro": cliente.bairro,
            "municipio": cliente.cidade, "uf": cliente.estado, "cep": cliente.cep,
        },
        # TODO Fase 4: PIS/COFINS CST "49" e o CSOSN são do SIMPLES. Para regime normal/presumido,
        # ramificar aqui (CST próprios + alíquotas ICMS destacadas) com os valores do contador.
        "fiscal": {
            "csosn": perfil.csosn_padrao, "cfop_dentro": perfil.cfop_dentro_uf,
            "cfop_fora": perfil.cfop_fora_uf, "pis_cst": PIS_CST_SIMPLES,
            "cofins_cst": COFINS_CST_SIMPLES,
        },
        "itens": list(itens_preview),
    }


def montar_payload(nota):
    """Converte o dict neutro `nota` no payload JSON da Focus NFe (bloco fiscal por item)."""
    emit = nota["emitente"]
    dest = nota["destinatario"]
    fisc = nota["fiscal"]
    dentro = emit["uf"] == dest["uf"]
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
        "consumidor_final": 0 if dest["doc_tipo"] == "cnpj" else 1,   # PJ = 0, PF consumidor final = 1
        "presenca_comprador": 1,
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
        "indicador_inscricao_estadual_destinatario": 9,
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
    return payload
