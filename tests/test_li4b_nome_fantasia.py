# -*- coding: utf-8 -*-
"""LI-4b (docs/db/LISTA_IMEDIATA.md, decisão do Marcelo 25/09) — `lojas.nome` É o Nome Fantasia;
a razão social é OUTRO dado (Emitente, Fiscal → Configuração Fiscal), sem coluna nova e sem
duplicar. Trava o rótulo/texto de ajuda da tela (para ninguém reverter sem entender) e a
migração de NOME_EMPRESA/CNPJ_EMPRESA do contrato para o Emitente."""
import os
import re

import pytest

REPO = os.path.join(os.path.dirname(__file__), "..")
INDEX_HTML = os.path.join(REPO, "static", "index.html")


def _html():
    with open(INDEX_HTML, encoding="utf-8") as f:
        return f.read()


# ── tela: rótulo + ajuda + razão social em modo leitura ───────────────────────────────────────

def test_campo_nome_vira_nome_fantasia_com_ajuda():
    html = _html()
    assert "f('loja-nome','Nome Fantasia'," in html, \
        "rótulo 'Nome Fantasia' não encontrado em adminLojaCarregarDados — não reverta para 'Nome'"
    # A ajuda tem que dizer explicitamente que a razão social mora no Fiscal — é o achado que
    # motivou este item (o Marcelo procurou o campo e não achou).
    assert "razão social fica em Fiscal" in html


def test_razao_social_exibida_em_modo_leitura_com_link_para_fiscal():
    html = _html()
    m = re.search(r"async function adminLojaCarregarDados.*?\n}", html, re.S)
    assert m, "adminLojaCarregarDados não encontrada"
    bloco = m.group(0)
    assert "Razão social" in bloco
    assert "loja.razao_social" in bloco
    assert "disabled" in bloco   # não editável por esta tela
    assert "goPage(11)" in bloco   # link pra Fiscal → Configuração Fiscal


# ── backend: contrato lê do Emitente, não mais de lojas.nome/cnpj ─────────────────────────────

def test_montar_mapping_nome_empresa_vem_de_razao_social():
    from mod_contrato import _montar_mapping
    loja = {"nome": "Nome Fantasia Qualquer", "cnpj": "00.000.000/0001-00",
           "razao_social": "RAZAO SOCIAL DE VERDADE LTDA", "cnpj_fiscal": "11.111.111/0001-11"}
    m = _montar_mapping({"loja": loja}, {})
    assert m["NOME_EMPRESA"] == "RAZAO SOCIAL DE VERDADE LTDA"
    assert m["CNPJ_EMPRESA"] == "11.111.111/0001-11"
    # trava explícita: NÃO é mais o nome fantasia
    assert m["NOME_EMPRESA"] != loja["nome"]
    assert m["CNPJ_EMPRESA"] != loja["cnpj"]


def test_validar_loja_para_contrato_exige_razao_social_e_cnpj_fiscal():
    from mod_contrato import validar_loja_para_contrato
    loja = {"nome": "Fantasia", "cnpj": "00.000.000/0001-00", "codigo": "ABC",
           "telefone": "x", "email": "x", "cep": "x", "logradouro": "x", "numero": "x",
           "bairro": "x", "cidade": "x", "estado": "x",
           "testemunha1_nome": "x", "testemunha1_cpf": "123.456.789-00",
           "testemunha2_nome": "x", "testemunha2_cpf": "123.456.789-00",
           # sem razao_social/cnpj_fiscal
           }
    faltando = " ".join(validar_loja_para_contrato(loja))
    assert "Razão social" in faltando
    assert "CNPJ fiscal" in faltando


def test_loja_dict_inclui_razao_social_do_emitente(app_db, seed):
    """`main._loja_dict` (Admin → Dados da empresa) expõe razao_social pra tela mostrar em modo
    leitura -- vem do Emitente da loja (o seed já vincula um a cada loja de teste)."""
    import main
    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, seed["loja1_id"])
        d = main._loja_dict(db, loja)
        assert "razao_social" in d
        assert d["razao_social"] == "EMITENTE LOJA 1 LTDA"
        assert d["nome"] == loja.nome    # Nome Fantasia continua vindo de lojas.nome
    finally:
        db.close()


def test_loja_dict_sem_emitente_nao_quebra(app_db, seed):
    """Loja sem `emitente_id` (implantação em andamento, item 6 do roteiro ainda não feito) —
    `_loja_dict` devolve razao_social vazia, não levanta exceção."""
    import main
    db = app_db.get_session()
    try:
        nova = app_db.Loja(nome="Loja Sem Emitente Ainda", rede_id=seed["rede_id"])
        db.add(nova); db.flush()
        d = main._loja_dict(db, nova)
        assert d["razao_social"] == ""
        db.rollback()
    finally:
        db.close()


def test_loja_dict_pdv_sem_emitente_proprio_herda_razao_social_da_mae(app_db, seed):
    """Prova de campo do Marcelo (25/09): um PDV (loja com mãe) pode não ter `emitente_id`
    próprio e ainda assim ter razão social de verdade — herdada da mãe, mesma resolução "dona"
    que `_loja_dict_para_contrato` já usa pro contrato. Sem isto, a tela do PDV mostraria "não
    configurada" mesmo quando o contrato dele já funciona via herança (caso real: loja 4,
    PDV Caraguatatuba, é da Inspirium -- mesmo CNPJ/Emitente, nome de uso próprio)."""
    import main
    db = app_db.get_session()
    try:
        mae = db.get(app_db.Loja, seed["loja1_id"])   # já tem Emitente (seed)
        pdv = app_db.Loja(nome="PDV Sem Emitente Próprio", rede_id=seed["rede_id"],
                          loja_mae_id=mae.id, tipo="ponto_venda")
        db.add(pdv); db.flush()
        d = main._loja_dict(db, pdv)
        assert d["nome"] == "PDV Sem Emitente Próprio"       # Nome Fantasia é do PDV, não da mãe
        assert d["razao_social"] == "EMITENTE LOJA 1 LTDA"   # razão social herdada da mãe
        db.rollback()
    finally:
        db.close()
