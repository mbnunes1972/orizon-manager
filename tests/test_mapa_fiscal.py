import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from fiscal import mapa_fiscal as mp


def _nota(uf_emit="SP", uf_dest="SP", doc_tipo="cpf"):
    # doc_tipo cpf -> nao_contribuinte (indicador 9, consumidor_final 1);
    # doc_tipo cnpj -> contribuinte (indicador 1, consumidor_final 0, IE enviada).
    if doc_tipo == "cnpj":
        dest_doc = {"doc_tipo": "cnpj", "doc": "11111111111111",
                    "indicador_ie": 1, "ie": "ISE123", "consumidor_final": 0}
    else:
        dest_doc = {"doc_tipo": "cpf", "doc": "22222222222",
                    "indicador_ie": 9, "ie": None, "consumidor_final": 1}
    return {
        "ref": "R1", "natureza_operacao": "Venda de mercadoria",
        "data_emissao": "2026-07-05T10:00:00-03:00",
        "emitente": {"doc_tipo": "cnpj", "doc": "19152134000156", "nome": "LOJA X", "regime": 1,
                     "ie": "ISENTO", "logradouro": "Rua A", "numero": "1", "bairro": "Centro",
                     "municipio": "Sao Paulo", "uf": uf_emit, "cep": "01000-000"},
        "destinatario": {"nome": "CLIENTE Y", "logradouro": "Rua B", "numero": "2", "bairro": "Jd",
                         "municipio": "Rio", "uf": uf_dest, "cep": "20000-000", **dest_doc},
        "fiscal": {"csosn": "101", "cfop_dentro": "5102", "cfop_fora": "6102",
                   "pis_cst": "49", "cofins_cst": "49"},
        "itens": [
            {"cProd": "50079[2131748]", "xProd": "PAINEL", "ncm": "94035000", "uCom": "UN",
             "qCom": 2.0, "preco_venda_unit": 97.77},
            {"cProd": "80070", "xProd": "CORREDICA", "ncm": "83024200", "uCom": "UN",
             "qCom": 1.0, "preco_venda_unit": 13.65},
        ],
    }


def test_payload_topo_e_emitente():
    p = mp.montar_payload(_nota())
    assert p["tipo_documento"] == 1 and p["finalidade_emissao"] == 1
    assert p["consumidor_final"] == 1 and p["presenca_comprador"] == 1
    assert p["modalidade_frete"] == 9      # obrigatório p/ SEFAZ (era ausente → "Modalidade frete não pode ser vazio")
    assert p["natureza_operacao"] == "Venda de mercadoria"
    assert p["data_emissao"] == "2026-07-05T10:00:00-03:00"
    assert p["cnpj_emitente"] == "19152134000156" and "cpf_emitente" not in p
    assert p["regime_tributario_emitente"] == 1 and p["nome_emitente"] == "LOJA X"
    assert p["uf_emitente"] == "SP" and p["cep_emitente"] == "01000-000"


def test_payload_destinatario_cpf_e_indicador():
    p = mp.montar_payload(_nota(doc_tipo="cpf"))
    assert p["cpf_destinatario"] == "22222222222" and "cnpj_destinatario" not in p
    assert p["indicador_inscricao_estadual_destinatario"] == 9
    assert p["pais_destinatario"] == "Brasil" and p["nome_destinatario"] == "CLIENTE Y"
    assert p["consumidor_final"] == 1          # PF -> consumidor final


def test_payload_destinatario_cnpj():
    p = mp.montar_payload(_nota(doc_tipo="cnpj"))
    assert p["cnpj_destinatario"] == "11111111111111" and "cpf_destinatario" not in p
    assert p["consumidor_final"] == 0          # PJ -> não consumidor final


def test_payload_cfop_dentro_uf():
    p = mp.montar_payload(_nota(uf_emit="SP", uf_dest="SP"))
    assert all(it["cfop"] == "5102" for it in p["items"])


def test_payload_cfop_fora_uf():
    p = mp.montar_payload(_nota(uf_emit="SP", uf_dest="RJ"))
    assert all(it["cfop"] == "6102" for it in p["items"])


def test_payload_itens():
    p = mp.montar_payload(_nota())
    it0 = p["items"][0]
    assert it0["numero_item"] == 1 and it0["codigo_produto"] == "50079[2131748]"
    assert it0["descricao"] == "PAINEL" and it0["codigo_ncm"] == "94035000"
    assert it0["unidade_comercial"] == "UN"
    assert it0["icms_origem"] == "0" and it0["icms_situacao_tributaria"] == "101"
    assert it0["pis_situacao_tributaria"] == "49" and it0["cofins_situacao_tributaria"] == "49"
    assert it0["quantidade_comercial"] == 2.0 and it0["valor_unitario_comercial"] == 97.77
    assert it0["valor_bruto"] == 195.54          # round(2 * 97.77, 2)
    assert p["items"][1]["numero_item"] == 2 and p["items"][1]["valor_bruto"] == 13.65


from types import SimpleNamespace


def _emitente(**kw):
    base = dict(cnpj="19152134000156", razao_social="LOJA X LTDA", regime_tributario="simples",
                inscricao_estadual="ISENTO", csosn_padrao="101", csosn_contribuinte=None,
                cfop_dentro_uf="5102", cfop_fora_uf="6102", logradouro="Rua A", numero="1",
                bairro="Centro", cidade="Sao Paulo", uf="SP", cep="01000-000")
    base.update(kw)
    return SimpleNamespace(**base)


def _cli(tipo, **kw):
    base = dict(nome="C", tipo_dest=tipo, cpf="111.444.777-35", cnpj="11.222.333/0001-44",
                inscricao_estadual="ISE123", logradouro="R", numero="1", bairro="b",
                cidade="c", estado="SP", cep="20000-000")
    base.update(kw)
    return SimpleNamespace(**base)


def test_ramo_contribuinte():
    emit = _emitente(uf="SP", csosn_contribuinte="101", csosn_padrao="102")
    nota = mp.montar_nota(emit, _cli("contribuinte"), [], "R", "D")
    d = nota["destinatario"]
    assert d["doc_tipo"] == "cnpj" and d["doc"] == "11222333000144"
    assert d["indicador_ie"] == 1 and d["ie"] == "ISE123" and d["consumidor_final"] == 0
    assert nota["fiscal"]["csosn"] == "101"
    p = mp.montar_payload(nota)
    assert p["indicador_inscricao_estadual_destinatario"] == 1
    assert p["inscricao_estadual_destinatario"] == "ISE123" and p["consumidor_final"] == 0


def test_ramo_isento():
    emit = _emitente(uf="SP", csosn_padrao="102")
    nota = mp.montar_nota(emit, _cli("isento"), [], "R", "D")
    d = nota["destinatario"]
    assert d["doc_tipo"] == "cnpj" and d["indicador_ie"] == 2 and d["consumidor_final"] == 1
    assert nota["fiscal"]["csosn"] == "102"
    p = mp.montar_payload(nota)
    assert p["indicador_inscricao_estadual_destinatario"] == 2 and "inscricao_estadual_destinatario" not in p


def test_ramo_nao_contribuinte():
    emit = _emitente(uf="SP", csosn_padrao="102")
    nota = mp.montar_nota(emit, _cli("nao_contribuinte"), [], "R", "D")
    d = nota["destinatario"]
    assert d["doc_tipo"] == "cpf" and d["doc"] == "11144477735" and d["indicador_ie"] == 9 and d["consumidor_final"] == 1
    assert nota["fiscal"]["csosn"] == "102"
    p = mp.montar_payload(nota)
    assert p["indicador_inscricao_estadual_destinatario"] == 9 and "inscricao_estadual_destinatario" not in p


def test_csosn_default_no_codigo_quando_emitente_null():
    emit = _emitente(uf="SP", csosn_contribuinte=None, csosn_padrao=None)
    assert mp.montar_nota(emit, _cli("contribuinte"), [], "R", "D")["fiscal"]["csosn"] == "101"
    assert mp.montar_nota(emit, _cli("nao_contribuinte"), [], "R", "D")["fiscal"]["csosn"] == "102"


def test_montar_nota_from_objetos():
    emitente = _emitente(uf="SP")
    cliente = SimpleNamespace(nome="Cliente Y", cpf="22222222222", logradouro="Rua B", numero="2",
                              bairro="Jd", cidade="Rio", estado="RJ", cep="20000-000")
    itens = [{"cProd": "X", "xProd": "P", "ncm": "9403", "uCom": "UN",
              "qCom": 1.0, "preco_venda_unit": 10.0}]
    nota = mp.montar_nota(emitente, cliente, itens, ref="R9", data_emissao="D")
    assert nota["ref"] == "R9" and nota["data_emissao"] == "D"
    assert nota["natureza_operacao"] == "Venda de mercadoria"
    assert nota["emitente"]["doc_tipo"] == "cnpj" and nota["emitente"]["doc"] == "19152134000156"
    assert nota["emitente"]["regime"] == 1 and nota["emitente"]["nome"] == "LOJA X LTDA"
    assert nota["emitente"]["uf"] == "SP" and nota["emitente"]["municipio"] == "Sao Paulo"
    assert nota["emitente"]["ie"] == "ISENTO"
    assert nota["destinatario"]["doc_tipo"] == "cpf" and nota["destinatario"]["doc"] == "22222222222"
    assert nota["destinatario"]["uf"] == "RJ"
    assert nota["fiscal"]["csosn"] == "101" and nota["fiscal"]["cfop_dentro"] == "5102"
    assert nota["fiscal"]["pis_cst"] == "49" and nota["fiscal"]["cofins_cst"] == "49"
    assert nota["itens"] == itens
    p = mp.montar_payload(nota)
    assert p["items"][0]["cfop"] == "6102"          # SP emit vs RJ dest -> fora


def test_montar_nota_regime_normal_e_cliente_cnpj():
    emitente = _emitente(cnpj="1", razao_social="L", regime_tributario="normal",
                         inscricao_estadual="1", cidade="c", uf="SP", cep="1",
                         logradouro="a", numero="1", bairro="b")
    cliente = SimpleNamespace(nome="C", tipo_dest="contribuinte", cnpj="99999999000199", cpf=None,
                              inscricao_estadual="1", logradouro="a", numero="1",
                              bairro="b", cidade="c", estado="SP", cep="1")
    nota = mp.montar_nota(emitente, cliente, [], ref="R", data_emissao="D")
    assert nota["emitente"]["regime"] == 3          # normal -> 3
    assert nota["destinatario"]["doc_tipo"] == "cnpj" and nota["destinatario"]["doc"] == "99999999000199"


def test_montar_nota_emitente_e_um_cnpj_distinto_da_loja():
    # o emitente carrega seu próprio CNPJ/razão — não é a loja vendedora
    emitente = _emitente(cnpj="99999999000188", razao_social="CENTRAL LTDA")
    cliente = SimpleNamespace(nome="C", cpf="2", logradouro="a", numero="1", bairro="b",
                              cidade="c", estado="SP", cep="1")
    nota = mp.montar_nota(emitente, cliente, [], ref="R", data_emissao="D")
    assert nota["emitente"]["doc"] == "99999999000188"
    assert nota["emitente"]["nome"] == "CENTRAL LTDA"
    p = mp.montar_payload(nota)
    assert p["cnpj_emitente"] == "99999999000188"


def test_montar_nota_normaliza_doc_e_cep_para_digitos():
    # SEFAZ rejeitou "CPF inválido" com pontuação → doc/cep devem ir só com dígitos
    from types import SimpleNamespace
    emit = SimpleNamespace(cnpj="19.152.134/0001-56", razao_social="L", regime_tributario="simples",
                           inscricao_estadual="123", csosn_padrao="102", cfop_dentro_uf="5102",
                           cfop_fora_uf="6102", logradouro="R", numero="1", bairro="C",
                           cidade="SP", uf="SP", cep="01000-000")
    cli = SimpleNamespace(nome="C", cnpj=None, cpf="111.444.777-35", logradouro="R", numero="2",
                          bairro="J", cidade="Rio", estado="RJ", cep="20000-000")
    nota = mp.montar_nota(emit, cli, [], "R", "D")
    assert nota["emitente"]["doc"] == "19152134000156"
    assert nota["destinatario"]["doc"] == "11144477735"
    assert nota["emitente"]["cep"] == "01000000" and nota["destinatario"]["cep"] == "20000000"
