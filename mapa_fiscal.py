"""mapa_fiscal.py — mapa fiscal: preview (Fase 1) + PerfilFiscal/Loja (emitente) + Cliente
(destinatário) -> payload da NF-e da Focus. Puro: sem DB, sem rede. Regime Simples primeiro."""


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
        "consumidor_final": 1,
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
