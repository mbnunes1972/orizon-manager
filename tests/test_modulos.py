import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import modulos as m


def test_camadas_e_conjuntos():
    assert m.NUCLEO and m.DOMINIOS
    assert m.NUCLEO.isdisjoint(m.DOMINIOS)
    for nome in m.NUCLEO | m.DOMINIOS:
        assert nome in m.MODULOS
        assert m.MODULOS[nome]["camada"] in ("nucleo", "dominio")


def test_nucleo_nao_e_desligavel():
    for nome in m.NUCLEO:
        assert m.desligavel(nome) is False
    assert any(m.desligavel(d) for d in m.DOMINIOS)


def test_modulo_de_arquivo():
    assert m.modulo_de_arquivo("mod_fiscal.py") == "fiscal"
    assert m.modulo_de_arquivo("perfis.py") == "auth"
    assert m.modulo_de_arquivo("mod_tenancy.py") == "tenancy"
    assert m.modulo_de_arquivo("main.py") is None
    assert m.modulo_de_arquivo("inexistente.py") is None


def test_modulo_de_tabela():
    assert m.modulo_de_tabela("clientes") == "cadastro"
    assert m.modulo_de_tabela("documento_fiscal") == "fiscal"
    assert m.modulo_de_tabela("lojas") == "tenancy"
    assert m.modulo_de_tabela("ciclo_etapas") == "ciclo"


def test_modulo_do_path():
    assert m.modulo_do_path("/api/projetos/X/ciclo/15/emitir-nfe") == "fiscal"
    assert m.modulo_do_path("/api/admin/lojas/1/perfil-fiscal") == "fiscal"
    assert m.modulo_do_path("/api/clientes") == "cadastro"
    assert m.modulo_do_path("/api/orcamentos/9/margens") == "comercial"
    assert m.modulo_do_path("/api/login") is None


def test_rotulo_e_ordem_dos_dominios():
    ordem = m.dominios_com_rotulo()
    ids = [d["id"] for d in ordem]
    assert set(ids) == set(m.DOMINIOS)
    assert all(d["rotulo"] for d in ordem)
    assert ids[0] == "cadastro"


def test_topologia_valida_fecho_de_dependencia():
    ok, _ = m.topologia_valida(["comercial"])
    assert ok is False
    ok2, _ = m.topologia_valida(["cadastro", "comercial"])
    assert ok2 is True
    ok3, _ = m.topologia_valida(list(m.DOMINIOS))
    assert ok3 is True
    ok4, _ = m.topologia_valida([])
    assert ok4 is True
