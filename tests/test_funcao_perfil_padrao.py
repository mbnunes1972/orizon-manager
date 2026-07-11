import mod_cadastro


class _F:  # stub simples com os atributos usados
    def __init__(self):
        self.id = None; self.loja_id = None; self.nome = ""; self.status = "ativo"; self.perfil_padrao = None


def test_serialize_inclui_perfil_padrao():
    f = _F(); f.id = 1; f.nome = "Consultor"; f.perfil_padrao = "operador"
    d = mod_cadastro.funcao_serialize(f)
    assert d["perfil_padrao"] == "operador"


def test_aplicar_seta_perfil_padrao():
    f = _F()
    mod_cadastro.funcao_aplicar(None, f, {"nome": "Gerente", "perfil_padrao": "gerencial"}, loja_id=1)
    assert f.perfil_padrao == "gerencial"
