import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import validacao_doc as vd


def test_cpf_valido():
    assert vd.valida_cpf("111.444.777-35") and vd.valida_cpf("11144477735")
    assert vd.valida_cpf("390.533.447-05")


def test_cpf_invalido():
    assert not vd.valida_cpf("111.444.777-00")   # DV errado
    assert not vd.valida_cpf("111.111.111-11")   # repetido
    assert not vd.valida_cpf("123")              # tamanho
    assert not vd.valida_cpf("")                 # vazio
    assert not vd.valida_cpf(None)


def test_cnpj_valido():
    assert vd.valida_cnpj("11.222.333/0001-81") and vd.valida_cnpj("19152134000156")


def test_cnpj_invalido():
    assert not vd.valida_cnpj("11.222.333/0001-00")
    assert not vd.valida_cnpj("00000000000000")
    assert not vd.valida_cnpj("123")


def test_doc_valido_por_tamanho():
    assert vd.doc_valido("11144477735") and vd.doc_valido("11222333000181")
    assert not vd.doc_valido("123456")           # nem 11 nem 14
    assert not vd.doc_valido("111.444.777-00")   # 11 díg mas DV errado


def test_erro_doc():
    assert vd.erro_doc("", "CPF") is None                        # vazio -> ok
    assert vd.erro_doc(None, "CPF") is None
    assert vd.erro_doc("111.444.777-35", "CPF", "cpf") is None   # válido
    assert vd.erro_doc("111.444.777-00", "CPF", "cpf")           # inválido -> msg
    assert vd.erro_doc("11.222.333/0001-00", "CNPJ", "cnpj")
    assert vd.erro_doc("123456", "Documento")                    # auto -> inválido
    assert vd.erro_doc("11.222.333/0001-81", "CPF/CNPJ") is None  # auto -> CNPJ válido
