# tests/test_tenancy_validadores.py
import mod_tenancy as mt


def test_validar_rede():
    assert mt.validar_rede({"nome": "Rede A"}) == []
    erros = mt.validar_rede({"nome": "   "})
    assert any("nome" in e.lower() for e in erros)


def test_validar_loja_ok():
    assert mt.validar_loja({"nome": "Loja A1", "codigo": "AAA"}, codigos_existentes=["INS"]) == []


def test_validar_loja_campos_obrigatorios():
    erros = mt.validar_loja({"nome": "", "codigo": ""}, codigos_existentes=[])
    j = " ".join(erros).lower()
    assert "nome" in j and "código" in j


def test_validar_loja_codigo_3_letras():
    assert any("3 letras" in e.lower() for e in
               mt.validar_loja({"nome": "X", "codigo": "AB"}, []))
    assert any("3 letras" in e.lower() for e in
               mt.validar_loja({"nome": "X", "codigo": "AB12"}, []))
    assert any("3 letras" in e.lower() for e in
               mt.validar_loja({"nome": "X", "codigo": "12"}, []))


def test_validar_loja_codigo_unico_case_insensitive():
    erros = mt.validar_loja({"nome": "X", "codigo": "ins"}, codigos_existentes=["INS"])
    assert any("existe" in e.lower() for e in erros)


def test_validar_abrangencia_parceiro():
    assert mt.validar_abrangencia_parceiro({"abrangencia": "loja", "lojas": [1]}) == []
    assert mt.validar_abrangencia_parceiro({"abrangencia": "rede", "rede_id": 3}) == []
    assert any("loja" in e.lower() for e in
               mt.validar_abrangencia_parceiro({"abrangencia": "loja", "lojas": []}))
    assert any("rede" in e.lower() for e in
               mt.validar_abrangencia_parceiro({"abrangencia": "rede"}))
    assert any("abrang" in e.lower() for e in
               mt.validar_abrangencia_parceiro({"abrangencia": "mundo"}))
