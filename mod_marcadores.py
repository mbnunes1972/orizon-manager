# -*- coding: utf-8 -*-
"""mod_marcadores.py — Catálogo dos [MARCADORES] aceitos nos modelos de documento.

Fonte única do que EXISTE. Quem calcula os VALORES é mod_contrato._montar_mapping();
tests/test_marcadores.py trava os dois juntos — se um ganhar chave que o outro não
tem, a suíte quebra. Ao acrescentar marcador, mexa nos DOIS.
"""

CATALOGO = {
    # ── documento ────────────────────────────────────────────────────────────
    "NUM_CONTRATO":       {"rotulo": "Número do contrato",      "escopo": "documento"},
    "DATA_CONTRATO":      {"rotulo": "Data do contrato",        "escopo": "documento"},
    "TEXTO_COMPLEMENTAR": {"rotulo": "Adendo (texto livre)",    "escopo": "documento"},
    "REDE_IDENTIFICADOR": {"rotulo": "Identificador da rede",   "escopo": "documento"},

    # ── cliente ──────────────────────────────────────────────────────────────
    "NOME_CLIENTE":     {"rotulo": "Nome do cliente",           "escopo": "cliente"},
    "CPF":              {"rotulo": "CPF do cliente",            "escopo": "cliente"},
    "CPF_CLIENTE":      {"rotulo": "CPF do cliente (alias)",    "escopo": "cliente"},
    "EMAIL":            {"rotulo": "E-mail do cliente",         "escopo": "cliente"},
    "TELEFONE":         {"rotulo": "Telefone do cliente",       "escopo": "cliente"},
    "RES_LOGRADOURO":   {"rotulo": "Residencial — logradouro",  "escopo": "cliente"},
    "RES_NUMERO":       {"rotulo": "Residencial — número",      "escopo": "cliente"},
    "RES_COMPLEMENTO":  {"rotulo": "Residencial — complemento", "escopo": "cliente"},
    "RES_BAIRRO":       {"rotulo": "Residencial — bairro",      "escopo": "cliente"},
    "RES_CIDADE":       {"rotulo": "Residencial — cidade",      "escopo": "cliente"},
    "RES_CEP":          {"rotulo": "Residencial — CEP",         "escopo": "cliente"},
    "RES_UF":           {"rotulo": "Residencial — UF",          "escopo": "cliente"},
    "INST_LOGRADOURO":  {"rotulo": "Instalação — logradouro",   "escopo": "cliente"},
    "INST_NUMERO":      {"rotulo": "Instalação — número",       "escopo": "cliente"},
    "INST_COMPLEMENTO": {"rotulo": "Instalação — complemento",  "escopo": "cliente"},
    "INST_BAIRRO":      {"rotulo": "Instalação — bairro",       "escopo": "cliente"},
    "INST_CIDADE":      {"rotulo": "Instalação — cidade",       "escopo": "cliente"},
    "INST_CEP":         {"rotulo": "Instalação — CEP",          "escopo": "cliente"},
    "INST_UF":          {"rotulo": "Instalação — UF",           "escopo": "cliente"},

    # ── loja (CONTRATADA) ────────────────────────────────────────────────────
    "NOME_EMPRESA":      {"rotulo": "Razão social da loja",     "escopo": "loja"},
    "CNPJ_EMPRESA":      {"rotulo": "CNPJ da loja",             "escopo": "loja"},
    "LOJA_LOGRADOURO":   {"rotulo": "Loja — logradouro",        "escopo": "loja"},
    "LOJA_NUMERO":       {"rotulo": "Loja — número",            "escopo": "loja"},
    "LOJA_COMPLEMENTO":  {"rotulo": "Loja — complemento",       "escopo": "loja"},
    "LOJA_BAIRRO":       {"rotulo": "Loja — bairro",            "escopo": "loja"},
    "LOJA_CIDADE":       {"rotulo": "Loja — cidade",            "escopo": "loja"},
    "LOJA_UF":           {"rotulo": "Loja — UF",                "escopo": "loja"},
    "LOJA_CEP":          {"rotulo": "Loja — CEP",               "escopo": "loja"},
    "LOJA_TELEFONE":     {"rotulo": "Loja — telefone",          "escopo": "loja"},
    "LOJA_EMAIL":        {"rotulo": "Loja — e-mail",            "escopo": "loja"},
    "CONSULTOR_NOME":     {"rotulo": "Consultor — nome",        "escopo": "loja"},
    "CONSULTOR_TELEFONE": {"rotulo": "Consultor — telefone",    "escopo": "loja"},
    # Testemunhas: cadastro da loja (lojas.testemunha1_nome/cpf, testemunha2_nome/cpf).
    # Há duas famílias de nome para o MESMO dado, porque _montar_mapping expõe as duas:
    #   - NOME_/CPF_TESTEMUNHA_N: em uso — contrato_template/contrato.md:105-110 depende delas.
    #   - TESTEMUNHA_N_NOME/_DOC e NOME_TESTEMUNHA2: sem consumidor em nenhum template hoje.
    # As segundas seguem catalogadas só porque o mapping as produz (o teste anti-drift exige
    # paridade). Se um dia forem podadas, tirar de _montar_mapping e daqui no mesmo commit.
    "TESTEMUNHA_1_NOME": {"rotulo": "Testemunha 1 — nome (alias de NOME_TESTEMUNHA_1)", "escopo": "loja"},
    "TESTEMUNHA_1_DOC":  {"rotulo": "Testemunha 1 — CPF (alias de CPF_TESTEMUNHA_1)",   "escopo": "loja"},
    "TESTEMUNHA_2_NOME": {"rotulo": "Testemunha 2 — nome (alias de NOME_TESTEMUNHA_2)", "escopo": "loja"},
    "TESTEMUNHA_2_DOC":  {"rotulo": "Testemunha 2 — CPF (alias de CPF_TESTEMUNHA_2)",   "escopo": "loja"},
    "NOME_TESTEMUNHA_1": {"rotulo": "Testemunha 1 — nome",      "escopo": "loja"},
    "CPF_TESTEMUNHA_1":  {"rotulo": "Testemunha 1 — CPF",       "escopo": "loja"},
    "NOME_TESTEMUNHA_2": {"rotulo": "Testemunha 2 — nome",      "escopo": "loja"},
    "CPF_TESTEMUNHA_2":  {"rotulo": "Testemunha 2 — CPF",       "escopo": "loja"},
    "NOME_TESTEMUNHA2":  {"rotulo": "Testemunha 2 — nome (alias de NOME_TESTEMUNHA_2, sem underscore)", "escopo": "loja"},

    # ── pagamento ────────────────────────────────────────────────────────────
    "VALOR_ENTRADA":  {"rotulo": "Valor da entrada",   "escopo": "pagamento"},
    "FORMA_ENTRADA":  {"rotulo": "Forma da entrada",   "escopo": "pagamento"},
    "DATA_ENTRADA":   {"rotulo": "Data da entrada",    "escopo": "pagamento"},
    "MODALIDADE":     {"rotulo": "Modalidade",         "escopo": "pagamento"},
    "NUM_PARCELAS":   {"rotulo": "Nº de parcelas",     "escopo": "pagamento"},
    "TIPO":           {"rotulo": "Tipo da parcela",    "escopo": "pagamento"},
    "TOTAL_CONTRATO": {"rotulo": "Valor total",        "escopo": "pagamento"},
}
