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
    # "projeto" é reserva: seria o escopo de marcadores calculados a partir do
    # orçamento (ambientes, valor bruto, desconto, validade) se um dia entrarem.
    # Existiram no mod_proposta.py, que era o caminho .docx morto, REMOVIDO em
    # 2026-07-15 — não os ressuscite de lá. Hoje _montar_mapping não produz
    # nenhum marcador de escopo "projeto", então nenhum verbete o usa.
    for chave, v in mod_marcadores.CATALOGO.items():
        assert v.get("rotulo"), f"{chave} sem rótulo"
        assert v.get("escopo") in ("cliente", "loja", "pagamento", "projeto", "documento"), \
            f"{chave} com escopo inválido: {v.get('escopo')}"


def test_novos_marcadores_saem_no_mapping():
    ctx = {"loja": {"nome": "L", "cnpj": "1", "cidade": "C"},
           "data_prevista_entrega": "01/01/2028", "previsao_medicao": "01/06/2027",
           "prazo_contratual": "50 dias úteis a partir da assinatura",
           "venda_programada_txt": "Trata-se de VENDA PROGRAMADA."}
    m = mod_contrato._montar_mapping(ctx, {})
    assert m["DATA_PREVISTA_ENTREGA"] == "01/01/2028"
    assert m["PREVISAO_MEDICAO"] == "01/06/2027"
    assert m["PRAZO_CONTRATUAL"].endswith("a partir da assinatura")
    assert "VENDA PROGRAMADA" in m["VENDA_PROGRAMADA"]


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
    # ESSENCIAIS é lista de GRUPOS equivalentes; o 1º de cada grupo é o canônico.
    corpo = " ".join("[%s]" % g[0] for g in mod_marcadores.ESSENCIAIS)
    assert mod_marcadores.analisar_corpo(corpo, {})["ausentes"] == []


def test_alias_satisfaz_o_essencial_do_grupo():
    """O CATALOGO tem duas famílias para o mesmo dado (CPF/CPF_CLIENTE) justamente
    para tolerar convenções de outras lojas. Avisar 'CPF_CLIENTE ausente' num
    documento que usa [CPF] é aviso FALSO — e aviso falso ensina o lojista a
    ignorar os avisos."""
    r = mod_marcadores.analisar_corpo("Cliente [NOME_CLIENTE], CPF [CPF].", {})
    assert "CPF_CLIENTE" not in r["ausentes"]
    assert "CPF" not in r["ausentes"]


def test_alias_de_testemunha_satisfaz_o_essencial():
    corpo = "[TESTEMUNHA_1_NOME] e [NOME_TESTEMUNHA2]"
    aus = mod_marcadores.analisar_corpo(corpo, {})["ausentes"]
    assert "NOME_TESTEMUNHA_1" not in aus
    assert "NOME_TESTEMUNHA_2" not in aus


def test_ausentes_reporta_a_chave_canonica_do_grupo():
    """Uma chave por grupo, não a família inteira — senão a tela vira sopa."""
    aus = mod_marcadores.analisar_corpo("Nada aqui.", {})["ausentes"]
    assert "CPF_CLIENTE" in aus
    assert "CPF" not in aus, "só a canônica do grupo vai pra tela"
    assert aus == [g[0] for g in mod_marcadores.ESSENCIAIS]


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


def test_cravado_traz_trecho_com_o_contexto_em_volta():
    """Sem contexto o lojista aprova às cegas — e aprovar às cegas não é aprovar.
    Caso real: bairro 'Centro' casando em 'Centro Empresarial ABC' produziria
    '[LOJA_BAIRRO] Empresarial ABC'. Renderiza certo hoje; quando a loja mudar de
    endereço no cadastro, todo contrato passa a dizer 'Jardim Empresarial ABC'.
    O trecho é o que dá ao lojista como enxergar isso antes de aprovar."""
    corpo = "A empresa fica no Centro Empresarial ABC, sala 12."
    c = mod_marcadores.analisar_corpo(corpo, {"bairro": "Centro"})["cravados"][0]
    assert c["marcador"] == "LOJA_BAIRRO"
    assert len(c["trechos"]) == 1
    assert "Empresarial ABC" in c["trechos"][0], "o trecho tem que mostrar o que vem depois"
    assert ">>>Centro<<<" in c["trechos"][0], "a ocorrência tem que vir demarcada"


def test_trechos_limitados_declaram_quantos_ficaram_de_fora():
    """Truncar em silêncio seria mentir de novo, só que na tela."""
    corpo = " ".join(["bairro Centro."] * 10)
    c = mod_marcadores.analisar_corpo(corpo, {"bairro": "Centro"})["cravados"][0]
    assert c["ocorrencias"] == 10
    assert len(c["trechos"]) == 3
    assert c["trechos_omitidos"] == 7


def test_trecho_marca_reticencias_so_quando_ha_corte():
    c = mod_marcadores.analisar_corpo("Centro", {"bairro": "Centro"})["cravados"][0]
    assert c["trechos"] == [">>>Centro<<<"], "corpo inteiro cabe: sem reticências"


def test_ocorrencias_do_cnpj_sem_pontuacao_conta_de_verdade():
    """'ocorrencias' era 1 hardcoded neste ramo — a tela mostraria '1×' como fato."""
    corpo = ("CNPJ 19.152.134/0001-56 ... e tambem 19152134000156 "
             "em outro ponto do documento.")
    c = [x for x in mod_marcadores.analisar_corpo(corpo, LOJA_EXEMPLO)["cravados"]
         if x["marcador"] == "CNPJ_EMPRESA"][0]
    assert c["ocorrencias"] == 2, "as duas formatações são a mesma loja"
    assert c["so_digitos"] is True, "há ocorrência que aplicar_cravados não troca"


def test_cnpj_so_com_pontuacao_exata_nao_marca_so_digitos():
    """Se toda ocorrência casa exata, aplicar_cravados resolve — não é caso manual."""
    c = [x for x in mod_marcadores.analisar_corpo(
        "CNPJ 19.152.134/0001-56.", LOJA_EXEMPLO)["cravados"]
        if x["marcador"] == "CNPJ_EMPRESA"][0]
    assert c.get("so_digitos", False) is False
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


def test_aplicar_cravados_respeita_a_ordem_do_mais_especifico():
    """A ordem de _CRAVAVEIS é funcional, não cosmética: aplicar_cravados faz
    replace SEQUENCIAL mutando o corpo. Se o literal curto ('São José dos Campos')
    fosse trocado antes, o literal longo que o contém ('Rua São José dos Campos')
    não existiria mais no texto e seria pulado em silêncio.

    Inverter logradouro/cidade em _CRAVAVEIS faz este teste falhar — é o objetivo.
    """
    loja = {"logradouro": "Rua São José dos Campos", "cidade": "São José dos Campos"}
    corpo = "Sede na Rua São José dos Campos, cidade de São José dos Campos."
    novo = mod_marcadores.aplicar_cravados(corpo, loja, ["LOJA_LOGRADOURO", "LOJA_CIDADE"])
    assert "[LOJA_LOGRADOURO]" in novo, "o logradouro (mais longo) tem que ser trocado"
    assert "[LOJA_CIDADE]" in novo
    assert novo == "Sede na [LOJA_LOGRADOURO], cidade de [LOJA_CIDADE]."


def test_aplicar_cravados_num_achado_misto_troca_so_a_ocorrencia_exata():
    """Trava o que a docstring de aplicar_cravados promete: replace é exato, então
    a ocorrência sem pontuação sobrevive. O documento sai meio parametrizado, meio
    cravado — é justamente por isso que so_digitos vira aviso na tela."""
    loja = {"cnpj": "19.152.134/0001-56"}
    corpo = "CNPJ 19.152.134/0001-56 e tambem 19152134000156 no fim."
    novo = mod_marcadores.aplicar_cravados(corpo, loja, ["CNPJ_EMPRESA"])
    assert novo == "CNPJ [CNPJ_EMPRESA] e tambem 19152134000156 no fim."


def test_ordem_de_cravaveis_esta_travada():
    """A ordem é funcional (replace sequencial em aplicar_cravados). Mudou a
    lista? Leia o comentário de _CRAVAVEIS antes de atualizar este teste: um
    campo cujo literal seja substring do literal de outro TEM que vir depois dele."""
    assert [m for _, m in mod_marcadores._CRAVAVEIS] == [
        "CNPJ_EMPRESA", "NOME_EMPRESA", "LOJA_LOGRADOURO",
        "LOJA_BAIRRO", "LOJA_CIDADE", "LOJA_CEP",
    ]
