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
    assert m.modulo_de_arquivo("perfis.py") == "auth"
    assert m.modulo_de_arquivo("mod_tenancy.py") == "tenancy"
    assert m.modulo_de_arquivo("main.py") is None
    assert m.modulo_de_arquivo("inexistente.py") is None


def test_modulo_de_arquivo_dentro_de_pacote():
    """Arquivo dentro de PACOTE tem dono: o manifesto registra o pacote pelo diretório.

    Antes de 2026-07-15 isto devolvia None — `mod_fin/aymore.py` estava órfão desde
    que o mod_fin virou pacote, e ninguém notou porque nada além destes testes chama
    modulo_de_arquivo. Trava os dois pacotes atuais."""
    assert m.modulo_de_arquivo("fiscal/mod_fiscal.py") == "fiscal"
    assert m.modulo_de_arquivo("fiscal/nfe_emissao.py") == "fiscal"
    assert m.modulo_de_arquivo("fiscal") == "fiscal"
    assert m.modulo_de_arquivo("mod_fin/aymore.py") == "comercial"
    assert m.modulo_de_arquivo("mod_fin") == "comercial"
    # separador do Windows não pode mudar o dono
    assert m.modulo_de_arquivo("fiscal\\mod_nfe.py") == "fiscal"


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
    assert ids[0] == "captacao"
    assert "posvenda" not in ids                       # virou FAIXA, não módulo (Modulos_Orizon_v4)
    assert {"montagem", "assistencias"} <= set(ids)    # substituem o antigo Pós-venda


def test_faixa_por_dominio():
    assert m.MODULOS["fiscal"]["faixa"] == "expedicao"
    assert m.MODULOS["comercial"]["faixa"] == "vendas"
    assert m.MODULOS["financeiro"]["faixa"] == "financeiro"
    for d in m.DOMINIOS:
        assert m.MODULOS[d].get("faixa"), f"{d} sem faixa"


def test_hub_layout_agrupa_por_faixa():
    g = m.hub_layout(list(m.DOMINIOS))
    faixas = [x["faixa"] for x in g]
    # 'execucao_projeto' saiu do hub: seu único módulo ('producao'/"Projetos") foi retirado da navegação
    # (medição rehospedada em 'comercial'); a faixa sem módulo ativo não aparece.
    assert faixas == ["vendas", "expedicao", "montagem", "financeiro"]
    vendas = next(x for x in g if x["faixa"] == "vendas")
    ids = [mm["id"] for mm in vendas["modulos"]]
    assert ids == ["captacao", "cadastro", "comercial"] and vendas["rotulo"] == "Vendas"


def test_hub_layout_so_ativos_e_sem_faixa_vazia():
    g = m.hub_layout(["cadastro", "comercial"])
    assert [x["faixa"] for x in g] == ["vendas"]
    assert m.hub_layout([]) == []


def test_topologia_valida_fecho_de_dependencia():
    ok, _ = m.topologia_valida(["comercial"])
    assert ok is False
    ok2, _ = m.topologia_valida(["cadastro", "comercial"])
    assert ok2 is True
    ok3, _ = m.topologia_valida(list(m.DOMINIOS))
    assert ok3 is True
    ok4, _ = m.topologia_valida([])
    assert ok4 is True
