import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import mod_documentos_import as imp

# Export de texto do LibreOffice: capa antes, numeração já achatada em literal.
TXT_EXEMPLO = """MODELO DE CONTRATO
Capa gerada pelo Word — não faz parte do corpo
Cliente: ____________

CONTRATO DE COMPRA E VENDA DE PRODUTOS E DE PRESTAÇÃO DE SERVIÇOS

Pelo presente instrumento particular, de um lado, O CONTRATANTE.

1. CLÁUSULA PRIMEIRA – DO OBJETO E PREÇO
    1.1. A CONTRATADA se obriga a fornecer o material.
    1.1.1. O esboço será considerado aprovado.
    a) MEDIÇÃO: conferência de medidas;

2. CLÁUSULA SEGUNDA – DOS PAGAMENTOS
    2.1. Os pagamentos deverão ser feitos nas datas estipuladas.

E assim, por estarem assim convencionados, firmam as PARTES.
"""


def test_corta_a_capa():
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "Capa gerada pelo Word" not in md
    assert md.startswith("CONTRATO DE COMPRA E VENDA")


def test_clausula_vira_heading_sem_o_numero_da_lista():
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "# CLÁUSULA PRIMEIRA – DO OBJETO E PREÇO" in md
    assert "# CLÁUSULA SEGUNDA – DOS PAGAMENTOS" in md
    # o "1. " que o LibreOffice achatou antes de "CLÁUSULA" não sobrevive
    assert "# 1. CLÁUSULA" not in md


def test_preserva_a_numeracao_das_clausulas():
    """O motivo de existir o caminho LibreOffice: python-docx perderia estes números."""
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "1.1. A CONTRATADA se obriga" in md
    assert "1.1.1. O esboço" in md
    assert "a) MEDIÇÃO" in md
    assert "2.1. Os pagamentos" in md


def test_tira_a_indentacao():
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "\n1.1. A CONTRATADA" in md
    assert "    1.1." not in md


def test_insere_texto_complementar_antes_do_fecho():
    md = imp.extrair_corpo(TXT_EXEMPLO)
    assert "[TEXTO_COMPLEMENTAR]" in md
    assert md.index("[TEXTO_COMPLEMENTAR]") < md.index("E assim, por estarem")


def test_texto_sem_o_marco_de_inicio_e_usado_inteiro():
    """Documento que não tem 'CONTRATO DE COMPRA E VENDA' não pode virar string vazia."""
    md = imp.extrair_corpo("# CLÁUSULA ÚNICA\n1.1. Vale tudo.\n")
    assert "1.1. Vale tudo." in md


def test_corpo_vazio_nao_explode():
    assert imp.extrair_corpo("") == ""
