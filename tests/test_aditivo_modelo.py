# -*- coding: utf-8 -*-
"""Termo Aditivo — modelo jurídico completo + modais sequenciais (spec
docs/superpowers/specs/contrato-documentos/2026-07-22-termo-aditivo-modelo-modais-design.md).

Unidade: ordinal, textos-padrão dos 5 blocos (as 4 combinações com/sem inclusões ×
com/sem exclusões + valores com/sem alteração) e render do modelo REAL
(contrato_template/termo_aditivo.md) com os blocos multi-linha virando <br>.
O anti-drift CATALOGO×mapping dos marcadores novos é o test_marcadores.py de sempre."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_contrato
import mod_marcadores


# ── ordinal ──────────────────────────────────────────────────────────────────

def test_ordinal_aditivo():
    assert mod_contrato.ordinal_aditivo(1) == "PRIMEIRO"
    assert mod_contrato.ordinal_aditivo(2) == "SEGUNDO"
    assert mod_contrato.ordinal_aditivo(3) == "TERCEIRO"
    assert mod_contrato.ordinal_aditivo(10) == "DÉCIMO"
    assert mod_contrato.ordinal_aditivo(11) == "11º"


# ── defaults dos 5 blocos ────────────────────────────────────────────────────

def _defaults(**kw):
    base = dict(lista_integral=[("Cozinha", 93333.33), ("Suíte Master", 10000.0)],
                inclusoes=[], exclusoes=[],
                valor_original=88888.89, valor_novo=103333.33, diferenca=14444.44,
                condicoes="à vista, na data de assinatura deste TERMO ADITIVO")
    base.update(kw)
    return mod_contrato.montar_defaults_aditivo(**base)


def test_considerandos_sao_os_tres_do_advogado():
    d = _defaults()
    c = d["considerandos"]
    assert c.count("CONSIDERANDO QUE") == 3
    assert "1.5.1" in c and "2.3.4 a 2.3.6" in c          # PE
    assert "produtos e serviços objeto do CONTRATO" in c  # produtos/serviços
    assert "medição" in c and "alínea (a)" in c           # medição
    # um por parágrafo, para o operador apagar os que não se aplicam
    assert c.count("\n\n") == 2


def test_lista_integral_tem_todos_os_ambientes():
    d = _defaults()
    li = d["lista_integral"]
    assert "substituindo integralmente" in li and "rol constante do CONTRATO" in li
    assert "Cozinha: R$ 93.333,33" in li
    assert "Suíte Master: R$ 10.000,00" in li   # não alterado TAMBÉM entra


def test_combinacao_com_inclusao_com_exclusao():
    d = _defaults(inclusoes=[("Adega", 10000.0)], exclusoes=[("Lavabo", 5000.0)])
    assert "promove-se a inclusão" in d["inclusoes"]
    assert "não constavam do texto original do CONTRATO" in d["inclusoes"]
    assert "Adega: R$ 10.000,00" in d["inclusoes"]
    assert "promove-se a exclusão" in d["exclusoes"]
    assert "Lavabo: R$ 5.000,00" in d["exclusoes"]


def test_combinacao_com_inclusao_sem_exclusao():
    d = _defaults(inclusoes=[("Adega", 10000.0)])
    assert "Adega" in d["inclusoes"]
    assert "não promove a exclusão de produtos ou materiais" in d["exclusoes"]
    assert "Registram as PARTES" in d["exclusoes"]


def test_combinacao_sem_inclusao_com_exclusao():
    d = _defaults(exclusoes=[("Lavabo", 5000.0)])
    assert "não promove a inclusão de produtos ou materiais" in d["inclusoes"]
    assert "Lavabo" in d["exclusoes"]


def test_combinacao_sem_inclusao_sem_exclusao():
    d = _defaults()
    assert "não promove a inclusão" in d["inclusoes"]
    assert "não promove a exclusão" in d["exclusoes"]


def test_valores_com_alteracao_ao_centavo():
    d = _defaults()
    v = d["valores"]
    assert "passa de R$ 88.888,89 para R$ 103.333,33" in v
    assert "diferença de R$ 14.444,44" in v
    assert "à vista, na data de assinatura deste TERMO ADITIVO" in v


def test_valores_sem_alteracao_vira_negativa():
    d = _defaults(valor_novo=88888.89, diferenca=0.0)
    assert "não implicam modificação" in d["valores"]
    assert "permanecem integralmente vigentes" in d["valores"]
    assert "passa de" not in d["valores"]


# ── mapping (mesmo commit do CATALOGO — anti-drift em test_marcadores.py) ────

def test_mapping_recebe_blocos_do_ctx_aditivo():
    ctx = {"loja": {"nome": "L", "cnpj": "1", "cidade": "C"},
           "_aditivo": {"ordinal": "SEGUNDO", "data_aditivo": "22/07/2026",
                        "data_contrato_original": "01/03/2026",
                        "considerandos": "CONSIDERANDO X", "lista_integral": "- A: R$ 1,00",
                        "inclusoes": "inc", "exclusoes": "exc", "valores": "val"}}
    m = mod_contrato._montar_mapping(ctx, {})
    assert m["ORDINAL_ADITIVO"] == "SEGUNDO"
    assert m["DATA_ADITIVO"] == "22/07/2026"
    assert m["DATA_CONTRATO_ORIGINAL"] == "01/03/2026"
    assert m["ADITIVO_CONSIDERANDOS"] == "CONSIDERANDO X"
    assert m["ADITIVO_LISTA_INTEGRAL"] == "- A: R$ 1,00"
    assert m["ADITIVO_INCLUSOES"] == "inc"
    assert m["ADITIVO_EXCLUSOES"] == "exc"
    assert m["ADITIVO_VALORES"] == "val"


def test_catalogo_tem_os_marcadores_novos_do_aditivo():
    for c in ("ORDINAL_ADITIVO", "DATA_ADITIVO", "DATA_CONTRATO_ORIGINAL",
              "ADITIVO_CONSIDERANDOS", "ADITIVO_LISTA_INTEGRAL",
              "ADITIVO_INCLUSOES", "ADITIVO_EXCLUSOES", "ADITIVO_VALORES"):
        assert c in mod_marcadores.CATALOGO, f"faltou {c}"
        assert mod_marcadores.CATALOGO[c]["escopo"] == "documento"


# ── render do modelo real ────────────────────────────────────────────────────

def test_render_modelo_real_com_blocos():
    corpo = mod_contrato.corpo_modelo_aditivo_padrao()
    assert corpo, "contrato_template/termo_aditivo.md ausente"
    defaults = _defaults(inclusoes=[("Adega", 10000.0)])
    ctx = {"loja": {"nome": "INSPIRIUM LTDA", "cnpj": "19.152.134/0001-56",
                    "cidade": "São José dos Campos", "estado": "SP",
                    "testemunha1_nome": "T1", "testemunha1_cpf": "1",
                    "testemunha2_nome": "T2", "testemunha2_cpf": "2"},
           "cliente_nome": "Cliente X", "cliente_cpf": "111.444.777-35",
           "_corpo_md_aditivo": corpo,
           "_aditivo": {"num_aditivo": "TA20260722001",
                        "num_contrato_original": "CT-1", "ordinal": "PRIMEIRO",
                        "data_aditivo": "22/07/2026", "data_contrato_original": "01/03/2026",
                        **defaults}}
    html = mod_contrato.montar_html_aditivo(ctx)
    assert "PRIMEIRO TERMO ADITIVO AO CONTRATO" in html
    assert "CT-1" in html and "01/03/2026" in html and "22/07/2026" in html
    # blocos multi-linha viram <br> (a substituição acontece DEPOIS do corpo virar <p>)
    assert html.count("CONSIDERANDO QUE") == 3
    assert "<br>" in html
    assert "Adega: R$ 10.000,00" in html
    # texto fixo do advogado preservado
    assert "reserva de domínio" in html
    assert "parte integrante e inseparável do CONTRATO" in html
    # nenhum marcador do aditivo sobrando
    assert "[ADITIVO_" not in html and "[ORDINAL_ADITIVO]" not in html
    assert "[DATA_CONTRATO_ORIGINAL]" not in html
