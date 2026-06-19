import mod_medicao as mm


def test_pareceres():
    assert mm.PARECERES == {"aprovado", "reprovado", "parcial"}


def test_validar_parecer_ok():
    assert mm.validar_parecer("aprovado", "") == []
    assert mm.validar_parecer("reprovado", "") == []
    assert mm.validar_parecer("parcial", "Cozinha, Dormitório") == []


def test_validar_parecer_invalido():
    erros = mm.validar_parecer("talvez", "")
    assert any("parecer" in e.lower() for e in erros)


def test_validar_parcial_exige_ambientes():
    erros = mm.validar_parecer("parcial", "   ")
    assert any("ambiente" in e.lower() for e in erros)


def test_modelo_medicao_campos():
    from database import Medicao
    m = Medicao(projeto_nome="p", parecer="aprovado")
    assert m.projeto_nome == "p"
    assert m.parecer == "aprovado"
    for c in ["solicitacao_arquivo", "planta_arquivo", "doc_cliente_arquivo",
              "ambientes_aprovados", "medidor_id", "excecao_por", "solicitacao_por"]:
        assert hasattr(m, c)
