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
from datetime import datetime
from docx import Document

_THIS_DIR     = os.path.dirname(os.path.abspath(__file__))
CONTRATOS_DIR = os.path.join(_THIS_DIR, "CONTRATOS")

_MODELO = os.path.join(_THIS_DIR, "modelo_contrato_final.docx")

_TELEFONE_LOJA = "(12) 3341-8777"
_EMAIL_LOJA    = "sac@dalmobilesjc.com.br"


# ── Utilitários ───────────────────────────────────────────────────────────────

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


def _set_cell(cell, text: str):
    """Substitui o conteúdo de uma célula pelo texto, preservando a formatação do primeiro run."""
    para = cell.paragraphs[0]
    font_name = font_size = bold = None
    if para.runs:
        r0 = para.runs[0]
        font_name = r0.font.name
        font_size = r0.font.size
        bold = r0.bold
    for run in para.runs:
        run.text = ""
    run = para.add_run(text)
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if bold is not None:
        run.bold = bold


def _set_para(para, text: str):
    """Substitui o conteúdo de um parágrafo, preservando a formatação do primeiro run."""
    font_name = font_size = bold = None
    if para.runs:
        r0 = para.runs[0]
        font_name = r0.font.name
        font_size = r0.font.size
        bold = r0.bold
    for run in para.runs:
        run.text = ""
    run = para.add_run(text)
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if bold is not None:
        run.bold = bold


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

    # Grade p01..p24 — lê datas diretamente das parcelas capturadas
    datas = []
    if tipo == "cartao":
        datas = ["—"] * 24
    else:
        for p in parcelas:
            datas.append(_formatar_data_br(p.get("data") or ""))
        datas = (datas + ["—"] * 24)[:24]

    return {
        "tipo":           tipo,
        "nome_forma":     nome_forma,
        "entrada_valor":  _formatar_valor(entrada_val),
        "entrada_tipo":   entrada_tipo,
        "entrada_data":   entrada_data,
        "modalidade":     nome_forma,
        "num_parcelas":   str(num_parcelas) if num_parcelas else "—",
        "data_primeira":  data_primeira,
        "datas":          datas,          # lista de 24 strings
    }


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
    _set_cell(tables[0].rows[1].cells[0], ctx.get("cliente_nome", ""))
    _set_cell(tables[0].rows[1].cells[1], ctx.get("cliente_cpf",  ""))
    _set_cell(tables[0].rows[2].cells[0], ctx.get("cliente_email", ""))
    _set_cell(tables[0].rows[2].cells[1], ctx.get("cliente_telefone", ""))

    # ── Tabela 1: Endereço residencial ────────────────────────────────────────
    _set_cell(_unique_cells(tables[1].rows[1])[0], ctx.get("res_logradouro", ""))
    t1r2 = _unique_cells(tables[1].rows[2])
    if len(t1r2) >= 3:
        _set_cell(t1r2[0], ctx.get("res_numero",      ""))
        _set_cell(t1r2[1], ctx.get("res_complemento", ""))
        _set_cell(t1r2[2], ctx.get("res_bairro",      ""))
    t1r3 = _unique_cells(tables[1].rows[3])
    if len(t1r3) >= 3:
        _set_cell(t1r3[0], ctx.get("res_cidade", ""))
        _set_cell(t1r3[1], ctx.get("res_cep",    ""))
        _set_cell(t1r3[2], ctx.get("res_uf",     ""))

    # ── Tabela 2: Endereço de instalação ──────────────────────────────────────
    _set_cell(_unique_cells(tables[2].rows[1])[0], ctx.get("inst_logradouro", ""))
    t2r2 = _unique_cells(tables[2].rows[2])
    if len(t2r2) >= 3:
        _set_cell(t2r2[0], ctx.get("inst_numero",      ""))
        _set_cell(t2r2[1], ctx.get("inst_complemento", ""))
        _set_cell(t2r2[2], ctx.get("inst_bairro",      ""))
    t2r3 = _unique_cells(tables[2].rows[3])
    if len(t2r3) >= 3:
        _set_cell(t2r3[0], ctx.get("inst_cidade", ""))
        _set_cell(t2r3[1], ctx.get("inst_cep",    ""))
        _set_cell(t2r3[2], ctx.get("inst_uf",     ""))

    # ── Tabela 3: Forma de pagamento ──────────────────────────────────────────
    pag = ctx.get("_pag", {})
    t3 = tables[3]
    r1u = _unique_cells(t3.rows[1])   # 3 células únicas: Entrada | Tipo | Data
    r2u = _unique_cells(t3.rows[2])   # 3 células únicas: Modalidade | Parcelas | DataPrimeira
    if len(r1u) >= 3:
        _set_cell(r1u[0], pag.get("entrada_valor", ""))
        _set_cell(r1u[1], pag.get("entrada_tipo",  ""))
        _set_cell(r1u[2], pag.get("entrada_data",  ""))
    if len(r2u) >= 3:
        _set_cell(r2u[0], pag.get("modalidade",    ""))
        _set_cell(r2u[1], pag.get("num_parcelas",  ""))
        _set_cell(r2u[2], pag.get("data_primeira", ""))
    datas = pag.get("datas", ["—"] * 24)
    p_idx = 0
    for row_idx in range(3, 11):
        if p_idx >= 24:
            break
        row_cells = t3.rows[row_idx].cells
        for col in [1, 3, 5]:
            if p_idx >= 24 or col >= len(row_cells):
                break
            _set_cell(row_cells[col], datas[p_idx])
            p_idx += 1

    # ── Parágrafos do corpo — data, assinatura e identificação do cliente ─────
    data_hoje = ctx.get("data_contrato", datetime.now().strftime("%d/%m/%Y"))
    for para in doc.paragraphs:
        t = para.text.strip()
        # Data do contrato
        if t.startswith("São José dos Campos") and ("de 20" in t or "de 2026" in t):
            _set_para(para, f"São José dos Campos - SP, {data_hoje}.")
        # Assinante da empresa (rep. comercial / consultor)
        elif "Ferreira Machado" in t or "787.834" in t:
            _set_para(para, ctx.get("consultor_nome", ""))
        # Identificação do cliente (NOME: / Documento:)
        elif t == "NOME:":
            _set_para(para, f"NOME: {ctx.get('cliente_nome', '')}")
        elif t == "Documento:":
            _set_para(para, f"Documento: {ctx.get('cliente_cpf', '')}")
            break   # preenche só o primeiro par (do cliente); testemunhas ficam em branco

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
