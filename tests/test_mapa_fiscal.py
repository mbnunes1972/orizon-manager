import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mapa_fiscal as mp


def _nota(uf_emit="SP", uf_dest="SP", doc_tipo="cpf"):
    dest_doc = {"doc_tipo": doc_tipo,
                "doc": ("11111111111111" if doc_tipo == "cnpj" else "22222222222")}
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


def test_montar_nota_from_objetos():
    perfil = SimpleNamespace(razao_social="LOJA X LTDA", regime_tributario="simples",
                             inscricao_estadual="ISENTO", csosn_padrao="101",
                             cfop_dentro_uf="5102", cfop_fora_uf="6102")
    loja = SimpleNamespace(cnpj="19152134000156", nome="Loja X", logradouro="Rua A", numero="1",
                           bairro="Centro", cidade="Sao Paulo", estado="SP", cep="01000-000")
    cliente = SimpleNamespace(nome="Cliente Y", cpf="22222222222", logradouro="Rua B", numero="2",
                              bairro="Jd", cidade="Rio", estado="RJ", cep="20000-000")
    itens = [{"cProd": "X", "xProd": "P", "ncm": "9403", "uCom": "UN",
              "qCom": 1.0, "preco_venda_unit": 10.0}]
    nota = mp.montar_nota(perfil, loja, cliente, itens, ref="R9", data_emissao="D")
    assert nota["ref"] == "R9" and nota["data_emissao"] == "D"
    assert nota["natureza_operacao"] == "Venda de mercadoria"
    assert nota["emitente"]["doc_tipo"] == "cnpj" and nota["emitente"]["doc"] == "19152134000156"
    assert nota["emitente"]["regime"] == 1 and nota["emitente"]["nome"] == "LOJA X LTDA"
    assert nota["emitente"]["uf"] == "SP"
    assert nota["destinatario"]["doc_tipo"] == "cpf" and nota["destinatario"]["doc"] == "22222222222"
    assert nota["destinatario"]["uf"] == "RJ"
    assert nota["fiscal"]["csosn"] == "101" and nota["fiscal"]["cfop_dentro"] == "5102"
    assert nota["fiscal"]["pis_cst"] == "49" and nota["fiscal"]["cofins_cst"] == "49"
    assert nota["itens"] == itens
    p = mp.montar_payload(nota)
    assert p["items"][0]["cfop"] == "6102"          # SP emit vs RJ dest -> fora


def test_montar_nota_regime_normal_e_cliente_cnpj():
    perfil = SimpleNamespace(razao_social="L", regime_tributario="normal", inscricao_estadual="1",
                             csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102")
    loja = SimpleNamespace(cnpj="1", nome="L", logradouro="a", numero="1", bairro="b",
                           cidade="c", estado="SP", cep="1")
    cliente = SimpleNamespace(nome="C", cnpj="99999999000199", cpf=None, logradouro="a", numero="1",
                              bairro="b", cidade="c", estado="SP", cep="1")
    nota = mp.montar_nota(perfil, loja, cliente, [], ref="R", data_emissao="D")
    assert nota["emitente"]["regime"] == 3          # normal -> 3
    assert nota["destinatario"]["doc_tipo"] == "cnpj" and nota["destinatario"]["doc"] == "99999999000199"


def test_montar_nota_nome_cai_para_loja_sem_razao_social():
    perfil = SimpleNamespace(razao_social=None, regime_tributario="simples", inscricao_estadual=None,
                             csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102")
    loja = SimpleNamespace(cnpj="1", nome="NOME FANTASIA", logradouro="a", numero="1", bairro="b",
                           cidade="c", estado="SP", cep="1")
    cliente = SimpleNamespace(nome="C", cpf="2", logradouro="a", numero="1", bairro="b",
                              cidade="c", estado="SP", cep="1")
    nota = mp.montar_nota(perfil, loja, cliente, [], ref="R", data_emissao="D")
    assert nota["emitente"]["nome"] == "NOME FANTASIA"   # sem razao_social -> loja.nome
