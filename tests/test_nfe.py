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
