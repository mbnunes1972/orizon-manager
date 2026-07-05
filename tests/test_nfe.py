import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_nfe as mn


def test_split_cprod_sob_medida():
    assert mn.split_cprod("50079[2131748]") == ("50079", "2131748", "sob_medida")
    assert mn.split_cprod("50057[2131751]") == ("50057", "2131751", "sob_medida")


def test_split_cprod_padrao():
    assert mn.split_cprod("80070") == ("80070", None, "padrao")
    assert mn.split_cprod("") == ("", None, "padrao")


def test_parse_infadprod_valido():
    assert mn.parse_infadprod("EBANO 622 600") == {"cor": "EBANO", "largura": 622, "altura": 600}
    assert mn.parse_infadprod("METROPOLITAN 2406 185") == {"cor": "METROPOLITAN", "largura": 2406, "altura": 185}


def test_parse_infadprod_nao_confiavel():
    # só-cor, cor+1-número, número-solto, vazio/None → None (não confiável)
    assert mn.parse_infadprod("MDF BP BRANCO") is None
    assert mn.parse_infadprod("FOSCO 2420") is None
    assert mn.parse_infadprod("970") is None
    assert mn.parse_infadprod("") is None
    assert mn.parse_infadprod(None) is None


import os as _os
_FIX = _os.path.join(_os.path.dirname(__file__), "fixtures", "nfe")

def _ler(nome):
    with open(_os.path.join(_FIX, nome), encoding="utf-8") as f:
        return f.read()


def test_parse_nfe_cabecalho():
    nfe = mn.parse_nfe(_ler("nfe_basica.xml"))
    cab = nfe["cabecalho"]
    assert cab["nNF"] == "170942" and cab["serie"] == "1"
    assert cab["emit"]["cnpj"] == "00000000000000" and cab["emit"]["crt"] == "3"
    assert cab["emit"]["nome"] == "FABRICA TESTE LTDA"
    assert cab["dest"]["nome"] == "LOJA TESTE LTDA" and cab["dest"]["doc"] == "11111111111111"


def test_parse_nfe_itens():
    itens = mn.parse_nfe(_ler("nfe_basica.xml"))["itens"]
    assert len(itens) == 3   # ainda NÃO consolidado
    i0 = itens[0]
    assert i0["cProd"] == "50079[2131748]" and i0["ncm"] == "94035000" and i0["cfop"] == "6101"
    assert i0["qCom"] == 1.0 and i0["vUnCom"] == 71.63 and i0["vProd"] == 71.63
    assert i0["vIPI"] == 3.58 and i0["infAdProd"] == "METROPOLITAN 2406 185"
    # item padrão sem infAdProd
    assert itens[2]["cProd"] == "80070" and itens[2]["infAdProd"] is None


def test_parse_nfe_aceita_bytes():
    itens = mn.parse_nfe(_ler("nfe_basica.xml").encode("utf-8"))["itens"]
    assert len(itens) == 3


def test_parse_nfe_sem_ipi_e_cpf_e_nfe_puro():
    nfe = mn.parse_nfe(_ler("nfe_sem_ipi.xml"))
    assert nfe["cabecalho"]["dest"]["doc"] == "00000000000"   # CPF
    it = nfe["itens"][0]
    assert it["vIPI"] == 0.0 and it["vProd"] == 50.0
