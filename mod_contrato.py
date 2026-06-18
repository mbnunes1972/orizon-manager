"""
mod_contrato.py — Geração de contrato a partir de modelo_contrato_final.docx

Usa python-docx para preencher capa e assinatura diretamente no modelo original,
sem necessidade de template pré-processado. LibreOffice converte para PDF.
"""

import os
import json
import platform
import subprocess
import hashlib
import re as _re_cpf
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor

_THIS_DIR     = os.path.dirname(os.path.abspath(__file__))
CONTRATOS_DIR = os.path.join(_THIS_DIR, "CONTRATOS")

_MODELO = os.path.join(_THIS_DIR, "modelo_contrato_mapeado.docx")

_TELEFONE_LOJA = "(12) 3341-8777"
_EMAIL_LOJA    = "sac@dalmobilesjc.com.br"

# Testemunhas provisórias — TODO: vir do painel de configuração de loja.
_TESTEMUNHAS = [
    ("Jaime Perinazzo",     "xxx.xxx.xxx-xx"),
    ("Felipe Guizalberte",  "yyy.yyy.yyy-yy"),
]

_CODIGO_LOJA = "INS"       # 3 letras da loja — TODO: vir do painel de configuração de loja
_TRACO       = "--------"  # preenche slots de parcela inexistentes


# ── Utilitários ───────────────────────────────────────────────────────────────


def gerar_num_contrato(existing_nums, loja: str = _CODIGO_LOJA, data=None) -> str:
    """Próximo número de contrato no formato 'LOJA-AAAA-MM-DD-SEQ'.

    `existing_nums`: iterável com os num_contrato já existentes (qualquer loja).
    A sequência (SEQ) é CONTÍNUA por loja (máximo existente + 1), não reinicia por dia.
    """
    data = data or datetime.now()
    pref = f"{loja}-"
    maxseq = 0
    for n in (existing_nums or []):
        if n and n.startswith(pref):
            tail = n.rsplit("-", 1)[-1]
            if tail.isdigit():
                maxseq = max(maxseq, int(tail))
    return f"{loja}-{data:%Y-%m-%d}-{maxseq + 1:03d}"

def calcular_hash_assinatura(nome: str, cpf: str, contrato_id: int, timestamp: str) -> str:
    dados = f"{nome}|{cpf}|{contrato_id}|{timestamp}"
    return hashlib.sha256(dados.encode("utf-8")).hexdigest()


def _formatar_valor(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_data_br(data: str) -> str:
    """Converte ISO 'YYYY-MM-DD' → 'DD/MM/AAAA'. Datas já em DD/MM são passadas direto."""
    if not data:
        return "—"
    data = data.strip()
    # Já está no formato brasileiro
    if len(data) == 10 and data[2] == "/" and data[5] == "/":
        return data
    if len(data) >= 10:
        try:
            return datetime.strptime(data[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            pass
    return data or "—"


def _unique_cells(row):
    """Retorna apenas células únicas de uma linha (deduplica células mescladas)."""
    seen, cells = set(), []
    for c in row.cells:
        tc = c._tc
        if id(tc) not in seen:
            seen.add(id(tc))
            cells.append(c)
    return cells


def _set_cell(cell, text: str, rotulo: str = None):
    """Substitui o conteúdo de uma célula. Se `rotulo`, adiciona uma tag cinza pequena acima."""
    para = cell.paragraphs[0]
    font_name = font_size = bold = None
    if para.runs:
        r0 = para.runs[0]
        font_name = r0.font.name; font_size = r0.font.size; bold = r0.bold
    for run in para.runs:
        run.text = ""
    if rotulo:
        rl = para.add_run(rotulo)
        rl.font.size = Pt(7)
        rl.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        para.add_run().add_break()
    run = para.add_run(text)
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if bold is not None:
        run.bold = bold


def _set_para(para, text: str, rotulo: str = None):
    """Substitui o conteúdo de um parágrafo. Se `rotulo`, adiciona uma tag cinza pequena acima."""
    font_name = font_size = bold = None
    if para.runs:
        r0 = para.runs[0]
        font_name = r0.font.name; font_size = r0.font.size; bold = r0.bold
    for run in para.runs:
        run.text = ""
    if rotulo:
        rl = para.add_run(rotulo)
        rl.font.size = Pt(7)
        rl.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        para.add_run().add_break()
    run = para.add_run(text)
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if bold is not None:
        run.bold = bold


def _relabel_cpf_cnpj(doc):
    """Substitui 'CPF' por 'CPF/CNPJ' em parágrafos e células, sem duplicar."""
    def fix(para):
        for run in para.runs:
            if "CPF" in run.text:
                run.text = _re_cpf.sub(r'CPF(?!/CNPJ)', 'CPF/CNPJ', run.text)
    for para in doc.paragraphs:
        fix(para)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    fix(para)


def _preencher_cabecalho(doc, ctx):
    """Substitui os marcadores [Num_Contrato] e [Data_contrato] nos cabeçalhos.

    Os marcadores ficam numa caixa de texto do cabeçalho, então iteramos os
    elementos <w:t> via XML (cobre txbxContent). Tolera bracket extra ('[[').
    """
    from docx.oxml.ns import qn
    num  = str(ctx.get("num_contrato", "") or "")
    data = str(ctx.get("data_contrato", "") or "")

    def fix(text):
        text = _re_cpf.sub(r'\[+\s*num[_ ]?contrato\s*\]',  num,  text, flags=_re_cpf.I)
        text = _re_cpf.sub(r'\[+\s*data[_ ]?contrato\s*\]', data, text, flags=_re_cpf.I)
        return text

    for sec in doc.sections:
        for hdr in (sec.header, sec.first_page_header, sec.even_page_header):
            for t_el in hdr._element.iter(qn('w:t')):
                if t_el.text and '[' in t_el.text:
                    t_el.text = fix(t_el.text)


# ── Parser de pagamento ───────────────────────────────────────────────────────

def _parse_pagamento(pag_json_str: str) -> dict:
    """
    Normaliza o JSON de pagamento capturado pelo frontend (_capturarPagamento).

    Formato de entrada (do frontend):
      { tipo, nome_forma, entrada_valor, entrada_data, entrada_forma,
        parcelas: [{seq, descricao, data, valor, forma}],
        texto (apenas cartão) }

    Retorna dict normalizado com campos prontos para preencher a capa.
    """
    try:
        pag = json.loads(pag_json_str) if pag_json_str else {}
    except Exception:
        pag = {}

    tipo         = (pag.get("tipo") or "").lower()
    nome_forma   = pag.get("nome_forma") or ""
    entrada_val  = float(pag.get("entrada_valor") or 0)
    entrada_data = _formatar_data_br(pag.get("entrada_data") or "")
    entrada_tipo = pag.get("entrada_forma") or pag.get("entrada_tipo") or ""
    parcelas     = pag.get("parcelas") or []
    num_parcelas = len(parcelas)

    # Primeira data de parcela
    data_primeira = ""
    if parcelas:
        data_primeira = _formatar_data_br(parcelas[0].get("data") or "")

    # Grade p01..p24 — datas e valores diretamente das parcelas capturadas
    datas, valores = [], []
    if tipo != "cartao":
        for p in parcelas:
            datas.append(_formatar_data_br(p.get("data") or ""))
            valores.append((p.get("valor") or "").strip())
    datas   = (datas   + ["—"] * 24)[:24]
    valores = (valores + [""]  * 24)[:24]

    return {
        "tipo":             tipo,
        "nome_forma":       nome_forma,
        "entrada_valor":    _formatar_valor(entrada_val),
        "entrada_tipo":     entrada_tipo,
        "entrada_data":     entrada_data,
        "modalidade":       nome_forma,
        "num_parcelas":     str(num_parcelas) if num_parcelas else "—",
        "num_parcelas_int": num_parcelas,
        "data_primeira":    data_primeira,
        "datas":            datas,          # lista de 24 strings (data ou "—")
        "valores":          valores,        # lista de 24 strings (valor ou "")
    }


# ── Validação de dados do cliente ─────────────────────────────────────────────

def validar_cliente_para_contrato(cliente: dict) -> list:
    """
    Retorna a lista de rótulos dos campos obrigatórios que estão vazios para
    gerar um contrato a partir do dict do cliente (formato _cliente_dict).

    Lista vazia → cliente está completo e pode gerar o contrato.

    Regra: identificação + endereço residencial são sempre obrigatórios.
    O endereço de instalação só é cobrado quando NÃO for o mesmo do residencial
    (inst_mesmo_residencial falso) — quando é o mesmo, o residencial é reutilizado.
    Complemento é opcional em ambos.
    """
    obrigatorios = [
        ("nome",       "Nome"),
        ("cpf",        "CPF"),
        ("email",      "E-mail"),
        ("telefone",   "Telefone"),
        ("logradouro", "Logradouro (residencial)"),
        ("numero",     "Número (residencial)"),
        ("bairro",     "Bairro (residencial)"),
        ("cidade",     "Cidade (residencial)"),
        ("cep",        "CEP (residencial)"),
        ("estado",     "Estado/UF (residencial)"),
    ]

    inst_mesmo = cliente.get("inst_mesmo_residencial", True)
    if not inst_mesmo:
        obrigatorios += [
            ("inst_logradouro", "Logradouro (instalação)"),
            ("inst_numero",     "Número (instalação)"),
            ("inst_bairro",     "Bairro (instalação)"),
            ("inst_cidade",     "Cidade (instalação)"),
            ("inst_cep",        "CEP (instalação)"),
            ("inst_uf",         "UF (instalação)"),
        ]

    faltando = []
    for campo, rotulo in obrigatorios:
        valor = cliente.get(campo)
        if not (valor and str(valor).strip()):
            faltando.append(rotulo)
    return faltando


# ── Preenchimento dinâmico do modelo ─────────────────────────────────────────

def preencher_contrato(contrato_id: int, ctx: dict) -> str:
    """
    Preenche modelo_contrato_final.docx com os dados de ctx e salva
    como CONTRATOS/contrato_<id>.docx. Retorna o caminho do .docx.
    """
    if not os.path.exists(_MODELO):
        raise FileNotFoundError(
            f"Modelo de contrato não encontrado: {_MODELO}\n"
            "Adicione 'modelo_contrato_final.docx' na raiz do projeto."
        )
    os.makedirs(CONTRATOS_DIR, exist_ok=True)

    doc = Document(_MODELO)
    tables = doc.tables

    # ── Parágrafo 0: "Consultor: ... Telefone: ... e-mail:" ──────────────────
    p0 = doc.paragraphs[0]
    linha_consultor = (
        f"Consultor: {ctx.get('consultor_nome', '')}\t\t\t\t\t"
        f"Telefone: {ctx.get('consultor_tel', '')}\t\t\t\t"
        f"e-mail: {ctx.get('consultor_email', '')}"
    )
    _set_para(p0, linha_consultor)

    # ── Tabela 0: Identificação do cliente ────────────────────────────────────
    _set_cell(tables[0].rows[1].cells[0], ctx.get("cliente_nome", ""),     rotulo="Nome")
    _set_cell(tables[0].rows[1].cells[1], ctx.get("cliente_cpf",  ""),     rotulo="CPF/CNPJ")
    _set_cell(tables[0].rows[2].cells[0], ctx.get("cliente_email", ""),    rotulo="E-mail")
    _set_cell(tables[0].rows[2].cells[1], ctx.get("cliente_telefone", ""), rotulo="Telefone")

    # ── Tabela 1: Endereço residencial ────────────────────────────────────────
    _set_cell(_unique_cells(tables[1].rows[1])[0], ctx.get("res_logradouro", ""), rotulo="Logradouro")
    t1r2 = _unique_cells(tables[1].rows[2])
    if len(t1r2) >= 3:
        _set_cell(t1r2[0], ctx.get("res_numero",      ""), rotulo="Número")
        _set_cell(t1r2[1], ctx.get("res_complemento", ""), rotulo="Complemento")
        _set_cell(t1r2[2], ctx.get("res_bairro",      ""), rotulo="Bairro")
    t1r3 = _unique_cells(tables[1].rows[3])
    if len(t1r3) >= 3:
        _set_cell(t1r3[0], ctx.get("res_cidade", ""), rotulo="Cidade")
        _set_cell(t1r3[1], ctx.get("res_cep",    ""), rotulo="CEP")
        _set_cell(t1r3[2], ctx.get("res_uf",     ""), rotulo="Estado/UF")

    # ── Tabela 2: Endereço de instalação ──────────────────────────────────────
    _set_cell(_unique_cells(tables[2].rows[1])[0], ctx.get("inst_logradouro", ""), rotulo="Logradouro")
    t2r2 = _unique_cells(tables[2].rows[2])
    if len(t2r2) >= 3:
        _set_cell(t2r2[0], ctx.get("inst_numero",      ""), rotulo="Número")
        _set_cell(t2r2[1], ctx.get("inst_complemento", ""), rotulo="Complemento")
        _set_cell(t2r2[2], ctx.get("inst_bairro",      ""), rotulo="Bairro")
    t2r3 = _unique_cells(tables[2].rows[3])
    if len(t2r3) >= 3:
        _set_cell(t2r3[0], ctx.get("inst_cidade", ""), rotulo="Cidade")
        _set_cell(t2r3[1], ctx.get("inst_cep",    ""), rotulo="CEP")
        _set_cell(t2r3[2], ctx.get("inst_uf",     ""), rotulo="Estado/UF")

    # ── Tabela 3: Forma de pagamento ──────────────────────────────────────────
    pag = ctx.get("_pag", {})
    t3 = tables[3]
    r1u = _unique_cells(t3.rows[1])   # 3 células únicas: Entrada | Tipo | Data
    r2u = _unique_cells(t3.rows[2])   # 3 células únicas: Modalidade | Parcelas | DataPrimeira
    if len(r1u) >= 3:
        _set_cell(r1u[0], pag.get("entrada_valor", ""), rotulo="Entrada")
        _set_cell(r1u[1], pag.get("entrada_tipo",  ""), rotulo="Tipo")
        _set_cell(r1u[2], pag.get("entrada_data",  ""), rotulo="Data")
    if len(r2u) >= 3:
        _set_cell(r2u[0], pag.get("modalidade",    ""), rotulo="Modalidade")
        _set_cell(r2u[1], pag.get("num_parcelas",  ""), rotulo="Parcelas")
        _set_cell(r2u[2], pag.get("data_primeira", ""), rotulo="1ª data")
    # Grade de parcelas (linhas 3-10): célula do ordinal (0/2/4) = "Nª  <valor>",
    # célula ao lado (1/3/5) = data. Slots sem parcela = traços; linhas totalmente
    # vazias são removidas da tabela.
    datas   = pag.get("datas",   ["—"] * 24)
    valores = pag.get("valores", [""]  * 24)
    num     = pag.get("num_parcelas_int", 0)
    _rows_remover = []
    for gi, row_idx in enumerate(range(3, 11)):    # 8 linhas, 3 parcelas cada
        row       = t3.rows[row_idx]
        row_cells = row.cells
        if gi * 3 + 1 > num:                        # primeira parcela da linha já passou → linha vazia
            _rows_remover.append(row)
            continue
        for j, (ord_col, data_col) in enumerate([(0, 1), (2, 3), (4, 5)]):
            if data_col >= len(row_cells):
                break
            p = gi * 3 + j + 1                      # nº da parcela (1-based)
            if p <= num:
                _set_cell(row_cells[ord_col],  f"{p}ª  {valores[p-1]}".rstrip())
                _set_cell(row_cells[data_col], datas[p-1])
            else:
                _set_cell(row_cells[ord_col],  _TRACO)
                _set_cell(row_cells[data_col], _TRACO)
    for row in _rows_remover:
        row._element.getparent().remove(row._element)

    # ── Parágrafos do corpo — data, assinatura e identificação do cliente ─────
    data_hoje = ctx.get("data_contrato", datetime.now().strftime("%d/%m/%Y"))
    _w_idx = 0  # índice da testemunha atual
    for para in doc.paragraphs:
        t = para.text.strip()
        # Data do contrato
        if t.startswith("São José dos Campos") and ("de 20" in t or "de 2026" in t):
            _set_para(para, f"São José dos Campos - SP, {data_hoje}.", rotulo="Data")
        # 2º signatário = CLIENTE (a linha INSPIRIUM acima permanece intacta)
        elif "Ferreira Machado" in t or "787.834" in t:
            _set_para(para, f"{ctx.get('cliente_nome', '')} CPF/CNPJ: {ctx.get('cliente_cpf', '')}",
                      rotulo="Cliente (signatário)")
        # Testemunhas (dois pares NOME:/Documento:)
        elif t == "NOME:" and _w_idx < len(_TESTEMUNHAS):
            _set_para(para, f"NOME: {_TESTEMUNHAS[_w_idx][0]}", rotulo="Testemunha")
        elif t == "Documento:" and _w_idx < len(_TESTEMUNHAS):
            _set_para(para, f"CPF/CNPJ: {_TESTEMUNHAS[_w_idx][1]}", rotulo="CPF/CNPJ")
            _w_idx += 1

    _preencher_cabecalho(doc, ctx)
    _relabel_cpf_cnpj(doc)
    docx_path = os.path.join(CONTRATOS_DIR, f"contrato_{contrato_id}.docx")
    doc.save(docx_path)
    return docx_path


def construir_contexto(cliente: dict, usuario: dict, forma_pagamento_json: str) -> dict:
    """Monta o dicionário completo para preencher o contrato."""
    inst_mesmo = cliente.get("inst_mesmo_residencial", True)
    if inst_mesmo:
        inst = {k: cliente.get(r, "") for k, r in [
            ("logradouro","logradouro"), ("numero","numero"),
            ("complemento","complemento"), ("bairro","bairro"),
            ("cidade","cidade"), ("cep","cep"), ("uf","estado"),
        ]}
    else:
        inst = {
            "logradouro":  cliente.get("inst_logradouro",  ""),
            "numero":      cliente.get("inst_numero",      ""),
            "complemento": cliente.get("inst_complemento", ""),
            "bairro":      cliente.get("inst_bairro",      ""),
            "cidade":      cliente.get("inst_cidade",      ""),
            "cep":         cliente.get("inst_cep",         ""),
            "uf":          cliente.get("inst_uf",          ""),
        }

    pag = _parse_pagamento(forma_pagamento_json)
    datas = pag["datas"]

    ctx = {
        "consultor_nome":  usuario.get("nome",     "") or "",
        "consultor_tel":   (usuario.get("telefone") or "").strip() or _TELEFONE_LOJA,
        "consultor_email": (usuario.get("email")    or "").strip() or _EMAIL_LOJA,
        "cliente_nome":    cliente.get("nome",     "") or "",
        "cliente_cpf":     cliente.get("cpf",      "") or "",
        "cliente_email":   cliente.get("email",    "") or "",
        "cliente_telefone":cliente.get("telefone", "") or "",
        "res_logradouro":  cliente.get("logradouro",  "") or "",
        "res_numero":      cliente.get("numero",      "") or "",
        "res_complemento": cliente.get("complemento", "") or "",
        "res_bairro":      cliente.get("bairro",      "") or "",
        "res_cidade":      cliente.get("cidade",      "") or "",
        "res_cep":         cliente.get("cep",         "") or "",
        "res_uf":          cliente.get("estado",      "") or "",
        "inst_logradouro":  inst["logradouro"],
        "inst_numero":      inst["numero"],
        "inst_complemento": inst["complemento"],
        "inst_bairro":      inst["bairro"],
        "inst_cidade":      inst["cidade"],
        "inst_cep":         inst["cep"],
        "inst_uf":          inst["uf"],
        # Pagamento — chaves planas para compatibilidade com templates antigos
        "pgto_entrada_valor":  pag["entrada_valor"],
        "pgto_entrada_tipo":   pag["entrada_tipo"],
        "pgto_entrada_data":   pag["entrada_data"],
        "pgto_modalidade":     pag["modalidade"],
        "pgto_num_parcelas":   pag["num_parcelas"],
        "pgto_data_primeira":  pag["data_primeira"],
        "data_contrato":       datetime.now().strftime("%d/%m/%Y"),
        "_pag":                pag,   # dict normalizado para preencher_contrato()
    }
    # Grade de datas p01..p24
    for i in range(24):
        ctx[f"p{i+1:02d}_data"] = datas[i]
    return ctx


# ── LibreOffice ───────────────────────────────────────────────────────────────

class LibreOfficeIndisponivel(Exception):
    def __init__(self, docx_path: str):
        self.docx_path = docx_path
        super().__init__(
            "LibreOffice não encontrado no servidor.\n"
            "O arquivo Word (.docx) foi gerado e está disponível para download.\n"
            "Instale o LibreOffice no servidor para gerar PDF automaticamente."
        )


def _libreoffice_cmd() -> str:
    if platform.system() == "Windows":
        for p in [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]:
            if os.path.exists(p):
                return p
    return "libreoffice"


def gerar_pdf_contrato(contrato_id: int, variaveis: dict) -> str:
    """
    Preenche o modelo de contrato com os dados de variaveis e converte para PDF.
    Retorna o caminho do PDF (ou .docx se LibreOffice indisponível).
    """
    docx_path = preencher_contrato(contrato_id, variaveis)

    try:
        subprocess.run(
            [_libreoffice_cmd(), "--headless", "--convert-to", "pdf",
             "--outdir", CONTRATOS_DIR, docx_path],
            check=True, capture_output=True, timeout=120,
        )
    except FileNotFoundError:
        raise LibreOfficeIndisponivel(docx_path)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"LibreOffice falhou:\n{e.stderr.decode(errors='replace')}"
        ) from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("LibreOffice demorou mais de 120s")

    return os.path.join(CONTRATOS_DIR, f"contrato_{contrato_id}.pdf")


# ── Legado — mantido para compatibilidade com chamadas antigas ────────────────

def _formatar_bloco_pagamento(pagamento_json_str: str, forma_entrada_label: str = "Pix") -> str:
    pag = _parse_pagamento(pagamento_json_str)
    if not pag["nome_forma"]:
        return ""
    linhas = [f"Forma de Pagamento: {pag['nome_forma']}",
              f"Entrada: {pag['entrada_valor']} — {pag['entrada_data']}",
              f"Modalidade: {pag['modalidade']}  |  {pag['num_parcelas']} parcelas"]
    return "\n".join(linhas)


def montar_variaveis_contrato(projeto, cliente, orcamento, endereco_instalacao,
                               entrada_valor, parcelas_descricao, adendo,
                               forma_entrada="pix", forma_parcelas="boleto",
                               pagamento_json="") -> dict:
    """Legado — use construir_contexto() para novos contratos."""
    return {
        "cliente_nome": cliente.get("nome", ""),
        "cliente_cpf":  cliente.get("cpf",  ""),
        "consultor_nome": projeto.get("consultor", ""),
        "data_contrato":  datetime.now().strftime("%d/%m/%Y"),
        "tem_adendo": bool(adendo),
        "adendo":     adendo or "",
        "_pag": _parse_pagamento(pagamento_json),
    }
