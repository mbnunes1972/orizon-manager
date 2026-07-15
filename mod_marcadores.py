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


# ── Análise do corpo importado (modelos de documento por loja) ─────────────────

import re as _re

# Reusa o regex do motor de substituição — se divergirem, a análise validaria
# um marcador que o renderizador não reconhece (ou o contrário).
from mod_contrato import _MARK_RE

# Sem estes, o documento sai quebrado: cliente sem nome, contrato sem data,
# fecho sem testemunha. O wizard avisa; não bloqueia (pode ser um modelo parcial).
#
# TEXTO_COMPLEMENTAR está aqui por um achado da revisão do Task 2: é o ponto de
# injeção do adendo do ciclo (mod_contrato.py:744). mod_documentos_import só o
# insere se o texto tiver o marco de fecho do modelo ATUAL ("E assim, por estarem
# assim convencionados") — um contrato de outra loja, com redação própria, não
# tem. Sem este aviso, o adendo some do PDF em silêncio.
ESSENCIAIS = ["NOME_CLIENTE", "CPF_CLIENTE", "DATA_CONTRATO",
              "NOME_EMPRESA", "CNPJ_EMPRESA",
              "NOME_TESTEMUNHA_1", "NOME_TESTEMUNHA_2",
              "TEXTO_COMPLEMENTAR"]

# Campos da loja que valem procurar cravados no texto → marcador correspondente.
# Ordem importa: NOME_EMPRESA (razão social, longa e específica) vem antes de
# LOJA_LOGRADOURO/LOJA_CIDADE para não deixar diferença de precedência causar
# confusão de leitura; na prática cada campo busca seu próprio literal (contagem
# via str.count), então um não interfere no resultado do outro — mas manter o
# nome fantasia/razão social primeiro deixa a lista de achados mais legível na
# tela (o dado mais "identificador" da loja aparece primeiro).
_CRAVAVEIS = [
    ("cnpj",       "CNPJ_EMPRESA"),
    ("nome",       "NOME_EMPRESA"),
    ("logradouro", "LOJA_LOGRADOURO"),
    ("bairro",     "LOJA_BAIRRO"),
    ("cidade",     "LOJA_CIDADE"),
    ("cep",        "LOJA_CEP"),
]

# Abaixo disto, o valor casa por acidente ("Sé", "SP", nº "12").
_MIN_LITERAL = 4


def _so_digitos(s):
    return _re.sub(r"\D", "", s or "")


def _chaves_usadas(corpo_md):
    return [m.group(1).strip().upper().replace(" ", "_")
            for m in _MARK_RE.finditer(corpo_md or "")]


def analisar_corpo(corpo_md, loja):
    """Analisa um corpo importado contra o catálogo e o cadastro da loja.

    Devolve:
      conhecidos_usados  marcadores do catálogo presentes no corpo
      desconhecidos      [FOO] sem verbete — seria impresso literal no PDF
      ausentes           essenciais que o corpo não tem
      cravados           dados da loja literais no texto, candidatos a marcador
      bloqueia_ativacao  True se há desconhecido
    """
    loja = loja or {}
    usadas = _chaves_usadas(corpo_md)
    conhecidos = [c for c in dict.fromkeys(usadas) if c in CATALOGO]
    desconhecidos = [c for c in dict.fromkeys(usadas) if c not in CATALOGO]
    ausentes = [c for c in ESSENCIAIS if c not in usadas]

    cravados = []
    for campo, marcador in _CRAVAVEIS:
        valor = (loja.get(campo) or "").strip()
        if len(valor) < _MIN_LITERAL:
            continue
        n = (corpo_md or "").count(valor)
        if n:
            cravados.append({"marcador": marcador, "literal": valor,
                             "ocorrencias": n, "campo": campo})
            continue
        # CNPJ/CEP: o documento pode usar pontuação diferente do cadastro.
        if campo in ("cnpj", "cep"):
            nus = _so_digitos(valor)
            if len(nus) >= _MIN_LITERAL and nus in _so_digitos(corpo_md):
                cravados.append({"marcador": marcador, "literal": valor,
                                 "ocorrencias": 1, "campo": campo,
                                 "so_digitos": True})
    return {"conhecidos_usados": conhecidos, "desconhecidos": desconhecidos,
            "ausentes": ausentes, "cravados": cravados,
            "bloqueia_ativacao": bool(desconhecidos)}


def aplicar_cravados(corpo_md, loja, marcadores_aprovados):
    """Troca pelo marcador só os literais que o lojista aprovou.

    Só troca correspondência EXATA de string (str.replace) — quando o achado
    veio da via `so_digitos` (CNPJ/CEP com pontuação diferente do cadastro),
    não há literal exato para substituir; a tela mostra o achado e o lojista
    corrige à mão. Regex por dígitos arriscaria casar outro número do texto
    (outro CNPJ, outro CEP) — num contrato, não vale o risco.
    """
    loja = loja or {}
    aprovados = set(marcadores_aprovados or [])
    out = corpo_md or ""
    for campo, marcador in _CRAVAVEIS:
        if marcador not in aprovados:
            continue
        valor = (loja.get(campo) or "").strip()
        if len(valor) < _MIN_LITERAL:
            continue
        out = out.replace(valor, "[%s]" % marcador)
    return out
