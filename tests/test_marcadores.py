import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_marcadores
import mod_contrato


def _mapping_real():
    """Chaves que _montar_mapping realmente produz, com um ctx mínimo."""
    ctx = {"loja": {"nome": "L", "cnpj": "1", "cidade": "C"}}
    return set(mod_contrato._montar_mapping(ctx, {}).keys())


def test_catalogo_cobre_todo_marcador_do_mapping():
    faltando = _mapping_real() - set(mod_marcadores.CATALOGO)
    assert not faltando, f"marcadores sem verbete no catálogo: {sorted(faltando)}"


def test_catalogo_nao_inventa_marcador():
    # TEXTO_COMPLEMENTAR é injetado em _montar_html_contrato, não em _montar_mapping.
    sobrando = set(mod_marcadores.CATALOGO) - _mapping_real() - {"TEXTO_COMPLEMENTAR"}
    assert not sobrando, f"catálogo promete marcador que ninguém preenche: {sorted(sobrando)}"


def test_todo_verbete_tem_rotulo_e_escopo():
    # "projeto" é reserva: seria o escopo dos marcadores da proposta (AMBIENTES_LISTA,
    # VALOR_BRUTO, DESCONTO_PCT, VALOR_TOTAL, VALIDADE — hoje em mod_proposta.py:18-24)
    # se um dia entrarem; _montar_mapping não os produz, então nenhum verbete o usa ainda.
    for chave, v in mod_marcadores.CATALOGO.items():
        assert v.get("rotulo"), f"{chave} sem rótulo"
        assert v.get("escopo") in ("cliente", "loja", "pagamento", "projeto", "documento"), \
            f"{chave} com escopo inválido: {v.get('escopo')}"


def test_marcadores_de_endereco_da_loja_existem():
    """Sem estes, o preâmbulo do contrato não tem como ser parametrizado."""
    for c in ("LOJA_LOGRADOURO", "LOJA_NUMERO", "LOJA_BAIRRO",
              "LOJA_CIDADE", "LOJA_UF", "LOJA_CEP"):
        assert c in mod_marcadores.CATALOGO, f"faltou {c}"


LOJA_EXEMPLO = {
    "nome": "INSPIRIUM MÓVEIS PLANEJADOS E DECORAÇÃO LTDA",
    "cnpj": "19.152.134/0001-56",
    "cidade": "São José dos Campos",
    "logradouro": "Avenida Barão do Rio Branco",
}


def test_detecta_marcador_conhecido_usado():
    r = mod_marcadores.analisar_corpo("Cliente: [NOME_CLIENTE], CPF [CPF].", {})
    assert set(r["conhecidos_usados"]) == {"NOME_CLIENTE", "CPF"}


def test_detecta_marcador_desconhecido():
    """[FOO] sem verbete seria IMPRESSO literalmente no PDF (_aplica_mark
    devolve m.group(0) quando a chave não existe) — tem que bloquear."""
    r = mod_marcadores.analisar_corpo("Olá [FOO] e [NOME_CLIENTE].", {})
    assert r["desconhecidos"] == ["FOO"]
    assert r["bloqueia_ativacao"] is True


def test_sem_desconhecido_nao_bloqueia():
    r = mod_marcadores.analisar_corpo("Olá [NOME_CLIENTE].", {})
    assert r["desconhecidos"] == []
    assert r["bloqueia_ativacao"] is False


def test_aponta_marcador_essencial_ausente():
    r = mod_marcadores.analisar_corpo("Contrato sem nada.", {})
    assert "NOME_CLIENTE" in r["ausentes"]
    assert "NOME_TESTEMUNHA_1" in r["ausentes"]


def test_avisa_quando_falta_o_ponto_de_injecao_do_adendo():
    """Achado da revisão do Task 2: mod_documentos_import só insere
    [TEXTO_COMPLEMENTAR] se o texto tiver o marco de fecho do modelo atual.
    Contrato de outra loja não tem -> sem este aviso, o adendo do ciclo
    (mod_contrato.py:744) some do PDF em silêncio."""
    corpo = "# CLÁUSULA ÚNICA\n1.1. Contrato de outra loja, com fecho próprio.\n"
    assert "TEXTO_COMPLEMENTAR" in mod_marcadores.analisar_corpo(corpo, {})["ausentes"]


def test_adendo_presente_sai_dos_ausentes():
    corpo = "1.1. Texto.\n\n[TEXTO_COMPLEMENTAR]\n\nFecho."
    assert "TEXTO_COMPLEMENTAR" not in mod_marcadores.analisar_corpo(corpo, {})["ausentes"]


def test_essencial_presente_sai_dos_ausentes():
    corpo = " ".join("[%s]" % c for c in mod_marcadores.ESSENCIAIS)
    assert mod_marcadores.analisar_corpo(corpo, {})["ausentes"] == []


def test_detecta_cnpj_da_loja_cravado_com_pontuacao_diferente():
    corpo = "inscrita no CNPJ/MF sob o n. 19152134000156, doravante CONTRATADA"
    cravados = mod_marcadores.analisar_corpo(corpo, LOJA_EXEMPLO)["cravados"]
    assert any(c["marcador"] == "CNPJ_EMPRESA" for c in cravados), \
        "CNPJ tem que casar sem pontuação"


def test_detecta_nome_e_cidade_da_loja_cravados():
    corpo = ("INSPIRIUM MÓVEIS PLANEJADOS E DECORAÇÃO LTDA, com sede em "
             "São José dos Campos, elegem o Foro da Comarca de São José dos Campos.")
    marcs = {c["marcador"] for c in mod_marcadores.analisar_corpo(corpo, LOJA_EXEMPLO)["cravados"]}
    assert "NOME_EMPRESA" in marcs
    assert "LOJA_CIDADE" in marcs


def test_cravado_traz_o_literal_para_a_tela_mostrar():
    corpo = "Foro da Comarca de São José dos Campos."
    c = [x for x in mod_marcadores.analisar_corpo(corpo, LOJA_EXEMPLO)["cravados"]
         if x["marcador"] == "LOJA_CIDADE"][0]
    assert c["literal"] == "São José dos Campos"
    assert c["ocorrencias"] == 1


def test_nao_inventa_cravado_quando_o_campo_da_loja_e_vazio():
    r = mod_marcadores.analisar_corpo("Texto qualquer.", {"nome": "", "cnpj": None})
    assert r["cravados"] == []


def test_campo_curto_da_loja_nao_gera_falso_positivo():
    """Cidade 'Sé' (2 letras) casaria dentro de mil palavras — ignorar."""
    r = mod_marcadores.analisar_corpo("A CONTRATADA se obriga.", {"cidade": "Sé"})
    assert r["cravados"] == []


def test_aplicar_cravados_troca_o_literal_pelo_marcador():
    corpo = "Foro da Comarca de São José dos Campos."
    novo = mod_marcadores.aplicar_cravados(corpo, LOJA_EXEMPLO, ["LOJA_CIDADE"])
    assert novo == "Foro da Comarca de [LOJA_CIDADE]."


def test_aplicar_cravados_ignora_o_que_nao_foi_aprovado():
    corpo = "INSPIRIUM MÓVEIS PLANEJADOS E DECORAÇÃO LTDA em São José dos Campos."
    novo = mod_marcadores.aplicar_cravados(corpo, LOJA_EXEMPLO, ["LOJA_CIDADE"])
    assert "[LOJA_CIDADE]" in novo
    assert "INSPIRIUM MÓVEIS PLANEJADOS E DECORAÇÃO LTDA" in novo, "não aprovado, não troca"
